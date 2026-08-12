from sqlalchemy import func
from typing import Literal

from uuid import uuid4

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from scripts.temp.background_jobs.background_fetch import run_fetch_background
from scripts.temp.background_jobs.background_persist import run_persist_background
from scripts.temp.background_jobs.background_reconcile_translations import run_translation_reconciliation_background
from shared.auth.admin import current_admin
from shared.database import get_session
from shared.models import TranslationReviewOccurrence
from shared.models.scraping import ScrapeLog, ScrapeRun, ScrapeSite, ScrapeStepRun
from scripts.temp.background_jobs.background_list import run_list_background
from scripts.sites import SITE_CONFIG


router = APIRouter(
    prefix="/admin/scraping",
    tags=["admin-scraping"],
    dependencies=[Depends(current_admin)],
)


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

def generate_run_key(site_key: str) -> str:
    timestamp = datetime.utcnow().strftime(
        "%Y%m%d-%H%M%S"
    )
    unique_suffix = uuid4().hex[:8]

    return f"{site_key}-{timestamp}-{unique_suffix}"

def get_run_duration_seconds(
    started_at: datetime | None,
    finished_at: datetime | None,
) -> float | None:
    if not started_at:
        return None

    end_time = finished_at or datetime.utcnow()

    return round(
        (end_time - started_at).total_seconds(),
        3,
    )

def to_scrape_run_read(
    run: ScrapeRun,
    site: ScrapeSite,
) -> ScrapeRunRead:
    return ScrapeRunRead(
        id=run.id,
        run_key=run.run_key,
        site_id=run.site_id,
        site_key=site.key,
        site_name=site.name,
        status=run.status,
        triggered_by=run.triggered_by,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_seconds=get_run_duration_seconds(
            started_at=run.started_at,
            finished_at=run.finished_at,
        ),
    )

@router.post(
    "/start-list",
    response_model=StartScrapeRunResponse,
    status_code=202,
)
async def start_list_scraping(
    payload: StartListRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    site_key = payload.site

    if site_key not in SITE_CONFIG:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown site '{site_key}'",
        )

    site_meta = SITE_CONFIG[site_key]

    result = await session.execute(
        select(ScrapeSite).where(
            ScrapeSite.key == site_key
        )
    )
    site = result.scalar_one_or_none()

    if not site:
        site = ScrapeSite(
            key=site_key,
            name=site_meta["name"],
            base_url=site_meta["base_url"],
        )
        session.add(site)
        await session.flush()

    run = ScrapeRun(
        site_id=site.id,
        run_key=generate_run_key(site_key),
        triggered_by="manual:admin",
        status="queued",
    )
    session.add(run)

    await session.commit()
    await session.refresh(run)

    background_tasks.add_task(
        run_list_background,
        run.id,
        site_key,
    )

    return StartScrapeRunResponse(
        run_id=run.id,
        run_key=run.run_key,
        site=site.key,
        status=run.status,
    )

@router.post(
    "/runs/{run_id}/start-fetch",
    response_model=StartFetchResponse,
    status_code=202,
)
async def start_fetch_scraping(
    run_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ScrapeRun, ScrapeSite)
        .join(
            ScrapeSite,
            ScrapeSite.id == ScrapeRun.site_id,
        )
        .where(ScrapeRun.id == run_id)
    )
    row = result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Scrape run not found",
        )

    run, site = row

    list_step_result = await session.execute(
        select(ScrapeStepRun)
        .where(
            ScrapeStepRun.run_id == run_id,
            ScrapeStepRun.step_key == "list",
        )
        .order_by(ScrapeStepRun.id.desc())
    )
    list_step = list_step_result.scalars().first()

    if not list_step:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot start fetch: this run has no completed "
                "listing step."
            ),
        )

    if list_step.status != "succeeded":
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot start fetch: the listing step must be "
                f"succeeded first. Current status: {list_step.status}."
            ),
        )

    fetch_step_result = await session.execute(
        select(ScrapeStepRun)
        .where(
            ScrapeStepRun.run_id == run_id,
            ScrapeStepRun.step_key == "fetch",
        )
        .order_by(ScrapeStepRun.id.desc())
    )
    existing_fetch_step = fetch_step_result.scalars().first()

    if existing_fetch_step:
        raise HTTPException(
            status_code=409,
            detail=(
                "A fetch step already exists for this scrape run. "
                "Start a new listing run before fetching again."
            ),
        )

    background_tasks.add_task(
        run_fetch_background,
        run.id,
        site.key,
    )

    return StartFetchResponse(
        run_id=run.id,
        run_key=run.run_key,
        site=site.key,
        step_key="fetch",
        status="queued",
    )

