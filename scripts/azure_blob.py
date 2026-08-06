import os
from azure.storage.blob import BlobServiceClient

def get_blob_service_client() -> BlobServiceClient:
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is not set")
    return BlobServiceClient.from_connection_string(conn_str)


def upload_text_blob(
    container_name: str,
    blob_name: str,
    content: str,
) -> str:
    service = get_blob_service_client()
    container_client = service.get_container_client(container_name)

    try:
        container_client.create_container()
    except Exception:
        pass

    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(content, overwrite=True)

    return f"{container_name}/{blob_name}"