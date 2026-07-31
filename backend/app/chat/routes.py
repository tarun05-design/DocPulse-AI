import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models import Document, Embedding, ChatHistory
from ..services import gemini_service, embeddings

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@chat_bp.post("/<doc_id>")
@jwt_required()
def chat_with_document(doc_id):
    user_id = get_jwt_identity()
    doc = Document.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    if doc.status != "processed":
        return jsonify({"error": f"Document is not ready yet (status: {doc.status})"}), 409

    data = request.get_json(force=True) or {}
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    try:
        embedding_rows = Embedding.query.filter_by(document_id=doc.id).all()
        top_chunks = embeddings.top_k_chunks(question, embedding_rows, k=4)
        if embedding_rows:
            header_chunk = embedding_rows[0].chunk_text
            if header_chunk not in top_chunks:
                top_chunks = [header_chunk] + top_chunks[:3]
        relevant_chunks = top_chunks
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chunk retrieval failed for doc %s: %s — falling back to raw text", doc.id, exc)
        raw = doc.extracted_text.raw_text if doc.extracted_text else ""
        relevant_chunks = [raw[:3000]] if raw else []

    answer = gemini_service.answer_question(question, relevant_chunks)

    entry = ChatHistory(document_id=doc.id, user_id=user_id, question=question, answer=answer)
    db.session.add(entry)
    db.session.commit()

    return jsonify(entry.to_dict())


@chat_bp.get("/<doc_id>/history")
@jwt_required()
def chat_history(doc_id):
    user_id = get_jwt_identity()
    doc = Document.query.filter_by(id=doc_id, user_id=user_id).first()
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    entries = (
        ChatHistory.query.filter_by(document_id=doc.id, user_id=user_id)
        .order_by(ChatHistory.created_at.asc())
        .all()
    )
    return jsonify([e.to_dict() for e in entries])
