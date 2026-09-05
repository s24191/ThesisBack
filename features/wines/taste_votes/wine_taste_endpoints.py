from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.database import get_session
from shared.models.wine import Wine
from shared.models.wine_taste_vote import WineTasteVote
from shared.models.user import User
from features.wines.taste_votes.schemas import WineTasteVoteCreate, WineTasteVoteRead, WineTasteSummary
from shared.auth.user_binding import current_active_user

router = APIRouter(prefix="/wines", tags=["wines:taste"])

@router.put(
    "/{wine_id}/taste",
    response_model=WineTasteVoteRead,
    status_code=status.HTTP_200_OK,
)
async def upsert_my_taste_vote(
    wine_id: int,
    payload: WineTasteVoteCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    wine = await session.get(Wine, wine_id)
    if not wine:
        raise HTTPException(status_code=404, detail="Wine not found")

    stmt = select(WineTasteVote).where(
        WineTasteVote.wine_id == wine_id,
        WineTasteVote.user_id == user.id,
    )
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.body = payload.body
        existing.tannin = payload.tannin
        existing.sweetness = payload.sweetness
        existing.acidity = payload.acidity
        await session.commit()
        await session.refresh(existing)
        return WineTasteVoteRead(
            body=existing.body,
            tannin=existing.tannin,
            sweetness=existing.sweetness,
            acidity=existing.acidity,
        )

    vote = WineTasteVote(
        wine_id=wine_id,
        user_id=user.id,
        body=payload.body,
        tannin=payload.tannin,
        sweetness=payload.sweetness,
        acidity=payload.acidity,
    )
    session.add(vote)
    await session.commit()
    await session.refresh(vote)

    return WineTasteVoteRead(
        body=vote.body,
        tannin=vote.tannin,
        sweetness=vote.sweetness,
        acidity=vote.acidity,
    )

@router.get(
    "/{wine_id}/taste/me",
    response_model=WineTasteVoteRead | None,
)
async def get_my_taste_vote(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    stmt = select(WineTasteVote).where(
        WineTasteVote.wine_id == wine_id,
        WineTasteVote.user_id == user.id,
    )
    res = await session.execute(stmt)
    vote = res.scalar_one_or_none()

    if not vote:
        return None

    return WineTasteVoteRead(
        body=vote.body,
        tannin=vote.tannin,
        sweetness=vote.sweetness,
        acidity=vote.acidity,
    )


@router.get(
    "/{wine_id}/taste-summary",
    response_model=WineTasteSummary,
)
async def get_taste_summary(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(
        func.avg(WineTasteVote.body),
        func.avg(WineTasteVote.tannin),
        func.avg(WineTasteVote.sweetness),
        func.avg(WineTasteVote.acidity),
        func.count(),
    ).where(WineTasteVote.wine_id == wine_id)

    res = await session.execute(stmt)
    avg_body, avg_tannin, avg_sweetness, avg_acidity, count = res.one()

    if count == 0:
        return WineTasteSummary(
            body=0.0,
            tannin=0.0,
            sweetness=0.0,
            acidity=0.0,
            votes_count=0,
        )

    return WineTasteSummary(
        body=float(avg_body),
        tannin=float(avg_tannin),
        sweetness=float(avg_sweetness),
        acidity=float(avg_acidity),
        votes_count=count,
    )
