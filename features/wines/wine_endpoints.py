from sqlalchemy import cast, func, Float
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.database import get_session
from shared.models import WineComment
from shared.models.wine import Wine, Grape, WineGrapeLink, Country, Region, WineType, TasteProfile,  \
    RetailerWine, Retailer
from shared.schemas.wine import WineRead, WineCreate, WineCardRead, WineCardOffer
from shared.schemas.wine_detail import WineDetail, WineOffer
from shared.schemas.wine_list import WineListItem
from thefuzz import fuzz

router = APIRouter(prefix="/wines", tags=["wines"])

rating_stats = (
    select(
        WineComment.wine_id.label("wine_id"),
        cast(
            func.avg(WineComment.rating),
            Float,
        ).label("rating"),
        func.count(WineComment.id).label(
            "ratings_count",
        ),
    )
    .group_by(WineComment.wine_id)
    .subquery()
)

offer_stats = (
    select(
        RetailerWine.wine_id.label("wine_id"),
        func.min(RetailerWine.price).label(
            "best_price",
        ),
    )
    .group_by(RetailerWine.wine_id)
    .subquery()
)

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


@router.get(
    "/",
    response_model=List[WineCardRead],
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
    stmt = (
        select(
            Wine,
            Country,
            Region,
            WineType,
            TasteProfile,
            rating_stats.c.rating,
            func.coalesce(
                rating_stats.c.ratings_count,
                0,
            ).label("ratings_count"),
            offer_stats.c.best_price,
        )
        .join(Country, Country.id == Wine.country_id)
        .outerjoin(
            Region,
            Region.id == Wine.region_id,
        )
        .join(
            WineType,
            WineType.id == Wine.wine_type_id,
        )
        .outerjoin(
            TasteProfile,
            TasteProfile.id == Wine.taste_profile_id,
        )
        .outerjoin(
            rating_stats,
            rating_stats.c.wine_id == Wine.id,
        )
        .outerjoin(
            offer_stats,
            offer_stats.c.wine_id == Wine.id,
        )
    )

    if search:
        stmt = stmt.where(
            Wine.name.ilike(f"%{search.strip()}%"),
        )

    if country:
        stmt = stmt.where(
            Country.name == country,
        )

    if region:
        stmt = stmt.where(
            Region.name == region,
        )

    if sort == "rating-desc":
        stmt = stmt.order_by(
            rating_stats.c.rating.desc().nullslast(),
            Wine.id.asc(),
        )

    elif sort == "price-asc":
        stmt = stmt.order_by(
            offer_stats.c.best_price.asc().nullslast(),
            Wine.id.asc(),
        )

    elif sort == "price-desc":
        stmt = stmt.order_by(
            offer_stats.c.best_price.desc().nullslast(),
            Wine.id.asc(),
        )

    else:
        stmt = stmt.order_by(Wine.id.desc())

    stmt = stmt.offset(offset).limit(limit)

    result = await session.execute(stmt)
    wine_rows = result.all()

    wine_ids = [
        wine.id
        for (
            wine,
            _country,
            _region,
            _wine_type,
            _taste,
            _rating,
            _ratings_count,
            _best_price,
        ) in wine_rows
    ]

    offers_by_wine: dict[int, list[WineCardOffer]] = {
        wine_id: []
        for wine_id in wine_ids
    }

    if wine_ids:
        offers_stmt = (
            select(
                RetailerWine.wine_id,
                Retailer.name,
                RetailerWine.url,
                RetailerWine.price,
                RetailerWine.image_url,
            )
            .join(
                Retailer,
                Retailer.id == RetailerWine.retailer_id,
            )
            .where(
                RetailerWine.wine_id.in_(wine_ids),
            )
            .order_by(
                RetailerWine.wine_id,
                RetailerWine.price.asc(),
            )
        )

        offers_result = await session.execute(
            offers_stmt,
        )

        for (
            wine_id,
            retailer_name,
            shop_url,
            price,
            image_url,
        ) in offers_result.all():
            offers_by_wine[wine_id].append(
                WineCardOffer(
                    shop_name=retailer_name,
                    shop_url=shop_url,
                    price=float(price),
                    image_url=image_url,
                )
            )

    return [
        WineCardRead(
            id=wine.id,
            name=wine.name,
            year=wine.year,
            country=country_row.name,
            region=(
                region_row.name
                if region_row is not None
                else None
            ),
            wine_type=wine_type_row.name,
            taste=(
                taste_row.name
                if taste_row is not None
                else None
            ),
            rating=(
                float(average_rating)
                if average_rating is not None
                else None
            ),
            ratings_count=int(ratings_count),
            best_price=(
                float(best_price)
                if best_price is not None
                else None
            ),
            offers=offers_by_wine[wine.id],
            image_url=(
                offers_by_wine[wine.id][0].image_url
                if offers_by_wine[wine.id]
                else None
            ),
        )
        for (
            wine,
            country_row,
            region_row,
            wine_type_row,
            taste_row,
            average_rating,
            ratings_count,
            best_price,
        ) in wine_rows
    ]


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

    rating_stats = (
        select(
            WineComment.wine_id.label("wine_id"),
            cast(
                func.avg(WineComment.rating),
                Float,
            ).label("rating"),
            func.count(WineComment.id).label(
                "ratings_count",
            ),
        )
        .group_by(WineComment.wine_id)
        .subquery()
    )

    offer_stats = (
        select(
            RetailerWine.wine_id.label("wine_id"),
            func.min(RetailerWine.price).label(
                "best_price",
            ),
        )
        .group_by(RetailerWine.wine_id)
        .subquery()
    )

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

    stmt = (
        select(
            Wine,
            Country,
            Region,
            WineType,
            TasteProfile,

            rating_stats.c.rating,

            func.coalesce(
                rating_stats.c.ratings_count,
                0,
            ).label("ratings_count"),

            offer_stats.c.best_price,
        )
        .join(Country, Country.id == Wine.country_id)
        .join(
            Region,
            Region.id == Wine.region_id,
            isouter=True,
        )
        .join(
            WineType,
            WineType.id == Wine.wine_type_id,
        )
        .join(
            TasteProfile,
            TasteProfile.id == Wine.taste_profile_id,
            isouter=True,
        )
        .outerjoin(
            rating_stats,
            rating_stats.c.wine_id == Wine.id,
        )
        .outerjoin(
            offer_stats,
            offer_stats.c.wine_id == Wine.id,
        )
        .where(Wine.country_id == country_id)
        .where(Wine.wine_type_id == wine_type_id)
        .where(Wine.id != wine_id)
    )

    res = await session.execute(stmt)
    rows = res.all()

    def norm_name(s: str) -> str:
        return " ".join(str(s).lower().split())

    base_name = norm_name(base_wine.name)

    scored: list[
        tuple[
            float,
            Wine,
            Country,
            Region | None,
            WineType,
            TasteProfile | None,
            float | None,
            int,
            float | None,
        ]
    ] = []

    for (
        wine,
        country,
        region,
        wine_type,
        taste_profile,
        rating,
        ratings_count,
        best_price,
    ) in rows:
        stmt_candidate_grapes = (
            select(Grape.name)
            .join(
                WineGrapeLink,
                WineGrapeLink.grape_id == Grape.id,
            )
            .where(
                WineGrapeLink.wine_id == wine.id,
            )
        )

        candidate_grapes_result = await session.execute(
            stmt_candidate_grapes,
        )

        candidate_grapes = {
            name
            for (name,) in candidate_grapes_result.all()
        }

        common_grapes = base_grapes.intersection(
            candidate_grapes,
        )

        grape_score = len(common_grapes)

        taste_score = (
            1
            if (
                taste_profile
                and taste_profile.id == taste_profile_id
            )
            else 0
        )

        name_score = fuzz.partial_ratio(
            base_name,
            norm_name(wine.name),
        )

        total_score = (
            grape_score * 3
            + taste_score * 2
            + name_score / 20.0
        )

        scored.append(
            (
                total_score,
                wine,
                country,
                region,
                wine_type,
                taste_profile,
                float(rating)
                if rating is not None
                else None,
                int(ratings_count),
                float(best_price)
                if best_price is not None
                else None,
            )
        )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    top = scored[:limit]

    return [
        WineListItem(
            id=wine.id,
            name=wine.name,
            country=country.name,
            region=(
                region.name
                if region
                else None
            ),

            rating=rating,
            ratings_count=ratings_count,
            best_price=best_price,

            offers=[],
        )
        for (
            _score,
            wine,
            country,
            region,
            _wine_type,
            _taste_profile,
            rating,
            ratings_count,
            best_price,
        ) in top
    ]

@router.get("/{wine_id}/detail", response_model=WineDetail)
async def get_wine_detail(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Wine, Country, Region, WineType, TasteProfile)
        .join(Country, Country.id == Wine.country_id)
        .join(Region, Region.id == Wine.region_id, isouter=True)
        .join(WineType, WineType.id == Wine.wine_type_id)
        .join(TasteProfile, TasteProfile.id == Wine.taste_profile_id, isouter=True)
        .where(Wine.id == wine_id)
    )
    res = await session.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Wine not found")

    wine, country, region, wine_type, taste_profile = row

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

    stmt_grapes = (
        select(Grape.name)
        .join(WineGrapeLink, WineGrapeLink.grape_id == Grape.id)
        .where(WineGrapeLink.wine_id == wine.id)
    )
    res_grapes = await session.execute(stmt_grapes)
    grape_names = [name for (name,) in res_grapes.all()]
    grapes_str: Optional[str] = ", ".join(grape_names) if grape_names else None

    rating: Optional[float] = None
    ratings_count: Optional[int] = None

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

