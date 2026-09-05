import logging

from features.collection.workflow.steps.translation_reconciliation import (
    run_translation_reconciliation,
)
from features.collection.retailers.sites import SITE_CONFIG
from shared.database import async_session_maker
from shared.models.scraping import (
    ScrapeRun,
    ScrapeSite,
    ScrapeStepRun,
)


logger = logging.getLogger(__name__)


async def run_translation_reconciliation_background(
    source_run_id: int,
    source_fetch_step_id: int,
    site_key: str,
    mode: str,
) -> None:
    allowed_modes = {
        "merge_existing_csv",
        "create_reprocess_run",
    }

    if mode not in allowed_modes:
        logger.error(
            "Invalid translation reconciliation mode=%s "
            "for source_run_id=%s",
            mode,
            source_run_id,
        )
        return

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
        source_run = await session.get(
            ScrapeRun,
            source_run_id,
        )

        if not source_run:
            logger.error(
                "Source scrape run not found: run_id=%s",
                source_run_id,
            )
            return

        site = await session.get(
            ScrapeSite,
            source_run.site_id,
        )

        if not site:
            logger.error(
                "Scrape site not found for source run: "
                "run_id=%s, site_id=%s",
                source_run.id,
                source_run.site_id,
            )
            return

        if site.key != site_key:
            logger.error(
                "Site key mismatch for translation "
                "reconciliation: source_run_id=%s, "
                "requested_site_key=%s, actual_site_key=%s",
                source_run.id,
                site_key,
                site.key,
            )
            return

        source_fetch_step = await session.get(
            ScrapeStepRun,
            source_fetch_step_id,
        )

        if not source_fetch_step:
            logger.error(
                "Source fetch step not found: "
                "step_id=%s",
                source_fetch_step_id,
            )
            return

        if source_fetch_step.run_id != source_run.id:
            logger.error(
                "Source fetch step does not belong to "
                "source run: step_id=%s, step_run_id=%s, "
                "source_run_id=%s",
                source_fetch_step.id,
                source_fetch_step.run_id,
                source_run.id,
            )
            return

        if source_fetch_step.step_key != "fetch":
            logger.error(
                "Source step is not a fetch step: "
                "step_id=%s, step_key=%s",
                source_fetch_step.id,
                source_fetch_step.step_key,
            )
            return

        try:
            await run_translation_reconciliation(
                session=session,
                source_run=source_run,
                source_fetch_step=source_fetch_step,
                site_key=site_key,
                site_name=site_meta["name"],
                fetch_product_details=fetch_product_details,
                mode=mode,
            )

        except Exception:
            logger.exception(
                "Translation reconciliation failed: "
                "source_run_id=%s, source_fetch_step_id=%s, "
                "site_key=%s, mode=%s",
                source_run_id,
                source_fetch_step_id,
                site_key,
                mode,
            )