from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ComponentType(str, Enum):
    TITLE = "title"
    BODY = "body"
    TEXT_BOX = "text_box"
    PICTURE = "picture"
    TABLE = "table"
    CHART = "chart"
    GROUP = "group"
    OTHER = "other"


class BBox(BaseModel):
    """Normalized bounding box as fractions of slide width/height (0–1)."""

    left: float
    top: float
    width: float
    height: float


class ComponentContext(BaseModel):
    context: str = ""
    sources: list[str] = Field(default_factory=list)


class Component(BaseModel):
    id: str
    type: ComponentType
    bbox: BBox
    text: str = ""
    context: str = ""
    sources: list[str] = Field(default_factory=list)


class Slide(BaseModel):
    index: int
    notes: str = ""
    components: list[Component] = Field(default_factory=list)


class DocChunk(BaseModel):
    text: str
    source: str
    embedding: Optional[list[float]] = None


class Deck(BaseModel):
    """Full in-memory representation of a processed deck."""

    id: str
    slides_filename: str
    doc_filename: str
    slides: list[Slide] = Field(default_factory=list)
    doc_chunks: list[DocChunk] = Field(default_factory=list)


class DeckSummary(BaseModel):
    id: str
    slides_filename: str
    doc_filename: str
    slide_count: int


class DeckAnalysisResponse(BaseModel):
    """Public response returned to the frontend after upload / GET."""

    id: str
    slides_filename: str
    doc_filename: str
    slides: list[Slide]


class QueryMode(str, Enum):
    ASK = "ask"
    SUMMARIZE = "summarize"
    EXPLAIN = "explain"


class QueryRequest(BaseModel):
    question: str = ""
    mode: QueryMode = QueryMode.ASK
    slide_index: Optional[int] = None
    component_id: Optional[str] = None


class SourceCitation(BaseModel):
    text: str
    source: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceCitation] = Field(default_factory=list)
    mode: QueryMode


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
