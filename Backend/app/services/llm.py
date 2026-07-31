from __future__ import annotations

import json
import logging
from typing import Any

from mistralai.client import Mistral

from app.config import Settings
from app.models.schemas import DocChunk, Slide

logger = logging.getLogger(__name__)


ANALYSIS_SYSTEM_PROMPT = """You are an assistant that relates slide components to a supporting document.
The document is a deeper, more detailed version of the slide deck.

Given a list of slide components (each with an id and text) and relevant document passages,
return a JSON object mapping each component id to an object with:
  - "context": a concise explanation (2–5 sentences) of what this component means,
    grounded in the document passages. If the document does not cover it, say so briefly.
  - "sources": a list of source labels (from the provided passages) that support the context.

Only use the provided document passages. Do not invent facts.
Respond with ONLY valid JSON of the form:
{
  "<component_id>": {"context": "...", "sources": ["..."]},
  ...
}
"""


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

        res = self._client.chat.complete(**kwargs)
        content = res.choices[0].message.content
        if isinstance(content, list):
            # Some SDK versions may return content parts.
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

    def relate_slide_components(
        self,
        slide: Slide,
        retrieved_chunks: list[DocChunk],
    ) -> dict[str, dict[str, Any]]:
        """
        Call the LLM once per slide to produce per-component context.
        Returns a dict keyed by component_id -> {context, sources}.
        """
        if not slide.components:
            return {}

        components_payload = [
            {"id": c.id, "type": c.type.value, "text": c.text}
            for c in slide.components
        ]
        passages_payload = [
            {"source": ch.source, "text": ch.text} for ch in retrieved_chunks
        ]

        user_content = json.dumps(
            {
                "slide_index": slide.index,
                "notes": slide.notes,
                "components": components_payload,
                "document_passages": passages_payload,
            },
            ensure_ascii=False,
        )

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
    ) -> str:
        passages = "\n\n".join(
            f"[{ch.source}]\n{ch.text}" for ch in retrieved_chunks
        ) or "(no document passages retrieved)"

        user_parts = []
        if anchor_text:
            user_parts.append(f"Focus / anchor context:\n{anchor_text}")
        if question:
            user_parts.append(f"User request:\n{question}")
        user_parts.append(f"Supporting document passages:\n{passages}")

        return self.chat(
            [
                {"role": "system", "content": _mode_system_prompt(mode)},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            temperature=0.4,
        )
