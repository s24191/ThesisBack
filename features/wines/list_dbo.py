from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.database import get_session
from shared.models.wine import (
    Wine,
    Country,
    Region,
    VivinoWine,
    Retailer,
    RetailerWine,
)
from shared.schemas.wine_list import WineListItem, WineOffer

router = APIRouter(prefix="/wines", tags=["wines-list"])


@router.get("/", response_model=List[WineListItem])
async def list_wines_dbo(
    search: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(
            Wine,
            Country,
            Region,
            VivinoWine,
            Retailer,
            RetailerWine,
        )
        .join(Country, Country.id == Wine.country_id)
        .join(Region, Region.id == Wine.region_id, isouter=True)
        .join(VivinoWine, VivinoWine.id == Wine.vivino_wine_id, isouter=True)
        .join(RetailerWine, RetailerWine.wine_id == Wine.id)
        .join(Retailer, Retailer.id == RetailerWine.retailer_id)
    )

    if search:
        ilike = f"%{search.lower()}%"
        stmt = stmt.where(Wine.name.ilike(ilike))
    if country:
        stmt = stmt.where(Country.name == country)
    if region:
        stmt = stmt.where(Region.name == region)

    # apply sort
    if sort == "price-asc":
        stmt = stmt.order_by(RetailerWine.price.asc())
    elif sort == "price-desc":
        stmt = stmt.order_by(RetailerWine.price.desc())
    elif sort == "rating-desc":
        stmt = stmt.order_by(VivinoWine.average_rating.desc().nullslast())

    stmt = stmt.offset(offset).limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    wines_map: Dict[int, WineListItem] = {}

    for wine, country_obj, region_obj, vivino, retailer, offer in rows:
        if wine.id not in wines_map:
            wines_map[wine.id] = WineListItem(
                id=wine.id,
                name=wine.name,
                country=country_obj.name,
                region=region_obj.name if region_obj else None,
                rating=vivino.average_rating if vivino else None,
                ratings_count=vivino.ratings_count if vivino else None,
                best_price=None,
                offers=[],
            )

        dto = wines_map[wine.id]

        offer_dto = WineOffer(
            shop_name=retailer.name,
            shop_url=offer.url,
            price=offer.price,
            image_url=offer.image_url,
        )
        dto.offers.append(offer_dto)

        if dto.best_price is None or offer.price < dto.best_price:
            dto.best_price = offer.price

    return list(wines_map.values())

@router.get("/countries", response_model=List[str])
async def list_countries(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Country.name).order_by(Country.name))
    return [row[0] for row in result.all()]


@router.get("/regions", response_model=List[str])
async def list_regions(
    country: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Region.name).order_by(Region.name)
    if country:
        stmt = (
            stmt.join(Country, Country.id == Region.country_id)
            .where(Country.name == country)
        )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]
