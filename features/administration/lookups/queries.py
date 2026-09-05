from sqlalchemy import Float, cast, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.models import WineComment, WineTasteVote
from shared.models.wine import (
    Country,
    Grape,
    Region,
    Retailer,
    RetailerWine,
    TasteProfile,
    Wine,
    WineType,
)

from features.administration.lookups.schemas import AdminWineRow, PaginatedWineRows


async def list_countries(session: AsyncSession) -> list[Country]:
    result = await session.execute(
        select(Country).order_by(Country.name)
    )
    return list(result.scalars().all())


async def list_regions(
    session: AsyncSession,
    country_id: int | None = None,
) -> list[Region]:
    statement = select(Region).order_by(Region.name)

    if country_id is not None:
        statement = statement.where(Region.country_id == country_id)

    result = await session.execute(statement)
    return list(result.scalars().all())


async def list_wine_types(session: AsyncSession) -> list[WineType]:
    result = await session.execute(
        select(WineType).order_by(WineType.name)
    )
    return list(result.scalars().all())


async def list_taste_profiles(
    session: AsyncSession,
) -> list[TasteProfile]:
    result = await session.execute(
        select(TasteProfile).order_by(TasteProfile.name)
    )
    return list(result.scalars().all())


async def list_grapes(session: AsyncSession) -> list[Grape]:
    result = await session.execute(
        select(Grape).order_by(Grape.name)
    )
    return list(result.scalars().all())


async def list_retailers(session: AsyncSession) -> list[Retailer]:
    result = await session.execute(
        select(Retailer).order_by(Retailer.name)
    )
    return list(result.scalars().all())


async def get_wine(
    session: AsyncSession,
    wine_id: int,
) -> Wine | None:
    return await session.get(Wine, wine_id)


