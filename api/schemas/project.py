from pydantic import BaseModel

class EmbCreate(BaseModel):
    id: int | None = None
    name: str  # Project name

class EmbGet(BaseModel):
    id: int
    name: str  # Project name

