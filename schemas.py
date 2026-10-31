"""
MovieBox API Pro — https://github.com/faisaljs/Moviebox-API
Author: Faisal (https://github.com/faisaljs)
License: MIT
"""

from pydantic import BaseModel, Field


class BookmarkIn(BaseModel):
    slug: str = Field(min_length=1)
    name: str | None = None
    poster_url: str | None = None
    rating: str | None = None
    year: str | None = None
    badge: str | None = None


class HistoryIn(BaseModel):
    slug: str = Field(min_length=1)
    se: int = Field(ge=0)
    ep: int = Field(ge=0)
    name: str | None = None
    poster_url: str | None = None
    position: int = Field(default=0, ge=0)
    duration: int = Field(default=0, ge=0)