from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from shared.database import get_session
from shared.auth.user_binding import current_active_user
from shared.models.user import User
from shared.models.wine import Wine, RetailerWine, Country, Region, Retailer
from shared.models.wine_follow import WineFollow
from shared.schemas.followed_wine import FollowedWineItem

router = APIRouter(prefix="/wines", tags=["wines-follow"])

@router.post("/{wine_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def follow_wine(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    wine = await session.get(Wine, wine_id)
    if not wine:
        raise HTTPException(status_code=404, detail="Wine not found")

    stmt = select(WineFollow).where(
        WineFollow.user_id == user.id,
        WineFollow.wine_id == wine_id,
    )
    res = await session.execute(stmt)
    existing = res.one_or_none()
    if existing:
        return

    follow = WineFollow(user_id=user.id, wine_id=wine_id)
    session.add(follow)
    await session.commit()

@router.delete("/{wine_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_wine(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):

    res = await session.execute(
        select(WineFollow).where(
            WineFollow.user_id == user.id,
            WineFollow.wine_id == wine_id,
        )
    )
    follow = res.scalar_one_or_none()

    if follow is None:
        return

    await session.delete(follow)
    await session.commit()

@router.get("/me/followed", response_model=list[FollowedWineItem])
async def get_my_followed_wines(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    stmt = (
        select(Wine, Country, Region, RetailerWine, Retailer)
        .join(WineFollow, WineFollow.wine_id == Wine.id)
        .join(Country, Country.id == Wine.country_id)
        .join(Region, Region.id == Wine.region_id, isouter=True)
        .join(RetailerWine, RetailerWine.wine_id == Wine.id, isouter=True)
        .join(Retailer, Retailer.id == RetailerWine.retailer_id, isouter=True)
        .where(WineFollow.user_id == user.id)
    )
    res = await session.execute(stmt)
    rows = res.all()

    wines_map: dict[int, FollowedWineItem] = {}

    for wine, country, region, offer, retailer in rows:
        if wine.id not in wines_map:
            wines_map[wine.id] = FollowedWineItem(
                id=wine.id,
                name=wine.name,
                country=country.name,
                region=region.name if region else None,
                best_price=offer.price if offer else None,
                image_url=offer.image_url if offer else None,
            )
        else:
            dto = wines_map[wine.id]
            if offer and (dto.best_price is None or offer.price < dto.best_price):
                dto.best_price = offer.price
                dto.image_url = offer.image_url

    return list(wines_map.values())

@router.get("/{wine_id}/follow", response_model=bool)
async def is_following_wine(
    wine_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    stmt = select(WineFollow).where(
        WineFollow.user_id == user.id,
        WineFollow.wine_id == wine_id,
    )
    res = await session.execute(stmt)
    return res.first() is not None
