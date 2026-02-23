# app/services/optimizer.py
from __future__ import annotations

from copy import deepcopy
from app.config import settings


def optimize_payload(payload: dict) -> dict:
    """Trim image frames on Jetson while keeping the OpenAI vision schema."""
    if settings.HOST_PLATFORM != "js":
        return payload

    out = deepcopy(payload)
    messages = out.get("messages", [])

    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue

        text_items = [it for it in content if isinstance(it, dict) and it.get("type") == "text"]
        image_items = [it for it in content if isinstance(it, dict) and it.get("type") == "image_url"]

        if len(image_items) > settings.DEFAULT_MAX_FRAMES:
            image_items = image_items[-settings.DEFAULT_MAX_FRAMES :]

        msg["content"] = text_items + image_items

    out["messages"] = messages
    return out


class PayloadOptimizer:
    @staticmethod
    def process(payload: dict) -> dict:
        return optimize_payload(payload)
