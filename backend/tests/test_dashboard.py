"""Tests for dashboard endpoint."""

from app.extensions import db
from app.models import Document, ChatHistory


class TestDashboardSummary:
    def test_summary_empty(self, client, auth_headers):
        res = client.get("/api/dashboard/summary", headers=auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["total_documents"] == 0
        assert data["total_chat_messages"] == 0
        assert data["by_status"] == {}
        assert data["by_type"] == {}
        assert data["recent_documents"] == []

    def test_summary_with_data(self, client, auth_headers, sample_user, app):
        with app.app_context():
            doc1 = Document(
                user_id=sample_user["id"], filename="a.pdf",
                blob_url="local://a.pdf", status="processed", doc_type="invoice",
            )
            doc2 = Document(
                user_id=sample_user["id"], filename="b.pdf",
                blob_url="local://b.pdf", status="failed", doc_type="contract",
            )
            db.session.add_all([doc1, doc2])
            db.session.commit()

            chat = ChatHistory(
                document_id=doc1.id, user_id=sample_user["id"],
                question="What?", answer="Something.",
            )
            db.session.add(chat)
            db.session.commit()

        res = client.get("/api/dashboard/summary", headers=auth_headers)
        data = res.get_json()
        assert data["total_documents"] == 2
        assert data["total_chat_messages"] == 1
        assert data["by_status"]["processed"] == 1
        assert data["by_status"]["failed"] == 1
        assert data["by_type"]["invoice"] == 1
        assert len(data["recent_documents"]) == 2

    def test_summary_unauthenticated(self, client):
        res = client.get("/api/dashboard/summary")
        assert res.status_code == 401
