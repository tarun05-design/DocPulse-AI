"""
Entity extraction service.

Uses fast, zero-latency regex patterns for dates, monetary amounts, emails,
and phone numbers. Higher-level entity understanding (names, organizations,
clauses) is handled by Gemini 1.5 Flash downstream, avoiding heavy local ML
model downloads that cause upload hangs.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Fast deterministic regex extractions (0ms execution time)
DATE_RE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)
AMOUNT_RE = re.compile(r"(?:USD|EUR|GBP|₹|Rs\.?|\$)\s?[\d,]+(?:\.\d{2})?")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


def extract_entities(text):
    """Returns a list of dicts: {entity_type, value, confidence}."""
    if not text or not text.strip():
        return []

    entities = []

    # 1. Dates
    for m in DATE_RE.finditer(text):
        entities.append({"entity_type": "date", "value": m.group(0), "confidence": 0.95})

    # 2. Financial Amounts
    for m in AMOUNT_RE.finditer(text):
        entities.append({"entity_type": "amount", "value": m.group(0), "confidence": 0.95})

    # 3. Emails
    for m in EMAIL_RE.finditer(text):
        entities.append({"entity_type": "email", "value": m.group(0), "confidence": 0.99})

    # 4. Phone Numbers
    for m in PHONE_RE.finditer(text):
        entities.append({"entity_type": "phone", "value": m.group(0), "confidence": 0.90})

    return entities
