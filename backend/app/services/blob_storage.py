"""
Blob storage abstraction layer.

Uses Azure Blob Storage when AZURE_STORAGE_CONNECTION_STRING is configured.
Falls back to local filesystem storage when Azure is not available, so the
app can run without any cloud credentials for local development.
"""
import os
import uuid
import logging

from flask import current_app

logger = logging.getLogger(__name__)


def _use_azure():
    return bool(current_app.config.get("AZURE_STORAGE_CONNECTION_STRING"))


# ---------------------------------------------------------------------------
# Azure path
# ---------------------------------------------------------------------------

def _get_azure_client():
    from azure.storage.blob import BlobServiceClient, ContentSettings  # noqa: F811
    conn_str = current_app.config["AZURE_STORAGE_CONNECTION_STRING"]
    service_client = BlobServiceClient.from_connection_string(conn_str)
    container_name = current_app.config["AZURE_STORAGE_CONTAINER"]
    container_client = service_client.get_container_client(container_name)
    if not container_client.exists():
        container_client.create_container()
    return container_client


def _azure_upload(file_bytes, original_filename, content_type=None):
    from azure.storage.blob import ContentSettings
    container_client = _get_azure_client()
    ext = original_filename.rsplit(".", 1)[-1] if "." in original_filename else "bin"
    blob_name = f"{uuid.uuid4()}.{ext}"
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(
        file_bytes,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type or "application/octet-stream"),
    )
    return blob_name, blob_client.url


def _azure_download(blob_name):
    container_client = _get_azure_client()
    return container_client.get_blob_client(blob_name).download_blob().readall()


def _azure_delete(blob_name):
    container_client = _get_azure_client()
    container_client.get_blob_client(blob_name).delete_blob()


# ---------------------------------------------------------------------------
# Local filesystem path
# ---------------------------------------------------------------------------

def _local_dir():
    path = current_app.config["LOCAL_STORAGE_PATH"]
    os.makedirs(path, exist_ok=True)
    return path


def _local_upload(file_bytes, original_filename, content_type=None):
    ext = original_filename.rsplit(".", 1)[-1] if "." in original_filename else "bin"
    blob_name = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(_local_dir(), blob_name)
    with open(filepath, "wb") as f:
        f.write(file_bytes if isinstance(file_bytes, bytes) else file_bytes.read())
    logger.info("Saved file locally: %s", filepath)
    return blob_name, f"local://{blob_name}"


def _local_download(blob_name):
    filepath = os.path.join(_local_dir(), blob_name)
    with open(filepath, "rb") as f:
        return f.read()


def _local_delete(blob_name):
    filepath = os.path.join(_local_dir(), blob_name)
    if os.path.exists(filepath):
        os.remove(filepath)


# ---------------------------------------------------------------------------
# Public API — delegates to Azure or local automatically
# ---------------------------------------------------------------------------

def upload_file(file_stream, original_filename, content_type=None):
    """Uploads a file and returns (blob_name, blob_url)."""
    if _use_azure():
        return _azure_upload(file_stream, original_filename, content_type)
    return _local_upload(file_stream, original_filename, content_type)


def download_file(blob_name):
    """Returns the raw bytes for a stored blob."""
    if _use_azure():
        return _azure_download(blob_name)
    return _local_download(blob_name)


def delete_file(blob_name):
    """Deletes a stored file."""
    if _use_azure():
        return _azure_delete(blob_name)
    return _local_delete(blob_name)
