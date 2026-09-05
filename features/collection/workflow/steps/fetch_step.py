from functools import partial

import asyncio
import csv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import StringIO
from typing import Any, Callable

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.storage.azure_blob import (
    download_text_blob,
    upload_text_blob,
)
from shared.translations.mapping_loader import load_active_translation_mappings
from shared.models import TranslationReviewItem, TranslationReviewOccurrence
from shared.models.scraping import (
    ScrapeLog,
    ScrapeRun,
    ScrapeStepRun,
)

import threading
import time

from shared.database import async_session_maker


AZURE_DETAILS_CONTAINER = os.getenv(
    "AZURE_STORAGE_DETAILS_CONTAINER",
    "wine-details",
)

FetchProductDetailsFn = Callable[[str], dict[str, Any]]

ProgressCallback = Callable[[int, int], None]


async def persist_fetch_progress(
    step_id: int,
    completed_count: int,
) -> None:
    async with async_session_maker() as progress_session:
        step = await progress_session.get(
            ScrapeStepRun,
            step_id,
        )

        if not step:
            return

        step.fetched_count = max(
            step.fetched_count,
            completed_count,
        )
        step.last_heartbeat_at = datetime.utcnow()

        await progress_session.commit()

class FetchProgressReporter:
    def __init__(
        self,
        step_id: int,
        total_count: int,
        event_loop: asyncio.AbstractEventLoop,
        interval_seconds: int = 15,
    ) -> None:
        self.step_id = step_id
        self.total_count = total_count
        self.event_loop = event_loop
        self.interval_seconds = interval_seconds
        self.last_persisted_at = 0.0
        self.lock = threading.Lock()

    def __call__(
        self,
        completed_count: int,
        total_count: int,
    ) -> None:
        now = time.monotonic()

        with self.lock:
            should_persist = (
                completed_count == total_count
                or now - self.last_persisted_at
                >= self.interval_seconds
            )

            if not should_persist:
                return

            self.last_persisted_at = now

        asyncio.run_coroutine_threadsafe(
            persist_fetch_progress(
                step_id=self.step_id,
                completed_count=completed_count,
            ),
            self.event_loop,
        )

CSV_FIELDS = [
    "name",
    "year",
    "alc_perc",
    "capacity_ml",
    "country",
    "region",
    "wine_type",
    "taste_profile",
    "grapes",
    "price",
    "available",
    "url",
    "image_url",
]


def prepare_csv_row(
    product: dict[str, Any],
) -> dict[str, Any]:
    return {
        **product,
        "grapes": ", ".join(product.get("grapes") or []),
    }


def create_products_csv(
    products: list[dict[str, Any]],
) -> str:
    output = StringIO()

    writer = csv.DictWriter(
        output,
        fieldnames=CSV_FIELDS,
        extrasaction="ignore",
    )
    writer.writeheader()

    writer.writerows(
        prepare_csv_row(product)
        for product in products
    )

    return output.getvalue()


