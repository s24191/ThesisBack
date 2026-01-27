from typing import List, Optional
from sqlmodel import SQLModel

class WineOffer(SQLModel):
    shop_name: str
    shop_url: str
    price: float
    image_url: Optional[str] = None


class WineDetail(SQLModel):
    id: int
    name: str
    year: Optional[int] = None

    country: str
    region: Optional[str] = None

    type_of_wine: str
    taste: Optional[str] = None

    grapes: Optional[str] = None

    alc_perc: Optional[float] = None
    capacity_ml: Optional[int] = None

    rating: Optional[float] = None
    ratings_count: Optional[int] = None

    offers: List[WineOffer]
