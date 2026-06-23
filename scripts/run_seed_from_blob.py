import os
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

from shared.database import init_db, async_session_maker
from shared.seed.wine_seed import seed_wines_from_csvs

load_dotenv()

CLEAN_CONTAINER = os.getenv("AZURE_STORAGE_CLEAN_CONTAINER", "wine-clean")
CONNECT_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
LOCAL_BASE = Path("/tmp/seed_csvs")

BLOBS = [
    ("sklep-wina/cleaned_wine_data.csv", "sklep-wina/cleaned_wine_data.csv"),
    ("winapl/cleaned_wine_data.csv", "winapl/cleaned_wine_data.csv"),
    ("malawinnica/cleaned_wine_data.csv", "malawinnica/cleaned_wine_data.csv"),
]

def download_blob(blob_service_client, blob_name: str, local_relative_path: str) -> None:
    blob_client = blob_service_client.get_blob_client(
        container=CLEAN_CONTAINER,
        blob=blob_name,
    )
    local_path = LOCAL_BASE / local_relative_path
    local_path.parent.mkdir(parents=True, exist_ok=True)

    with open(local_path, "wb") as f:
        f.write(blob_client.download_blob().readall())

async def main():
    if not CONNECT_STR:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING is not set")

    blob_service_client = BlobServiceClient.from_connection_string(CONNECT_STR)

    for blob_name, local_relative_path in BLOBS:
        download_blob(blob_service_client, blob_name, local_relative_path)

    os.environ["SEED_CSV_DIR"] = str(LOCAL_BASE)

    await init_db()

    async with async_session_maker() as session:
        await seed_wines_from_csvs(session)

if __name__ == "__main__":
    print("DATABASE_URL =", os.getenv("DATABASE_URL"))
    asyncio.run(main())