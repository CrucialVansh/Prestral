from __future__ import annotations

import json
import logging
import time
from typing import Any

from mistralai.client import Mistral

from app.config import Settings
from app.models.schemas import DocChunk, Slide

logger = logging.getLogger(__name__)


def _retry_with_backoff(func, max_retries: int = 5, base_delay: float = 1.0):
    """
    Retry a function with exponential backoff for rate limits (429) and temporary errors.
    
    The Mistral SDK raises SDKError (from httpx) which has a status_code attribute.
    
    Args:
        func: Function to call (should take no arguments)
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds (doubles each retry)
    
    Returns:
        The result of func() if successful
    
    Raises:
        Exception: The last exception if all retries fail
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            # Check if it's a rate limit error (429)
            if hasattr(e, 'status_code'):
                if e.status_code == 429:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "Rate limited (429). Attempt %d/%d. Retrying in %.1fs...",
                        attempt + 1, max_retries, delay
                    )
                    time.sleep(delay)
                    continue
                # For server errors (5xx), also retry
                if 500 <= e.status_code < 600:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "Server error (%d). Attempt %d/%d. Retrying in %.1fs...",
                        e.status_code, attempt + 1, max_retries, delay
                    )
                    time.sleep(delay)
                    continue
            # For connection errors or other transient errors, retry
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "Error: %s. Attempt %d/%d. Retrying in %.1fs...",
                    str(e), attempt + 1, max_retries, delay
                )
                time.sleep(delay)
                continue
            # Non-retryable error or last attempt
            raise
    
    raise last_exception


ANALYSIS_SYSTEM_PROMPT = """You are an assistant that relates slide components to a supporting document.
The document is a deeper, more detailed version of the slide deck.

Given a list of slide components (each with an id and text) and relevant document passages,
return a JSON object mapping each component id to an object with:
  - "context": a concise explanation (2–5 sentences) of what this component means,
    grounded in the document passages (and any attached images for picture components).
    If the document does not cover it, say so briefly.
  - "sources": a list of source labels (from the provided passages) that support the context.

Some picture components may include an image in this request. Describe what the image shows
when relevant, and relate it to the document. Ignore native charts/decorative shapes — only
embedded pictures are provided as images.

