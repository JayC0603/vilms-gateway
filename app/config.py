# app/config.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, List

import yaml


def _normalize_params(params: Any) -> Dict[str, Any]:
    # Supports:
    # params:
    #   - temperature: 0.7
    #   - max-tokens: 1024
    if params is None:
        return {}
    if isinstance(params, dict):
        return dict(params)
    if isinstance(params, list):
        out: Dict[str, Any] = {}
        for item in params:
            if isinstance(item, dict) and len(item) == 1:
                k, v = next(iter(item.items()))
                out[str(k)] = v
        return out
    return {}


def _normalize_model_type(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().lower()
    aliases = {
        "text": "llm",
        "chat": "llm",
        "llm": "llm",
        "vision": "vlm",
        "multimodal": "vlm",
        "vlm": "vlm",
        "embed": "embedding",
        "embedding": "embedding",
        "rerank": "reranker",
        "reranker": "reranker",
    }
    return aliases.get(raw, raw)


def _normalize_model_engine(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().lower()
    if raw in {"ollama", "vllm", "openai"}:
        return raw
    return raw


def _normalize_model_aliases(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, list):
        out: List[str] = []
        seen = set()
        for item in value:
            if not isinstance(item, str):
                continue
            alias = item.strip()
            if not alias or alias in seen:
                continue
            seen.add(alias)
            out.append(alias)
        return out
    return []


class AppConfig:
    """
    Minimal YAML config loader.
    Default path: ./app/configs/config.yaml
    """

    def __init__(self, path: Optional[str] = None):
        base_dir = Path(__file__).resolve().parent  # .../app
        self.path = Path(path) if path else (base_dir / "configs" / "config.yaml")
        self.data: Dict[str, Any] = {}

        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                self.data = yaml.safe_load(f) or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def serving(self) -> Dict[str, Any]:
        return self.data.get("serving", {}) if isinstance(self.data.get("serving"), dict) else {}

    @property
    def host(self) -> Dict[str, Any]:
        return self.data.get("host", {}) if isinstance(self.data.get("host"), dict) else {}

    @property
    def engine(self) -> str:
        return str(self.serving.get("engine", "ollama"))

    @property
    def base_url(self) -> str:
        return str(self.serving.get("base-url", ""))

    @property
    def ollama_base_url(self) -> str:
        return str(self.serving.get("ollama-base-url", "")) or self.base_url

    @property
    def vllm_base_url(self) -> str:
        return str(self.serving.get("vllm-base-url", "")) or self.base_url

    @property
    def models(self) -> List[Dict[str, Any]]:
        raw = self.serving.get("models", [])
        if not isinstance(raw, list):
            return []
        out: List[Dict[str, Any]] = []
        for m in raw:
            if not isinstance(m, dict):
                continue
            m2 = dict(m)
            m2["name"] = str(m.get("name", "")).strip()
            m2["params"] = _normalize_params(m.get("params"))
            # Optional per-model metadata for extensible routing/selection.
            m2["type"] = _normalize_model_type(m.get("type"))
            m2["engine"] = _normalize_model_engine(m.get("engine", m.get("backend")))
            m2["aliases"] = _normalize_model_aliases(m.get("aliases"))
            out.append(m2)
        return out

    def resolve_alias(self, model: str) -> str:
        current = model
        seen = set()
        aliases = self.MODEL_ALIASES

        while isinstance(current, str) and current in aliases and current not in seen:
            seen.add(current)
            nxt = aliases.get(current)
            if not isinstance(nxt, str) or not nxt or nxt == current:
                break
            current = nxt
        return current

    def find_model(self, model: str) -> Optional[Dict[str, Any]]:
        """Find model metadata by requested name, alias, or canonical name."""
        if not isinstance(model, str) or not model.strip():
            return None

        requested = model.strip()
        canonical = self.resolve_alias(requested)

        for m in self.models:
            name = str(m.get("name", "")).strip()
            if not name:
                continue
            if requested == name or canonical == name:
                return m
            aliases = m.get("aliases", [])
            if isinstance(aliases, list) and (requested in aliases or canonical in aliases):
                return m
        return None

    # ---------- Compatibility aliases (so existing code using settings.ENGINE works) ----------
    @property
    def ENGINE(self) -> str:
        return self.engine

    @property
    def MODELS(self) -> List[Dict[str, Any]]:
        return self.models

    # ---------- Extra convenience properties ----------
    @property
    def HOST_PLATFORM(self) -> str:
        return str(self.host.get("platform", "dgpu"))

    @property
    def OLLAMA_BASE_URL(self) -> str:
        return self.ollama_base_url

    @property
    def BASE_URL(self) -> str:
        # Backward-compatible alias for code paths expecting the primary (vLLM) URL.
        return self.vllm_base_url

    @property
    def VLLM_BASE_URL(self) -> str:
        return self.vllm_base_url

    @property
    def DEFAULT_MAX_FRAMES(self) -> int:
        # If not set in YAML, fallback 8
        return int(self.serving.get("default-max-frames", 8))

    @property
    def MODEL_ALIASES(self) -> Dict[str, str]:
        aliases = self.data.get("model-aliases", {})
        out = dict(aliases) if isinstance(aliases, dict) else {}
        # Allow local aliases directly in serving.models[*].aliases without forcing duplication
        # in the global "model-aliases" block.
        for m in self.models:
            name = m.get("name")
            if not isinstance(name, str) or not name:
                continue
            for alias in m.get("aliases", []):
                if alias not in out:
                    out[alias] = name
        return out

    @property
    def EMBEDDING_MODEL(self) -> str:
        embedding = self.data.get("embedding", {}) or {}
        return str(embedding.get("model", ""))

    @property
    def EMBEDDING_BASE_URL(self) -> str:
        embedding = self.data.get("embedding", {}) or {}
        return str(embedding.get("base-url", ""))

    @property
    def EMBEDDING_ENABLED(self) -> bool:
        embedding = self.data.get("embedding", {}) or {}
        return bool(embedding.get("enabled", False))


config = AppConfig()
settings = config
