# from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class ScrapeSite(SQLModel, table=True):
    __tablename__ = "scrape_site"

    id: Optional[int] = Field(default=None, primary_key=True)

    key: str = Field(index=True, unique=True)

    name: str

    base_url: str

    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScrapeRun(SQLModel, table=True):
    __tablename__ = "scrape_run"

    id: Optional[int] = Field(default=None, primary_key=True)

    site_id: int = Field(foreign_key="scrape_site.id", index=True)

    run_key: str = Field(index=True, unique=True)

    triggered_by: Optional[str] = Field(default=None, index=True)

    status: str = Field(default="queued", index=True)

    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None

    duration_seconds: Optional[float] = None

    total_wines_fetched: int = Field(default=0)
    changed_records: int = Field(default=0)
    retries: int = Field(default=0)

    error_message: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScrapeStepRun(SQLModel, table=True):
    __tablename__ = "scrape_step_run"

    id: Optional[int] = Field(default=None, primary_key=True)

    run_id: int = Field(foreign_key="scrape_run.id", index=True)

    step_key: str = Field(index=True)

    status: str = Field(default="queued", index=True)

    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None

    duration_seconds: Optional[float] = None

    fetched_count: int = Field(default=0)
    changed_count: int = Field(default=0)
    retries: int = Field(default=0)
    links_blob_path: Optional[str] = Field(default=None)
    error_message: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScrapeLog(SQLModel, table=True):
    __tablename__ = "scrape_log"

    id: Optional[int] = Field(default=None, primary_key=True)

    run_id: int = Field(foreign_key="scrape_run.id", index=True)
    step_run_id: Optional[int] = Field(
        default=None,
        foreign_key="scrape_step_run.id",
        index=True,
    )

    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)

    level: str = Field(default="info", index=True)

    message: str