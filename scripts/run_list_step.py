from datetime import datetime
from typing import Callable, List, Tuple

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.models.scraping import ScrapeSite, ScrapeRun, ScrapeStepRun, ScrapeLog
from scripts.azure_blob import upload_text_blob
import os

AZURE_LINKS_CONTAINER = os.getenv("AZURE_STORAGE_LINKS_CONTAINER", "wine-links")

FetchFn = Callable[[], List[str]]


async def run_list_step(
    session: AsyncSession,
    run: ScrapeRun,
    site_key: str,
    site_name: str,
    site_base_url: str,
    fetch_links: FetchFn,
) -> Tuple[List[str], str]:

    result = await session.execute(
        select(ScrapeSite).where(ScrapeSite.key == site_key)
    )
    site = result.scalar_one_or_none()
    if not site:
        site = ScrapeSite(
            key=site_key,
            name=site_name,
            base_url=site_base_url,
        )
        session.add(site)
        await session.flush()

    run.site_id = site.id

    step = ScrapeStepRun(
        run_id=run.id,
        step_key="list",
        status="running",
        started_at=datetime.utcnow(),
    )
    session.add(step)
    await session.flush()

    try:
        links = fetch_links()

        content = "\n".join(links)
        blob_name = f"{site_key}/product_links_{run.run_key}.txt"
        blob_path = upload_text_blob(
            container_name=AZURE_LINKS_CONTAINER,
            blob_name=blob_name,
            content=content,
        )

        now = datetime.utcnow()
        step.fetched_count = len(links)
        step.status = "succeeded"
        step.finished_at = now
        step.duration_seconds = (now - step.started_at).total_seconds()
        step.error_message = None
        step.links_blob_path = blob_path

        run.total_wines_fetched += len(links)
        run.status = "succeeded"
        run.finished_at = now
        run.duration_seconds = (now - run.started_at).total_seconds()
        run.error_message = None

        session.add(
            ScrapeLog(
                run_id=run.id,
                step_run_id=step.id,
                level="info",
                message=(
                    f"{site_name} list step succeeded: {len(links)} links, "
                    f"stored in blob {blob_path}"
                ),
            )
        )

        await session.commit()
        return links, blob_path

    except Exception as exc:
        now = datetime.utcnow()
        step.status = "failed"
        step.finished_at = now
        step.duration_seconds = (now - step.started_at).total_seconds()
        step.error_message = str(exc)

        run.status = "failed"
        run.finished_at = now
        run.duration_seconds = (now - run.started_at).total_seconds()
        run.error_message = str(exc)

        session.add(
            ScrapeLog(
                run_id=run.id,
                step_run_id=step.id,
                level="error",
                message=f"{site_name} list step failed: {exc}",
            )
        )

        await session.commit()
        raise