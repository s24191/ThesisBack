import logging

from features.collection.workflow.steps.persist_step import run_persist_step
from features.collection.retailers.sites import SITE_CONFIG
from shared.database import async_session_maker
from shared.models.scraping import ScrapeRun


logger = logging.getLogger(__name__)


async def run_persist_background(
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

    async with async_session_maker() as session:
        run = await session.get(ScrapeRun, run_id)

        if not run:
            logger.error(
                "Scrape run not found: run_id=%s",
                run_id,
            )
            return

        if run.status in {
            "completed",
            "failed",
            "cancelled",
        }:
            logger.warning(
                "Persist background task skipped: run_id=%s "
                "has terminal status=%s",
                run.id,
                run.status,
            )
            return

        try:
            await run_persist_step(
                session=session,
                run=run,
                site_name=site_meta["name"],
                site_base_url=site_meta["base_url"],
            )

        except Exception:
            logger.exception(
                "Persist step background task failed: "
                "run_id=%s, site_key=%s",
                run_id,
                site_key,
            )