Only use the provided document passages and images. Do not invent facts.
Respond with ONLY valid JSON of the form:
{
  "<component_id>": {"context": "...", "sources": ["..."]},
  ...
}
"""


def _image_content_part(data_uri: str) -> dict[str, Any]:
    """Mistral multimodal image part (data URI or URL)."""
    return {"type": "image_url", "image_url": data_uri}

_AUDIENCE_GUIDANCE: dict[str, str] = {
    "general": (
        "Audience: a general professional reader. Use clear language, light jargon, "
        "and a balanced level of detail. Define uncommon terms briefly."
    ),
    "swe": (
        "Audience: a software engineer. Prefer technical precision, systems thinking, "
        "implementation implications, trade-offs, and concrete mechanisms. "
        "Jargon is OK when accurate; skip fluff and marketing spin."
    ),
    "marketing": (
        "Audience: a marketing professional. Emphasize positioning, narrative, audience "
        "impact, messaging hooks, and competitive differentiation. Keep technical depth light "
        "unless it affects the story; translate metrics into what they mean for go-to-market."
    ),
    "executive": (
        "Audience: an executive / decision-maker. Lead with the so-what, risks, and decisions. "
        "Be concise, prioritize outcomes and numbers, minimize implementation detail."
    ),
    "sales": (
        "Audience: a sales professional. Focus on customer value, objections, proof points, "
        "and how to pitch this slide beat. Keep it actionable and buyer-facing."
    ),
    "student": (
        "Audience: a student learning the topic. Explain step-by-step, define terms, "
        "use simple analogies, and avoid assuming prior domain expertise."
    ),
    "designer": (
        "Audience: a product/UX designer. Emphasize user impact, flows, clarity of the slide's "
        "message, and how information hierarchy or visuals support understanding."
    ),
    "finance": (
        "Audience: a finance / analyst reader. Emphasize numbers, drivers, margins, assumptions, "
        "and variance. Be precise with figures and call out what is / isn't supported by the doc."
    ),
}


def normalize_audience(audience: str | None) -> str:
    value = (audience or "general").strip()
    return value if value else "general"


def _audience_system_prompt(audience: str) -> str:
    key = normalize_audience(audience).lower()
    preset = _AUDIENCE_GUIDANCE.get(key)
    if preset:
        return preset
    # Free-text role from the frontend (e.g. "junior PM at a B2B SaaS startup")
    return (
        f"Audience / role: {normalize_audience(audience)}. "
        "Adapt complexity, vocabulary, examples, and framing to what this person needs. "
        "Do not over-explain basics they would already know; do not drown them in "
        "irrelevant detail for their role. Stay faithful to the supporting document."
    )


def _mode_system_prompt(mode: str) -> str:
    if mode == "summarize":
        return (
            "You are a helpful presentation assistant. Summarize the given slide/component "
            "content clearly and concisely, using the supporting document passages. "
            "Cite sources by their labels when relevant."
        )
    if mode == "explain":
        return (
            "You are a helpful presentation assistant. Provide a deeper explanation of the "
            "given slide/component, expanding with details from the supporting document. "
            "Use the document as the primary source of truth. Cite source labels when relevant."
        )
    return (
        "You are a helpful presentation assistant. Answer the user's question about the "
        "slides using the supporting document passages and any provided component/slide context. "
        "Be accurate and cite source labels when relevant. If the answer is not in the materials, say so."
    )


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._client = Mistral(api_key=settings.mistral_api_key)
        self._model = settings.mistral_chat_model

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        json_mode: bool = False,
        temperature: float = 0.3,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        # Use retry logic for rate limits and temporary errors
        def _do_chat():
            res = self._client.chat.complete(**kwargs)
            content = res.choices[0].message.content
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, str):
                        parts.append(part)
                    elif isinstance(part, dict) and "text" in part:
                        parts.append(part["text"])
                    else:
                        parts.append(str(part))
                return "".join(parts)
            return content or ""
        
        return _retry_with_backoff(_do_chat, max_retries=5, base_delay=2.0)

    def relate_slide_components(
        self,
        slide: Slide,
        retrieved_chunks: list[DocChunk],
        images: dict[str, str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Call the LLM once per slide to produce per-component context.

        ``images`` maps component_id -> data URI for embedded PPTX pictures only.
        """
        if not slide.components:
            return {}

        images = images or {}
        components_payload = [
            {
                "id": c.id,
                "type": c.type.value,
                "text": c.text,
                "has_image": c.id in images,
            }
            for c in slide.components
        ]
        passages_payload = [
            {"source": ch.source, "text": ch.text} for ch in retrieved_chunks
        ]

        text_payload = json.dumps(
            {
                "slide_index": slide.index,
                "notes": slide.notes,
                "components": components_payload,
                "document_passages": passages_payload,
                "image_note": (
                    "Following images are labeled by component_id in order. "
                    "Use them only for components with has_image=true."
                ),
            },
            ensure_ascii=False,
        )

        # Multimodal user content: text JSON + up to N picture data URIs.
        user_parts: list[Any] = [{"type": "text", "text": text_payload}]
        for comp in slide.components:
            data_uri = images.get(comp.id)
            if not data_uri:
                continue
            user_parts.append(
                {"type": "text", "text": f"Image for component_id={comp.id}:"}
            )
            user_parts.append(_image_content_part(data_uri))

        user_content: Any = user_parts if len(user_parts) > 1 else text_payload

        try:
            raw = self.chat(
                [
                    {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                json_mode=True,
                temperature=0.2,
            )
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                logger.warning("LLM analysis returned non-dict JSON for slide %s", slide.index)
                return {}
            return parsed
        except Exception as exc:
            logger.warning("LLM analysis failed for slide %s: %s", slide.index, exc)
            return {}

    def answer_query(
        self,
        *,
        mode: str,
        question: str,
        anchor_text: str,
        retrieved_chunks: list[DocChunk],
        audience: str = "general",
        image_data_uri: str | None = None,
    ) -> str:
        return self.answer_chat(
            mode=mode,
            question=question,
            anchor_text=anchor_text,
            retrieved_chunks=retrieved_chunks,
            history=[],
            audience=audience,
            image_data_uri=image_data_uri,
        )

    def answer_chat(
        self,
        *,
        mode: str,
        question: str,
        anchor_text: str,
        retrieved_chunks: list[DocChunk],
        history: list[dict[str, str]],
        audience: str = "general",
        image_data_uri: str | None = None,
    ) -> str:
        """
        Multi-turn answer. ``history`` is prior [{role, content}, ...] excluding
        the current user turn (passed as ``question``).

        When ``image_data_uri`` is set (embedded PPTX picture), it is attached to
        the current user turn for multimodal reasoning.
        """
        passages = "\n\n".join(
            f"[{ch.source}]\n{ch.text}" for ch in retrieved_chunks
        ) or "(no document passages retrieved)"

        system = (
            _mode_system_prompt(mode)
            + "\n\n"
            + _audience_system_prompt(audience)
            + "\n\nYou are in a multi-turn chat about a specific slide component. "
            "Stay focused on that component and the supporting document. "
            "Use prior turns for continuity when the user refers to earlier answers."
        )
        if image_data_uri:
            system += (
                " An image of the focus component (embedded slide picture) is attached "
                "to the latest user message — use it together with the document."
            )

        grounding = []
        if anchor_text:
            grounding.append(f"Focus / anchor context:\n{anchor_text}")
        grounding.append(f"Supporting document passages:\n{passages}")

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {
                "role": "system",
                "content": "Grounding materials for this turn:\n\n" + "\n\n".join(grounding),
            },
        ]

        for turn in history:
            role = turn.get("role", "user")
            if role not in ("user", "assistant"):
                continue
            content = (turn.get("content") or "").strip()
            if content:
                messages.append({"role": role, "content": content})

        user_text = question.strip() or (
            "Please continue based on the mode and the focus component."
            if mode != "ask"
            else "Please answer based on the focus component and documents."
        )
        if mode == "summarize" and not question.strip():
            user_text = "Summarize the focus component using the supporting document."
        elif mode == "explain" and not question.strip():
            user_text = "Explain the focus component in more depth using the supporting document."

        if image_data_uri:
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        _image_content_part(image_data_uri),
                    ],
                }
            )
        else:
            messages.append({"role": "user", "content": user_text})

        return self.chat(messages, temperature=0.4)
