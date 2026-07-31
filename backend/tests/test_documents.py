"""Tests for document endpoints."""
from unittest.mock import patch, MagicMock
import json

from app.extensions import db
from app.models import Document, ExtractedText, Entity, Embedding


def _make_doc(user_id, filename="test.pdf", status="processed"):
    """Helper to create a document directly in the DB."""
    doc = Document(
        user_id=user_id,
        filename=filename,
        blob_url="local://test.pdf",
        status=status,
        doc_type="report",
        summary="Test summary",
    )
    db.session.add(doc)
    db.session.commit()
    return doc


class TestListDocuments:
    def test_list_empty(self, client, auth_headers):
        res = client.get("/api/documents", headers=auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["documents"] == []
        assert data["total"] == 0

    def test_list_with_docs(self, client, auth_headers, sample_user, app):
        with app.app_context():
            _make_doc(sample_user["id"], "doc1.pdf")
            _make_doc(sample_user["id"], "doc2.pdf")

        res = client.get("/api/documents", headers=auth_headers)
        data = res.get_json()
        assert data["total"] == 2
        assert len(data["documents"]) == 2

    def test_list_user_isolation(self, client, auth_headers, sample_user, app):
        """Users should only see their own documents."""
        with app.app_context():
            _make_doc(sample_user["id"], "mine.pdf")
            _make_doc("other-user-id", "theirs.pdf")

        res = client.get("/api/documents", headers=auth_headers)
        data = res.get_json()
        assert data["total"] == 1
        assert data["documents"][0]["filename"] == "mine.pdf"

    def test_list_unauthenticated(self, client):
        res = client.get("/api/documents")
        assert res.status_code == 401


class TestGetDocument:
    def test_get_success(self, client, auth_headers, sample_user, app):
        with app.app_context():
            doc = _make_doc(sample_user["id"])
            doc_id = doc.id

        res = client.get(f"/api/documents/{doc_id}", headers=auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["filename"] == "test.pdf"
        assert data["summary"] == "Test summary"

    def test_get_not_found(self, client, auth_headers):
        res = client.get("/api/documents/nonexistent", headers=auth_headers)
        assert res.status_code == 404


class TestDeleteDocument:
    def test_delete_success(self, client, auth_headers, sample_user, app):
        with app.app_context():
            doc = _make_doc(sample_user["id"])
            doc_id = doc.id

        res = client.delete(f"/api/documents/{doc_id}", headers=auth_headers)
        assert res.status_code == 200
        assert "deleted" in res.get_json()["message"].lower()

        # Verify it's gone
        res2 = client.get(f"/api/documents/{doc_id}", headers=auth_headers)
        assert res2.status_code == 404

    def test_delete_not_found(self, client, auth_headers):
        res = client.delete("/api/documents/nonexistent", headers=auth_headers)
        assert res.status_code == 404

    def test_delete_other_users_doc(self, client, auth_headers, app):
        with app.app_context():
            doc = _make_doc("other-user-id")
            doc_id = doc.id

        res = client.delete(f"/api/documents/{doc_id}", headers=auth_headers)
        assert res.status_code == 404


class TestUploadDocument:
    @patch("app.documents.routes._process_document_sync")
    def test_upload_success(self, mock_process, client, auth_headers):
        """Upload with mocked processing."""
        import io
        data = {
            "file": (io.BytesIO(b"fake pdf bytes"), "test.pdf"),
        }
        res = client.post(
            "/api/documents/upload",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert res.status_code == 201
        assert res.get_json()["filename"] == "test.pdf"
        mock_process.assert_called_once()

    def test_upload_no_file(self, client, auth_headers):
        res = client.post("/api/documents/upload", headers=auth_headers)
        assert res.status_code == 400

    def test_upload_bad_extension(self, client, auth_headers):
        import io
        data = {"file": (io.BytesIO(b"data"), "malware.exe")}
        res = client.post(
            "/api/documents/upload",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert res.status_code == 400
        assert "Unsupported" in res.get_json()["error"]
