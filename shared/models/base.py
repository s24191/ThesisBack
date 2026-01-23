from sqlmodel import SQLModel, Field


class Base(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
