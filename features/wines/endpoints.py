from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from features.wines import  queries
from features.wines.schemas import WineDetail, WineListItem, WineOffer
from shared.database import get_session
from shared.schemas.wine import  WineRead


router = APIRouter(
    prefix="/wines",
    tags=["wines"],
)


@router.get(
    "/countries",
    response_model=List[str],
)
async def list_countries(
    session: AsyncSession = Depends(get_session),
):
    return await queries.list_country_names(session)


@router.get(
    "/regions",
    response_model=List[str],
)
async def list_regions(
    country: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    return await queries.list_region_names(
        session,
        country=country,
    )


@router.get(
    "",
    response_model=List[WineDetail],
)
async def list_wines(
    search: Optional[str] = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    sort: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    return await queries.list_wine_cards(
        session,
        search=search,
        country=country,
        region=region,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{wine_id}",
    response_model=WineRead,
)
async def get_wine(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    wine = await queries.get_wine(session, wine_id)

    if wine is None:
        raise HTTPException(
            status_code=404,
            detail="Wine not found",
        )

    return wine


@router.get(
    "/{wine_id}/similar",
    response_model=List[WineListItem],
)
async def get_similar_wines(
    wine_id: int,
    limit: int = 6,
    session: AsyncSession = Depends(get_session),
):
    similar_wines = await queries.get_similar_wines(
        session,
        wine_id=wine_id,
        limit=limit,
    )

    if similar_wines is None:
        raise HTTPException(
            status_code=404,
            detail="Wine not found",
        )

    return similar_wines


@router.get(
    "/{wine_id}/detail",
    response_model=WineDetail,
)
async def get_wine_detail(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    wine_detail = await queries.get_wine_detail(
        session,
        wine_id=wine_id,
    )

    if wine_detail is None:
        raise HTTPException(
            status_code=404,
            detail="Wine not found",
        )

    return wine_detail