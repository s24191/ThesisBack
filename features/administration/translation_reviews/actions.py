from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.models.translations import (
    TranslationMapping,
    TranslationReviewItem,
    TranslationReviewOccurrence,
)

from .schemas import (
    TranslationReviewActionResponse,
)


async def resolve_review_item(
    session: AsyncSession,
    *,
    item: TranslationReviewItem,
    target_value: str,
) -> TranslationReviewActionResponse:
    mapping_result = await session.execute(
        select(TranslationMapping).where(
            TranslationMapping.field_name
            == item.field_name,
            TranslationMapping.source_value
            == item.source_value,
        )
    )

    mapping = mapping_result.scalar_one_or_none()

    if mapping:
        mapping.target_value = target_value
        mapping.active = True
    else:
        mapping = TranslationMapping(
            field_name=item.field_name,
            source_value=item.source_value,
            target_value=target_value,
            active=True,
            created_by="manual:admin",
        )
        session.add(mapping)
        await session.flush()

    item.status = "resolved"
    item.translation_mapping_id = mapping.id
    item.mapped_at = datetime.utcnow()

    occurrence_result = await session.execute(
        select(TranslationReviewOccurrence).where(
            TranslationReviewOccurrence
            .translation_review_item_id
            == item.id,
            TranslationReviewOccurrence.status
            == "pending",
        )
    )

    pending_occurrences = (
        occurrence_result.scalars().all()
    )

    for occurrence in pending_occurrences:
        occurrence.status = "resolved"

    await session.commit()

    return TranslationReviewActionResponse(
        id=item.id,
        field_name=item.field_name,
        source_value=item.source_value,
        status=item.status,
        translation_mapping_id=item.translation_mapping_id,
        affected_occurrences=len(pending_occurrences),
    )


async def ignore_review_item(
    session: AsyncSession,
    *,
    item: TranslationReviewItem,
) -> TranslationReviewActionResponse:
    item.status = "ignored"

    occurrence_result = await session.execute(
        select(TranslationReviewOccurrence).where(
            TranslationReviewOccurrence
            .translation_review_item_id
            == item.id,
            TranslationReviewOccurrence.status
            == "pending",
        )
    )

    pending_occurrences = (
        occurrence_result.scalars().all()
    )

    for occurrence in pending_occurrences:
        occurrence.status = "ignored"

    await session.commit()

    return TranslationReviewActionResponse(
        id=item.id,
        field_name=item.field_name,
        source_value=item.source_value,
        status=item.status,
        translation_mapping_id=item.translation_mapping_id,
        affected_occurrences=len(pending_occurrences),
    )