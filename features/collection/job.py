import asyncio
import logging
import sys
from datetime import datetime
from uuid import uuid4

from sqlmodel import select

from features.collection.retailers.sites import SITE_CONFIG
from features.collection.workflow.background_jobs.background_fetch import run_fetch_background
from features.collection.workflow.background_jobs.background_list import run_list_background
from features.collection.workflow.background_jobs.background_persist import run_persist_background
from shared.database import async_session_maker
from shared.models.scraping import (
    ScrapeLog,
    ScrapeRun,
    ScrapeSite,
    ScrapeStepRun,
)


logger = logging.getLogger(__name__)


def generate_run_key(site_key: str) -> str:
    timestamp = datetime.utcnow().strftime(
        "%Y%m%d-%H%M%S"
    )
    suffix = uuid4().hex[:8]

    return f"{site_key}-{timestamp}-{suffix}"


async def get_or_create_site(
    site_key: str,
) -> ScrapeSite:
    site_meta = SITE_CONFIG[site_key]

    async with async_session_maker() as session:
        result = await session.execute(
            select(ScrapeSite).where(
                ScrapeSite.key == site_key
            )
        )
        site = result.scalar_one_or_none()

        if site is None:
            site = ScrapeSite(
                key=site_key,
                name=str(site_meta["name"]),
                base_url=str(site_meta["base_url"]),
            )
            session.add(site)
            await session.commit()
            await session.refresh(site)

        return site


async def create_run(
    site_key: str,
    site: ScrapeSite,
) -> ScrapeRun:
    async with async_session_maker() as session:
        run = ScrapeRun(
            site_id=site.id,
            run_key=generate_run_key(site_key),
            triggered_by="scheduled-container-app-job",
            status="queued",
        )

        session.add(run)
        await session.commit()
        await session.refresh(run)

        return run


async def get_latest_step(
    run_id: int,
    step_key: str,
) -> ScrapeStepRun | None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(ScrapeStepRun)
            .where(
                ScrapeStepRun.run_id == run_id,
                ScrapeStepRun.step_key == step_key,
            )
            .order_by(ScrapeStepRun.id.desc())
        )

        return result.scalars().first()


async def get_run_status(
    run_id: int,
) -> str | None:
    async with async_session_maker() as session:
        run = await session.get(ScrapeRun, run_id)

        if run is None:
            return None

        return run.status


async def write_job_log(
    run_id: int,
    *,
    level: str,
    message: str,
) -> None:
    async with async_session_maker() as session:
        session.add(
            ScrapeLog(
                run_id=run_id,
                timestamp=datetime.utcnow(),
                level=level,
                message=message,
            )
        )
        await session.commit()


async def mark_run_failed(
    run_id: int,
    error_message: str,
) -> None:
    async with async_session_maker() as session:
        run = await session.get(ScrapeRun, run_id)

        if run is None:
            return

        run.status = "failed"
        run.finished_at = datetime.utcnow()

        session.add(
            ScrapeLog(
                run_id=run.id,
                timestamp=datetime.utcnow(),
                level="error",
                message=error_message,
            )
        )

        await session.commit()


async def run_list_step(
    run_id: int,
    site_key: str,
) -> None:

    await run_list_background(
        run_id,
        site_key,
    )

    list_step = await get_latest_step(
        run_id,
        "list",
    )

    if list_step is None:
        raise RuntimeError(
            f"{site_key}: list step was not created"
        )

    if list_step.status != "succeeded":
        raise RuntimeError(
            f"{site_key}: list step failed with status "
            f"'{list_step.status}': "
            f"{list_step.error_message or 'no error message'}"
        )


async def run_fetch_step(
    run_id: int,
    site_key: str,
) -> None:

    await run_fetch_background(
        run_id,
        site_key,
    )

    fetch_step = await get_latest_step(
        run_id,
        "fetch",
    )

    if fetch_step is None:
        raise RuntimeError(
            f"{site_key}: fetch step was not created"
        )

    if fetch_step.status not in {
        "succeeded",
        "partial",
    }:
        raise RuntimeError(
            f"{site_key}: fetch step failed with status "
            f"'{fetch_step.status}': "
            f"{fetch_step.error_message or 'no error message'}"
        )


async def run_persist_step(
    run_id: int,
    site_key: str,
) -> None:

    await run_persist_background(
        run_id,
        site_key,
    )

    persist_step = await get_latest_step(
        run_id,
        "persist",
    )

    if persist_step is None:
        raise RuntimeError(
            f"{site_key}: persist step was not created"
        )

    if persist_step.status != "succeeded":
        raise RuntimeError(
            f"{site_key}: persist step failed with status "
            f"'{persist_step.status}': "
            f"{persist_step.error_message or 'no error message'}"
        )


async def run_retailer_pipeline(
    site_key: str,
) -> bool:

    site_meta = SITE_CONFIG[site_key]
    site_name = str(site_meta["name"])

    site = await get_or_create_site(site_key)
    run = await create_run(site_key, site)

    logger.info(
        "Starting retailer pipeline: site=%s run_id=%s",
        site_key,
        run.id,
    )

    await write_job_log(
        run.id,
        level="info",
        message=(
            f"Scheduled job started retailer pipeline "
            f"for {site_name}."
        ),
    )

    try:
        await run_list_step(
            run.id,
            site_key,
        )

        await run_fetch_step(
            run.id,
            site_key,
        )

        fetch_step = await get_latest_step(
            run.id,
            "fetch",
        )

        if fetch_step is not None and fetch_step.status == "partial":
            await write_job_log(
                run.id,
                level="warning",
                message=(
                    f"{site_name}: fetch completed partially. "
                    "Persist step skipped; review translations "
                    "before reconciliation."
                ),
            )

            logger.warning(
                "Retailer fetch is partial; persistence skipped: "
                "site=%s run_id=%s",
                site_key,
                run.id,
            )

            return False

        await run_persist_step(
            run.id,
            site_key,
        )

        final_status = await get_run_status(run.id)

        if final_status != "completed":
            raise RuntimeError(
                f"{site_key}: pipeline ended with run status "
                f"'{final_status}'"
            )

        await write_job_log(
            run.id,
            level="info",
            message=(
                f"Scheduled job completed retailer pipeline "
                f"for {site_name}."
            ),
        )

        logger.info(
            "Retailer pipeline succeeded: site=%s run_id=%s",
            site_key,
            run.id,
        )

        return True

    except Exception as exc:
        error_message = (
            f"Scheduled retailer pipeline failed for "
            f"{site_name}: {exc}"
        )

        logger.exception(
            "Retailer pipeline failed: site=%s run_id=%s",
            site_key,
            run.id,
        )

        await mark_run_failed(
            run.id,
            error_message,
        )

        return False


async def main() -> int:

    failed_sites: list[str] = []

    for site_key in SITE_CONFIG:
        try:
            succeeded = await run_retailer_pipeline(
                site_key
            )

            if not succeeded:
                failed_sites.append(site_key)

        except Exception:

            failed_sites.append(site_key)

            logger.exception(
                "Unexpected orchestration failure for "
                "site=%s. Continuing with the next retailer.",
                site_key,
            )

    if failed_sites:
        logger.error(
            "Scraping job finished with retailer failures: %s",
            ", ".join(failed_sites),
        )


        return 1

    logger.info(
        "Scraping job completed successfully for all retailers."
    )

    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s %(message)s"
        ),
    )

    sys.exit(
        asyncio.run(main())
    )