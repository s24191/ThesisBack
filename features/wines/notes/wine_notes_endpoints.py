from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from shared.database import get_session
from shared.auth.user_binding import current_active_user
from shared.models.wine_note import WineNote, WineNoteVote
from shared.models.wine import Wine
from features.wines.notes.schemas import WineNoteCreate, WineNoteRead, WineNotesList


router = APIRouter(prefix="/wines/{wine_id}/notes", tags=["wine-notes"])

@router.get("", response_model=WineNotesList)
async def list_wine_notes(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(WineNote)
        .where(WineNote.wine_id == wine_id)
        .order_by(WineNote.votes_count.desc(), WineNote.id.asc())
    )
    result = await session.execute(stmt)
    notes = result.scalars().all()

    return WineNotesList(
        notes=[
            WineNoteRead(
                id=n.id,
                wine_id=n.wine_id,
                text=n.text,
                votes_count=n.votes_count,
                created_at=n.created_at,
                user_voted=False,
            )
            for n in notes
        ]
    )

@router.get("/me", response_model=WineNotesList)
async def list_wine_notes_for_me(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(current_active_user),
):
    stmt = (
        select(WineNote)
        .where(WineNote.wine_id == wine_id)
        .order_by(WineNote.votes_count.desc(), WineNote.id.asc())
    )
    result = await session.execute(stmt)
    notes = result.scalars().all()

    if not notes:
        return WineNotesList(notes=[])

    note_ids = [n.id for n in notes]

    vote_stmt = select(WineNoteVote.note_id).where(
        WineNoteVote.user_id == user.id,
        WineNoteVote.note_id.in_(note_ids),
    )
    vote_res = await session.execute(vote_stmt)
    voted_ids = {row[0] for row in vote_res.all()}

    return WineNotesList(
        notes=[
            WineNoteRead(
                id=n.id,
                wine_id=n.wine_id,
                text=n.text,
                votes_count=n.votes_count,
                created_at=n.created_at,
                user_voted=(n.id in voted_ids),
            )
            for n in notes
        ]
    )

@router.post("", response_model=WineNoteRead, status_code=status.HTTP_201_CREATED)
async def create_wine_note(
    wine_id: int,
    data: WineNoteCreate,
    session: AsyncSession = Depends(get_session),
    user=Depends(current_active_user),
):
    wine = await session.get(Wine, wine_id)
    if not wine:
        raise HTTPException(status_code=404, detail="Wine not found")

    stmt = select(WineNote).where(
        WineNote.wine_id == wine_id,
        WineNote.text == data.text,
    )
    result = await session.execute(stmt)
    note = result.scalar_one_or_none()

    if not note:
        note = WineNote(wine_id=wine_id, text=data.text)
        session.add(note)
        await session.flush()

    vote_stmt = select(WineNoteVote).where(
        WineNoteVote.user_id == user.id,
        WineNoteVote.note_id == note.id,
    )
    vote_res = await session.execute(vote_stmt)
    existing_vote = vote_res.scalar_one_or_none()

    if not existing_vote:
        session.add(WineNoteVote(user_id=user.id, note_id=note.id))
        note.votes_count += 1

    await session.commit()
    await session.refresh(note)

    return WineNoteRead(
        id=note.id,
        wine_id=note.wine_id,
        text=note.text,
        votes_count=note.votes_count,
        created_at=note.created_at,
        user_voted=True,
    )


@router.post("/{note_id}/toggle", response_model=WineNoteRead)
async def toggle_wine_note_vote(
    wine_id: int,
    note_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(current_active_user),
):
    note = await session.get(WineNote, note_id)
    if not note or note.wine_id != wine_id:
        raise HTTPException(status_code=404, detail="Note not found")

    stmt = select(WineNoteVote).where(
        WineNoteVote.user_id == user.id,
        WineNoteVote.note_id == note.id,
    )
    result = await session.execute(stmt)
    vote = result.scalar_one_or_none()

    if vote:
        await session.delete(vote)
        note.votes_count = max(0, note.votes_count - 1)
        user_voted = False
    else:
        session.add(WineNoteVote(user_id=user.id, note_id=note.id))
        note.votes_count += 1
        user_voted = True

    await session.commit()
    await session.refresh(note)

    return WineNoteRead(
        id=note.id,
        wine_id=note.wine_id,
        text=note.text,
        votes_count=note.votes_count,
        created_at=note.created_at,
        user_voted=user_voted,
    )
