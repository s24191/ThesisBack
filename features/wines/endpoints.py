from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.database import get_session
from shared.models.wine import Wine, Grape, WineGrapeLink, Country, Region, WineType, TasteProfile, VivinoWine, \
    RetailerWine, Retailer
from shared.schemas.wine import WineRead, WineCreate
from shared.schemas.wine_detail import WineDetail, WineOffer
from shared.schemas.wine_list import WineListItem
from thefuzz import fuzz

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


@router.get("/{wine_id}/similar", response_model=List[WineListItem])
async def get_similar_wines(
    wine_id: int,
    limit: int = 6,
    session: AsyncSession = Depends(get_session),
):
    base_wine = await session.get(Wine, wine_id)
    if not base_wine:
        raise HTTPException(status_code=404, detail="Wine not found")

    country_id = base_wine.country_id
    wine_type_id = base_wine.wine_type_id
    taste_profile_id = base_wine.taste_profile_id

    stmt_grapes = (
        select(Grape.name)
        .join(WineGrapeLink, WineGrapeLink.grape_id == Grape.id)
        .where(WineGrapeLink.wine_id == wine_id)
    )
    res_g = await session.execute(stmt_grapes)
    base_grapes = {name for (name,) in res_g.all()}

    # select candidate wines with same country + type
    stmt = (
        select(Wine, Country, Region, WineType, TasteProfile)
        .join(Country, Country.id == Wine.country_id)
        .join(Region, Region.id == Wine.region_id, isouter=True)
        .join(WineType, WineType.id == Wine.wine_type_id)
        .join(TasteProfile, TasteProfile.id == Wine.taste_profile_id, isouter=True)
        .where(Wine.country_id == country_id)
        .where(Wine.wine_type_id == wine_type_id)
        .where(Wine.id != wine_id)
    )

    res = await session.execute(stmt)
    rows = res.all()

    # score candidates by: same taste, shared grapes, name similarity


    def norm_name(s: str) -> str:
        return " ".join(str(s).lower().split())

    base_name = norm_name(base_wine.name)

    scored = []
    for wine, country, region, wt, taste in rows:
        # grapes for candidate
        stmt_cg = (
            select(Grape.name)
            .join(WineGrapeLink, WineGrapeLink.grape_id == Grape.id)
            .where(WineGrapeLink.wine_id == wine.id)
        )
        res_cg = await session.execute(stmt_cg)
        cand_grapes = {name for (name,) in res_cg.all()}

        common_grapes = base_grapes.intersection(cand_grapes)
        grape_score = len(common_grapes)

        taste_score = 1 if taste and taste.id == taste_profile_id else 0

        name_score = fuzz.partial_ratio(base_name, norm_name(wine.name))

        # basic heuristic
        total_score = grape_score * 3 + taste_score * 2 + name_score / 20.0

        scored.append(
            (total_score, wine, country, region, wt, taste)
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]


    similar: List[WineListItem] = []
    for score, wine, country, region, wt, taste in top:
        similar.append(
            WineListItem(
                id=wine.id,
                name=wine.name,
                country=country.name,
                region=region.name if region else None,
                rating=None,
                ratings_count=None,
                best_price=None,
                offers=[],
            )
        )

    return similar


@router.get("/{wine_id}/detail", response_model=WineDetail)
async def get_wine_detail(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    # 1) load wine + lookup tables
    stmt = (
        select(Wine, Country, Region, WineType, TasteProfile, VivinoWine)
        .join(Country, Country.id == Wine.country_id)
        .join(Region, Region.id == Wine.region_id, isouter=True)
        .join(WineType, WineType.id == Wine.wine_type_id)
        .join(TasteProfile, TasteProfile.id == Wine.taste_profile_id, isouter=True)
        .join(VivinoWine, VivinoWine.id == Wine.vivino_wine_id, isouter=True)
        .where(Wine.id == wine_id)
    )
    res = await session.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Wine not found")

    wine, country, region, wine_type, taste_profile, vivino = row

    # 2) offers for this wine
    stmt_offers = (
        select(RetailerWine, Retailer)
        .join(Retailer, Retailer.id == RetailerWine.retailer_id)
        .where(RetailerWine.wine_id == wine.id)
    )
    res_offers = await session.execute(stmt_offers)
    offers_rows = res_offers.all()

    offers: List[WineOffer] = []
    for offer, retailer in offers_rows:
        offers.append(
            WineOffer(
                shop_name=retailer.name,
                shop_url=offer.url,
                price=offer.price,
                image_url=offer.image_url,
            )
        )

    # 3) grapes list
    stmt_grapes = (
        select(Grape.name)
        .join(WineGrapeLink, WineGrapeLink.grape_id == Grape.id)
        .where(WineGrapeLink.wine_id == wine.id)
    )
    res_grapes = await session.execute(stmt_grapes)
    grape_names = [name for (name,) in res_grapes.all()]
    grapes_str: Optional[str] = ", ".join(grape_names) if grape_names else None

    # 4) Vivino rating (if present)
    rating: Optional[float] = None
    ratings_count: Optional[int] = None
    if vivino:
        rating = vivino.average_rating
        ratings_count = vivino.ratings_count

    # 5) build DTO
    return WineDetail(
        id=wine.id,
        name=wine.name,
        year=wine.year,
        country=country.name,
        region=region.name if region else None,
        type_of_wine=wine_type.name,
        taste=taste_profile.name if taste_profile else None,
        grapes=grapes_str,
        alc_perc=wine.alc_perc,
        capacity_ml=wine.capacity_ml,
        rating=rating,
        ratings_count=ratings_count,
        offers=offers,
    )