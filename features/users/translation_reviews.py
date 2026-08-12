
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.auth.admin import current_admin
from shared.database import get_session
from shared.models.scraping import (
    ScrapeRun,
    ScrapeSite,
    ScrapeStepRun,

)
from shared.models.translations import (
    TranslationMapping,
    TranslationReviewItem,
    TranslationReviewOccurrence,
)
router = APIRouter(
    prefix="/admin/translation_reviews",
    tags=["admin-translation_reviews"],
    dependencies=[Depends(current_admin)],
)


class TranslationReviewItemRead(BaseModel):
    id: int

    field_name: str
    source_value: str
    status: str

    translation_mapping_id: int | None = None

    created_at: datetime
    mapped_at: datetime | None = None

    occurrence_count: int


class TranslationReviewOccurrenceRead(BaseModel):
    id: int

    translation_review_item_id: int
    source_url: str

    status: str
    created_at: datetime

    original_step_run_id: int
    original_run_id: int
    site_key: str
    site_name: str

    reprocessed_at: datetime | None = None
    reprocessed_step_run_id: int | None = None
    reprocess_error: str | None = None


class ResolveTranslationReviewRequest(BaseModel):
    target_value: str = Field(
        min_length=1,
        max_length=255,
    )


class TranslationReviewActionResponse(BaseModel):
    id: int

    field_name: str
    source_value: str
    status: str

    translation_mapping_id: int | None = None
    affected_occurrences: int

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


@router.get(
    "",
    response_model=list[TranslationReviewItemRead],
)
async def list_translation_reviews(
    status: str | None = Query(default=None),
    field_name: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
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
    rows = result.all()

    return [
        to_review_item_read(
            item=item,
            occurrence_count=occurrence_count,
        )
        for item, occurrence_count in rows
    ]


@router.get(
    "/{item_id}/occurrences",
    response_model=list[TranslationReviewOccurrenceRead],
)
async def list_translation_review_occurrences(
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    item = await session.get(
        TranslationReviewItem,
        item_id,
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Translation review item not found",
        )

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


@router.post(
    "/{item_id}/resolve",
    response_model=TranslationReviewActionResponse,
)
async def resolve_translation_review(
    item_id: int,
    payload: ResolveTranslationReviewRequest,
    session: AsyncSession = Depends(get_session),
):
    item = await session.get(
        TranslationReviewItem,
        item_id,
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Translation review item not found",
        )

    target_value = payload.target_value.strip()

    if not target_value:
        raise HTTPException(
            status_code=422,
            detail="target_value cannot be blank",
        )

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
    pending_occurrences = occurrence_result.scalars().all()

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


@router.post(
    "/{item_id}/ignore",
    response_model=TranslationReviewActionResponse,
)
async def ignore_translation_review(
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    item = await session.get(
        TranslationReviewItem,
        item_id,
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Translation review item not found",
        )

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
    pending_occurrences = occurrence_result.scalars().all()

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