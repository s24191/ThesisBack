from datetime import datetime

from sqlmodel import select

from shared.database import async_session_maker
from shared.models.scraping import ScrapeRun
from scripts.run_list_step import run_list_step, FetchFn


async def run_list_background(
    run_id: int,
    site_key: str,
    site_name: str,
    site_base_url: str,
    fetch_links: FetchFn,
) -> None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(ScrapeRun).where(ScrapeRun.id == run_id)
        )
        run = result.scalar_one_or_none()

        if not run:
            return

        run.status = "running"
        run.started_at = datetime.utcnow()
        await session.flush()

        try:
            links, blob_path = await run_list_step(
                session=session,
                run=run,
                site_key=site_key,
                site_name=site_name,
                site_base_url=site_base_url,
                fetch_links=fetch_links,
            )


        except Exception:
            return