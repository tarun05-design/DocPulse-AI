"""Unit tests for backend services (non-network, non-model tests)."""
import json
import numpy as np


class TestChunkText:
    def test_empty(self):
        from app.services.embeddings import chunk_text
        assert chunk_text("") == []
        assert chunk_text(None) == []

    def test_short_text(self):
        from app.services.embeddings import chunk_text
        result = chunk_text("hello world", chunk_size=800)
        assert len(result) == 1
        assert result[0] == "hello world"

    def test_long_text_overlap(self):
        from app.services.embeddings import chunk_text
        text = "A" * 2000
        chunks = chunk_text(text, chunk_size=800, overlap=100)
        # Should have multiple overlapping chunks
        assert len(chunks) > 1
        # Each chunk <= chunk_size
        assert all(len(c) <= 800 for c in chunks)
        # Overlap exists
        assert chunks[0][-100:] == chunks[1][:100]


class TestCosineSim:
    def test_identical_vectors(self):
        from app.services.embeddings import _cosine_sim
        a = np.array([1.0, 0.0, 0.0])
        assert abs(_cosine_sim(a, a) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        from app.services.embeddings import _cosine_sim
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert abs(_cosine_sim(a, b)) < 1e-6

    def test_zero_vector(self):
        from app.services.embeddings import _cosine_sim
        a = np.array([1.0, 2.0])
        z = np.array([0.0, 0.0])
        assert _cosine_sim(a, z) == 0.0


class TestExtractEntitiesRegex:
    def test_dates(self):
        from app.services.entity_extraction import extract_entities
        # Mock NER pipeline to avoid loading models
        import app.services.entity_extraction as mod
        mod._ner_pipeline = lambda: None  # disable NER

        text = "Invoice date: 01/15/2024 and due by 2024-02-28"
        entities = extract_entities(text)
        dates = [e for e in entities if e["entity_type"] == "date"]
        assert len(dates) >= 2

    def test_amounts(self):
        from app.services.entity_extraction import extract_entities
        import app.services.entity_extraction as mod
        mod._ner_pipeline = lambda: None

        text = "Total: $1,500.00 plus Rs. 200"
        entities = extract_entities(text)
        amounts = [e for e in entities if e["entity_type"] == "amount"]
        assert len(amounts) >= 2

    def test_empty_text(self):
        from app.services.entity_extraction import extract_entities
        assert extract_entities("") == []
        assert extract_entities("   ") == []


class TestGuessDocType:
    def test_invoice(self):
        from app.services.ocr_pipeline import _guess_doc_type
        assert _guess_doc_type("Invoice #123, Amount Due: $500") == "invoice"

    def test_contract(self):
        from app.services.ocr_pipeline import _guess_doc_type
        assert _guess_doc_type("This agreement is hereby entered into by the party") == "contract"

    def test_resume(self):
        from app.services.ocr_pipeline import _guess_doc_type
        assert _guess_doc_type("Education: BS Computer Science, Skills: Python") == "resume"

    def test_fallback_report(self):
        from app.services.ocr_pipeline import _guess_doc_type
        assert _guess_doc_type("Random text about weather today") == "report"


class TestSafeJson:
    def test_valid_json(self):
        from app.services.gemini_service import _safe_json
        result = _safe_json('{"doc_type": "invoice", "summary": "test"}')
        assert result["doc_type"] == "invoice"

    def test_markdown_fenced(self):
        from app.services.gemini_service import _safe_json
        text = '```json\n{"doc_type": "contract", "summary": "test"}\n```'
        result = _safe_json(text)
        assert result["doc_type"] == "contract"

    def test_garbage_fallback(self):
        from app.services.gemini_service import _safe_json
        result = _safe_json("this is not json at all")
        assert result["doc_type"] == "other"
        assert "this is not json" in result["summary"]
