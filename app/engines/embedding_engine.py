# app/engines/embedding_engine.py
from typing import List, Optional
from urllib.parse import urlparse, urlunparse

import httpx

from app.config import settings


class _BaseEmbeddingEngine:
    def embed(self, inputs: List[str], model_name: Optional[str] = None) -> List[List[float]]:
        raise NotImplementedError


class HFEmbeddingEngine(_BaseEmbeddingEngine):
    def __init__(self):
        aliases = settings.MODEL_ALIASES
        self.model_name = self._resolve_alias(
            aliases.get("Embedding")
            or aliases.get("Embbeding")
            or aliases.get("Qwen3-Embedding-4B")
            or aliases.get("Qwen3-Embbeding-4B")
            or settings.EMBEDDING_MODEL
            or "Qwen/Qwen3-Embedding-4B"
        )
        self.model = None

    def _resolve_alias(self, model_name: str) -> str:
        current = model_name
        seen = set()
        aliases = settings.MODEL_ALIASES

        while isinstance(current, str) and current in aliases and current not in seen:
            seen.add(current)
            nxt = aliases.get(current)
            if not isinstance(nxt, str) or not nxt or nxt == current:
                break
            current = nxt
        return current

    def _ensure_model(self):
        if self.model is not None:
            return self.model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers is not installed. Install it to enable embeddings."
            ) from e
        self.model = SentenceTransformer(self.model_name, trust_remote_code=True)
        return self.model

    def embed(self, inputs: List[str], model_name: Optional[str] = None) -> List[List[float]]:
        model = self._ensure_model()
        vecs = model.encode(inputs, normalize_embeddings=True)
        return vecs.tolist()


class RemoteEmbeddingEngine(_BaseEmbeddingEngine):
    def __init__(self, base_url: str):
        base = (base_url or "").rstrip("/")
        if base.endswith("/v1/embeddings"):
            self.url = base
        else:
            self.url = f"{base}/v1/embeddings"
        self.candidate_urls = self._build_candidate_urls(self.url)
        self.default_model_name = (
            settings.EMBEDDING_MODEL
            or "Qwen/Qwen3-Embedding-4B"
        )

    @staticmethod
    def _replace_host(url: str, host: str, default_port: int):
        parsed = urlparse(url)
        port = parsed.port or default_port
        netloc = f"{host}:{port}"
        return urlunparse((parsed.scheme or "http", netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

    @classmethod
    def _build_candidate_urls(cls, primary_url: str):
        parsed = urlparse(primary_url)
        host = (parsed.hostname or "").lower()
        candidates = [primary_url]

        if host in {"localhost", "127.0.0.1"}:
            candidates.append(cls._replace_host(primary_url, "vilms-embedding", 8001))
        elif host.startswith("vilms-"):
            candidates.append(cls._replace_host(primary_url, "localhost", 8001))
            candidates.append(cls._replace_host(primary_url, "127.0.0.1", 8001))

        deduped = []
        for u in candidates:
            if u and u not in deduped:
                deduped.append(u)
        return deduped

    def embed(self, inputs: List[str], model_name: Optional[str] = None) -> List[List[float]]:
        payload = {
            "model": model_name or self.default_model_name,
            "input": inputs,
        }

        tried = []
        last_http_error = None
        with httpx.Client(timeout=300) as client:
            for url in self.candidate_urls:
                tried.append(url)
                try:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    items = data.get("data")
                    if not isinstance(items, list):
                        raise RuntimeError("Invalid embedding response: missing 'data' list")
                    out: List[List[float]] = []
                    for i, item in enumerate(items):
                        if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                            raise RuntimeError(f"Invalid embedding response at data[{i}]")
                        out.append(item["embedding"])
                    return out
                except httpx.RequestError:
                    continue
                except httpx.HTTPStatusError as e:
                    last_http_error = e
                    continue

        if last_http_error is not None:
            raise RuntimeError(str(last_http_error)) from last_http_error
        raise RuntimeError(
            "Cannot connect to embedding backend. Tried: " + ", ".join(tried) +
            ". Configure embedding.base-url to either localhost or vilms-* service host depending on runtime."
        )
