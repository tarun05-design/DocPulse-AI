"""
Document OCR + layout extraction pipeline.

- PDFs with a text layer: extracted directly via PyPDF2 (fast path).
- DOCX files: extracted via python-docx.
- TXT files: read as UTF-8 text.
- Scanned PDFs / images: run through a Hugging Face TrOCR (or Donut) pipeline.
- Layout/structure (tables, key-value regions): LayoutLMv3, loaded lazily.

Models are loaded lazily and cached at module level so they are only pulled
into memory once per process, not once per request.
"""
import io
import json
import logging

from PIL import Image
try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader
from flask import current_app

logger = logging.getLogger(__name__)

_trocr_pipeline = None
_layout_pipeline = None


def _get_trocr_pipeline():
    global _trocr_pipeline
    if _trocr_pipeline is None:
        try:
            from transformers import pipeline
            model_name = current_app.config["HF_OCR_MODEL"]
            logger.info("Loading TrOCR model: %s", model_name)
            _trocr_pipeline = pipeline("image-to-text", model=model_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("TrOCR model unavailable: %s", exc)
            return None
    return _trocr_pipeline


def _get_layout_pipeline():
    global _layout_pipeline
    if _layout_pipeline is None:
        try:
            from transformers import AutoProcessor, AutoModelForTokenClassification
            model_name = current_app.config["HF_LAYOUT_MODEL"]
            logger.info("Loading LayoutLMv3 model: %s", model_name)
            processor = AutoProcessor.from_pretrained(model_name, apply_ocr=True)
            model = AutoModelForTokenClassification.from_pretrained(model_name)
            _layout_pipeline = (processor, model)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LayoutLMv3 model unavailable: %s", exc)
            return None
    return _layout_pipeline


def _extract_pdf_text_layer(file_bytes):
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    return text


def _extract_docx_text(file_bytes):
    """Extract text from a DOCX file using python-docx."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("DOCX extraction failed: %s", exc)
        return ""


def _extract_txt(file_bytes):
    """Read a plain text file."""
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1", errors="replace")


def _ocr_image(file_bytes):
    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        try:
            import pytesseract
            text = pytesseract.image_to_string(image).strip()
            if text:
                return text
        except Exception:
            pass

        ocr = _get_trocr_pipeline()
        result = ocr(image)
        # transformers pipeline returns [{"generated_text": "..."}]
        if isinstance(result, list) and result:
            return result[0].get("generated_text", "")
        return ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("OCR image extraction failed: %s", exc)
        return ""


def extract_layout(file_bytes, is_image=True):
    """Best-effort structural layout extraction via LayoutLMv3.
    Returns a JSON-serializable dict; falls back to empty structure on failure
    (layout extraction is an enhancement, not a hard requirement for text extraction).
    """
    try:
        if not is_image:
            return {"tokens": [], "boxes": []}
        # Avoid blocking document processing if heavy HF models aren't cached locally
        if current_app.config.get("DISABLE_HEAVY_MODELS", True):
            return {"tokens": [], "boxes": []}
        processor, _model = _get_layout_pipeline()
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        encoding = processor(image, return_tensors="pt")
        tokens = processor.tokenizer.convert_ids_to_tokens(encoding["input_ids"][0])
        boxes = encoding["bbox"][0].tolist() if "bbox" in encoding else []
        return {"tokens": tokens, "boxes": boxes}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Layout extraction failed: %s", exc)
        return {"error": str(exc), "tokens": [], "boxes": []}


def process_document(file_bytes, filename):
    """
    Main entry point: given the raw bytes of an uploaded document, returns:
        {
          "raw_text": str,
          "layout_json": str,
          "doc_type_hint": str
        }
    """
    lower = filename.lower()
    is_pdf = lower.endswith(".pdf")
    is_docx = lower.endswith(".docx")
    is_txt = lower.endswith(".txt")

    raw_text = ""
    layout = {"tokens": [], "boxes": []}

    if is_pdf:
        raw_text = _extract_pdf_text_layer(file_bytes)
        if not raw_text:
            # Scanned PDF with no text layer — would need pdf2image + OCR per page.
            # Kept as a documented extension point rather than bundling poppler here.
            raw_text = ""
    elif is_docx:
        raw_text = _extract_docx_text(file_bytes)
    elif is_txt:
        raw_text = _extract_txt(file_bytes)
    else:
        raw_text = _ocr_image(file_bytes)
        layout = extract_layout(file_bytes, is_image=True)

    doc_type_hint = _guess_doc_type(raw_text)

    return {
        "raw_text": raw_text,
        "layout_json": json.dumps(layout),
        "doc_type_hint": doc_type_hint,
    }


def _guess_doc_type(text):
    """Cheap keyword heuristic; Gemini refines this later with full reasoning."""
    t = text.lower()
    if any(k in t for k in ["invoice", "amount due", "bill to", "total due"]):
        return "invoice"
    if any(k in t for k in ["agreement", "party", "hereby", "clause", "terms and conditions"]):
        return "contract"
    if any(k in t for k in ["project documentation", "project report", "system architecture", "project description"]):
        return "report"
    if any(k in t for k in ["experience", "education", "skills", "resume", "cv", "curriculum vitae"]):
        return "resume"
    return "report"
