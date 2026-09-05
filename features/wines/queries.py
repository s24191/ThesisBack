from typing import Optional

from sqlalchemy import Float, cast, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from thefuzz import fuzz

from features.wines.schemas import WineDetail, WineOffer, WineListItem
from shared.models import WineComment
from shared.models.wine import (
    Country,
    Grape,
    Region,
    Retailer,
    RetailerWine,
    TasteProfile,
    Wine,
    WineGrapeLink,
    WineType,
)


def build_rating_stats():
    return (
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

def build_offer_stats():
    return (
        select(
            RetailerWine.wine_id.label("wine_id"),

            func.bool_or(
                RetailerWine.available
            ).label("available"),

            func.min(
                RetailerWine.price
            ).filter(
                RetailerWine.available.is_(True)
            ).label("best_price"),
        )
        .group_by(RetailerWine.wine_id)
        .subquery()
    )


async def list_country_names(
    session: AsyncSession,
) -> list[str]:
    result = await session.execute(
        select(Country.name).order_by(Country.name)
    )
    return [name for (name,) in result.all()]


async def list_region_names(
    session: AsyncSession,
    country: Optional[str] = None,
) -> list[str]:
    statement = select(Region.name).order_by(Region.name)

    if country:
        statement = (
            statement
            .join(
                Country,
                Country.id == Region.country_id,
            )
            .where(Country.name == country)
        )

    result = await session.execute(statement)
    return [name for (name,) in result.all()]


async def list_wine_cards(
    session: AsyncSession,
    *,
    search: Optional[str] = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    sort: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WineDetail]:
    rating_stats = build_rating_stats()
    offer_stats = build_offer_stats()

    statement = (
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
            func.coalesce(
                offer_stats.c.available,
                False,
            ).label("available"),
            offer_stats.c.best_price,
        )
        .join(
            Country,
            Country.id == Wine.country_id,
        )
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

    if search and search.strip():
        statement = statement.where(
            Wine.name.ilike(f"%{search.strip()}%")
        )

    if country:
        statement = statement.where(Country.name == country)

    if region:
        statement = statement.where(Region.name == region)

    if sort == "rating-desc":
        statement = statement.order_by(
            rating_stats.c.rating.desc().nullslast(),
            Wine.id.asc(),
        )
    elif sort == "price-asc":
        statement = statement.order_by(
            offer_stats.c.best_price.asc().nullslast(),
            Wine.id.asc(),
        )
    elif sort == "price-desc":
        statement = statement.order_by(
            offer_stats.c.best_price.desc().nullslast(),
            Wine.id.asc(),
        )
    else:
        statement = statement.order_by(Wine.id.desc())

    statement = statement.offset(offset).limit(limit)

    result = await session.execute(statement)
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
            _available,
            _best_price,
        ) in wine_rows
    ]

    offers_by_wine: dict[int, list[WineOffer]] = {
        wine_id: []
        for wine_id in wine_ids
    }

    if wine_ids:
        offers_statement = (
            select(
                RetailerWine.wine_id,
                Retailer.name,
                RetailerWine.url,
                RetailerWine.price,
                RetailerWine.image_url,
                RetailerWine.available,
            )
            .join(
                Retailer,
                Retailer.id == RetailerWine.retailer_id,
            )
            .where(
                RetailerWine.wine_id.in_(wine_ids)
            )
            .order_by(
                RetailerWine.wine_id,
                RetailerWine.available.desc(),
                RetailerWine.price.asc(),
            )
        )

        offers_result = await session.execute(
            offers_statement
        )

        for (
            wine_id,
            retailer_name,
            shop_url,
            price,
            image_url,
            available
        ) in offers_result.all():
            offers_by_wine[wine_id].append(
                WineOffer(
                    shop_name=retailer_name,
                    shop_url=shop_url,
                    price=float(price),
                    image_url=image_url,
                    available=bool(available),
                )
            )

    return [
        WineDetail(
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
            available=bool(available),
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
            available,
            best_price,
        ) in wine_rows
    ]


async def get_wine(
    session: AsyncSession,
    wine_id: int,
) -> Wine | None:
    return await session.get(Wine, wine_id)


