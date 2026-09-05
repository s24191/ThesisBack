from datetime import datetime

from typing import Literal

from pydantic import BaseModel


class StartListRequest(BaseModel):
    site: str

class StartScrapeRunResponse(BaseModel):
    run_id: int
    run_key: str
    site: str
    status: str

class ScrapeRunRead(BaseModel):
    id: int
    run_key: str

    site_id: int
    site_key: str
    site_name: str

    triggered_by: str | None = None
    status: str

    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    duration_seconds: float  | None = None

class ScrapeStepRunRead(BaseModel):
    id: int
    run_id: int

    step_key: str
    status: str

    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None

    fetched_count: int
    changed_count: int
    retries: int

    input_blob_path: str | None = None
    output_blob_path: str | None = None

    error_message: str | None = None

class ScrapeLogRead(BaseModel):
    id: int
    run_id: int
    step_run_id: int | None = None
    timestamp: datetime
    level: str
    message: str

class StartFetchResponse(BaseModel):
    run_id: int
    run_key: str
    site: str
    step_key: str
    status: str

class StartPersistResponse(BaseModel):
    run_id: int
    run_key: str
    site: str
    step_key: str
    status: str

class ReconcileTranslationsResponse(BaseModel):
    source_run_id: int
    source_fetch_step_id: int

    site: str

    mode: Literal[
        "merge_existing_csv",
        "create_reprocess_run",
    ]

    resolved_occurrence_count: int
    ignored_occurrence_count: int

    status: str