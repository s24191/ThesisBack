import asyncio
import csv
import os
from datetime import datetime
from functools import partial
from io import StringIO
from typing import Literal
from uuid import uuid4

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.storage.azure_blob import (
    download_text_blob,
    split_blob_path,
    upload_text_blob,
)
from features.collection.workflow.steps.fetch_step import (
    FetchProductDetailsFn,
    create_products_csv,
    fetch_all_product_details,
)
from shared.translations.mapping_loader import (
    load_active_translation_mappings,
)
from shared.models.scraping import (
    ScrapeLog,
    ScrapeRun,
    ScrapeStepRun,

)
from shared.models.translations import TranslationReviewOccurrence


AZURE_DETAILS_CONTAINER = os.getenv(
    "AZURE_STORAGE_DETAILS_CONTAINER",
    "wine-details",
)

AZURE_LINKS_CONTAINER = os.getenv(
    "AZURE_STORAGE_LINKS_CONTAINER",
    "wine-links",
)


def generate_reprocess_run_key(
    site_key: str,
) -> str:
    timestamp = datetime.utcnow().strftime(
        "%Y%m%d-%H%M%S"
    )
    suffix = uuid4().hex[:8]

    return (
        f"{site_key}-translation-reprocess-"
        f"{timestamp}-{suffix}"
    )


def parse_products_csv(
    csv_content: str,
) -> list[dict[str, object]]:
    reader = csv.DictReader(StringIO(csv_content))
    products: list[dict[str, object]] = []

    for row in reader:
        grapes_value = row.get("grapes") or ""

        row["grapes"] = [
            grape.strip()
            for grape in grapes_value.split(",")
            if grape.strip()
        ]

        products.append(row)

    return products


def get_failure_message(
    failure: dict[str, object],
) -> str:
    error_type = failure.get(
        "error_type",
        "unknown_fetch_error",
    )
    error = failure.get(
        "error",
        "Unknown product fetch error",
    )

    return f"{error_type}: {error}"


async def create_reconcile_step(
    session: AsyncSession,
    *,
    source_run: ScrapeRun,
    source_fetch_step: ScrapeStepRun,
) -> ScrapeStepRun:
    step = ScrapeStepRun(
        run_id=source_run.id,
        step_key="reconcile",
        status="running",
        started_at=datetime.utcnow(),
        input_blob_path=source_fetch_step.output_blob_path,
    )
    session.add(step)

    await session.flush()

    if step.id is None:
        raise ValueError(
            "Could not create reconciliation step"
        )

    await session.commit()
    await session.refresh(step)

    return step


async def create_reprocess_run_and_step(
    session: AsyncSession,
    *,
    source_run: ScrapeRun,
    site_key: str,
    source_urls: list[str],
) -> tuple[ScrapeRun, ScrapeStepRun]:
    now = datetime.utcnow()

    run = ScrapeRun(
        site_id=source_run.site_id,
        run_key=generate_reprocess_run_key(site_key),
        triggered_by=(
            f"translation-reprocess:source-run-"
            f"{source_run.id}"
        ),
        status="running",
        started_at=now,
    )
    session.add(run)

    await session.flush()

    if run.id is None:
        raise ValueError(
            "Could not create translation reprocess run"
        )

    links_blob_name = (
        f"{site_key}/translation_reprocess_links_"
        f"{run.run_key}.txt"
    )

    links_content = "\n".join(source_urls)

    links_blob_path = await asyncio.to_thread(
        upload_text_blob,
        container_name=AZURE_LINKS_CONTAINER,
        blob_name=links_blob_name,
        content=links_content,
    )

    step = ScrapeStepRun(
        run_id=run.id,
        step_key="fetch",
        status="running",
        started_at=now,
        input_blob_path=links_blob_path,
    )
    session.add(step)

    await session.flush()

    if step.id is None:
        raise ValueError(
            "Could not create reprocess fetch step"
        )


    await session.commit()
    await session.refresh(run)
    await session.refresh(step)

    return run, step


