from sqlmodel import SQLModel

class WineTasteVoteCreate(SQLModel):
    body: int
    tannin: int
    sweetness: int
    acidity: int

class WineTasteVoteRead(SQLModel):
    body: int
    tannin: int
    sweetness: int
    acidity: int

class WineTasteSummary(SQLModel):
    body: float
    tannin: float
    sweetness: float
    acidity: float
    votes_count: int
