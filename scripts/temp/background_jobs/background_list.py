import logging
from datetime import datetime

from scripts.run_list_step import run_list_step
from scripts.sites import SITE_CONFIG
from shared.database import async_session_maker
from shared.models.scraping import ScrapeRun


logger = logging.getLogger(__name__)


async def run_list_background(
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

        if run.status != "queued":
            logger.warning(
                "List background task skipped: "
                "run_id=%s has status=%s",
                run.id,
                run.status,
            )
            return

        run.status = "running"
        run.started_at = datetime.utcnow()

        await session.commit()

        try:
            await run_list_step(
                session=session,
                run=run,
                site_key=site_key,
                site_name=site_meta["name"],
                fetch_links=site_meta["fetch_fn"],
            )

        except Exception:
            logger.exception(
                "List step background task failed: "
                "run_id=%s, site_key=%s",
                run_id,
                site_key,
            )