async def get_similar_wines(
    session: AsyncSession,
    wine_id: int,
    limit: int = 6,
) -> list[WineListItem] | None:
    base_wine = await session.get(Wine, wine_id)

    if base_wine is None:
        return None

    rating_stats = build_rating_stats()
    offer_stats = build_offer_stats()

    base_grapes_statement = (
        select(Grape.name)
        .join(
            WineGrapeLink,
            WineGrapeLink.grape_id == Grape.id,
        )
        .where(WineGrapeLink.wine_id == wine_id)
    )

    base_grapes_result = await session.execute(
        base_grapes_statement
    )

    base_grapes = {
        grape_name
        for (grape_name,) in base_grapes_result.all()
    }

    statement = (
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
        .join(
            Country,
            Country.id == Wine.country_id,
        )
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
        .where(Wine.country_id == base_wine.country_id)
        .where(Wine.wine_type_id == base_wine.wine_type_id)
        .where(Wine.id != wine_id)
    )

    result = await session.execute(statement)
    candidate_rows = result.all()

    def normalize_name(value: str) -> str:
        return " ".join(value.lower().split())

    base_name = normalize_name(base_wine.name)

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
    ) in candidate_rows:
        candidate_grapes_statement = (
            select(Grape.name)
            .join(
                WineGrapeLink,
                WineGrapeLink.grape_id == Grape.id,
            )
            .where(WineGrapeLink.wine_id == wine.id)
        )

        candidate_grapes_result = await session.execute(
            candidate_grapes_statement
        )

        candidate_grapes = {
            grape_name
            for (grape_name,) in candidate_grapes_result.all()
        }

        shared_grapes_count = len(
            base_grapes.intersection(candidate_grapes)
        )

        same_taste_score = (
            1
            if (
                taste_profile is not None
                and taste_profile.id
                == base_wine.taste_profile_id
            )
            else 0
        )

        name_score = fuzz.partial_ratio(
            base_name,
            normalize_name(wine.name),
        )

        total_score = (
            shared_grapes_count * 3
            + same_taste_score * 2
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

    return [
        WineListItem(
            id=wine.id,
            name=wine.name,
            country=country.name,
            region=region.name if region else None,
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
        ) in scored[:limit]
    ]


async def get_wine_detail(
    session: AsyncSession,
    wine_id: int,
) -> WineDetail | None:
    statement = (
        select(
            Wine,
            Country,
            Region,
            WineType,
            TasteProfile,
        )
        .join(
            Country,
            Country.id == Wine.country_id,
        )
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
        .where(Wine.id == wine_id)
    )

    result = await session.execute(statement)
    row = result.first()

    if row is None:
        return None

    wine, country, region, wine_type, taste_profile = row

    offers_statement = (
        select(RetailerWine, Retailer)
        .join(
            Retailer,
            Retailer.id == RetailerWine.retailer_id,
        )
        .where(RetailerWine.wine_id == wine.id)
        .order_by(
            RetailerWine.available.desc(),
            RetailerWine.price.asc())
    )

    offers_result = await session.execute(
        offers_statement
    )

    offers = [
        WineOffer(
            shop_name=retailer.name,
            shop_url=offer.url,
            price=offer.price,
            image_url=offer.image_url,
            available=bool(offer.available),
        )
        for offer, retailer in offers_result.all()
    ]

    grapes_statement = (
        select(Grape.name)
        .join(
            WineGrapeLink,
            WineGrapeLink.grape_id == Grape.id,
        )
        .where(WineGrapeLink.wine_id == wine.id)
        .order_by(Grape.name)
    )

    grapes_result = await session.execute(
        grapes_statement
    )

    grape_names = [
        grape_name
        for (grape_name,) in grapes_result.all()
    ]

    return WineDetail(
        id=wine.id,
        name=wine.name,
        year=wine.year,
        country=country.name,
        region=region.name if region else None,
        wine_type=wine_type.name,
        taste=taste_profile.name if taste_profile else None,
        grapes=", ".join(grape_names) if grape_names else None,
        alc_perc=wine.alc_perc,
        capacity_ml=wine.capacity_ml,
        rating=None,
        ratings_count=None,
        available=any(offer.available for offer in offers),
        offers=offers,
    )