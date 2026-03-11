from pydantic import BaseModel

from schemas.agents import Chunk


class ChunkPage(BaseModel):
    items: list[Chunk]
    page: int
    size: int
    total: int
