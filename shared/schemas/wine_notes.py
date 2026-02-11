from datetime import datetime
from typing import List
from pydantic import BaseModel


class WineNoteBase(BaseModel):
    text: str


class WineNoteCreate(WineNoteBase):
    pass


class WineNoteRead(WineNoteBase):
    id: int
    wine_id: int
    votes_count: int
    created_at: datetime
    user_voted: bool = False


class WineNotesList(BaseModel):
    notes: List[WineNoteRead]