def fetch_all_product_details(
    links: list[str],
    fetch_product_details: FetchProductDetailsFn,
    max_workers: int,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    products: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    with ThreadPoolExecutor(
        max_workers=max_workers,
    ) as executor:
        future_to_url = {
            executor.submit(
                fetch_product_details,
                url,
            ): url
            for url in links
        }

        total_links = len(future_to_url)

        for completed_count, future in enumerate(
                as_completed(future_to_url),
                start=1,
        ):
            url = future_to_url[future]

            if progress_callback:
                progress_callback(
                    completed_count,
                    total_links,
                )

            try:
                result = future.result()
            except Exception as exc:
                failures.append(
                    {
                        "url": url,
                        "final_url": None,
                        "error_type": "unhandled_fetch_error",
                        "error": str(exc),
                    }
                )
                continue

            if not isinstance(result, dict):
                failures.append(
                    {
                        "url": url,
                        "final_url": None,
                        "error_type": "invalid_fetch_result",
                        "error": (
                            "fetch_product_details returned "
                            f"{type(result).__name__}, expected dict"
                        ),
                    }
                )
                continue

            if "error" in result:
                failure = {
                    "url": result.get("url", url),
                    "final_url": result.get("final_url"),
                    "error_type": result.get(
                        "error_type",
                        "unknown_fetch_error",
                    ),
                    "error": result.get(
                        "error",
                        "Unknown product fetch error",
                    ),
                }

                if result.get("error_type") == "untranslated_value":
                    failure["translation_field"] = result.get(
                        "translation_field"
                    )
                    failure["source_value"] = result.get(
                        "source_value"
                    )

                failures.append(failure)
                continue

            products.append(result)

    return products, failures

async def create_translation_review_occurrence(
    session: AsyncSession,
    *,
    step_run_id: int,
    field_name: str,
    source_value: str,
    source_url: str,
) -> None:
    review_item_result = await session.execute(
        select(TranslationReviewItem)
        .where(
            TranslationReviewItem.field_name
            == field_name,
            TranslationReviewItem.source_value
            == source_value,
        )
    )
    review_item = review_item_result.scalar_one_or_none()

    if not review_item:
        review_item = TranslationReviewItem(
            field_name=field_name,
            source_value=source_value,
            status="pending",
        )
        session.add(review_item)

        await session.flush()

    occurrence_result = await session.execute(
        select(TranslationReviewOccurrence)
        .where(
            TranslationReviewOccurrence
            .translation_review_item_id
            == review_item.id,
            TranslationReviewOccurrence.step_run_id
            == step_run_id,
            TranslationReviewOccurrence.source_url
            == source_url,
        )
    )
    existing_occurrence = (
        occurrence_result.scalar_one_or_none()
    )

    if existing_occurrence:
        return

    session.add(
        TranslationReviewOccurrence(
            translation_review_item_id=review_item.id,
            step_run_id=step_run_id,
            source_url=source_url,
        )
    )

async def run_fetch_step(
    session: AsyncSession,
    run: ScrapeRun,
    site_key: str,
    site_name: str,
    fetch_product_details: FetchProductDetailsFn,
    max_workers: int = 4,
) -> str:
    list_step_result = await session.execute(
        select(ScrapeStepRun)
        .where(
            ScrapeStepRun.run_id == run.id,
            ScrapeStepRun.step_key == "list",
            ScrapeStepRun.status == "succeeded",
        )
        .order_by(ScrapeStepRun.id.desc())
    )
    list_step = list_step_result.scalars().first()

    if not list_step:
        raise ValueError(
            "Cannot start fetch step: "
            "no successful list step exists for this run"
        )

    if not list_step.output_blob_path:
        raise ValueError(
            "Cannot start fetch step: "
            "list step has no output Blob path"
        )

    started_at = datetime.utcnow()

    step = ScrapeStepRun(
        run_id=run.id,
        step_key="fetch",
        status="running",
        started_at=started_at,
        input_blob_path=list_step.output_blob_path,
    )
    session.add(step)
    await session.flush()
    await session.commit()
    await session.refresh(step)

    try:

        links_content = await asyncio.to_thread(
            download_text_blob,
            blob_path=list_step.output_blob_path,
        )

        links = list(
            dict.fromkeys(
                line.strip()
                for line in links_content.splitlines()
                if line.strip()
            )
        )

        if not links:
            raise ValueError(
                "Fetch step input Blob contains zero links"
            )

        translation_mappings = (
            await load_active_translation_mappings(session)
        )

        fetch_details_with_mappings = partial(
            fetch_product_details,
            translation_mappings=translation_mappings,
        )

        event_loop = asyncio.get_running_loop()

        progress_reporter = FetchProgressReporter(
            step_id=step.id,
            total_count=len(links),
            event_loop=event_loop,
            interval_seconds=15,
        )
        products, failures = await asyncio.to_thread(
            fetch_all_product_details,
            links,
            fetch_details_with_mappings,
            max_workers,
            progress_reporter,
        )

        csv_content = create_products_csv(products)

        details_blob_name = (
            f"{site_key}/"
            f"product_details_{run.run_key}.csv"
        )

        details_blob_path = await asyncio.to_thread(
            upload_text_blob,
            container_name=AZURE_DETAILS_CONTAINER,
            blob_name=details_blob_name,
            content=csv_content,
        )

        now = datetime.utcnow()

        warning_types = {
            "product_not_found",
        }

        actual_errors = [
            failure
            for failure in failures
            if failure["error_type"] not in warning_types
        ]

        step.fetched_count = len(links)
        step.last_heartbeat_at = now
        step.changed_count = 0
        step.status = (
            "partial"
            if actual_errors
            else "succeeded"
        )
        step.finished_at = now
        step.duration_seconds = (
            now - started_at
        ).total_seconds()
        step.output_blob_path = details_blob_path
        step.error_message = None

        run.status = "running"

        for failure in failures:
            error_type = failure["error_type"]

            if error_type == "untranslated_value":
                translation_field = failure.get(
                    "translation_field"
                )
                source_value = failure.get("source_value")

                if (
                        isinstance(translation_field, str)
                        and translation_field
                        and isinstance(source_value, str)
                        and source_value
                ):
                    await create_translation_review_occurrence(
                        session=session,
                        step_run_id=step.id,
                        field_name=translation_field,
                        source_value=source_value,
                        source_url=failure["url"],
                    )

            level = (
                "warning"
                if error_type in warning_types
                else "error"
            )

            final_url_part = ""

            if failure["final_url"]:
                final_url_part = (
                    f" final_url={failure['final_url']}"
                )

            session.add(
                ScrapeLog(
                    run_id=run.id,
                    step_run_id=step.id,
                    timestamp=now,
                    level=level,
                    message=(
                        f"{site_name} fetch issue: "
                        f"error_type={error_type} "
                        f"url={failure['url']}"
                        f"{final_url_part} "
                        f"error={failure['error']}"
                    ),
                )
            )

        session.add(
            ScrapeLog(
                run_id=run.id,
                step_run_id=step.id,
                timestamp=now,
                level=(
                    "error"
                    if actual_errors
                    else "info"
                ),
                message=(
                    f"{site_name} fetch step "
                    f"{step.status}: "
                    f"{len(products)} products written to "
                    f"{details_blob_path}; "
                    f"{len(failures)} product issues."
                ),
            )
        )

        await session.commit()

        return details_blob_path

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
                    f"{site_name} fetch step failed: {exc}"
                ),
            )
        )

        await session.commit()
        raise