# DocPulse AI

> **Enterprise Document Intelligence Platform powered by Google Gemini 2.5 Flash, Multimodal OCR, Dense Vector RAG, Flask REST API, PostgreSQL, and Docker Containerization.**

🌐 **Live Demo**: [https://doc-pulse-ai-seven.vercel.app/](https://doc-pulse-ai-seven.vercel.app/)

[![Live Demo](https://img.shields.io/badge/Live%20Demo-doc--pulse--ai--seven.vercel.app-00C7B7?style=for-the-badge&logo=vercel&logoColor=white)](https://doc-pulse-ai-seven.vercel.app/)

[![Docker](https://img.shields.io/badge/Container-Docker%20%26%20Docker%20Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Python 3.14](https://img.shields.io/badge/Language-Python%203.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask REST API](https://img.shields.io/badge/Backend-Flask%20REST%20API-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Google Gemini 2.5](https://img.shields.io/badge/AI%20Engine-Google%20Gemini%202.5%20Flash-8E44AD?logo=google&logoColor=white)](https://ai.google.dev/)
[![Vector RAG](https://img.shields.io/badge/Vector%20Search-SentenceTransformers%20RAG-FF6F00?logo=huggingface&logoColor=white)](https://huggingface.co/)
[![PyTesseract OCR](https://img.shields.io/badge/OCR-PyTesseract%20%26%20TrOCR-009688)](https://github.com/tesseract-ocr/tesseract)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20%2F%20SQLite-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Security](https://img.shields.io/badge/Auth-JWT%20%26%20Bcrypt-D32F2F)](https://jwt.io/)
[![Tests](https://img.shields.io/badge/Tests-41%20Passed-brightgreen.svg)]()

DocPulse AI is a production-grade AI SaaS platform that transforms unstructured documents (**PDF, DOCX, TXT, PNG, JPG, TIFF, BMP**) into actionable intelligence. It orchestrates optical character recognition, spatial layout parsing, 384-dimensional dense vector embeddings, and Google Gemini neural reasoning to generate executive summaries, audit compliance risks, extract named entities, and power context-grounded Q&A chat.

---

### 🛠️ Technology Stack at a Glance

| Category | Technologies & Frameworks |
|---|---|
| **DevOps & Infrastructure** | **Docker**, **Docker Compose**, **Nginx Web Server**, Pytest Automation Suite (41 Tests) |
| **AI & Neural Reasoning** | **Google Gemini 2.5 Flash API**, Smart Local Heuristic NLP Engine |
| **Multimodal OCR & Layout** | **PyTesseract OCR**, PyPDF/pypdf, `python-docx`, LayoutLMv3, TrOCR |
| **Vector RAG Engine** | `sentence-transformers/all-MiniLM-L6-v2` (384-dim dense embeddings), Cosine Similarity Retrieval |
| **Backend & Security** | Python 3.14, **Flask REST API**, SQLAlchemy ORM, JWT Bearer Tokens, Bcrypt Password Hashing |
| **Database & Cloud Storage** | **PostgreSQL**, SQLite (Development), Azure Blob Storage + Local Filesystem Fallback |
| **Frontend UI/UX** | Modern Vercel/Linear-inspired Glassmorphism Dark Theme, Vanilla JS (No heavy framework overhead), Dynamic Profile Navigation |

---

## 🌟 Key Features & Architecture

- **Multimodal Document Processing**: Automatic text layer extraction for digital PDFs, DOCX parsing via `python-docx`, plain text ingestion, and OCR for scanned images using `PyTesseract` and Hugging Face TrOCR (`microsoft/trocr-base-printed`).
- **Spatial Layout Parsing**: Preserves document structure, tables, section headers, and bounding boxes via LayoutLMv3 (`microsoft/layoutlmv3-base`).
- **Google Gemini 2.5 Flash AI Reasoning**: Produces 2-paragraph summaries, audits compliance risks and red flags, generates concrete action items, and classifies document types (Contracts, Invoices, Reports, Resumes).
- **Dense Vector RAG Chat**: Character sliding-window chunking with `sentence-transformers/all-MiniLM-L6-v2` (384-dim vectors) and cosine similarity retrieval for context-grounded sub-second Q&A.
- **Smart Hybrid Fallback Engine**: Runs 100% locally offline using custom heuristic NLP algorithms when offline, or supercharged with Google Gemini Cloud AI when connected.
- **Entity Extraction**: Regex pattern matching for dates and monetary amounts + Hugging Face NER pipeline (`ner`) for person names, organizations, and location tags.
- **Production Vercel/Linear Frontend**: High-converting glassmorphism dark theme (`#07080c`), 4-step interactive pipeline cards, dynamic Profile header menu, live background processing polling, and mobile-responsive layout.
- **Enterprise Isolation & Security**: Bcrypt password hashing, JWT bearer token authentication, user-isolated database records, and Azure Blob Storage abstraction with local filesystem fallback.

---

## 📁 Repository Structure

```
DocPulse-AI/
├── backend/                 # Flask REST API Backend
│   ├── app/
│   │   ├── auth/            # Register, login, JWT token, user profile, password updates
│   │   ├── documents/       # Upload, async processing, listing, detail, reprocess, download, delete
│   │   ├── chat/            # Vector RAG Q&A engine over documents + chat history
│   │   ├── dashboard/       # Analytics endpoints (counts by type/status, total messages)
│   │   ├── services/
│   │   │   ├── blob_storage.py     # Azure Blob Storage + Local Filesystem Fallback
│   │   │   ├── ocr_pipeline.py     # PyPDF/PyTesseract/python-docx/TrOCR/LayoutLMv3
│   │   │   ├── entity_extraction.py # Regex + NER named entity extraction
│   │   │   ├── gemini_service.py   # Gemini 2.5 Flash reasoning + Local Smart Fallback
│   │   │   └── embeddings.py       # SentenceTransformers chunking + vector search
│   │   ├── models.py        # SQLAlchemy Models (Users, Documents, Extracted_Text, Entities, Embeddings, Chat_History)
│   │   └── config.py        # Environment & Database Configuration
│   ├── tests/               # Pytest suite (41 passing tests covering auth, docs, RAG, services)
│   ├── run.py               # Flask application entry point
│   ├── requirements.txt     # Python dependencies
│   ├── .env.example         # Template environment variables
│   ├── .dockerignore
│   └── Dockerfile
├── frontend/                # Production SPA UI (Vercel/Linear Dark Theme)
│   ├── index.html           # Landing page with interactive hero mockup, stats & 4-step workflow
│   ├── upload.html          # Document drag & drop upload + background processing list
│   ├── chat.html            # Split-layout document viewer & grounded Gemini Q&A chat
│   ├── dashboard.html       # Visual analytics & metric progress bars
│   ├── login.html           # Authentication portal (Sign in / Register)
│   ├── css/
│   │   └── style.css        # Premium SaaS glassmorphism CSS design system
│   └── js/
│       └── api.js           # Central API client, JWT session management, header rendering & toasts
├── docker-compose.yml       # Docker Compose setup (PostgreSQL + Flask + Nginx)
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start (Local Setup)

### 1. Backend Setup

```bash
cd backend

# Create & activate virtual environment
python -m venv venv
# Windows: venv\Scripts\activate | Linux/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Open `backend/.env` and add your Google Gemini API Key:
```env
GEMINI_API_KEY=AIzaSy...your_gemini_api_key...
GEMINI_MODEL=gemini-2.5-flash
```

Launch Flask REST server:
```bash
python run.py
```
*Backend runs on `http://localhost:5000`.*

---

### 2. Frontend Setup

```bash
cd frontend
python -m http.server 5500
```
*Open `http://localhost:5500` in your web browser.*

---

## 🐳 Docker Deployment

To launch the complete enterprise container stack (PostgreSQL + Flask REST API + Nginx Web Server):

```bash
docker compose up --build
```

- **Frontend UI**: `http://localhost:5500`
- **Backend API**: `http://localhost:5000`
- **PostgreSQL**: `localhost:5432`

---

## 🧪 Running Automated Tests

Run the full backend test suite using `pytest`:

```bash
cd backend
python -m pytest tests/ -v
```

```text
====================== 41 passed in 9.38s ======================
```

---

## 📡 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register` | `POST` | Create a new user account |
| `/api/auth/login` | `POST` | Authenticate user & return JWT Bearer Token |
| `/api/auth/me` | `GET` | Retrieve current authenticated user details |
| `/api/auth/profile` | `PUT` | Update user profile name |
| `/api/auth/password` | `PUT` | Update account password |
| `/api/documents/upload` | `POST` *(multipart)* | Upload file & trigger automated AI pipeline |
| `/api/documents` | `GET` | List user's documents (supports `page`, `per_page`) |
| `/api/documents/<id>` | `GET` | Retrieve document details (summary, risks, entities, text) |
| `/api/documents/<id>/download` | `GET` | Download original uploaded document file |
| `/api/documents/<id>/reprocess` | `POST` | Re-trigger AI pipeline on document |
| `/api/documents/<id>` | `DELETE` | Delete document and associated embeddings/chats |
| `/api/chat/<doc_id>` | `POST` | Ask a natural language question (Vector RAG + Gemini AI) |
| `/api/chat/<doc_id>/history` | `GET` | Fetch past Q&A message history |
| `/api/dashboard/summary` | `GET` | Fetch user analytics (document counts by status/type) |
| `/api/health` | `GET` | Health check endpoint |

---

## 👤 Author & Credits

**DocPulse AI — Engineered by Tarun P**  
*Built with Python, Flask, Google Gemini 2.5 Flash, PyTesseract, SentenceTransformers, and Vanilla Web Technologies.*
