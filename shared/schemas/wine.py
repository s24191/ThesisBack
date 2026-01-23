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


class WineCreate(WineBase):
    pass