async def list_admin_wines(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    search: str | None,
    country: str | None,
    region: str | None,
    sort: str | None,
    country_id: int | None,
    region_id: int | None,
    wine_type_id: int | None,
) -> PaginatedWineRows:
    comment_stats = (
        select(
            WineComment.wine_id.label("wine_id"),
            func.count(WineComment.id).label("comments_count"),
            cast(
                func.avg(WineComment.rating),
                Float,
            ).label("rating_average"),
        )
        .group_by(WineComment.wine_id)
        .subquery()
    )

    taste_score_per_vote = cast(
        (
            WineTasteVote.body
            + WineTasteVote.tannin
            + WineTasteVote.sweetness
            + WineTasteVote.acidity
        )
        / 4.0,
        Float,
    )

    taste_stats = (
        select(
            WineTasteVote.wine_id.label("wine_id"),
            func.count(WineTasteVote.id).label(
                "taste_votes_count"
            ),
            cast(
                func.avg(taste_score_per_vote),
                Float,
            ).label("taste_average"),
            cast(
                func.avg(WineTasteVote.body),
                Float,
            ).label("body_average"),
            cast(
                func.avg(WineTasteVote.tannin),
                Float,
            ).label("tannin_average"),
            cast(
                func.avg(WineTasteVote.sweetness),
                Float,
            ).label("sweetness_average"),
            cast(
                func.avg(WineTasteVote.acidity),
                Float,
            ).label("acidity_average"),
        )
        .group_by(WineTasteVote.wine_id)
        .subquery()
    )

    offer_stats = (
        select(
            RetailerWine.wine_id.label("wine_id"),
            func.min(RetailerWine.price).label("best_price"),
        )
        .group_by(RetailerWine.wine_id)
        .subquery()
    )

    base_statement = (
        select(Wine)
        .join(
            Country,
            Country.id == Wine.country_id,
            isouter=True,
        )
        .join(
            Region,
            Region.id == Wine.region_id,
            isouter=True,
        )
    )

    if search and search.strip():
        base_statement = base_statement.where(
            Wine.name.ilike(f"%{search.strip()}%")
        )

    if country:
        base_statement = base_statement.where(
            Country.name == country
        )

    if region:
        base_statement = base_statement.where(
            Region.name == region
        )

    if country_id is not None:
        base_statement = base_statement.where(
            Wine.country_id == country_id
        )

    if region_id is not None:
        base_statement = base_statement.where(
            Wine.region_id == region_id
        )

    if wine_type_id is not None:
        base_statement = base_statement.where(
            Wine.wine_type_id == wine_type_id
        )

    total_result = await session.execute(
        select(func.count()).select_from(
            base_statement.subquery()
        )
    )
    total = total_result.scalar_one() or 0

    statement = (
        select(
            Wine,
            Country,
            Region,
            WineType,
            TasteProfile,
            func.coalesce(
                taste_stats.c.taste_votes_count,
                0,
            ).label("taste_votes_count"),
            taste_stats.c.taste_average,
            func.coalesce(
                comment_stats.c.comments_count,
                0,
            ).label("comments_count"),
            comment_stats.c.rating_average,
        )
        .join(
            Country,
            Country.id == Wine.country_id,
            isouter=True,
        )
        .join(
            Region,
            Region.id == Wine.region_id,
            isouter=True,
        )
        .join(
            WineType,
            WineType.id == Wine.wine_type_id,
            isouter=True,
        )
        .join(
            TasteProfile,
            TasteProfile.id == Wine.taste_profile_id,
            isouter=True,
        )
        .outerjoin(
            taste_stats,
            taste_stats.c.wine_id == Wine.id,
        )
        .outerjoin(
            comment_stats,
            comment_stats.c.wine_id == Wine.id,
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
        statement = statement.where(
            Country.name == country
        )

    if region:
        statement = statement.where(
            Region.name == region
        )

    if country_id is not None:
        statement = statement.where(
            Wine.country_id == country_id
        )

    if region_id is not None:
        statement = statement.where(
            Wine.region_id == region_id
        )

    if wine_type_id is not None:
        statement = statement.where(
            Wine.wine_type_id == wine_type_id
        )

    sort_columns = {
        "year": Wine.year,
        "alcohol": Wine.alc_perc,
        "volume": Wine.capacity_ml,
        "comments": comment_stats.c.comments_count,
        "rating": comment_stats.c.rating_average,
        "body": taste_stats.c.body_average,
        "tannin": taste_stats.c.tannin_average,
        "sweetness": taste_stats.c.sweetness_average,
        "acidity": taste_stats.c.acidity_average,
        "price": offer_stats.c.best_price,
    }

    if sort:
        sort_key, _, sort_direction = sort.partition("-")
        sort_column = sort_columns.get(sort_key)

        if sort_column is not None:
            if sort_direction == "asc":
                statement = statement.order_by(
                    sort_column.asc().nullslast(),
                    Wine.id.asc(),
                )
            else:
                statement = statement.order_by(
                    sort_column.desc().nullslast(),
                    Wine.id.asc(),
                )
        else:
            statement = statement.order_by(Wine.id.asc())
    else:
        statement = statement.order_by(Wine.id.asc())

    statement = statement.offset(offset).limit(limit)

    result = await session.execute(statement)
    rows = result.all()

    items = [
        AdminWineRow(
            id=wine.id,
            name=wine.name,
            year=wine.year,
            alc_perc=wine.alc_perc,
            capacity_ml=wine.capacity_ml,
            country_id=wine.country_id,
            region_id=wine.region_id,
            wine_type_id=wine.wine_type_id,
            taste_profile_id=wine.taste_profile_id,
            country=country_row.name if country_row else None,
            region=region_row.name if region_row else None,
            wine_type=wine_type_row.name if wine_type_row else None,
            taste_profile=(
                taste_profile_row.name
                if taste_profile_row
                else None
            ),
            taste_votes_count=int(taste_votes_count),
            taste_average=(
                float(taste_average)
                if taste_average is not None
                else None
            ),
            comments_count=int(comments_count),
            rating_average=(
                float(rating_average)
                if rating_average is not None
                else None
            ),
        )
        for (
            wine,
            country_row,
            region_row,
            wine_type_row,
            taste_profile_row,
            taste_votes_count,
            taste_average,
            comments_count,
            rating_average,
        ) in rows
    ]

    return PaginatedWineRows(
        items=items,
        total=total,
    )