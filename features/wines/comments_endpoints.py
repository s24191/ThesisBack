from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, func, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.database import get_session
from shared.models.wine import Wine
from shared.models.comment import WineComment
from shared.models.user import User
from shared.schemas.comment import WineCommentRead, WineCommentCreate
from shared.auth.user_binding import current_active_user

router = APIRouter(prefix="/wines", tags=["wines:comments"])


@router.get("/{wine_id}/comments", response_model=list[WineCommentRead])
async def list_wine_comments(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(WineComment, User)
        .join(User, User.id == WineComment.user_id)
        .where(WineComment.wine_id == wine_id)
        .order_by(WineComment.created_at.desc())
    )
    res = await session.execute(stmt)
    rows = res.all()

    return [
        WineCommentRead(
            id=comment.id,
            user_id=str(user.id),
            username=user.username or user.email,
            rating=comment.rating,
            text=comment.text,
            created_at=comment.created_at,
        )
        for comment, user in rows
    ]

@router.post(
    "/{wine_id}/comments",
    response_model=WineCommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_wine_comment(
    wine_id: int,
    payload: WineCommentCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    wine = await session.get(Wine, wine_id)
    if not wine:
        raise HTTPException(status_code=404, detail="Wine not found")

    stmt_existing = select(WineComment).where(
        WineComment.wine_id == wine_id,
        WineComment.user_id == str(user.id),
    )
    res_existing = await session.execute(stmt_existing)
    existing = res_existing.scalar_one_or_none()

    if existing:
        existing.rating = payload.rating
        existing.text = payload.text
        await session.commit()
        await session.refresh(existing)

        return WineCommentRead(
            id=existing.id,
            user_id=str(user.id),
            username=user.username or user.email,
            rating=existing.rating,
            text=existing.text,
            created_at=existing.created_at,
        )

    comment = WineComment(
        wine_id=wine_id,
        user_id=str(user.id),
        rating=payload.rating,
        text=payload.text,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    return WineCommentRead(
        id=comment.id,
        user_id=str(user.id),
        username=user.username or user.email,
        rating=comment.rating,
        text=comment.text,
        created_at=comment.created_at,
    )

@router.delete(
    "/{wine_id}/comments/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_my_comment(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    stmt = select(WineComment).where(
        WineComment.wine_id == wine_id,
        WineComment.user_id == str(user.id),
    )
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()

    if not existing:
        raise HTTPException(status_code=404, detail="Comment not found")

    await session.delete(existing)
    await session.commit()

class RatingBucket(SQLModel):
    rating: int
    count: int
@router.get("/{wine_id}/rating-summary", response_model=list[RatingBucket])
async def get_rating_summary(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(WineComment.rating, func.count())
        .where(WineComment.wine_id == wine_id)
        .group_by(WineComment.rating)
    )
    res = await session.execute(stmt)
    rows = res.all()
    return [RatingBucket(rating=rating, count=count) for rating, count in rows]