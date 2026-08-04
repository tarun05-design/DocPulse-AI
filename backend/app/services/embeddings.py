"""
Chunking + embeddings for semantic search ("chat with document").

Uses sentence-transformers locally (no API cost per chunk). Vectors are
stored as JSON in the Embeddings table for simplicity; swap for pgvector /
Azure AI Search in production for real similarity search at scale.

Gracefully falls back when the embedding model is unavailable — documents
are still uploaded and analyzed by Gemini, but chat won't be grounded in
retrieval until the model is available.
"""
import json
import logging

import numpy as np
from flask import current_app

logger = logging.getLogger(__name__)

_embedding_model = None
_model_load_failed = False


def _get_model():
    global _embedding_model, _model_load_failed
    try:
        if current_app.config.get("DISABLE_HEAVY_MODELS", False):
            return None
    except Exception:
        pass
    if _model_load_failed:
        return None
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            model_name = current_app.config["HF_EMBEDDING_MODEL"]
            logger.info("Loading embedding model: %s", model_name)
            _embedding_model = SentenceTransformer(model_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load embedding model: %s. Chat retrieval will use zero-RAM search.", exc)
            _model_load_failed = True
            return None
    return _embedding_model


def chunk_text(text, chunk_size=800, overlap=100):
    """Simple sliding-window chunker over characters."""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def embed_chunks(chunks):
    """Returns list of (chunk_text, vector_json). Returns text with empty vector if model unavailable."""
    if not chunks:
        return []
    model = _get_model()
    if model is None:
        logger.info("Embedding model unavailable — storing chunk text for keyword search")
        return [(c, json.dumps([])) for c in chunks]
    try:
        vectors = model.encode(chunks)
        return [(c, json.dumps(v.tolist())) for c, v in zip(chunks, vectors)]
    except Exception as exc:
        logger.warning("Embedding encoding failed (%s) — storing raw text", exc)
        return [(c, json.dumps([])) for c in chunks]


def embed_query(query):
    """Returns query vector or None if model unavailable."""
    model = _get_model()
    if model is None:
        return None
    try:
        return model.encode([query])[0]
    except Exception:
        return None


def top_k_chunks(query, embedding_rows, k=4):
    """
    embedding_rows: list of Embedding model instances (with .chunk_text and .vector)
    Returns the k most relevant chunk texts by vector or keyword similarity.
    """
    if not embedding_rows:
        return []

    query_vec = embed_query(query)

    # Fallback to zero-RAM keyword relevance scoring if model is unavailable
    if query_vec is None:
        import re
        query_words = set(re.findall(r"\w+", query.lower()))
        if query_words:
            scored = []
            for row in embedding_rows:
                chunk_words = set(re.findall(r"\w+", row.chunk_text.lower()))
                overlap = len(query_words.intersection(chunk_words))
                scored.append((overlap, row.chunk_text))
            scored.sort(key=lambda x: x[0], reverse=True)
            results = [text for score, text in scored[:k] if score > 0]
            if results:
                return results
        return [row.chunk_text for row in embedding_rows[:k]]

    try:
        matrix = np.array([json.loads(row.vector) for row in embedding_rows])
        query_norm = np.linalg.norm(query_vec)
        matrix_norms = np.linalg.norm(matrix, axis=1)

        denoms = query_norm * matrix_norms
        denoms[denoms == 0] = 1e-10  # avoid div zero

        sims = np.dot(matrix, query_vec) / denoms
        top_indices = np.argsort(sims)[::-1][:k]
        return [embedding_rows[idx].chunk_text for idx in top_indices]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vector search failed (%s), falling back to list iteration", exc)
        return [row.chunk_text for row in embedding_rows[:k]]


def _cosine_sim(a, b):
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
