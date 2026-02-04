from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
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