@router.post(
    "/runs/{run_id}/start-persist",
    response_model=StartPersistResponse,
    status_code=202,
)
async def start_persist_scraping(
    run_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ScrapeRun, ScrapeSite)
        .join(
            ScrapeSite,
            ScrapeSite.id == ScrapeRun.site_id,
        )
        .where(ScrapeRun.id == run_id)
    )
    row = result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Scrape run not found",
        )

    run, site = row

    if run.status in {
        "completed",
        "failed",
        "cancelled",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot start persist step: scrape run has "
                f"terminal status '{run.status}'."
            ),
        )

    fetch_step_result = await session.execute(
        select(ScrapeStepRun)
        .where(
            ScrapeStepRun.run_id == run_id,
            ScrapeStepRun.step_key == "fetch",
        )
        .order_by(ScrapeStepRun.id.desc())
    )
    fetch_step = fetch_step_result.scalars().first()

    if not fetch_step:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot start persist step: this run has "
                "no fetch step."
            ),
        )

    if fetch_step.status not in {
        "succeeded",
        "partial",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot start persist step: fetch step must "
                "finish with status 'succeeded' or 'partial'. "
                f"Current status: '{fetch_step.status}'."
            ),
        )

    if not fetch_step.output_blob_path:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot start persist step: fetch step has "
                "no output CSV Blob path."
            ),
        )

    persist_step_result = await session.execute(
        select(ScrapeStepRun)
        .where(
            ScrapeStepRun.run_id == run_id,
            ScrapeStepRun.step_key == "persist",
        )
        .order_by(ScrapeStepRun.id.desc())
    )
    existing_persist_step = (
        persist_step_result.scalars().first()
    )
    can_update_fetch_csv = existing_persist_step is None

    if existing_persist_step:
        raise HTTPException(
            status_code=409,
            detail=(
                "A persist step already exists for this scrape run. "
                "Start a new scrape run before persisting again."
            ),
        )

    background_tasks.add_task(
        run_persist_background,
        run.id,
        site.key,
    )

    return StartPersistResponse(
        run_id=run.id,
        run_key=run.run_key,
        site=site.key,
        step_key="persist",
        status="queued",
    )

@router.post(
    "/runs/{run_id}/reconcile-translations",
    response_model=ReconcileTranslationsResponse,
    status_code=202,
)
async def reconcile_run_translations(
    run_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    run_result = await session.execute(
        select(ScrapeRun, ScrapeSite)
        .join(
            ScrapeSite,
            ScrapeSite.id == ScrapeRun.site_id,
        )
        .where(ScrapeRun.id == run_id)
    )
    row = run_result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Scrape run not found",
        )

    run, site = row

    fetch_step_result = await session.execute(
        select(ScrapeStepRun)
        .where(
            ScrapeStepRun.run_id == run.id,
            ScrapeStepRun.step_key == "fetch",
        )
        .order_by(ScrapeStepRun.id.desc())
    )
    fetch_step = fetch_step_result.scalars().first()

    if not fetch_step:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot reconcile translations: this run "
                "has no fetch step."
            ),
        )

    if fetch_step.status != "partial":
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot reconcile translations: the latest "
                "fetch step must have status 'partial'. "
                f"Current status: '{fetch_step.status}'."
            ),
        )

    if not fetch_step.output_blob_path:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot reconcile translations: fetch step "
                "has no output CSV Blob path."
            ),
        )

    pending_count_result = await session.execute(
        select(
            func.count(
                TranslationReviewOccurrence.id
            )
        )
        .where(
            TranslationReviewOccurrence.step_run_id
            == fetch_step.id,
            TranslationReviewOccurrence.status
            == "pending",
        )
    )
    pending_occurrence_count = (
        pending_count_result.scalar_one()
    )

    resolved_count_result = await session.execute(
        select(
            func.count(
                TranslationReviewOccurrence.id
            )
        )
        .where(
            TranslationReviewOccurrence.step_run_id
            == fetch_step.id,
            TranslationReviewOccurrence.status
            == "resolved",
        )
    )
    resolved_occurrence_count = (
        resolved_count_result.scalar_one()
    )

    ignored_count_result = await session.execute(
        select(
            func.count(
                TranslationReviewOccurrence.id
            )
        )
        .where(
            TranslationReviewOccurrence.step_run_id
            == fetch_step.id,
            TranslationReviewOccurrence.status
            == "ignored",
        )
    )
    ignored_occurrence_count = (
        ignored_count_result.scalar_one()
    )

    if (
        resolved_occurrence_count == 0
        and ignored_occurrence_count == 0
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot reconcile translations: this fetch "
                "step has no resolved or ignored translation "
                "review occurrences."
            ),
        )

    persist_step_result = await session.execute(
        select(ScrapeStepRun)
        .where(
            ScrapeStepRun.run_id == run.id,
            ScrapeStepRun.step_key == "persist",
        )
        .order_by(ScrapeStepRun.id.desc())
    )
    persist_step = persist_step_result.scalars().first()


    if not persist_step and pending_occurrence_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot reconcile the original fetch CSV while "
                f"{pending_occurrence_count} translation "
                "occurrence(s) are still pending. Resolve or "
                "ignore every translation issue first."
            ),
        )

    mode = (
        "create_reprocess_run"
        if persist_step
        else "merge_existing_csv"
    )

    background_tasks.add_task(
        run_translation_reconciliation_background,
        source_run_id=run.id,
        source_fetch_step_id=fetch_step.id,
        site_key=site.key,
        mode=mode,
    )

    return ReconcileTranslationsResponse(
        source_run_id=run.id,
        source_fetch_step_id=fetch_step.id,
        site=site.key,
        mode=mode,
        resolved_occurrence_count=resolved_occurrence_count,
        ignored_occurrence_count=ignored_occurrence_count,
        status="queued",
    )

