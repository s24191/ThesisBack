from fastapi import HTTPException, status
from sqlmodel import select
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

from features.administration.lookups.schemas import (
    CountryCreate,
    CountryUpdate,
    GrapeCreate,
    GrapeUpdate,
    RegionCreate,
    RegionUpdate,
    RetailerCreate,
    RetailerUpdate,
    TasteProfileCreate,
    TasteProfileUpdate,
    WineTypeCreate,
    WineTypeUpdate,
    WineUpdate,
)
from shared.schemas.wine import WineCreate


async def create_country(
    session: AsyncSession,
    payload: CountryCreate,
) -> Country:
    name = payload.name.strip()

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Country name is required",
        )

    existing_result = await session.execute(
        select(Country).where(Country.name == name)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Country already exists",
        )

    country = Country(name=name)
    session.add(country)
    await session.commit()
    await session.refresh(country)
    return country


async def update_country(
    session: AsyncSession,
    country_id: int,
    payload: CountryUpdate,
) -> Country:
    country = await session.get(Country, country_id)

    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Country not found",
        )

    if payload.name is not None:
        name = payload.name.strip()

        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Country name cannot be empty",
            )

        existing_result = await session.execute(
            select(Country).where(
                Country.name == name,
                Country.id != country_id,
            )
        )

        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Country already exists",
            )

        country.name = name

    await session.commit()
    await session.refresh(country)
    return country


async def delete_country(
    session: AsyncSession,
    country_id: int,
) -> None:
    country = await session.get(Country, country_id)

    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Country not found",
        )

    wines_result = await session.execute(
        select(Wine).where(Wine.country_id == country_id)
    )
    if wines_result.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete country because wines are using it",
        )

    regions_result = await session.execute(
        select(Region).where(Region.country_id == country_id)
    )
    if regions_result.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete country because regions are using it",
        )

    await session.delete(country)
    await session.commit()


async def create_wine_type(
    session: AsyncSession,
    payload: WineTypeCreate,
) -> WineType:
    name = payload.name.strip()

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wine type name is required",
        )

    existing_result = await session.execute(
        select(WineType).where(WineType.name == name)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wine type already exists",
        )

    wine_type = WineType(name=name)
    session.add(wine_type)
    await session.commit()
    await session.refresh(wine_type)
    return wine_type


async def update_wine_type(
    session: AsyncSession,
    wine_type_id: int,
    payload: WineTypeUpdate,
) -> WineType:
    wine_type = await session.get(WineType, wine_type_id)

    if not wine_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wine type not found",
        )

    if payload.name is not None:
        name = payload.name.strip()

        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Wine type name cannot be empty",
            )

        existing_result = await session.execute(
            select(WineType).where(
                WineType.name == name,
                WineType.id != wine_type_id,
            )
        )

        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Wine type already exists",
            )

        wine_type.name = name

    await session.commit()
    await session.refresh(wine_type)
    return wine_type


async def delete_wine_type(
    session: AsyncSession,
    wine_type_id: int,
) -> None:
    wine_type = await session.get(WineType, wine_type_id)

    if not wine_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wine type not found",
        )

    wines_result = await session.execute(
        select(Wine).where(Wine.wine_type_id == wine_type_id)
    )
    if wines_result.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete wine type because wines are using it",
        )

    await session.delete(wine_type)
    await session.commit()


async def create_region(
    session: AsyncSession,
    payload: RegionCreate,
) -> Region:
    name = payload.name.strip()

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Region name is required",
        )

    country = await session.get(Country, payload.country_id)
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Country not found",
        )

    existing_result = await session.execute(
        select(Region).where(
            Region.name == name,
            Region.country_id == payload.country_id,
        )
    )

    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Region already exists for this country",
        )

    region = Region(
        name=name,
        country_id=payload.country_id,
    )
    session.add(region)
    await session.commit()
    await session.refresh(region)
    return region


