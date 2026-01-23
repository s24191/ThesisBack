from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from shared.models.base import Base


class Country(Base, table=True):
    name: str = Field(index=True, unique=True)

    regions: List["Region"] = Relationship(back_populates="country")
    wines: List["Wine"] = Relationship(back_populates="country")


class Region(Base, table=True):
    name: str = Field(index=True)
    country_id: int = Field(foreign_key="country.id", index=True)

    country: "Country" = Relationship(back_populates="regions")
    wines: List["Wine"] = Relationship(back_populates="region")

class WineType(Base, table=True):
    name: str = Field(index=True, unique=True)

    wines: List["Wine"] = Relationship(back_populates="wine_type")

class TasteProfile(Base, table=True):
    name: str = Field(index=True, unique=True)

    wines: List["Wine"] = Relationship(back_populates="taste_profile")

class Grape(Base, table=True):
    name: str = Field(index=True, unique=True)

    wines_link: List["WineGrapeLink"] = Relationship(back_populates="grape")

class WineGrapeLink(SQLModel, table=True):
    wine_id: int = Field(foreign_key="wine.id", primary_key=True)
    grape_id: int = Field(foreign_key="grape.id", primary_key=True)
    percentage: Optional[int] = Field(default=None)

    wine: "Wine" = Relationship(back_populates="grapes_link")
    grape: Grape = Relationship(back_populates="wines_link")


# Vivino

class VivinoWine(Base, table=True):
    average_rating: Optional[float] = Field(default=None)
    ratings_count: Optional[int] = Field(default=None)
    tasting_notes: Optional[str] = None
    food_pairings: Optional[str] = None
    link: Optional[str] = None

    wines: List["Wine"] = Relationship(back_populates="vivino_wine")


# Retailers & offers

class Retailer(Base, table=True):
    name: str = Field(index=True, unique=True)
    url: str

    offers: List["RetailerWine"] = Relationship(back_populates="retailer")


class RetailerWine(Base, table=True):
    retailer_id: int = Field(foreign_key="retailer.id", index=True)
    wine_id: int = Field(foreign_key="wine.id", index=True)

    price: float
    last_update: Optional[str] = None  # later: datetime
    available: bool = Field(default=True)
    url: str
    external_sku: Optional[str] = None

    image_url: Optional[str] = None

    retailer: Retailer = Relationship(back_populates="offers")
    wine: "Wine" = Relationship(back_populates="retailer_offers")


# ---------- Core wine entity ----------

class Wine(Base, table=True):
    name: str = Field(index=True)
    year: Optional[int] = Field(default=None, index=True)
    alc_perc: Optional[float] = Field(default=None)
    capacity_ml: Optional[int] = Field(default=None)

    country_id: int = Field(foreign_key="country.id", index=True)
    region_id: Optional[int] = Field(default=None, foreign_key="region.id")

    wine_type_id: int = Field(foreign_key="winetype.id", index=True)
    taste_profile_id: int = Field(
        foreign_key="tasteprofile.id", index=True
    )

    vivino_wine_id: Optional[int] = Field(
        default=None, foreign_key="vivinowine.id"
    )

    country: Country = Relationship(back_populates="wines")
    region: Optional[Region] = Relationship(back_populates="wines")
    wine_type: WineType = Relationship(back_populates="wines")
    taste_profile: TasteProfile = Relationship(back_populates="wines")
    vivino_wine: Optional[VivinoWine] = Relationship(back_populates="wines")

    grapes_link: List[WineGrapeLink] = Relationship(back_populates="wine")
    retailer_offers: List[RetailerWine] = Relationship(
        back_populates="wine"
    )
