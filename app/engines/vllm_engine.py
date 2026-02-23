# app/engines/vllm_engine.py
import httpx
from urllib.parse import urlparse, urlunparse
from .base import BaseViLMSEngine
from app.config import settings

class VLLMEngine(BaseViLMSEngine):
    def __init__(self):
        self.base_url = settings.VLLM_BASE_URL.rstrip("/")
        self.candidate_base_urls = self._build_candidate_base_urls(self.base_url)

    @staticmethod
    def _replace_host(base_url: str, host: str, default_port: int):
        parsed = urlparse(base_url)
        port = parsed.port or default_port
        netloc = f"{host}:{port}"
        return urlunparse((parsed.scheme or "http", netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

    @classmethod
    def _build_candidate_base_urls(cls, base_url: str):
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").lower()
        candidates = [base_url]

        if host == "localhost" or host == "127.0.0.1":
            candidates.append(cls._replace_host(base_url, "vilms-vllm", 8000))
        elif host.startswith("vilms-"):
            candidates.append(cls._replace_host(base_url, "localhost", 8000))
            candidates.append(cls._replace_host(base_url, "127.0.0.1", 8000))

        deduped = []
        for u in candidates:
            if u and u not in deduped:
                deduped.append(u)
        return deduped

    async def chat_completion(self, payload: dict):
        model = payload.get("model") or payload.get("model_name")
        if not model:
            raise ValueError("Missing 'model' in payload")

        async with httpx.AsyncClient(timeout=300) as client:
            tried = []
            for base in self.candidate_base_urls:
                # If BASE_URL is a format string (e.g. http://host:8000/{}/v1/chat/completions)
                url = base.format(model) if ("{" in base) else f"{base}/v1/chat/completions"
                tried.append(url)
                try:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    return resp.json()
                except httpx.RequestError:
                    continue

            raise RuntimeError(
                "Cannot connect to vLLM backend. Tried: " + ", ".join(tried) +
                ". Configure serving.base-url to either localhost or vilms-* service host depending on runtime."
            )
