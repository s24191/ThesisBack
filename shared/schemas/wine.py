from decimal import Decimal

from typing import Optional
from sqlmodel import SQLModel


class WineBase(SQLModel):
    name: str
    year: Optional[int] = None
    alc_perc: Optional[float] = None
    capacity_ml: Optional[int] = None

    country_id: int
    region_id: Optional[int] = None
    wine_type_id: int
    taste_profile_id: int


class WineRead(WineBase):
    id: int

class WineCardOffer(SQLModel):
    shop_name: str
    shop_url: str
    price: Decimal
    image_url: Optional[str] = None

class WineCardRead(SQLModel):
    id: int

    name: str
    year: Optional[int] = None
    country: str
    region: Optional[str] = None
    wine_type: str
    taste: Optional[str] = None

    rating: Optional[float] = None
    ratings_count: int = 0

    best_price: Optional[Decimal] = None
    offers: list[WineCardOffer] = []

    image_url: Optional[str] = None


class WineCreate(WineBase):
    pass
