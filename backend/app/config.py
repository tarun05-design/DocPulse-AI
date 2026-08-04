import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)

    _instance_db = os.path.abspath(os.path.join(basedir, "..", "instance", "docpulse.db"))
    _root_db = os.path.abspath(os.path.join(basedir, "..", "docpulse.db"))
    _default_db = _instance_db if os.path.exists(_instance_db) else _root_db

    _db_uri = os.environ.get("DATABASE_URL", f"sqlite:///{_default_db}")
    SQLALCHEMY_DATABASE_URI = _db_uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    AZURE_STORAGE_CONTAINER = os.environ.get("AZURE_STORAGE_CONTAINER", "docpulse-documents")

    # When Azure creds are empty, files are saved locally here instead.
    LOCAL_STORAGE_PATH = os.environ.get(
        "LOCAL_STORAGE_PATH", os.path.join(basedir, "..", "uploads")
    )

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

    HF_OCR_MODEL = os.environ.get("HF_OCR_MODEL", "microsoft/trocr-base-printed")
    HF_LAYOUT_MODEL = os.environ.get("HF_LAYOUT_MODEL", "microsoft/layoutlmv3-base")
    HF_EMBEDDING_MODEL = os.environ.get("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "*")
    DISABLE_HEAVY_MODELS = os.environ.get("DISABLE_HEAVY_MODELS", "true").lower() in ("true", "1", "t")

    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB upload cap


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    AZURE_STORAGE_CONNECTION_STRING = ""
    GEMINI_API_KEY = ""
    LOCAL_STORAGE_PATH = os.path.join(basedir, "..", "test_uploads")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
