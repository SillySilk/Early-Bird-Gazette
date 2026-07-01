from __future__ import annotations

from pydantic import BaseModel, Field


class Parameter(BaseModel):
    key: str
    value: str
    unit: str | None = None


class RawRecord(BaseModel):
    external_id: str
    url: str | None = None
    author: str | None = None
    raw_text: str
    score: float | None = None
    upvotes: int | None = None
    metadata: dict = Field(default_factory=dict)


class Technique(BaseModel):
    id: int | None = None
    title: str
    summary: str
    body: str
    domain: str
    dedup_key: str
    cluster_id: int | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    is_actionable: bool = True
    status: str = "published"
    domain_meta: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
