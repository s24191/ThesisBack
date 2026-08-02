from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import SQLModel, select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.auth.admin import current_admin
from shared.database import get_session
from shared.models.wine import Country, Region, WineType, Wine, TasteProfile, WineGrapeLink, Grape, Retailer, \
    RetailerWine
from shared.schemas.wine import WineRead, WineCreate

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(current_admin)],
)
@router.get("")
async def admin_home():
    return {
        "message": "Admin panel access granted",
    }

class CountryRead(SQLModel):
    id: int
    name: str


class CountryCreate(SQLModel):
    name: str


class CountryUpdate(SQLModel):
    name: Optional[str] = None


class WineTypeRead(SQLModel):
    id: int
    name: str


class WineTypeCreate(SQLModel):
    name: str


class WineTypeUpdate(SQLModel):
    name: Optional[str] = None


class RegionRead(SQLModel):
    id: int
    name: str
    country_id: int


class RegionCreate(SQLModel):
    name: str
    country_id: int


class RegionUpdate(SQLModel):
    name: Optional[str] = None
    country_id: Optional[int] = None

class TasteProfileRead(SQLModel):
    id: int
    name: str


class TasteProfileCreate(SQLModel):
    name: str


class TasteProfileUpdate(SQLModel):
    name: Optional[str] = None

class GrapeRead(SQLModel):
    id: int
    name: str

class GrapeCreate(SQLModel):
    name: str


class GrapeUpdate(SQLModel):
    name: Optional[str] = None

class RetailerRead(SQLModel):
    id: int
    name: str
    url: str


class RetailerCreate(SQLModel):
    name: str
    url: str


class RetailerUpdate(SQLModel):
    name: Optional[str] = None
    url: Optional[str] = None

class AdminWineRow(WineRead):
    country: str | None = None
    region: str | None = None
    wine_type: str | None = None
    taste_profile: str | None = None

    taste_votes_count: int | None = None
    taste_average: float | None = None
    comments_count: int | None = None
    rating_average: float | None = None

class WineUpdate(SQLModel):
    name: Optional[str] = None
    year: Optional[int] = None
    alc_perc: Optional[float] = None
    capacity_ml: Optional[int] = None
    country_id: Optional[int] = None
    region_id: Optional[int] = None
    wine_type_id: Optional[int] = None
    taste_profile_id: Optional[int] = None

class PaginatedWineRows(SQLModel):
    items: list[AdminWineRow]
    total: int

@router.get("/countries", response_model=list[CountryRead])
async def list_countries(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Country).order_by(Country.name))
    return result.scalars().all()


