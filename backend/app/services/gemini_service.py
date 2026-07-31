"""
Gemini-backed reasoning layer.

Responsibilities:
  - Summarize a document
  - Identify risks / flags
  - Identify action items
  - Answer natural-language questions over retrieved chunks (RAG)

Gracefully handles model versioning & retries across gemini-2.5-flash / gemini-2.0-flash.
"""
import json
import logging
import re

from flask import current_app

logger = logging.getLogger(__name__)

FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]


def _get_model(model_name=None):
    api_key = current_app.config.get("GEMINI_API_KEY", "")
    if not api_key or len(api_key.strip()) < 5:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        target = model_name or current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash")
        return genai.GenerativeModel(target)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to initialize GenerativeModel: %s", exc)
        return None


def _generate_content_with_fallback(prompt):
    """Executes prompt on configured Gemini model with automatic fallback if model name fails."""
    model = _get_model()
    if model is None:
        raise RuntimeError("GEMINI_API_KEY is not set or is invalid.")

    models_to_try = [current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash")]
    for fb in FALLBACK_MODELS:
        if fb not in models_to_try:
            models_to_try.append(fb)

    last_error = None
    for m_name in models_to_try:
        try:
            m = _get_model(m_name)
            if m is None:
                continue
            response = m.generate_content(prompt)
            return response.text
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("Gemini model '%s' failed (%s), trying next fallback...", m_name, exc)

    raise last_error or RuntimeError("No working Gemini model available.")


def _local_smart_summary(raw_text, doc_type_hint):
    """Generates a rich, structured local document summary when Gemini API is unavailable."""
    if not raw_text or not raw_text.strip():
        return {
            "doc_type": doc_type_hint or "other",
            "summary": "Empty document submitted.",
            "risks": "No text extracted from document.",
            "action_items": "Check document upload and file formatting.",
        }

    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    title = ""
    institution = ""

    for l in lines[:15]:
        clean_l = re.sub(r"^[•\-\*\s]+", "", l).strip()
        if not clean_l:
            continue

        if not title and len(clean_l) > 5 and not any(k in clean_l.lower() for k in ["page 1", "review date", "last updated", "approved by", "table of contents"]):
            title = clean_l

        if not institution:
            if any(k in clean_l.lower() for k in ["institute", "university", "college", "school", "ltd", "limited", "inc", "corp", "llc", "technologies", "services"]):
                institution = clean_l

    doc_type = doc_type_hint or "report"
    summary_parts = []

    if title:
        summary_parts.append(f"Document titled '{title}'")
    if institution:
        summary_parts.append(f"associated with {institution}")

    topic_keywords = []
    lower_text = raw_text.lower()
    for kw in ["rsa encryption", "encryption", "data sharing", "secure data", "machine learning", "analytics", "dashboard", "database", "python", "sql", "invoice", "payment", "agreement", "contract", "terms and conditions"]:
        if kw in lower_text:
            topic_keywords.append(kw.title())
            if len(topic_keywords) >= 4:
                break

    if topic_keywords:
        summary_parts.append(f"covering key topics: {', '.join(topic_keywords)}.")
    else:
        summary_parts.append("containing structured document details.")

    summary_str = " ".join(summary_parts)

    return {
        "doc_type": doc_type,
        "summary": summary_str,
        "risks": "Local processing mode — no compliance risks flagged.",
        "action_items": "Review extracted details and document entities.",
    }


def analyze_document(raw_text, doc_type_hint):
    """Returns dict: {summary, risks, action_items, doc_type}"""
    if _get_model() is None:
        logger.info("Gemini API key unavailable — returning smart local analysis summary")
        return _local_smart_summary(raw_text, doc_type_hint)

    prompt = f"""You are analyzing a document of hinted type "{doc_type_hint}".
Respond ONLY with valid JSON, no markdown fences, matching exactly this schema:
{{
  "doc_type": "invoice|contract|resume|report|other",
  "summary": "2-4 sentence plain-language summary",
  "risks": "bullet-style list of risks, red flags, or missing information (or 'None identified')",
  "action_items": "bullet-style list of concrete action items derived from the document"
}}

Document text:
\"\"\"{raw_text[:12000]}\"\"\"
"""
    try:
        raw_response = _generate_content_with_fallback(prompt)
        return _safe_json(raw_response)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini analyze_document failed: %s", exc)
        return _local_smart_summary(raw_text, doc_type_hint)


def answer_question(question, context_chunks):
    """RAG-style answer grounded in retrieved chunks."""
    if _get_model() is None:
        return _extractive_answer(question, context_chunks)

    context = "\n---\n".join(context_chunks) if context_chunks else "(no relevant context found)"

    prompt = f"""You are a helpful AI document assistant. Answer the user's question clearly, concisely, and neatly using ONLY the provided document excerpts.

Formatting Guidelines:
- Use clear bullet points (`•`) and bold key categories/headings (`**Category:**`).
- Group skills, experience, or details into logical sub-bullets.
- Avoid dense walls of text or long unbroken paragraphs.
- If the answer is not present in the excerpts, state clearly that it was not found.

Document excerpts:
\"\"\"{context}\"\"\"

Question: {question}

Answer:"""
    try:
        answer_text = _generate_content_with_fallback(prompt)
        return answer_text.strip()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini answer_question failed (%s) — falling back to extractive QA", exc)
        return _extractive_answer(question, context_chunks)


def _normalize_query(q):
    """Normalize typos, concatenated words, and missing spaces in user questions."""
    q_clean = q.lower()
    replacements = [
        (r"\bwhatis\b", "what is"),
        (r"\bwhois\b", "who is"),
        (r"\bwhereis\b", "where is"),
        (r"\bhowis\b", "how is"),
        (r"\bsummaryabout\b", "summary about"),
        (r"\bthesummary\b", "the summary"),
        (r"\bdocabout\b", "document about"),
        (r"\bdocumentabout\b", "document about"),
        (r"\bcompanyabout\b", "company about"),
        (r"\bwhatisthis\b", "what is this"),
        (r"\btellme\b", "tell me"),
        (r"\bgiveme\b", "give me"),
        (r"\btitlle\b", "title"),
        (r"\btitlee\b", "title"),
        (r"\bprojecttitle\b", "project title"),
        (r"\bprojectname\b", "project name"),
    ]
    for pat, repl in replacements:
        q_clean = re.sub(pat, repl, q_clean)
    return q_clean


def _extractive_answer(question, context_chunks):
    if not context_chunks:
        return "No relevant text was found in the document to answer your question."

    full_text = "\n".join(context_chunks)
    q_norm = _normalize_query(question)
    q_words = [w for w in re.findall(r"\w+", q_norm) if len(w) > 2]

    # 0.3. Project Title / Document Title Queries
    if any(k in q_norm for k in ["project title", "title of project", "project name", "title of the project", "title", "name of project", "what is the project"]):
        header_text = context_chunks[0] if context_chunks else full_text
        lines = [l.strip() for l in header_text.splitlines() if l.strip()]

        proj_title = ""
        tagline = ""
        full_heading = ""

        for line in lines[:10]:
            clean_l = re.sub(r"^[•\-\*\s]+", "", line).strip()
            if not clean_l or any(k in clean_l.lower() for k in ["page 1", "review date", "last updated", "table of contents"]):
                continue

            if "tagline:" in clean_l.lower():
                tagline = clean_l.split(":", 1)[1].strip()
            elif not proj_title:
                full_heading = clean_l
                if " - " in clean_l:
                    proj_title = clean_l.split(" - ", 1)[0].strip()
                elif ":" in clean_l:
                    proj_title = clean_l.split(":", 1)[0].strip()
                else:
                    proj_title = clean_l

        if proj_title:
            res = [f"• **Project Title:** {proj_title}"]
            if full_heading and full_heading != proj_title:
                res.append(f"• **Document Heading:** {full_heading}")
            if tagline:
                res.append(f"• **Tagline:** {tagline}")
            return "Here is the project title found in the document:\n\n" + "\n".join(res)

    # 0. Document Summary & Overview Queries (e.g. "whatis the summaryabout", "summary", "overview", "what is this document about")
    if any(k in q_norm for k in ["summary", "overview", "about this document", "what is this document", "explain this document", "summaryabout", "about"]):
        lines = [l.strip() for l in full_text.splitlines() if l.strip()]
        clean_lines = []
        for l in lines[:15]:
            cl = re.sub(r"^[•\-\*\s]+", "", l).strip()
            if cl and len(cl) > 5 and not any(k in cl.lower() for k in ["page 1", "review date", "last updated", "approved by", "table of contents", "input output summary table"]):
                clean_lines.append(cl)
            if len(clean_lines) >= 4:
                break

        if clean_lines:
            res = ["Here is a summary and key overview of the document:\n"]
            for idx, item in enumerate(clean_lines):
                if idx == 0:
                    res.append(f"• **Main Subject / Title:** {item}")
                elif idx == 1:
                    res.append(f"• **Organization / Subheading:** {item}")
                else:
                    res.append(f"• **Key Details:** {item}")
            return "\n".join(res)

    # 0. Candidate Name & Identity Queries
    if any(k in q_lower for k in ["name", "who is the candidate", "candidate", "applicant", "whose resume", "person name"]):
        header_text = context_chunks[0] if context_chunks else full_text
        lines = [l.strip() for l in header_text.splitlines() if l.strip()]
        cand_name, cand_title, cand_email = "", "", ""
        for line in lines[:8]:
            clean_l = re.sub(r"^[•\-\*\s]+", "", line).strip()
            if not clean_l:
                continue
            if "@" in clean_l and not cand_email:
                m_email = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", clean_l)
                if m_email:
                    cand_email = m_email.group(0)
            if not cand_name and len(clean_l) < 60 and not any(k in clean_l.lower() for k in ["http", "@", "certific", "summary", "experience", "skill"]):
                if "|" in clean_l:
                    parts = clean_l.split("|")
                    cand_name = parts[0].strip()
                    if len(parts) > 1:
                        cand_title = parts[1].strip()
                elif " - " in clean_l:
                    parts = clean_l.split(" - ", 1)
                    cand_name = parts[0].strip()
                    cand_title = parts[1].strip()
                else:
                    cand_name = clean_l
        if cand_name:
            res = [f"• **Candidate Name:** {cand_name}"]
            if cand_title:
                res.append(f"• **Role / Title:** {cand_title}")
            if cand_email:
                res.append(f"• **Email:** {cand_email}")
            return "Here is the candidate information found in the document:\n\n" + "\n".join(res)

    # 0.5. Company & Organization Queries
    if any(k in q_lower for k in ["company", "organization", "institute", "business", "firm", "issuer", "about this company", "who is this company"]):
        header_text = context_chunks[0] if context_chunks else full_text
        lines = [l.strip() for l in header_text.splitlines() if l.strip()]

        comp_name = ""
        doc_heading = ""
        org_re = re.compile(r"\b[A-Z0-9\s&,.'-]{3,70}\b\s*(?:LTD|LIMITED|INC|INCORPORATED|CORP|CORPORATION|LLC|PLC|PTY\s+LTD|INSTITUTE|UNIVERSITY|BANK|GROUP|CO\.|SOLUTIONS|TECHNOLOGIES|SERVICES)\b", re.IGNORECASE)

        for line in lines[:15]:
            clean_l = re.sub(r"^[•\-\*\s]+", "", line).strip()
            if not clean_l:
                continue

            if not comp_name:
                m_org = org_re.search(clean_l)
                if m_org:
                    comp_name = m_org.group(0).strip()

            if any(k in clean_l.lower() for k in ["terms and conditions", "privacy policy", "agreement", "invoice", "statement", "contract", "report"]):
                if not doc_heading:
                    doc_heading = clean_l

        if comp_name:
            res = [f"• **Company / Organization:** {comp_name}"]
            if doc_heading:
                res.append(f"• **Document Subject:** {doc_heading}")

            excerpt_lines = [l for l in lines[:10] if not any(k in l.lower() for k in ["page 1", "last updated", "review date", "review by", "approved by"])][:3]
            if excerpt_lines:
                res.append(f"• **Overview:** " + " ".join(excerpt_lines))

            return "Here is the company / organization details found in the document:\n\n" + "\n".join(res)

    # 0.8. Document Summary & Overview Queries
    if any(k in q_lower for k in ["summary", "overview", "what is this document", "explain this document", "about this document"]):
        header_text = context_chunks[0] if context_chunks else full_text
        lines = [l.strip() for l in header_text.splitlines() if l.strip()]
        clean_lines = [re.sub(r"^[•\-\*\s]+", "", l).strip() for l in lines[:10] if l.strip()]
        clean_lines = [l for l in clean_lines if not any(k in l.lower() for k in ["page 1", "last updated", "review date", "review by", "approved by"])][:4]
        if clean_lines:
            return "Document Summary & Key Details:\n\n" + "\n".join(f"• {l}" for l in clean_lines)

    # 1. Links & Contact Information
    if any(k in q_lower for k in ["link", "github", "linkedin", "url", "website", "social", "contact", "email", "phone"]):
        lines = []
        for line in full_text.splitlines():
            line_str = line.strip()
            if any(k in line_str.lower() for k in ["http", "github", "linkedin", "www.", ".com", "@", "mailto", "phone", "+91"]):
                for segment in line_str.split("|"):
                    seg = segment.strip()
                    if seg and seg not in lines:
                        lines.append(seg)
        if lines:
            formatted = []
            for item in lines[:8]:
                if "@" in item:
                    formatted.append(f"• **Email:** {item}")
                elif "linkedin" in item.lower():
                    formatted.append(f"• **LinkedIn:** {item}")
                elif "github" in item.lower():
                    formatted.append(f"• **GitHub:** {item}")
                else:
                    formatted.append(f"• {item}")
            return "Found the following contact details & links in the document:\n\n" + "\n".join(formatted)

    # 2. Skills & Technologies Query
    if any(k in q_lower for k in ["skill", "technolog", "tool", "language", "stack", "know", "expert", "ability", "abilities"]):
        categories = re.findall(
            r"((?:Languages|ML\s*&\s*Data\s*Science|Libraries\s*&\s*Frameworks|Visualization\s*&\s*BI|Tools\s*&\s*Cloud|Stack|Technical\s*Skills|Core\s*Competencies)[^:\n]*:\s*[^•\n]+)",
            full_text,
            re.IGNORECASE,
        )
        if categories:
            formatted_cat = []
            seen_cat = set()
            for cat in categories:
                cat_clean = cat.strip()
                if ":" in cat_clean:
                    key, val = cat_clean.split(":", 1)
                    key_str = key.strip().title()
                    val_str = val.strip()
                    if key_str not in seen_cat and val_str:
                        seen_cat.add(key_str)
                        formatted_cat.append(f"• **{key_str}:** {val_str}")
            if formatted_cat:
                return "Here are the technical skills found in the document:\n\n" + "\n".join(formatted_cat)

    # 3. General Sentence & Section Matching with Clean Formatting
    processed_text = re.sub(r"(•|\b(?:TECHNICAL SKILLS|SUMMARY|PROJECTS|EXPERIENCE|EDUCATION|CERTIFICATIONS)\b)", r"\n\1", full_text)
    processed_text = re.sub(r"(\b(?:Languages|ML & Data Science|Libraries & Frameworks|Visualization & BI|Tools & Cloud|Stack):)", r"\n\1", processed_text)

    lines = [l.strip() for l in processed_text.splitlines() if l.strip()]
    scored = []
    for l in lines:
        l_clean = re.sub(r"^[•\-\*\s]+", "", l).strip()
        if not l_clean:
            continue
        score = sum(1 for w in q_words if w in l_clean.lower())
        if score > 0:
            scored.append((score, l_clean))

    scored.sort(key=lambda x: x[0], reverse=True)
    if scored:
        seen = set()
        unique = []
        for _, line in scored:
            if line not in seen and len(line) > 5:
                seen.add(line)
                if ":" in line and not line.startswith("http"):
                    parts = line.split(":", 1)
                    k, v = parts[0].strip(), parts[1].strip()
                    if len(k) < 35 and v:
                        unique.append(f"• **{k}:** {v}")
                        continue
                unique.append(f"• {line}")
            if len(unique) >= 6:
                break
        return "Based on the document context:\n\n" + "\n".join(unique)

    return "Relevant excerpt from document:\n\n" + full_text[:800]


def _safe_json(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).replace("json", "", 1)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "doc_type": "other",
            "summary": cleaned[:500],
            "risks": "Could not parse structured risks — see raw summary.",
            "action_items": "Could not parse structured action items.",
        }
