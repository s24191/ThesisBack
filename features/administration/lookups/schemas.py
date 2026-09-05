from typing import Optional

from sqlmodel import SQLModel

from shared.schemas.wine import WineRead


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