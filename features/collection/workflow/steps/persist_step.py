import asyncio
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.storage.azure_blob import download_text_blob
from shared.models.scraping import (
    ScrapeLog,
    ScrapeRun,
    ScrapeStepRun,
)
from shared.seed.wine_seed import (
    SeedResult,
    seed_wines_from_csv_content,
)

async def run_persist_step(
    session: AsyncSession,
    run: ScrapeRun,
    site_name: str,
    site_base_url: str,
) -> SeedResult:
    fetch_step_result = await session.execute(
        select(ScrapeStepRun)
        .where(
            ScrapeStepRun.run_id == run.id,
            ScrapeStepRun.step_key == "fetch",
            ScrapeStepRun.status.in_([
                "succeeded",
                "partial",
            ]),
        )
        .order_by(ScrapeStepRun.id.desc())
    )
    fetch_step = fetch_step_result.scalars().first()

    if not fetch_step:
        raise ValueError(
            "Cannot start persist step: no succeeded or "
            "partial fetch step exists for this run"
        )

    if not fetch_step.output_blob_path:
        raise ValueError(
            "Cannot start persist step: fetch step has "
            "no output Blob path"
        )

    existing_persist_result = await session.execute(
        select(ScrapeStepRun)
        .where(
            ScrapeStepRun.run_id == run.id,
            ScrapeStepRun.step_key == "persist",
        )
        .order_by(ScrapeStepRun.id.desc())
    )
    existing_persist_step = (
        existing_persist_result.scalars().first()
    )

    if existing_persist_step:
        raise ValueError(
            "Cannot start persist step: this run already "
            "has a persist step"
        )

    started_at = datetime.utcnow()

    step = ScrapeStepRun(
        run_id=run.id,
        step_key="persist",
        status="running",
        started_at=started_at,
        input_blob_path=fetch_step.output_blob_path,
    )
    session.add(step)

    await session.flush()
    await session.commit()
    await session.refresh(step)

    try:
        csv_content = await asyncio.to_thread(
            download_text_blob,
            blob_path=fetch_step.output_blob_path,
        )

        if not csv_content.strip():
            raise ValueError(
                "Persist step input CSV Blob is empty"
            )

        seed_result = await seed_wines_from_csv_content(
            session=session,
            csv_content=csv_content,
            retailer_name=site_name,
            retailer_base_url=site_base_url,
        )

        now = datetime.utcnow()

        step.fetched_count = seed_result.rows_read

        step.changed_count = (
            seed_result.offers_created
            + seed_result.offers_updated
        )

        step.status = (
            "partial"
            if seed_result.rows_skipped > 0
            else "succeeded"
        )
        step.finished_at = now
        step.last_heartbeat_at = now
        step.duration_seconds = (
            now - started_at
        ).total_seconds()
        step.error_message = None

        run.status = "completed"
        run.finished_at = now

        session.add(
            ScrapeLog(
                run_id=run.id,
                step_run_id=step.id,
                timestamp=now,
                level=(
                    "warning"
                    if step.status == "partial"
                    else "info"
                ),
                message=(
                    f"{site_name} persist step "
                    f"{step.status}: "
                    f"rows={seed_result.rows_read}, "
                    f"skipped={seed_result.rows_skipped}, "
                    f"wines_created={seed_result.wines_created}, "
                    f"wines_updated={seed_result.wines_updated}, "
                    f"offers_created={seed_result.offers_created}, "
                    f"offers_updated={seed_result.offers_updated}."
                ),
            )
        )

        await session.commit()

        return seed_result

    except Exception as exc:
        now = datetime.utcnow()

        step.status = "failed"
        step.finished_at = now
        step.last_heartbeat_at = now
        step.duration_seconds = (
            now - started_at
        ).total_seconds()
        step.error_message = str(exc)

        run.status = "failed"
        run.finished_at = now

        session.add(
            ScrapeLog(
                run_id=run.id,
                step_run_id=step.id,
                timestamp=now,
                level="error",
                message=(
                    f"{site_name} persist step failed: {exc}"
                ),
            )
        )

        await session.commit()

        raise