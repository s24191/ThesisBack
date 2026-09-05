import asyncio
import os
from datetime import datetime
from typing import Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from shared.storage.azure_blob import upload_text_blob
from shared.models.scraping import (
    ScrapeLog,
    ScrapeRun,
    ScrapeStepRun,
)


AZURE_LINKS_CONTAINER = os.getenv(
    "AZURE_STORAGE_LINKS_CONTAINER",
    "wine-links",
)

FetchFn = Callable[[], list[str]]


async def run_list_step(
    session: AsyncSession,
    run: ScrapeRun,
    site_key: str,
    site_name: str,
    fetch_links: FetchFn,
) -> str:
    started_at = datetime.utcnow()

    step = ScrapeStepRun(
        run_id=run.id,
        step_key="list",
        status="running",
        started_at=started_at,
    )
    session.add(step)
    await session.flush()

    try:
        raw_links = await asyncio.to_thread(fetch_links)

        links = list(
            dict.fromkeys(
                link.strip()
                for link in raw_links
                if link.strip()
            )
        )

        if not links:
            raise ValueError(
                "List step returned zero product links"
            )

        content = "\n".join(links)

        blob_name = (
            f"{site_key}/"
            f"product_links_{run.run_key}.txt"
        )

        blob_path = await asyncio.to_thread(
            upload_text_blob,
            container_name=AZURE_LINKS_CONTAINER,
            blob_name=blob_name,
            content=content,
        )

        now = datetime.utcnow()

        step.fetched_count = len(links)
        step.changed_count = 0
        step.status = "succeeded"
        step.finished_at = now
        step.duration_seconds = (
            now - started_at
        ).total_seconds()

        step.output_blob_path = blob_path

        step.error_message = None

        run.status = "running"

        session.add(
            ScrapeLog(
                run_id=run.id,
                step_run_id=step.id,
                timestamp=now,
                level="info",
                message=(
                    f"{site_name} list step succeeded: "
                    f"{len(links)} unique links stored in "
                    f"{blob_path}"
                ),
            )
        )

        await session.commit()

        return blob_path

    except Exception as exc:
        now = datetime.utcnow()

        step.status = "failed"
        step.finished_at = now
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
                    f"{site_name} list step failed: {exc}"
                ),
            )
        )

        await session.commit()
        raise