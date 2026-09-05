import os
from azure.core.exceptions import ResourceExistsError
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
    except ResourceExistsError:
        pass

    blob_client = service.get_blob_client(
        container=container_name,
        blob=blob_name,
    )

    blob_client.upload_blob(content, overwrite=True)

    return f"{container_name}/{blob_name}"

def split_blob_path(
    blob_path: str,
) -> tuple[str, str]:
    try:
        container_name, blob_name = blob_path.split(
            "/",
            maxsplit=1,
        )
    except ValueError as exc:
        raise ValueError(
            "Invalid Azure Blob path. Expected format: "
            "'container-name/blob-name'"
        ) from exc

    if not container_name or not blob_name:
        raise ValueError(
            "Invalid Azure Blob path. Both container name "
            "and blob name are required."
        )

    return container_name, blob_name

def download_text_blob(
    blob_path: str,
) -> str:
    try:
        container_name, blob_name = split_blob_path(
            blob_path,
        )

    except ValueError as exc:
        raise ValueError(
            "Invalid Azure Blob path. Expected format: "
            "'container-name/blob-name'"
        ) from exc

    if not container_name or not blob_name:
        raise ValueError(
            "Invalid Azure Blob path. Both container name "
            "and blob name are required."
        )

    service = get_blob_service_client()

    blob_client = service.get_blob_client(
        container=container_name,
        blob=blob_name,
    )

    return blob_client.download_blob().readall().decode(
        "utf-8",
    )