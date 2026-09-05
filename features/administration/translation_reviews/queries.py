from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.models.scraping import (
    ScrapeRun,
    ScrapeSite,
    ScrapeStepRun,
)
from shared.models.translations import (
    TranslationReviewItem,
    TranslationReviewOccurrence,
)

from .schemas import (
    TranslationReviewItemRead,
    TranslationReviewOccurrenceRead,
)


def to_review_item_read(
    item: TranslationReviewItem,
    occurrence_count: int,
) -> TranslationReviewItemRead:
    if item.id is None:
        raise ValueError(
            "TranslationReviewItem has no database ID"
        )

    return TranslationReviewItemRead(
        id=item.id,
        field_name=item.field_name,
        source_value=item.source_value,
        status=item.status,
        translation_mapping_id=item.translation_mapping_id,
        created_at=item.created_at,
        mapped_at=item.mapped_at,
        occurrence_count=occurrence_count,
    )


async def list_review_items(
    session: AsyncSession,
    *,
    status: str | None,
    field_name: str | None,
    limit: int,
) -> list[TranslationReviewItemRead]:
    statement = (
        select(
            TranslationReviewItem,
            func.count(
                TranslationReviewOccurrence.id
            ).label("occurrence_count"),
        )
        .outerjoin(
            TranslationReviewOccurrence,
            TranslationReviewOccurrence
            .translation_review_item_id
            == TranslationReviewItem.id,
        )
        .group_by(TranslationReviewItem.id)
        .order_by(
            TranslationReviewItem.created_at.desc(),
            TranslationReviewItem.id.desc(),
        )
        .limit(limit)
    )

    if status:
        statement = statement.where(
            TranslationReviewItem.status == status
        )

    if field_name:
        statement = statement.where(
            TranslationReviewItem.field_name
            == field_name
        )

    result = await session.execute(statement)

    return [
        to_review_item_read(
            item=item,
            occurrence_count=occurrence_count,
        )
        for item, occurrence_count in result.all()
    ]


async def list_review_occurrences(
    session: AsyncSession,
    *,
    item_id: int,
) -> list[TranslationReviewOccurrenceRead]:
    item = await session.get(
        TranslationReviewItem,
        item_id,
    )

    if not item:
        return []

    statement = (
        select(
            TranslationReviewOccurrence,
            ScrapeStepRun,
            ScrapeRun,
            ScrapeSite,
        )
        .join(
            ScrapeStepRun,
            ScrapeStepRun.id
            == TranslationReviewOccurrence.step_run_id,
        )
        .join(
            ScrapeRun,
            ScrapeRun.id == ScrapeStepRun.run_id,
        )
        .join(
            ScrapeSite,
            ScrapeSite.id == ScrapeRun.site_id,
        )
        .where(
            TranslationReviewOccurrence
            .translation_review_item_id
            == item_id
        )
        .order_by(
            TranslationReviewOccurrence.created_at.desc(),
            TranslationReviewOccurrence.id.desc(),
        )
    )

    result = await session.execute(statement)

    return [
        TranslationReviewOccurrenceRead(
            id=occurrence.id,
            translation_review_item_id=(
                occurrence.translation_review_item_id
            ),
            source_url=occurrence.source_url,
            status=occurrence.status,
            created_at=occurrence.created_at,
            original_step_run_id=step_run.id,
            original_run_id=run.id,
            site_key=site.key,
            site_name=site.name,
            reprocessed_at=occurrence.reprocessed_at,
            reprocessed_step_run_id=(
                occurrence.reprocessed_step_run_id
            ),
            reprocess_error=occurrence.reprocess_error,
        )
        for occurrence, step_run, run, site in result.all()
    ]

