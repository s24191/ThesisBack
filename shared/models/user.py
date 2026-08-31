from typing import List

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from fastapi_users_db_sqlmodel import SQLModelBaseUserDB


class User(SQLModelBaseUserDB, SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    username: str = Field(max_length=50, unique=True, index=True)
    first_name: str | None = Field(default=None, max_length=50)
    last_name: str | None = Field(default=None, max_length=50)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    filter_setting: str | None = Field(default=None)
    filter_active: bool = Field(default=False)

    wine_comments: List["WineComment"] = Relationship(back_populates="author")
    taste_votes: List["WineTasteVote"] = Relationship(back_populates="user")


    model_config = {
        "arbitrary_types_allowed": True,
    }
