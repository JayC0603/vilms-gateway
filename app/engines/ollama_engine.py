# app/engines/ollama_engine.py
import base64
import time
import httpx
from urllib.parse import urlparse, urlunparse
from .base import BaseViLMSEngine

class OllamaEngine(BaseViLMSEngine):
    def __init__(self, base_url: str):
        base = base_url.rstrip("/")
        if base.endswith("/v1/chat/completions"):
            self.url = base
        else:
            self.url = f"{base}/v1/chat/completions"
        self.candidate_urls = self._build_candidate_urls(self.url)

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

        if host == "localhost" or host == "127.0.0.1":
            candidates.append(cls._replace_host(primary_url, "vilms-ollama", 11434))
        elif host.startswith("vilms-"):
            candidates.append(cls._replace_host(primary_url, "localhost", 11434))
            candidates.append(cls._replace_host(primary_url, "127.0.0.1", 11434))

        # keep order, remove duplicates
        deduped = []
        for u in candidates:
            if u and u not in deduped:
                deduped.append(u)
        return deduped

    @staticmethod
    def _to_native_chat_url(openai_url: str) -> str:
        parsed = urlparse(openai_url)
        return urlunparse(
            (
                parsed.scheme or "http",
                parsed.netloc,
                "/api/chat",
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )

    @staticmethod
    def _has_image_parts(payload: dict) -> bool:
        for msg in payload.get("messages", []) or []:
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    return True
        return False

    async def _image_url_to_base64(self, client: httpx.AsyncClient, url: str) -> str:
        if url.startswith("data:") and "," in url:
            # data:image/png;base64,<payload>
            return url.split(",", 1)[1]

        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode("ascii")

    async def _to_native_messages(self, client: httpx.AsyncClient, messages: list) -> list:
        native_messages = []
        for msg in messages or []:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, list):
                text_parts = []
                images = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    t = item.get("type")
                    if t == "text":
                        text_parts.append(str(item.get("text", "")))
                    elif t == "image_url":
                        image_obj = item.get("image_url") or {}
                        image_url = image_obj.get("url") if isinstance(image_obj, dict) else None
                        if not image_url:
                            continue
                        images.append(await self._image_url_to_base64(client, str(image_url)))

                native_msg = {"role": role, "content": "\n".join([p for p in text_parts if p])}
                if images:
                    native_msg["images"] = images
                native_messages.append(native_msg)
            else:
                native_messages.append({"role": role, "content": str(content or "")})

        return native_messages

    @staticmethod
    def _native_to_openai_response(native_resp: dict, model_name: str) -> dict:
        msg = native_resp.get("message") or {}
        prompt_tokens = int(native_resp.get("prompt_eval_count") or 0)
        completion_tokens = int(native_resp.get("eval_count") or 0)
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "system_fingerprint": "fp_ollama",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": msg.get("role", "assistant"),
                        "content": msg.get("content", ""),
                    },
                    "finish_reason": "stop" if native_resp.get("done", True) else None,
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    async def chat_completion(self, payload: dict):
        # OpenAI-style payload: {model, messages, stream, ...}
        has_images = self._has_image_parts(payload)
        ollama_payload = {
            "model": payload.get("model"),
            "messages": payload.get("messages", []),
            "stream": payload.get("stream", False),
        }

        # forward optional parameters when present
        for k in ("temperature", "max_tokens", "top_p", "presence_penalty", "frequency_penalty", "stop"):
            if k in payload and payload[k] is not None:
                ollama_payload[k] = payload[k]

        async with httpx.AsyncClient(timeout=300) as client:
            if has_images:
                native_payload = {
                    "model": payload.get("model"),
                    "messages": await self._to_native_messages(client, payload.get("messages", [])),
                    "stream": False,
                }
                options = {}
                if payload.get("temperature") is not None:
                    options["temperature"] = payload.get("temperature")
                if payload.get("top_p") is not None:
                    options["top_p"] = payload.get("top_p")
                if payload.get("max_tokens") is not None:
                    options["num_predict"] = payload.get("max_tokens")
                if payload.get("stop") is not None:
                    options["stop"] = payload.get("stop")
                if options:
                    native_payload["options"] = options

                tried = []
                for url in [self._to_native_chat_url(u) for u in self.candidate_urls]:
                    tried.append(url)
                    try:
                        resp = await client.post(url, json=native_payload)
                        resp.raise_for_status()
                        return self._native_to_openai_response(resp.json(), payload.get("model"))
                    except httpx.RequestError:
                        continue

                raise RuntimeError(
                    "Cannot connect to Ollama native chat backend. Tried: " + ", ".join(tried)
                )

            tried = []
            for url in self.candidate_urls:
                tried.append(url)
                try:
                    resp = await client.post(url, json=ollama_payload)
                    resp.raise_for_status()
                    return resp.json()
                except httpx.RequestError:
                    continue

            raise RuntimeError(
                "Cannot connect to Ollama backend. Tried: " + ", ".join(tried) +
                ". Configure serving.base-url to either localhost or vilms-ollama depending on runtime."
            )