async def update_region(
    session: AsyncSession,
    region_id: int,
    payload: RegionUpdate,
) -> Region:
    region = await session.get(Region, region_id)

    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found",
        )

    new_name = region.name
    new_country_id = region.country_id

    if payload.name is not None:
        new_name = payload.name.strip()

        if not new_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Region name cannot be empty",
            )

    if payload.country_id is not None:
        country = await session.get(Country, payload.country_id)

        if not country:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Country not found",
            )

        new_country_id = payload.country_id

    existing_result = await session.execute(
        select(Region).where(
            Region.name == new_name,
            Region.country_id == new_country_id,
            Region.id != region_id,
        )
    )

    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Region already exists for this country",
        )

    region.name = new_name
    region.country_id = new_country_id

    await session.commit()
    await session.refresh(region)
    return region


async def delete_region(
    session: AsyncSession,
    region_id: int,
) -> None:
    region = await session.get(Region, region_id)

    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found",
        )

    wines_result = await session.execute(
        select(Wine).where(Wine.region_id == region_id)
    )
    if wines_result.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete region because wines are using it",
        )

    await session.delete(region)
    await session.commit()


async def create_taste_profile(
    session: AsyncSession,
    payload: TasteProfileCreate,
) -> TasteProfile:
    name = payload.name.strip()

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Taste profile name is required",
        )

    existing_result = await session.execute(
        select(TasteProfile).where(TasteProfile.name == name)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Taste profile already exists",
        )

    taste_profile = TasteProfile(name=name)
    session.add(taste_profile)
    await session.commit()
    await session.refresh(taste_profile)
    return taste_profile


async def update_taste_profile(
    session: AsyncSession,
    taste_profile_id: int,
    payload: TasteProfileUpdate,
) -> TasteProfile:
    taste_profile = await session.get(
        TasteProfile,
        taste_profile_id,
    )

    if not taste_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Taste profile not found",
        )

    if payload.name is not None:
        name = payload.name.strip()

        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Taste profile name cannot be empty",
            )

        existing_result = await session.execute(
            select(TasteProfile).where(
                TasteProfile.name == name,
                TasteProfile.id != taste_profile_id,
            )
        )
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Taste profile already exists",
            )

        taste_profile.name = name

    await session.commit()
    await session.refresh(taste_profile)
    return taste_profile


async def delete_taste_profile(
    session: AsyncSession,
    taste_profile_id: int,
) -> None:
    taste_profile = await session.get(
        TasteProfile,
        taste_profile_id,
    )

    if not taste_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Taste profile not found",
        )

    wines_result = await session.execute(
        select(Wine).where(
            Wine.taste_profile_id == taste_profile_id
        )
    )
    if wines_result.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot delete taste profile because wines are using it"
            ),
        )

    await session.delete(taste_profile)
    await session.commit()


async def create_grape(
    session: AsyncSession,
    payload: GrapeCreate,
) -> Grape:
    name = payload.name.strip()

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grape name is required",
        )

    existing_result = await session.execute(
        select(Grape).where(Grape.name == name)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Grape already exists",
        )

    grape = Grape(name=name)
    session.add(grape)
    await session.commit()
    await session.refresh(grape)
    return grape


async def update_grape(
    session: AsyncSession,
    grape_id: int,
    payload: GrapeUpdate,
) -> Grape:
    grape = await session.get(Grape, grape_id)

    if not grape:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grape not found",
        )

    if payload.name is not None:
        name = payload.name.strip()

        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Grape name cannot be empty",
            )

        existing_result = await session.execute(
            select(Grape).where(
                Grape.name == name,
                Grape.id != grape_id,
            )
        )
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Grape already exists",
            )

        grape.name = name

    await session.commit()
    await session.refresh(grape)
    return grape


async def delete_grape(
    session: AsyncSession,
    grape_id: int,
) -> None:
    grape = await session.get(Grape, grape_id)

    if not grape:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grape not found",
        )

    links_result = await session.execute(
        select(WineGrapeLink).where(
            WineGrapeLink.grape_id == grape_id
        )
    )
    if links_result.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete grape because wines are using it",
        )

    await session.delete(grape)
    await session.commit()


