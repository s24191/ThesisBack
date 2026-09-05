from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from features.administration.translation_reviews.actions import resolve_review_item, ignore_review_item
from features.administration.translation_reviews.queries import list_review_items, list_review_occurrences
from features.administration.translation_reviews.schemas import TranslationReviewItemRead, \
    TranslationReviewOccurrenceRead, TranslationReviewActionResponse, ResolveTranslationReviewRequest
from shared.auth.admin import current_admin
from shared.database import get_session
from shared.models.translations import (
    TranslationReviewItem,
)

router = APIRouter(
    prefix="/admin/translation_reviews",
    tags=["admin-translation_reviews"],
    dependencies=[Depends(current_admin)],
)


@router.get(
    "",
    response_model=list[TranslationReviewItemRead],
)
async def list_translation_reviews(
        status: str | None = Query(default=None),
        field_name: str | None = Query(default=None),
        limit: int = Query(
            default=100,
            ge=1,
            le=500,
        ),
        session: AsyncSession = Depends(get_session),
):
    return await list_review_items(
        session,
        status=status,
        field_name=field_name,
        limit=limit,
    )


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

    return await list_review_occurrences(
        session,
        item_id=item_id,
    )


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

    return await resolve_review_item(
        session,
        item=item,
        target_value=target_value,
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

    return await ignore_review_item(
        session,
        item=item,
    )