@router.post(
    "/countries",
    response_model=CountryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_country(
    payload: CountryCreate,
    session: AsyncSession = Depends(get_session),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Country name is required")

    existing_result = await session.execute(
        select(Country).where(Country.name == name)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Country already exists")

    country = Country(name=name)
    session.add(country)
    await session.commit()
    await session.refresh(country)
    return country


@router.patch("/countries/{country_id}", response_model=CountryRead)
async def update_country(
    country_id: int,
    payload: CountryUpdate,
    session: AsyncSession = Depends(get_session),
):
    country = await session.get(Country, country_id)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Country name cannot be empty")

        existing_result = await session.execute(
            select(Country).where(Country.name == name, Country.id != country_id)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Country already exists")

        country.name = name

    await session.commit()
    await session.refresh(country)
    return country


@router.delete("/countries/{country_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_country(
    country_id: int,
    session: AsyncSession = Depends(get_session),
):
    country = await session.get(Country, country_id)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    wines_result = await session.execute(
        select(Wine).where(Wine.country_id == country_id)
    )
    has_wines = wines_result.first() is not None
    if has_wines:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete country because wines are using it",
        )

    regions_result = await session.execute(
        select(Region).where(Region.country_id == country_id)
    )
    has_regions = regions_result.first() is not None
    if has_regions:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete country because regions are using it",
        )

    await session.delete(country)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/wine-types", response_model=list[WineTypeRead])
async def list_wine_types(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(WineType).order_by(WineType.name))
    return result.scalars().all()


@router.post(
    "/wine-types",
    response_model=WineTypeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_wine_type(
    payload: WineTypeCreate,
    session: AsyncSession = Depends(get_session),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Wine type name is required")

    existing_result = await session.execute(
        select(WineType).where(WineType.name == name)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Wine type already exists")

    wine_type = WineType(name=name)
    session.add(wine_type)
    await session.commit()
    await session.refresh(wine_type)
    return wine_type


@router.patch("/wine-types/{wine_type_id}", response_model=WineTypeRead)
async def update_wine_type(
    wine_type_id: int,
    payload: WineTypeUpdate,
    session: AsyncSession = Depends(get_session),
):
    wine_type = await session.get(WineType, wine_type_id)
    if not wine_type:
        raise HTTPException(status_code=404, detail="Wine type not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Wine type name cannot be empty")

        existing_result = await session.execute(
            select(WineType).where(WineType.name == name, WineType.id != wine_type_id)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Wine type already exists")

        wine_type.name = name

    await session.commit()
    await session.refresh(wine_type)
    return wine_type


@router.delete("/wine-types/{wine_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wine_type(
    wine_type_id: int,
    session: AsyncSession = Depends(get_session),
):
    wine_type = await session.get(WineType, wine_type_id)
    if not wine_type:
        raise HTTPException(status_code=404, detail="Wine type not found")

    wines_result = await session.execute(
        select(Wine).where(Wine.wine_type_id == wine_type_id)
    )
    has_wines = wines_result.first() is not None
    if has_wines:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete wine type because wines are using it",
        )

    await session.delete(wine_type)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/regions", response_model=list[RegionRead])
async def list_regions(
    country_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Region).order_by(Region.name)

    if country_id is not None:
        stmt = stmt.where(Region.country_id == country_id)

    result = await session.execute(stmt)
    return result.scalars().all()


@router.post(
    "/regions",
    response_model=RegionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_region(
    payload: RegionCreate,
    session: AsyncSession = Depends(get_session),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Region name is required")

    country = await session.get(Country, payload.country_id)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    existing_result = await session.execute(
        select(Region).where(
            Region.name == name,
            Region.country_id == payload.country_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Region already exists for this country",
        )

    region = Region(name=name, country_id=payload.country_id)
    session.add(region)
    await session.commit()
    await session.refresh(region)
    return region


@router.patch("/regions/{region_id}", response_model=RegionRead)
async def update_region(
    region_id: int,
    payload: RegionUpdate,
    session: AsyncSession = Depends(get_session),
):
    region = await session.get(Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    new_name = region.name
    new_country_id = region.country_id

    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="Region name cannot be empty")

    if payload.country_id is not None:
        country = await session.get(Country, payload.country_id)
        if not country:
            raise HTTPException(status_code=404, detail="Country not found")
        new_country_id = payload.country_id

    existing_result = await session.execute(
        select(Region).where(
            Region.name == new_name,
            Region.country_id == new_country_id,
            Region.id != region_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Region already exists for this country",
        )

    region.name = new_name
    region.country_id = new_country_id

    await session.commit()
    await session.refresh(region)
    return region


@router.delete("/regions/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_region(
    region_id: int,
    session: AsyncSession = Depends(get_session),
):
    region = await session.get(Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    wines_result = await session.execute(
        select(Wine).where(Wine.region_id == region_id)
    )
    has_wines = wines_result.first() is not None
    if has_wines:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete region because wines are using it",
        )

    await session.delete(region)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/taste-profiles", response_model=list[TasteProfileRead])
async def list_taste_profiles(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(TasteProfile).order_by(TasteProfile.name))
    return result.scalars().all()


@router.post(
    "/taste-profiles",
    response_model=TasteProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_taste_profile(
    payload: TasteProfileCreate,
    session: AsyncSession = Depends(get_session),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Taste profile name is required")

    existing_result = await session.execute(
        select(TasteProfile).where(TasteProfile.name == name)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Taste profile already exists")

    taste_profile = TasteProfile(name=name)
    session.add(taste_profile)
    await session.commit()
    await session.refresh(taste_profile)
    return taste_profile


@router.patch(
    "/taste-profiles/{taste_profile_id}",
    response_model=TasteProfileRead,
)
async def update_taste_profile(
    taste_profile_id: int,
    payload: TasteProfileUpdate,
    session: AsyncSession = Depends(get_session),
):
    taste_profile = await session.get(TasteProfile, taste_profile_id)
    if not taste_profile:
        raise HTTPException(status_code=404, detail="Taste profile not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(
                status_code=400,
                detail="Taste profile name cannot be empty",
            )

        existing_result = await session.execute(
            select(TasteProfile).where(
                TasteProfile.name == name,
                TasteProfile.id != taste_profile_id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Taste profile already exists")

        taste_profile.name = name

    await session.commit()
    await session.refresh(taste_profile)
    return taste_profile


@router.delete(
    "/taste-profiles/{taste_profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_taste_profile(
    taste_profile_id: int,
    session: AsyncSession = Depends(get_session),
):
    taste_profile = await session.get(TasteProfile, taste_profile_id)
    if not taste_profile:
        raise HTTPException(status_code=404, detail="Taste profile not found")

    wines_result = await session.execute(
        select(Wine).where(Wine.taste_profile_id == taste_profile_id)
    )
    has_wines = wines_result.first() is not None
    if has_wines:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete taste profile because wines are using it",
        )

    await session.delete(taste_profile)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/grapes", response_model=list[GrapeRead])
async def list_grapes(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Grape).order_by(Grape.name))
    return result.scalars().all()


@router.post(
    "/grapes",
    response_model=GrapeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_grape(
    payload: GrapeCreate,
    session: AsyncSession = Depends(get_session),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Grape name is required")

    existing_result = await session.execute(
        select(Grape).where(Grape.name == name)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Grape already exists")

    grape = Grape(name=name)
    session.add(grape)
    await session.commit()
    await session.refresh(grape)
    return grape


@router.patch("/grapes/{grape_id}", response_model=GrapeRead)
async def update_grape(
    grape_id: int,
    payload: GrapeUpdate,
    session: AsyncSession = Depends(get_session),
):
    grape = await session.get(Grape, grape_id)
    if not grape:
        raise HTTPException(status_code=404, detail="Grape not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Grape name cannot be empty")

        existing_result = await session.execute(
            select(Grape).where(Grape.name == name, Grape.id != grape_id)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Grape already exists")

        grape.name = name

    await session.commit()
    await session.refresh(grape)
    return grape


@router.delete("/grapes/{grape_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grape(
    grape_id: int,
    session: AsyncSession = Depends(get_session),
):
    grape = await session.get(Grape, grape_id)
    if not grape:
        raise HTTPException(status_code=404, detail="Grape not found")

    links_result = await session.execute(
        select(WineGrapeLink).where(WineGrapeLink.grape_id == grape_id)
    )
    has_links = links_result.first() is not None
    if has_links:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete grape because wines are using it",
        )

    await session.delete(grape)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/retailers", response_model=list[RetailerRead])
async def list_retailers(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Retailer).order_by(Retailer.name))
    return result.scalars().all()


@router.post(
    "/retailers",
    response_model=RetailerRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_retailer(
    payload: RetailerCreate,
    session: AsyncSession = Depends(get_session),
):
    name = payload.name.strip()
    url = payload.url.strip()
    if not name or not url:
        raise HTTPException(status_code=400, detail="Name and URL are required")

    existing_result = await session.execute(
        select(Retailer).where(Retailer.name == name)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Retailer already exists")

    retailer = Retailer(name=name, url=url)
    session.add(retailer)
    await session.commit()
    await session.refresh(retailer)
    return retailer


@router.patch("/retailers/{retailer_id}", response_model=RetailerRead)
async def update_retailer(
    retailer_id: int,
    payload: RetailerUpdate,
    session: AsyncSession = Depends(get_session),
):
    retailer = await session.get(Retailer, retailer_id)
    if not retailer:
        raise HTTPException(status_code=404, detail="Retailer not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Retailer name cannot be empty")
        retailer.name = name

    if payload.url is not None:
        url = payload.url.strip()
        if not url:
            raise HTTPException(status_code=400, detail="Retailer URL cannot be empty")
        retailer.url = url

    await session.commit()
    await session.refresh(retailer)
    return retailer


@router.delete("/retailers/{retailer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_retailer(
    retailer_id: int,
    session: AsyncSession = Depends(get_session),
):
    retailer = await session.get(Retailer, retailer_id)
    if not retailer:
        raise HTTPException(status_code=404, detail="Retailer not found")

    offers_result = await session.execute(
        select(RetailerWine).where(RetailerWine.retailer_id == retailer_id)
    )
    has_offers = offers_result.first() is not None
    if has_offers:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete retailer because offers are using it",
        )

    await session.delete(retailer)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/wines", response_model=PaginatedWineRows)
async def admin_list_wines(
    limit: int = 100,
    offset: int = 0,
    country_id: int | None = None,
    region_id: int | None = None,
    wine_type_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    base_stmt = select(Wine)
    if country_id is not None:
        base_stmt = base_stmt.where(Wine.country_id == country_id)
    if region_id is not None:
        base_stmt = base_stmt.where(Wine.region_id == region_id)
    if wine_type_id is not None:
        base_stmt = base_stmt.where(Wine.wine_type_id == wine_type_id)

    total_result = await session.execute(select(func.count()).select_from(base_stmt.subquery()))
    total = total_result.scalar_one() or 0

    stmt = (
        select(Wine, Country, Region, WineType, TasteProfile)
        .join(Country, Country.id == Wine.country_id, isouter=True)
        .join(Region, Region.id == Wine.region_id, isouter=True)
        .join(WineType, WineType.id == Wine.wine_type_id, isouter=True)
        .join(TasteProfile, TasteProfile.id == Wine.taste_profile_id, isouter=True)
    )

    if country_id is not None:
        stmt = stmt.where(Wine.country_id == country_id)
    if region_id is not None:
        stmt = stmt.where(Wine.region_id == region_id)
    if wine_type_id is not None:
        stmt = stmt.where(Wine.wine_type_id == wine_type_id)

    stmt = stmt.order_by(Wine.id).offset(offset).limit(limit)

    result = await session.execute(stmt)
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
            country=country.name if country else None,
            region=region.name if region else None,
            wine_type=wine_type.name if wine_type else None,
            taste_profile=taste_profile.name if taste_profile else None,
            taste_votes_count=None,
            taste_average=None,
            comments_count=None,
            rating_average=None,
        )
        for wine, country, region, wine_type, taste_profile in rows
    ]

    return PaginatedWineRows(items=items, total=total)

@router.get("/wines/{wine_id}", response_model=WineRead)
async def admin_get_wine(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    wine = await session.get(Wine, wine_id)
    if not wine:
        raise HTTPException(status_code=404, detail="Wine not found")
    return wine

@router.post(
    "/wines",
    response_model=WineRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_wine(
    payload: WineCreate,
    session: AsyncSession = Depends(get_session),
):

    country = await session.get(Country, payload.country_id)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    if payload.region_id is not None:
        region = await session.get(Region, payload.region_id)
        if not region:
            raise HTTPException(status_code=404, detail="Region not found")

    wine_type = await session.get(WineType, payload.wine_type_id)
    if not wine_type:
        raise HTTPException(status_code=404, detail="Wine type not found")

    taste_profile = await session.get(TasteProfile, payload.taste_profile_id)
    if not taste_profile:
        raise HTTPException(status_code=404, detail="Taste profile not found")

    wine = Wine(**payload.dict())
    session.add(wine)
    await session.commit()
    await session.refresh(wine)
    return wine

@router.patch("/wines/{wine_id}", response_model=WineRead)
async def admin_update_wine(
    wine_id: int,
    payload: WineUpdate,
    session: AsyncSession = Depends(get_session),
):
    wine = await session.get(Wine, wine_id)
    if not wine:
        raise HTTPException(status_code=404, detail="Wine not found")


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
            raise HTTPException(status_code=404, detail="Country not found")
        wine.country_id = payload.country_id

    if payload.region_id is not None:
        if payload.region_id == 0:
            wine.region_id = None
        else:
            region = await session.get(Region, payload.region_id)
            if not region:
                raise HTTPException(status_code=404, detail="Region not found")
            wine.region_id = payload.region_id

    if payload.wine_type_id is not None:
        wine_type = await session.get(WineType, payload.wine_type_id)
        if not wine_type:
            raise HTTPException(status_code=404, detail="Wine type not found")
        wine.wine_type_id = payload.wine_type_id

    if payload.taste_profile_id is not None:
        taste_profile = await session.get(TasteProfile, payload.taste_profile_id)
        if not taste_profile:
            raise HTTPException(status_code=404, detail="Taste profile not found")
        wine.taste_profile_id = payload.taste_profile_id

    await session.commit()
    await session.refresh(wine)
    return wine

