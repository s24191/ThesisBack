from typing import List, Optional
from sqlmodel import SQLModel
from decimal import Decimal

class WineOffer(SQLModel):
    shop_name: str
    shop_url: str
    price: float
    image_url: Optional[str] = None
    available: bool

class WineDetail(SQLModel):
    id: int
    name: str
    year: Optional[int] = None

    country: str
    region: Optional[str] = None

    wine_type: str
    taste: Optional[str] = None

    grapes: Optional[str] = None

    alc_perc: Optional[float] = None
    capacity_ml: Optional[int] = None

    rating: Optional[float] = None
    ratings_count: Optional[int] = None
    available: bool = False
    offers: List[WineOffer]
    best_price: Optional[Decimal] = None

    image_url: Optional[str] = None

class WineListItem(SQLModel):
    id: int
    name: str

    country: str
    region: Optional[str] = None

    rating: Optional[float] = None
    ratings_count: Optional[int] = None

    best_price: Optional[float] = None
    offers: List[WineOffer] = []

