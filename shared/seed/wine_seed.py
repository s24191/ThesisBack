import csv
from dataclasses import dataclass
from io import StringIO
from typing import Any

from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

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


@dataclass
class SeedResult:
    rows_read: int = 0
    rows_skipped: int = 0

    wines_created: int = 0
    wines_updated: int = 0

    offers_created: int = 0
    offers_updated: int = 0


def parse_grapes(value: str | None) -> list[str]:
    if not value:
        return []

    return [
        grape.strip()
        for grape in value.split(",")
        if grape.strip()
    ]


def parse_optional_int(value: str | None) -> int | None:
    if not value or not value.strip():
        return None

    try:
        return int(float(value.replace(",", ".")))
    except ValueError:
        return None


def parse_optional_float(value: str | None) -> float | None:
    if not value or not value.strip():
        return None

    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def parse_available(value: str | None) -> bool:
    if not value:
        return False

    return value.strip().lower() in {
        "true",
        "1",
        "yes",
        "available",
    }


def get_required_value(
    row: dict[str, str],
    field_name: str,
) -> str:
    value = (row.get(field_name) or "").strip()

    if not value:
        raise ValueError(
            f"Missing required CSV field: {field_name}"
        )

    return value


async def get_or_create(
    session: AsyncSession,
    model: type[Any],
    name: str,
    *,
    extra_filter: dict[str, Any] | None = None,
) -> Any:
    statement = select(model).where(model.name == name)

    if extra_filter:
        for field_name, value in extra_filter.items():
            statement = statement.where(
                getattr(model, field_name) == value
            )

    result = await session.execute(statement)
    obj = result.scalar_one_or_none()

    if obj:
        return obj

    obj = model(
        name=name,
        **(extra_filter or {}),
    )
    session.add(obj)

    await session.flush()

    return obj


async def get_or_create_retailer(
    session: AsyncSession,
    *,
    retailer_name: str,
    retailer_base_url: str,
) -> Retailer:
    result = await session.execute(
        select(Retailer).where(
            Retailer.name == retailer_name
        )
    )
    retailer = result.scalar_one_or_none()

    if retailer:
        return retailer

    retailer = Retailer(
        name=retailer_name,
        url=retailer_base_url,
    )
    session.add(retailer)

    await session.flush()

    return retailer


async def get_reference_values(
    session: AsyncSession,
    row: dict[str, str],
) -> tuple[Country, Region | None, WineType, TasteProfile]:
    country_name = get_required_value(row, "country")
    wine_type_name = get_required_value(row, "wine_type")
    taste_profile_name = get_required_value(
        row,
        "taste_profile",
    )

    country = await get_or_create(
        session,
        Country,
        country_name,
    )

    region = None
    region_name = (row.get("region") or "").strip()

    if region_name:
        region = await get_or_create(
            session,
            Region,
            region_name,
            extra_filter={
                "country_id": country.id,
            },
        )

    wine_type = await get_or_create(
        session,
        WineType,
        wine_type_name,
    )

    taste_profile = await get_or_create(
        session,
        TasteProfile,
        taste_profile_name,
    )

    return (
        country,
        region,
        wine_type,
        taste_profile,
    )


async def replace_wine_grapes(
    session: AsyncSession,
    *,
    wine_id: int,
    grape_names: list[str],
) -> None:
    await session.execute(
        delete(WineGrapeLink).where(
            WineGrapeLink.wine_id == wine_id
        )
    )

    for grape_name in grape_names:
        grape = await get_or_create(
            session,
            Grape,
            grape_name,
        )

        session.add(
            WineGrapeLink(
                wine_id=wine_id,
                grape_id=grape.id,
            )
        )


async def upsert_offer_from_row(
    session: AsyncSession,
    *,
    retailer: Retailer,
    row: dict[str, str],
    result: SeedResult,
) -> None:
    url = get_required_value(row, "url")

    (
        country,
        region,
        wine_type,
        taste_profile,
    ) = await get_reference_values(
        session,
        row,
    )

    name = get_required_value(row, "name")

    year = parse_optional_int(row.get("year"))
    alc_perc = parse_optional_float(
        row.get("alc_perc")
    )
    capacity_ml = parse_optional_int(
        row.get("capacity_ml")
    )
    price = parse_optional_float(row.get("price"))
    image_url = (row.get("image_url") or "").strip() or None
    available = parse_available(row.get("available"))
    grape_names = parse_grapes(row.get("grapes"))

    offer_result = await session.execute(
        select(RetailerWine, Wine)
        .join(
            Wine,
            RetailerWine.wine_id == Wine.id,
        )
        .where(
            RetailerWine.retailer_id == retailer.id,
            RetailerWine.url == url,
        )
    )
    existing = offer_result.first()

    if existing:
        offer, wine = existing

        wine.name = name
        wine.year = year
        wine.alc_perc = alc_perc
        wine.capacity_ml = capacity_ml
        wine.country_id = country.id
        wine.region_id = region.id if region else None
        wine.wine_type_id = wine_type.id
        wine.taste_profile_id = taste_profile.id

        offer.price = price or 0.0
        offer.available = available
        offer.image_url = image_url

        await replace_wine_grapes(
            session,
            wine_id=wine.id,
            grape_names=grape_names,
        )

        result.wines_updated += 1
        result.offers_updated += 1

        return

    wine = Wine(
        name=name,
        year=year,
        alc_perc=alc_perc,
        capacity_ml=capacity_ml,
        country_id=country.id,
        region_id=region.id if region else None,
        wine_type_id=wine_type.id,
        taste_profile_id=taste_profile.id,
    )
    session.add(wine)

    await session.flush()

    await replace_wine_grapes(
        session,
        wine_id=wine.id,
        grape_names=grape_names,
    )

    offer = RetailerWine(
        retailer_id=retailer.id,
        wine_id=wine.id,
        price=price or 0.0,
        available=available,
        url=url,
        image_url=image_url,
    )
    session.add(offer)

    result.wines_created += 1
    result.offers_created += 1


async def seed_wines_from_csv_content(
    session: AsyncSession,
    *,
    csv_content: str,
    retailer_name: str,
    retailer_base_url: str,
) -> SeedResult:
    result = SeedResult()

    retailer = await get_or_create_retailer(
        session,
        retailer_name=retailer_name,
        retailer_base_url=retailer_base_url,
    )

    reader = csv.DictReader(
        StringIO(csv_content),
    )

    for row in reader:
        result.rows_read += 1

        try:
            await upsert_offer_from_row(
                session,
                retailer=retailer,
                row=row,
                result=result,
            )
        except ValueError:
            result.rows_skipped += 1

    return result