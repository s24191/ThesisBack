import logging

from sqlmodel import select

from scripts.run_fetch_step import run_fetch_step
from scripts.sites import SITE_CONFIG
from shared.database import async_session_maker
from shared.models.scraping import (
    ScrapeRun,
    ScrapeStepRun,
)


logger = logging.getLogger(__name__)


async def run_fetch_background(
    run_id: int,
    site_key: str,
) -> None:
    site_meta = SITE_CONFIG.get(site_key)

    if not site_meta:
        logger.error(
            "No site configuration found for site_key=%s",
            site_key,
        )
        return

    fetch_product_details = site_meta.get(
        "fetch_product_details_fn"
    )

    if not fetch_product_details:
        logger.error(
            "No product-details fetch function configured "
            "for site_key=%s",
            site_key,
        )
        return

    async with async_session_maker() as session:
        run = await session.get(ScrapeRun, run_id)

        if not run:
            logger.error(
                "Scrape run not found: run_id=%s",
                run_id,
            )
            return

        if run.status in {"completed", "failed", "cancelled"}:
            logger.warning(
                "Fetch background task skipped: run_id=%s "
                "has terminal status=%s",
                run.id,
                run.status,
            )
            return

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
            logger.warning(
                "Fetch background task skipped: no list step "
                "found for run_id=%s",
                run.id,
            )
            return

        if list_step.status != "succeeded":
            logger.warning(
                "Fetch background task skipped: list step for "
                "run_id=%s has status=%s",
                run.id,
                list_step.status,
            )
            return

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
            logger.warning(
                "Fetch background task skipped: fetch step "
                "already exists for run_id=%s",
                run.id,
            )
            return

        try:
            await run_fetch_step(
                session=session,
                run=run,
                site_key=site_key,
                site_name=site_meta["name"],
                fetch_product_details=fetch_product_details,
            )

        except Exception:
            logger.exception(
                "Fetch step background task failed: "
                "run_id=%s, site_key=%s",
                run_id,
                site_key,
            )