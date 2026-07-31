"""
Pydantic request/response models for the Prestral API.

These schemas drive the OpenAPI / Swagger docs at ``/docs``. Field descriptions
here appear in the schema browser — keep them frontend-friendly.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ComponentType(StrEnum):
    """Shape/placeholder type detected from the PPTX."""

    TITLE = "title"
    BODY = "body"
    TEXT_BOX = "text_box"
    PICTURE = "picture"
    TABLE = "table"
    CHART = "chart"
    GROUP = "group"
    OTHER = "other"


class BBox(BaseModel):
    """
    Normalized bounding box as fractions of slide width/height (0–1).

    Map onto your slide viewport, e.g. ``left: bbox.left * containerWidth``.
    """

    left: float = Field(..., ge=0, le=1, description="Distance from slide left edge (0–1).")
    top: float = Field(..., ge=0, le=1, description="Distance from slide top edge (0–1).")
    width: float = Field(..., ge=0, le=1, description="Box width as fraction of slide width.")
    height: float = Field(..., ge=0, le=1, description="Box height as fraction of slide height.")


class ComponentContext(BaseModel):
    context: str = Field("", description="Doc-grounded explanation for this component.")
    sources: list[str] = Field(
        default_factory=list,
        description="Source labels from the supporting document(s), e.g. ``notes.docx:paragraph:3``.",
    )


class Component(BaseModel):
    """
    One hoverable/clickable region on a slide.

    Use ``id`` when opening a chat session or sending a scoped query.
    Use ``bbox`` to position the hotspot overlay.
    Use ``context`` for instant hover text (no extra API call).
    """

    id: str = Field(..., description="Stable id, e.g. ``slide0-shape2``. Use for sessions/query.")
    type: ComponentType = Field(..., description="Detected shape type.")
    bbox: BBox = Field(..., description="Normalized position/size for overlays.")
    text: str = Field("", description="Extracted text from the shape (may be empty for images).")
    context: str = Field(
        "",
        description="LLM explanation linking this shape to the supporting doc(s). Safe for hover UI.",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Document source labels that support ``context``.",
    )


class Slide(BaseModel):
    """One slide and its interactive components."""

    index: int = Field(..., ge=0, description="Zero-based slide index.")
    notes: str = Field("", description="Speaker notes (not a hotspot; useful as side-panel context).")
    components: list[Component] = Field(
        default_factory=list,
        description="Hotspots to overlay on this slide.",
    )


class DocChunk(BaseModel):
    """Internal RAG chunk (not usually sent to the frontend)."""

    text: str
    source: str
    embedding: list[float] | None = None


class Deck(BaseModel):
    """Full in-memory representation of a processed deck (server-side)."""

    id: str
    slides_filename: str
    doc_filename: str
    doc_filenames: list[str] = Field(default_factory=list)
    slides: list[Slide] = Field(default_factory=list)
    doc_chunks: list[DocChunk] = Field(default_factory=list)
    source: str = Field("upload", description="``upload`` or ``google_drive``.")


class DeckSummary(BaseModel):
    """Lightweight deck row for list views."""

    id: str = Field(..., description="Deck id — keep this for all later calls.")
    slides_filename: str
    doc_filename: str = Field(..., description="Comma-joined doc names when multiple docs were used.")
    slide_count: int
    source: str = Field("upload", description="``upload`` or ``google_drive``.")


class DriveFileInfo(BaseModel):
    """A file discovered in Google Drive."""

    id: str = Field(..., description="Google Drive file id.")
    name: str = Field(..., description="Display filename.")
    mime_type: str
    kind: Literal["slides", "doc", "other"] = Field(
        "other",
        description="``slides`` = PPTX, ``doc`` = DOCX/PDF.",
    )
    modified_time: str | None = Field(None, description="ISO timestamp from Drive.")
    score: float | None = Field(
        None,
        description="Similarity score when auto-selected for RAG (higher = more relevant).",
    )


class DeckAnalysisResponse(BaseModel):
    """
    Primary payload after upload / Drive import / GET deck.

    Frontend flow: render each slide → overlay ``components[].bbox`` → hover shows
    ``context`` → click opens a session with ``component.id``.
    """

    id: str = Field(..., description="Deck id for query/sessions/get.")
    slides_filename: str
    doc_filename: str = Field(..., description="Human-readable doc label (may list several).")
    doc_filenames: list[str] = Field(
        default_factory=list,
        description="Individual supporting document filenames used for grounding.",
    )
    slides: list[Slide]
    source: str = Field("upload", description="``upload`` or ``google_drive``.")
    selected_docs: list[DriveFileInfo] = Field(
        default_factory=list,
        description="Drive docs chosen during import (empty for local upload).",
    )


class QueryMode(StrEnum):
    """Intent for single-shot query or a chat turn."""

    ASK = "ask"
    SUMMARIZE = "summarize"
    EXPLAIN = "explain"


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
    """Single-shot Q&A (no conversation history). Prefer sessions for multi-turn chat."""

    question: str = Field(
        "",
        description="Required when ``mode=ask``. Ignored/optional for summarize/explain.",
        examples=["What drove the revenue growth?"],
    )
    mode: QueryMode = Field(QueryMode.ASK, description="``ask`` | ``summarize`` | ``explain``.")
    slide_index: int | None = Field(
        None,
        description="Optional slide scope (0-based). Ignored if ``component_id`` is set.",
    )
    component_id: str | None = Field(
        None,
        description="Optional component scope, e.g. ``slide0-shape1``.",
        examples=["slide0-shape1"],
    )
    audience: str = Field(
        "general",
        description=(
            "Reader role controlling complexity/framing. Presets: "
            + ", ".join(AUDIENCE_PRESETS)
            + ". Free text also works."
        ),
        examples=["marketing"],
    )


class SourceCitation(BaseModel):
    """A retrieved document passage that grounded the answer."""

    text: str = Field(..., description="Passage text.")
    source: str = Field(..., description="Label such as ``notes.docx:paragraph:2``.")


class QueryResponse(BaseModel):
    answer: str = Field(..., description="Model answer grounded in the deck docs.")
    sources: list[SourceCitation] = Field(default_factory=list)
    mode: QueryMode
    audience: str = "general"


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """One turn in a component chat session."""

    id: str
    role: ChatRole
    content: str
    mode: QueryMode | None = None
    sources: list[SourceCitation] = Field(
        default_factory=list,
        description="Present on assistant messages when RAG retrieved passages.",
    )
    created_at: str = Field(..., description="ISO-8601 UTC timestamp.")


class ChatSession(BaseModel):
    """
    Multi-turn chat scoped to one component.

    Sessions are get-or-create on ``(deck_id, component_id)`` so revisiting the same
    hotspot resumes the same thread (unless ``force_new``).
    """

    id: str = Field(..., description="Session id — use for messages / get / patch / delete.")
    deck_id: str
    component_id: str = Field(..., description="Hotspot this chat is about.")
    slide_index: int
    title: str = Field("", description="Short label derived from component text.")
    audience: str = Field("general", description="Current reader role for this session.")
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ChatSessionSummary(BaseModel):
    """Row for a session switcher UI."""

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
    """Open or resume a chat for a hotspot."""

    component_id: str = Field(..., examples=["slide0-shape1"])
    audience: str = Field(
        "general",
        description="Reader role (preset or free text). Updates existing session if reopened.",
        examples=["swe"],
    )
    force_new: bool = Field(
        False,
        description="If true, start a fresh session even if one already exists for this component.",
    )


class UpdateSessionRequest(BaseModel):
    """Patch session settings without sending a chat message."""

    audience: str | None = Field(
        None,
        description="New reader role. Omit to leave unchanged.",
        examples=["executive"],
    )


class SendMessageRequest(BaseModel):
    """Send one user turn in a session (history is kept server-side)."""

    content: str = Field(
        "",
        description="User message. Required for ``mode=ask``; optional for summarize/explain.",
        examples=["Explain this like I'm in sales."],
    )
    mode: QueryMode = Field(QueryMode.ASK)
    audience: str | None = Field(
        None,
        description="Optional one-turn role override (also updates the session audience).",
    )


class SendMessageResponse(BaseModel):
    session_id: str
    user_message: ChatMessage
    assistant_message: ChatMessage
    audience: str = Field(..., description="Audience used for this turn.")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class StorageConnection(BaseModel):
    """A connected Google Drive account (in-memory until server restart)."""

    id: str = Field(..., description="Pass as ``connection_id`` to files/import.")
    provider: Literal["google_drive"] = "google_drive"
    email: str | None = None
    created_at: str


class GoogleAuthUrlResponse(BaseModel):
    auth_url: str = Field(..., description="Open this URL in a browser to authorize Drive.")
    state: str = Field(..., description="CSRF state (handled by the callback).")


class DriveFileListResponse(BaseModel):
    connection_id: str
    slides: list[DriveFileInfo] = Field(..., description="PPTX files available to import.")
    docs: list[DriveFileInfo] = Field(..., description="DOCX/PDF candidates for grounding.")


class DriveImportRequest(BaseModel):
    """
    Import a PPTX from Drive and ground it in supporting docs.

    Provide **either** ``connection_id`` (from OAuth callback) **or** a short-lived
    ``access_token`` from frontend Google login.
    """

    connection_id: str | None = Field(None, description="From ``/api/storage/google/callback``.")
    access_token: str | None = Field(
        None,
        description="Alternative to connection_id if the frontend completed Google OAuth.",
    )
    slides_file_id: str = Field(..., description="Drive file id of the PPTX to analyze.")
    doc_file_ids: list[str] = Field(
        default_factory=list,
        description="Explicit doc ids when ``auto_select_docs`` is false.",
    )
    auto_select_docs: bool = Field(
        True,
        description="If true, rank Drive docs against slide text and use the top matches.",
    )
    max_docs: int | None = Field(
        None,
        description="Cap on auto-selected docs (defaults to server ``DRIVE_MAX_AUTO_DOCS``).",
        ge=1,
    )
    folder_id: str | None = Field(
        None,
        description="Optional Drive folder to limit listing/ranking.",
    )


# Resolve forward refs (DeckAnalysisResponse.selected_docs → DriveFileInfo)
DeckAnalysisResponse.model_rebuild()
