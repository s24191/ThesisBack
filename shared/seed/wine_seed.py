import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.models.wine import (Country,
                                Region,
                                WineType,
                                TasteProfile,
                                Wine,
                                Retailer,
                                RetailerWine,
                                WineGrapeLink,
                                Grape,
                                )

@dataclass
class RetailerCSV:
    path: Path
    retailer_name: str
    retailer_base_url: str


BASE_CSV_DIR = Path(
    os.getenv("SEED_CSV_DIR", Path(__file__).resolve().parent / "csv_files")
)

CSV_FILES: list[RetailerCSV] = [
    RetailerCSV(
        path=BASE_CSV_DIR / "sklep-wina" / "cleaned_wine_data.csv",
        retailer_name="Sklep Wina",
        retailer_base_url="https://sklep-wina.pl",
    ),
    RetailerCSV(
        path=BASE_CSV_DIR / "winapl" / "cleaned_wine_data.csv",
        retailer_name="Wina.pl",
        retailer_base_url="https://wina.pl",
    ),
    RetailerCSV(
        path=BASE_CSV_DIR / "malawinnica" / "cleaned_winedata_malawinnica.csv",
        retailer_name="Mala Winnica",
        retailer_base_url="https://malawinnica.pl",
    ),
]

def _parse_grapes(raw: str) -> list[str]:
    if not raw:
        return []
    return [g.strip() for g in str(raw).split(",") if g.strip()]

async def _get_or_create(
    session: AsyncSession,
    model,
    name: str,
    extra_filter: Dict[str, Any] | None = None,
):
    stmt = select(model).where(model.name == name)
    if extra_filter:
        for field, value in extra_filter.items():
            stmt = stmt.where(getattr(model, field) == value)
    result = await session.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj:
        return obj
    obj = model(name=name, **(extra_filter or {}))
    session.add(obj)
    await session.flush()
    return obj

async def _get_or_create_country_region(session: AsyncSession, row):
    country = await _get_or_create(session, Country, row["country"])

    region = None
    if row.get("region"):
        region = await _get_or_create(
            session,
            Region,
            row["region"],
            extra_filter={"country_id": country.id},
        )

    wine_type = await _get_or_create(session, WineType, row["type_of_wine"])
    taste_profile = await _get_or_create(session, TasteProfile, row["taste"])

    return country, region, wine_type, taste_profile


async def _get_or_create_retailer(session, name: str, base_url: str) -> Retailer:
    stmt = select(Retailer).where(Retailer.name == name)
    res = await session.execute(stmt)
    retailer = res.scalar_one_or_none()
    if retailer:
        return retailer
    retailer = Retailer(name=name, url=base_url)
    session.add(retailer)
    await session.flush()
    return retailer

async def _upsert_offer_from_row(session, csv_info, row):
    country, region, wine_type, taste_profile = await _get_or_create_country_region(
        session, row
    )

    grape_names = _parse_grapes(row.get("grape", ""))
    image_url = row.get("image_url") or None

    capacity_ml = (
        int(float(row["capacity"].replace(",", ".")))
        if row.get("capacity")
        else None
    )
    price = float(row["price"].replace(",", ".")) if row.get("price") else 0.0
    url = row["url"]

    retailer = await _get_or_create_retailer(
        session, csv_info.retailer_name, csv_info.retailer_base_url
    )

    stmt = (
        select(RetailerWine)
        .where(RetailerWine.retailer_id == retailer.id)
        .where(RetailerWine.url == url)
    )
    res = await session.execute(stmt)

    stmt = (
        select(RetailerWine, Wine)
        .join(Wine, RetailerWine.wine_id == Wine.id)
        .where(RetailerWine.retailer_id == retailer.id)
        .where(RetailerWine.url == url)
    )
    res = await session.execute(stmt)
    row_obj = res.first()

    if row_obj:
        offer, wine = row_obj
        offer.price = price
        offer.image_url = image_url

        wine.name = row["name"]
        wine.capacity_ml = capacity_ml
        wine.country_id = country.id
        wine.region_id = region.id if region else None
        wine.wine_type_id = wine_type.id
        wine.taste_profile_id = taste_profile.id
        return

    wine = Wine(
        name=row["name"],
        year=None,
        alc_perc=None,
        capacity_ml=capacity_ml,
        country_id=country.id,
        region_id=region.id if region else None,
        wine_type_id=wine_type.id,
        taste_profile_id=taste_profile.id,
    )
    session.add(wine)
    await session.flush()

    for g_name in grape_names:
        grape = await _get_or_create(session, Grape, g_name)
        session.add(WineGrapeLink(wine_id=wine.id, grape_id=grape.id))

    offer = RetailerWine(
        retailer_id=retailer.id,
        wine_id=wine.id,
        price=price,
        url=url,
        available=True,
        image_url=image_url,
    )
    session.add(offer)

async def seed_wines_from_csvs(session: AsyncSession) -> None:
    for csv_info in CSV_FILES:
        if not csv_info.path.exists():
            continue

        with csv_info.path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                await _upsert_offer_from_row(session, csv_info, row)

    await session.commit()