async def create_retailer(
    session: AsyncSession,
    payload: RetailerCreate,
) -> Retailer:
    name = payload.name.strip()
    url = payload.url.strip()

    if not name or not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name and URL are required",
        )

    existing_result = await session.execute(
        select(Retailer).where(Retailer.name == name)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Retailer already exists",
        )

    retailer = Retailer(name=name, url=url)
    session.add(retailer)
    await session.commit()
    await session.refresh(retailer)
    return retailer


async def update_retailer(
    session: AsyncSession,
    retailer_id: int,
    payload: RetailerUpdate,
) -> Retailer:
    retailer = await session.get(Retailer, retailer_id)

    if not retailer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Retailer not found",
        )

    if payload.name is not None:
        name = payload.name.strip()

        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Retailer name cannot be empty",
            )

        retailer.name = name

    if payload.url is not None:
        url = payload.url.strip()

        if not url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Retailer URL cannot be empty",
            )

        retailer.url = url

    await session.commit()
    await session.refresh(retailer)
    return retailer


async def delete_retailer(
    session: AsyncSession,
    retailer_id: int,
) -> None:
    retailer = await session.get(Retailer, retailer_id)

    if not retailer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Retailer not found",
        )

    offers_result = await session.execute(
        select(RetailerWine).where(
            RetailerWine.retailer_id == retailer_id
        )
    )
    if offers_result.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete retailer because offers are using it",
        )

    await session.delete(retailer)
    await session.commit()


async def create_wine(
    session: AsyncSession,
    payload: WineCreate,
) -> Wine:
    country = await session.get(Country, payload.country_id)
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Country not found",
        )

    if payload.region_id is not None:
        region = await session.get(Region, payload.region_id)

        if not region:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Region not found",
            )

    wine_type = await session.get(
        WineType,
        payload.wine_type_id,
    )
    if not wine_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wine type not found",
        )

    taste_profile = await session.get(
        TasteProfile,
        payload.taste_profile_id,
    )
    if not taste_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Taste profile not found",
        )

    wine = Wine(**payload.dict())
    session.add(wine)
    await session.commit()
    await session.refresh(wine)
    return wine


async def update_wine(
    session: AsyncSession,
    wine_id: int,
    payload: WineUpdate,
) -> Wine:
    wine = await session.get(Wine, wine_id)

    if not wine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wine not found",
        )

    if payload.name is not None:
        wine.name = payload.name.strip()

    if payload.year is not None:
        wine.year = payload.year

    if payload.alc_perc is not None:
        wine.alc_perc = payload.alc_perc

    if payload.capacity_ml is not None:
        wine.capacity_ml = payload.capacity_ml

    if payload.country_id is not None:
        country = await session.get(Country, payload.country_id)

        if not country:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Country not found",
            )

        wine.country_id = payload.country_id

    if payload.region_id is not None:
        if payload.region_id == 0:
            wine.region_id = None
        else:
            region = await session.get(
                Region,
                payload.region_id,
            )

            if not region:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Region not found",
                )

            wine.region_id = payload.region_id

    if payload.wine_type_id is not None:
        wine_type = await session.get(
            WineType,
            payload.wine_type_id,
        )

        if not wine_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wine type not found",
            )

        wine.wine_type_id = payload.wine_type_id

    if payload.taste_profile_id is not None:
        taste_profile = await session.get(
            TasteProfile,
            payload.taste_profile_id,
        )

        if not taste_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Taste profile not found",
            )

        wine.taste_profile_id = payload.taste_profile_id

    await session.commit()
    await session.refresh(wine)
    return wine


async def delete_wine(
    session: AsyncSession,
    wine_id: int,
) -> None:
    wine = await session.get(Wine, wine_id)

    if not wine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wine not found",
        )

    await session.delete(wine)
    await session.commit()