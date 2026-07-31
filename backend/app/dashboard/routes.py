from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from ..extensions import db
from ..models import Document, ChatHistory

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.get("/summary")
@jwt_required()
def summary():
    user_id = get_jwt_identity()

    total_docs = Document.query.filter_by(user_id=user_id).count()

    by_status = dict(
        db.session.query(Document.status, func.count(Document.id))
        .filter(Document.user_id == user_id)
        .group_by(Document.status)
        .all()
    )

    by_type = dict(
        db.session.query(Document.doc_type, func.count(Document.id))
        .filter(Document.user_id == user_id)
        .group_by(Document.doc_type)
        .all()
    )

    total_chats = (
        db.session.query(func.count(ChatHistory.id))
        .filter(ChatHistory.user_id == user_id)
        .scalar()
    )

    recent = (
        Document.query.filter_by(user_id=user_id)
        .order_by(Document.uploaded_at.desc())
        .limit(5)
        .all()
    )

    return jsonify(
        {
            "total_documents": total_docs,
            "by_status": by_status,
            "by_type": by_type,
            "total_chat_messages": total_chats or 0,
            "recent_documents": [d.to_dict() for d in recent],
        }
    )
