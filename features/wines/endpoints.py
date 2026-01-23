from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.database import get_session
from shared.models.wine import Wine
from shared.schemas.wine import WineRead, WineCreate

router = APIRouter(prefix="/wines", tags=["wines"])


@router.get("/", response_model=List[WineRead])
async def list_wines(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Wine).limit(limit))
    wines = result.scalars().all()
    return wines


@router.post("/", response_model=WineRead, status_code=201)
async def create_wine(
    payload: WineCreate,
    session: AsyncSession = Depends(get_session),
):
    wine = Wine(**payload.dict())
    session.add(wine)
    await session.commit()
    await session.refresh(wine)
    return wine


@router.get("/{wine_id}", response_model=WineRead)
async def get_wine(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    wine = await session.get(Wine, wine_id)
    if not wine:
        raise HTTPException(status_code=404, detail="Wine not found")
    return wine
