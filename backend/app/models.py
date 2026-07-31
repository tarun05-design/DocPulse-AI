import uuid
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


def gen_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="user")  # user | admin
    created_at = db.Column(db.DateTime, default=_utcnow)

    documents = db.relationship("Document", backref="owner", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "role": self.role}


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)

    filename = db.Column(db.String(255), nullable=False)
    blob_url = db.Column(db.String(500), nullable=False)
    doc_type = db.Column(db.String(50))  # invoice | contract | resume | report | other
    status = db.Column(db.String(30), default="uploaded")  # uploaded|processing|processed|failed
    summary = db.Column(db.Text)
    risks = db.Column(db.Text)
    action_items = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=_utcnow)
    processed_at = db.Column(db.DateTime)

    extracted_text = db.relationship("ExtractedText", backref="document", uselist=False)
    entities = db.relationship("Entity", backref="document", lazy=True)
    embeddings = db.relationship("Embedding", backref="document", lazy=True)
    chats = db.relationship("ChatHistory", backref="document", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "doc_type": self.doc_type,
            "status": self.status,
            "summary": self.summary,
            "risks": self.risks,
            "action_items": self.action_items,
            "uploaded_at": (self.uploaded_at.isoformat() + "Z") if self.uploaded_at else None,
        }


class ExtractedText(db.Model):
    __tablename__ = "extracted_text"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    document_id = db.Column(db.String(36), db.ForeignKey("documents.id"), nullable=False)
    raw_text = db.Column(db.Text)
    layout_json = db.Column(db.Text)  # serialized layout/bbox data from LayoutLMv3
    tables_json = db.Column(db.Text)


class Entity(db.Model):
    __tablename__ = "entities"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    document_id = db.Column(db.String(36), db.ForeignKey("documents.id"), nullable=False)
    entity_type = db.Column(db.String(50))  # date | amount | name | clause | org
    value = db.Column(db.String(500))
    confidence = db.Column(db.Float)


class Embedding(db.Model):
    __tablename__ = "embeddings"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    document_id = db.Column(db.String(36), db.ForeignKey("documents.id"), nullable=False)
    chunk_text = db.Column(db.Text)
    vector = db.Column(db.Text)  # JSON-encoded float array (swap for pgvector in production)
    chunk_index = db.Column(db.Integer)


class ChatHistory(db.Model):
    __tablename__ = "chat_history"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    document_id = db.Column(db.String(36), db.ForeignKey("documents.id"), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    question = db.Column(db.Text)
    answer = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"))
    action = db.Column(db.String(120))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_utcnow)
