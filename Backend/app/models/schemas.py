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


# Common presets the frontend can offer; any free-text role string is also accepted.
AUDIENCE_PRESETS = (
    "general",
    "swe",
    "marketing",
    "executive",
    "sales",
    "student",
    "designer",
    "finance",
)


class QueryRequest(BaseModel):
    question: str = ""
    mode: QueryMode = QueryMode.ASK
    slide_index: Optional[int] = None
    component_id: Optional[str] = None
    # Who is reading — controls depth, jargon, and framing (e.g. "swe", "marketing", or free text).
    audience: str = "general"


class SourceCitation(BaseModel):
    text: str
    source: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceCitation] = Field(default_factory=list)
    mode: QueryMode
    audience: str = "general"


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    id: str
    role: ChatRole
    content: str
    mode: Optional[QueryMode] = None
    sources: list[SourceCitation] = Field(default_factory=list)
    created_at: str


class ChatSession(BaseModel):
    """Multi-turn chat scoped to one deck component."""

    id: str
    deck_id: str
    component_id: str
    slide_index: int
    title: str = ""
    audience: str = "general"
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ChatSessionSummary(BaseModel):
    id: str
    deck_id: str
    component_id: str
    slide_index: int
    title: str
    audience: str = "general"
    message_count: int
    created_at: str
    updated_at: str


class CreateSessionRequest(BaseModel):
    component_id: str
    audience: str = "general"
    # If true, always create a new session even if one already exists for this component.
    force_new: bool = False


class UpdateSessionRequest(BaseModel):
    audience: Optional[str] = None


class SendMessageRequest(BaseModel):
    content: str = ""
    mode: QueryMode = QueryMode.ASK
    # Optional one-turn override; otherwise the session's audience is used.
    audience: Optional[str] = None


class SendMessageResponse(BaseModel):
    session_id: str
    user_message: ChatMessage
    assistant_message: ChatMessage
    audience: str = "general"


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
