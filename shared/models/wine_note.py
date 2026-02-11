from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint


class WineNote(SQLModel, table=True):
    __tablename__ = "wine_notes"
    __table_args__ = (
        UniqueConstraint("wine_id", "text", name="uq_wine_note_text_per_wine"),
    )

    id: int = Field(default=None, primary_key=True)
    wine_id: int = Field(foreign_key="wine.id", index=True)
    text: str = Field(max_length=100, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    votes_count: int = Field(default=0, index=True)

    wine: "Wine" = Relationship(back_populates="notes")
    votes: list["WineNoteVote"] = Relationship(back_populates="note")


class WineNoteVote(SQLModel, table=True):
    __tablename__ = "wine_note_votes"
    __table_args__ = (
        UniqueConstraint("user_id", "note_id", name="uq_user_note_vote"),
    )

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    note_id: int = Field(foreign_key="wine_notes.id", primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    note: WineNote = Relationship(back_populates="votes")
