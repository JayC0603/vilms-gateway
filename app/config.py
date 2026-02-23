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
            m2["params"] = _normalize_params(m.get("params"))
            out.append(m2)
        return out

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
        return dict(aliases) if isinstance(aliases, dict) else {}

    @property
    def EMBEDDING_MODEL(self) -> str:
        embedding = self.data.get("embedding", {}) or {}
        return str(embedding.get("model", ""))

    @property
    def EMBEDDING_ENABLED(self) -> bool:
        embedding = self.data.get("embedding", {}) or {}
        return bool(embedding.get("enabled", False))


config = AppConfig()
settings = config
