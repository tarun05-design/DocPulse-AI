import logging
import threading
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models import Document, ExtractedText, Entity, Embedding, ChatHistory, AuditLog
from ..services import blob_storage, ocr_pipeline, entity_extraction, gemini_service, embeddings

logger = logging.getLogger(__name__)

documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "bmp", "docx", "txt"}


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXTENSIONS


def _async_process_document(app, doc_id, file_bytes):
    with app.app_context():
        doc = Document.query.get(doc_id)
        if doc:
            _process_document_sync(doc, file_bytes)


@documents_bp.post("/upload")
@jwt_required()
def upload_document():
    user_id = get_jwt_identity()

    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not _allowed(file.filename):
        return jsonify({"error": f"Unsupported file type. Allowed: {sorted(ALLOWED_EXTENSIONS)}"}), 400

    file_bytes = file.read()

    blob_name, blob_url = blob_storage.upload_file(
        file_bytes, file.filename, content_type=file.mimetype
    )

    doc = Document(
        user_id=user_id,
        filename=file.filename,
        blob_url=blob_url,
        status="processing",
    )
    db.session.add(doc)
    db.session.commit()

    db.session.add(AuditLog(user_id=user_id, action="upload", details=f"document {doc.id} uploaded"))
    db.session.commit()

    app = current_app._get_current_object()
    if app.config.get("TESTING"):
        _process_document_sync(doc, file_bytes)
    else:
        threading.Thread(target=_async_process_document, args=(app, doc.id, file_bytes), daemon=True).start()

    return jsonify(doc.to_dict()), 201


def _stringify_field(val):
    if val is None:
        return ""
    if isinstance(val, list):
        return "\n".join(f"• {str(item)}" for item in val)
    if isinstance(val, dict):
        import json
        return json.dumps(val, indent=2)
    return str(val)


def _process_document_sync(doc, file_bytes):
    doc.status = "processing"
    db.session.commit()

    try:
        extraction = ocr_pipeline.process_document(file_bytes, doc.filename)
        raw_text = extraction["raw_text"]

        et = ExtractedText(
            document_id=doc.id,
            raw_text=raw_text,
            layout_json=extraction["layout_json"],
        )
        db.session.add(et)

        for ent in entity_extraction.extract_entities(raw_text):
            db.session.add(Entity(document_id=doc.id, **ent))

        analysis = gemini_service.analyze_document(raw_text, extraction["doc_type_hint"])
        doc.doc_type = _stringify_field(analysis.get("doc_type")) or extraction["doc_type_hint"]
        doc.summary = _stringify_field(analysis.get("summary"))
        doc.risks = _stringify_field(analysis.get("risks"))
        doc.action_items = _stringify_field(analysis.get("action_items"))

        chunks = embeddings.chunk_text(raw_text)
        for idx, (chunk, vector_json) in enumerate(embeddings.embed_chunks(chunks)):
            db.session.add(
                Embedding(document_id=doc.id, chunk_text=chunk, vector=vector_json, chunk_index=idx)
            )

        doc.status = "processed"
        doc.processed_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.info("Document %s processed successfully", doc.id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Processing failed for document %s: %s", doc.id, exc)
        db.session.rollback()
        doc.status = "failed"
        doc.summary = f"Processing failed: {exc}"
        doc.risks = "Processing error"
        doc.action_items = "Processing error"
        db.session.commit()


@documents_bp.get("")
@jwt_required()
def list_documents():
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)  # cap at 100

    pagination = (
        Document.query.filter_by(user_id=user_id)
        .order_by(Document.uploaded_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return jsonify({
        "documents": [d.to_dict() for d in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    })


@documents_bp.get("/<doc_id>")
@jwt_required()
def get_document(doc_id):
    user_id = get_jwt_identity()
    doc = Document.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    result = doc.to_dict()
    result["entities"] = [
        {"type": e.entity_type, "value": e.value, "confidence": e.confidence} for e in doc.entities
    ]
    result["raw_text"] = doc.extracted_text.raw_text if doc.extracted_text else None
    return jsonify(result)


@documents_bp.delete("/<doc_id>")
@jwt_required()
def delete_document(doc_id):
    user_id = get_jwt_identity()
    doc = Document.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    # Delete related rows
    ChatHistory.query.filter_by(document_id=doc.id).delete()
    Embedding.query.filter_by(document_id=doc.id).delete()
    Entity.query.filter_by(document_id=doc.id).delete()
    ExtractedText.query.filter_by(document_id=doc.id).delete()

    # Delete blob (best-effort)
    try:
        blob_name = doc.blob_url.rsplit("/", 1)[-1]
        blob_storage.delete_file(blob_name)
    except Exception:  # noqa: BLE001
        logger.warning("Could not delete blob for document %s", doc.id)

    db.session.delete(doc)
    db.session.add(AuditLog(user_id=user_id, action="delete", details=f"document {doc_id} deleted"))
    db.session.commit()

    return jsonify({"message": "Document deleted"}), 200


@documents_bp.post("/<doc_id>/reprocess")
@jwt_required()
def reprocess_document(doc_id):
    user_id = get_jwt_identity()
    doc = Document.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    doc.status = "processing"
    db.session.commit()

    blob_name = doc.blob_url.rsplit("/", 1)[-1]
    file_bytes = blob_storage.download_file(blob_name)
    app = current_app._get_current_object()
    threading.Thread(target=_async_process_document, args=(app, doc.id, file_bytes), daemon=True).start()
    return jsonify(doc.to_dict())


@documents_bp.get("/<doc_id>/download")
@jwt_required()
def download_document(doc_id):
    """Download the original uploaded file."""
    from flask import Response
    user_id = get_jwt_identity()
    doc = Document.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    try:
        blob_name = doc.blob_url.rsplit("/", 1)[-1]
        file_bytes = blob_storage.download_file(blob_name)
    except Exception as exc:  # noqa: BLE001
        logger.error("Download failed for doc %s: %s", doc.id, exc)
        return jsonify({"error": "File not available for download"}), 404

    # Determine content type from extension
    ext = doc.filename.rsplit(".", 1)[-1].lower() if "." in doc.filename else ""
    content_types = {
        "pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg",
        "jpeg": "image/jpeg", "tiff": "image/tiff", "bmp": "image/bmp",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
    }
    ct = content_types.get(ext, "application/octet-stream")

    return Response(
        file_bytes,
        mimetype=ct,
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
    )

