from fastapi import APIRouter, Depends, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from features.administration.lookups import queries , actions
from shared.auth.admin import current_admin
from shared.database import get_session
from shared.schemas.wine import  WineRead, WineCreate

from features.administration.lookups. schemas import (
    CountryCreate,
    CountryRead,
    CountryUpdate,
    GrapeCreate,
    GrapeRead,
    GrapeUpdate,
    PaginatedWineRows,
    RegionCreate,
    RegionRead,
    RegionUpdate,
    RetailerCreate,
    RetailerRead,
    RetailerUpdate,
    TasteProfileCreate,
    TasteProfileRead,
    TasteProfileUpdate,
    WineTypeCreate,
    WineTypeRead,
    WineTypeUpdate,
    WineUpdate,
)


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


@router.get(
    "/countries",
    response_model=list[CountryRead],
)
async def list_countries(
    session: AsyncSession = Depends(get_session),
):
    return await queries.list_countries(session)


@router.post(
    "/countries",
    response_model=CountryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_country(
    payload: CountryCreate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.create_country(session, payload)


@router.patch(
    "/countries/{country_id}",
    response_model=CountryRead,
)
async def update_country(
    country_id: int,
    payload: CountryUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.update_country(
        session,
        country_id,
        payload,
    )


@router.delete(
    "/countries/{country_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_country(
    country_id: int,
    session: AsyncSession = Depends(get_session),
):
    await actions.delete_country(session, country_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/wine-types",
    response_model=list[WineTypeRead],
)
async def list_wine_types(
    session: AsyncSession = Depends(get_session),
):
    return await queries.list_wine_types(session)


@router.post(
    "/wine-types",
    response_model=WineTypeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_wine_type(
    payload: WineTypeCreate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.create_wine_type(session, payload)


@router.patch(
    "/wine-types/{wine_type_id}",
    response_model=WineTypeRead,
)
async def update_wine_type(
    wine_type_id: int,
    payload: WineTypeUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.update_wine_type(
        session,
        wine_type_id,
        payload,
    )


@router.delete(
    "/wine-types/{wine_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wine_type(
    wine_type_id: int,
    session: AsyncSession = Depends(get_session),
):
    await actions.delete_wine_type(session, wine_type_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/regions",
    response_model=list[RegionRead],
)
async def list_regions(
    country_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await queries.list_regions(session, country_id)


@router.post(
    "/regions",
    response_model=RegionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_region(
    payload: RegionCreate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.create_region(session, payload)


@router.patch(
    "/regions/{region_id}",
    response_model=RegionRead,
)
async def update_region(
    region_id: int,
    payload: RegionUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.update_region(
        session,
        region_id,
        payload,
    )


@router.delete(
    "/regions/{region_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_region(
    region_id: int,
    session: AsyncSession = Depends(get_session),
):
    await actions.delete_region(session, region_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/taste-profiles",
    response_model=list[TasteProfileRead],
)
async def list_taste_profiles(
    session: AsyncSession = Depends(get_session),
):
    return await queries.list_taste_profiles(session)


@router.post(
    "/taste-profiles",
    response_model=TasteProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_taste_profile(
    payload: TasteProfileCreate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.create_taste_profile(
        session,
        payload,
    )


@router.patch(
    "/taste-profiles/{taste_profile_id}",
    response_model=TasteProfileRead,
)
async def update_taste_profile(
    taste_profile_id: int,
    payload: TasteProfileUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.update_taste_profile(
        session,
        taste_profile_id,
        payload,
    )


@router.delete(
    "/taste-profiles/{taste_profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_taste_profile(
    taste_profile_id: int,
    session: AsyncSession = Depends(get_session),
):
    await actions.delete_taste_profile(
        session,
        taste_profile_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/grapes",
    response_model=list[GrapeRead],
)
async def list_grapes(
    session: AsyncSession = Depends(get_session),
):
    return await queries.list_grapes(session)


@router.post(
    "/grapes",
    response_model=GrapeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_grape(
    payload: GrapeCreate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.create_grape(session, payload)


@router.patch(
    "/grapes/{grape_id}",
    response_model=GrapeRead,
)
async def update_grape(
    grape_id: int,
    payload: GrapeUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.update_grape(
        session,
        grape_id,
        payload,
    )


@router.delete(
    "/grapes/{grape_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_grape(
    grape_id: int,
    session: AsyncSession = Depends(get_session),
):
    await actions.delete_grape(session, grape_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/retailers",
    response_model=list[RetailerRead],
)
async def list_retailers(
    session: AsyncSession = Depends(get_session),
):
    return await queries.list_retailers(session)


@router.post(
    "/retailers",
    response_model=RetailerRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_retailer(
    payload: RetailerCreate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.create_retailer(session, payload)


@router.patch(
    "/retailers/{retailer_id}",
    response_model=RetailerRead,
)
async def update_retailer(
    retailer_id: int,
    payload: RetailerUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.update_retailer(
        session,
        retailer_id,
        payload,
    )


@router.delete(
    "/retailers/{retailer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_retailer(
    retailer_id: int,
    session: AsyncSession = Depends(get_session),
):
    await actions.delete_retailer(session, retailer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/wines",
    response_model=PaginatedWineRows,
)
async def admin_list_wines(
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
    country: str | None = None,
    region: str | None = None,
    sort: str | None = None,
    country_id: int | None = None,
    region_id: int | None = None,
    wine_type_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await queries.list_admin_wines(
        session,
        limit=limit,
        offset=offset,
        search=search,
        country=country,
        region=region,
        sort=sort,
        country_id=country_id,
        region_id=region_id,
        wine_type_id=wine_type_id,
    )


@router.get(
    "/wines/{wine_id}",
    response_model=WineRead,
)
async def admin_get_wine(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    wine = await queries.get_wine(session, wine_id)

    if wine is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wine not found",
        )

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
    return await actions.create_wine(session, payload)


@router.patch(
    "/wines/{wine_id}",
    response_model=WineRead,
)
async def admin_update_wine(
    wine_id: int,
    payload: WineUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await actions.update_wine(
        session,
        wine_id,
        payload,
    )


@router.delete(
    "/wines/{wine_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_wine(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
):
    await actions.delete_wine(session, wine_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)