async def mark_occurrences_reprocessed(
    *,
    occurrences: list[TranslationReviewOccurrence],
    active_step_id: int,
    successful_urls: set[str],
    failures_by_url: dict[str, dict[str, object]],
) -> None:
    now = datetime.utcnow()

    for occurrence in occurrences:
        if occurrence.source_url in successful_urls:
            occurrence.status = "reprocessed"
            occurrence.reprocessed_at = now
            occurrence.reprocessed_step_run_id = active_step_id
            occurrence.reprocess_error = None
            continue

        failure = failures_by_url.get(
            occurrence.source_url,
        )

        occurrence.status = "reprocess_failed"
        occurrence.reprocessed_at = now
        occurrence.reprocessed_step_run_id = active_step_id
        occurrence.reprocess_error = (
            get_failure_message(failure)
            if failure
            else "No product result returned for this URL"
        )


async def run_translation_reconciliation(
    session: AsyncSession,
    source_run: ScrapeRun,
    source_fetch_step: ScrapeStepRun,
    site_key: str,
    site_name: str,
    fetch_product_details: FetchProductDetailsFn,
    mode: Literal[
        "merge_existing_csv",
        "create_reprocess_run",
    ],
    max_workers: int = 4,
) -> None:
    if mode not in {
        "merge_existing_csv",
        "create_reprocess_run",
    }:
        raise ValueError(
            f"Unsupported reconciliation mode: {mode}"
        )

    if not source_fetch_step.output_blob_path:
        raise ValueError(
            "Source fetch step has no output CSV Blob path"
        )

    occurrence_result = await session.execute(
        select(TranslationReviewOccurrence)
        .where(
            TranslationReviewOccurrence.step_run_id
            == source_fetch_step.id,
            TranslationReviewOccurrence.status
            == "resolved",
        )
        .order_by(TranslationReviewOccurrence.id.asc())
    )
    occurrences = occurrence_result.scalars().all()

    if not occurrences:
        return

    source_urls = list(
        dict.fromkeys(
            occurrence.source_url
            for occurrence in occurrences
        )
    )

    for occurrence in occurrences:
        occurrence.status = "reprocessing"
        occurrence.reprocess_error = None

    await session.commit()

    active_run = source_run
    active_step: ScrapeStepRun | None = None

    try:
        if mode == "merge_existing_csv":
            active_step = await create_reconcile_step(
                session,
                source_run=source_run,
                source_fetch_step=source_fetch_step,
            )

        else:
            active_run, active_step = (
                await create_reprocess_run_and_step(
                    session,
                    source_run=source_run,
                    site_key=site_key,
                    source_urls=source_urls,
                )
            )

            session.add(
                ScrapeLog(
                    run_id=source_run.id,
                    step_run_id=source_fetch_step.id,
                    timestamp=datetime.utcnow(),
                    level="info",
                    message=(
                        "Translation reconciliation started "
                        f"reprocess run {active_run.run_key} "
                        f"(run_id={active_run.id})."
                    ),
                )
            )

            await session.commit()

        if active_step.id is None:
            raise ValueError(
                "Active reconciliation step has no ID"
            )

        translation_mappings = (
            await load_active_translation_mappings(session)
        )

        fetcher = partial(
            fetch_product_details,
            translation_mappings=translation_mappings,
        )

        products, failures = await asyncio.to_thread(
            fetch_all_product_details,
            source_urls,
            fetcher,
            max_workers,
        )

        successful_urls = {
            str(product["url"])
            for product in products
            if product.get("url")
        }

        failures_by_url = {
            str(failure["url"]): failure
            for failure in failures
            if failure.get("url")
        }

        await mark_occurrences_reprocessed(
            occurrences=occurrences,
            active_step_id=active_step.id,
            successful_urls=successful_urls,
            failures_by_url=failures_by_url,
        )

        if mode == "merge_existing_csv":
            existing_csv_content = await asyncio.to_thread(
                download_text_blob,
                blob_path=source_fetch_step.output_blob_path,
            )

            existing_products = parse_products_csv(
                existing_csv_content,
            )

            products_by_url = {
                str(product["url"]): product
                for product in existing_products
                if product.get("url")
            }

            for product in products:
                product_url = str(product["url"])
                products_by_url[product_url] = product

            merged_csv_content = create_products_csv(
                list(products_by_url.values())
            )

            existing_container_name, existing_blob_name = (
                split_blob_path(
                    source_fetch_step.output_blob_path
                )
            )

            output_blob_path = await asyncio.to_thread(
                upload_text_blob,
                container_name=existing_container_name,
                blob_name=existing_blob_name,
                content=merged_csv_content,
            )

        else:
            details_blob_name = (
                f"{site_key}/"
                f"product_details_{active_run.run_key}.csv"
            )

            csv_content = create_products_csv(products)

            output_blob_path = await asyncio.to_thread(
                upload_text_blob,
                container_name=AZURE_DETAILS_CONTAINER,
                blob_name=details_blob_name,
                content=csv_content,
            )

        now = datetime.utcnow()

        active_step.fetched_count = len(source_urls)
        active_step.changed_count = len(products)
        active_step.status = (
            "partial"
            if failures
            else "succeeded"
        )
        active_step.finished_at = now
        active_step.last_heartbeat_at = now
        active_step.duration_seconds = (
            now - active_step.started_at
        ).total_seconds()
        active_step.output_blob_path = output_blob_path
        active_step.error_message = None

        if mode == "merge_existing_csv":
            remaining_failure_count = len(failures)

            source_fetch_step.status = (
                "partial"
                if remaining_failure_count > 0
                else "succeeded"
            )

            source_fetch_step.output_blob_path = (
                output_blob_path
            )

            session.add(
                ScrapeLog(
                    run_id=source_run.id,
                    step_run_id=source_fetch_step.id,
                    timestamp=now,
                    level=(
                        "warning"
                        if failures
                        else "info"
                    ),
                    message=(
                        f"{site_name} translation reconciliation "
                        f"{active_step.status}: "
                        f"{len(products)} product(s) merged into "
                        f"{output_blob_path}; "
                        f"{len(failures)} reprocess issue(s)."
                    ),
                )
            )

        else:
            active_run.status = "running"

            session.add(
                ScrapeLog(
                    run_id=active_run.id,
                    step_run_id=active_step.id,
                    timestamp=now,
                    level=(
                        "warning"
                        if failures
                        else "info"
                    ),
                    message=(
                        f"{site_name} translation reprocess fetch "
                        f"{active_step.status}: "
                        f"{len(products)} product(s) written to "
                        f"{output_blob_path}; "
                        f"{len(failures)} reprocess issue(s)."
                    ),
                )
            )

        await session.commit()

    except Exception as exc:
        now = datetime.utcnow()

        for occurrence in occurrences:
            if occurrence.status == "reprocessing":
                occurrence.status = "reprocess_failed"
                occurrence.reprocessed_at = now
                occurrence.reprocess_error = str(exc)

                if active_step and active_step.id:
                    occurrence.reprocessed_step_run_id = (
                        active_step.id
                    )

        if active_step:
            active_step.status = "failed"
            active_step.finished_at = now
            active_step.last_heartbeat_at = now
            active_step.duration_seconds = (
                now - active_step.started_at
            ).total_seconds()
            active_step.error_message = str(exc)

        if mode == "merge_existing_csv":
            source_fetch_step.status = "partial"

        else:
            active_run.status = "failed"
            active_run.finished_at = now

        log_run_id = active_run.id or source_run.id
        log_step_run_id = (
            active_step.id
            if active_step and active_step.id
            else source_fetch_step.id
        )

        session.add(
            ScrapeLog(
                run_id=log_run_id,
                step_run_id=log_step_run_id,
                timestamp=now,
                level="error",
                message=(
                    f"{site_name} translation reconciliation "
                    f"failed: {exc}"
                ),
            )
        )

        await session.commit()

        raise