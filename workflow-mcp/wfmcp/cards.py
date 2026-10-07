"""Adaptive Card builders. One card shape for everything a workflow sends to Teams."""
from __future__ import annotations

from typing import Any

CARD_VERSION = "1.4"


def card(
    title: str,
    body: str = "",
    facts: dict[str, Any] | None = None,
    actions: list[dict] | None = None,
    footer: str = "",
) -> dict:
    items: list[dict] = [{"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium", "wrap": True}]
    if body:
        items.append({"type": "TextBlock", "text": body, "wrap": True})
    if facts:
        items.append({"type": "FactSet", "facts": [{"title": str(k), "value": _s(v)} for k, v in facts.items() if v not in (None, "")]})
    if footer:
        items.append({"type": "TextBlock", "text": footer, "isSubtle": True, "size": "Small", "wrap": True})
    c = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": CARD_VERSION,
        "body": items,
    }
    if actions:
        c["actions"] = actions
    return c


def open_url(title: str, url: str, style: str = "default") -> dict:
    return {"type": "Action.OpenUrl", "title": title, "url": url, "style": style}


def webhook_payload(card_json: dict) -> dict:
    """Body for a Teams Workflows 'post to channel when a webhook request is received' flow."""
    return {
        "type": "message",
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "contentUrl": None, "content": card_json}],
    }


def _s(v: Any) -> str:
    return "" if v is None else str(v)