@router.get(
    "/runs/{run_id}",
    response_model=ScrapeRunRead,
)
async def get_scrape_run(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ScrapeRun, ScrapeSite)
        .join(
            ScrapeSite,
            ScrapeSite.id == ScrapeRun.site_id,
        )
        .where(ScrapeRun.id == run_id)
    )
    row = result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Scrape run not found",
        )

    run, site = row

    return to_scrape_run_read(
        run=run,
        site=site,
    )

@router.get(
    "/runs",
    response_model=list[ScrapeRunRead],
)
async def list_scrape_runs(
    site_key: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    statement = (
        select(ScrapeRun, ScrapeSite)
        .join(
            ScrapeSite,
            ScrapeSite.id == ScrapeRun.site_id,
        )
        .order_by(ScrapeRun.created_at.desc())
        .limit(limit)
    )

    if site_key:
        statement = statement.where(
            ScrapeSite.key == site_key
        )

    result = await session.execute(statement)

    return [
        to_scrape_run_read(run=run, site=site)
        for run, site in result.all()
    ]

@router.get("/runs/{run_id}/logs", response_model=list[ScrapeLogRead])
async def list_scrape_logs(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    run = await session.get(ScrapeRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Scrape run not found")

    result = await session.execute(
        select(ScrapeLog)
        .where(ScrapeLog.run_id == run_id)
        .order_by(ScrapeLog.id.asc())
    )
    logs = result.scalars().all()

    return [
        ScrapeLogRead(
            id=log.id,
            run_id=log.run_id,
            step_run_id=log.step_run_id,
            timestamp=log.timestamp,
            level=log.level,
            message=log.message,
        )
        for log in logs
    ]

@router.get(
    "/runs/{run_id}/steps",
    response_model=list[ScrapeStepRunRead],
)
async def list_scrape_steps(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    run = await session.get(ScrapeRun, run_id)

    if not run:
        raise HTTPException(
            status_code=404,
            detail="Scrape run not found",
        )

    result = await session.execute(
        select(ScrapeStepRun)
        .where(ScrapeStepRun.run_id == run_id)
        .order_by(
            ScrapeStepRun.created_at.asc(),
            ScrapeStepRun.id.asc(),
        )
    )
    steps = result.scalars().all()

    return [
        ScrapeStepRunRead(
            id=step.id,
            run_id=step.run_id,
            step_key=step.step_key,
            status=step.status,
            started_at=step.started_at,
            finished_at=step.finished_at,
            duration_seconds=step.duration_seconds,
            fetched_count=step.fetched_count,
            changed_count=step.changed_count,
            retries=step.retries,
            input_blob_path=step.input_blob_path,
            output_blob_path=step.output_blob_path,
            error_message=step.error_message,
        )
        for step in steps
    ]