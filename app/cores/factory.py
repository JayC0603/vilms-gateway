# app/factory.py
from app.config import settings
from app.engines.ollama_engine import OllamaEngine
from app.engines.vllm_engine import VLLMEngine
from app.engines.embedding_engine import HFEmbeddingEngine


class EngineFactory:
    def __init__(self):
        self.ollama = OllamaEngine(settings.OLLAMA_BASE_URL)
        self.vllm = VLLMEngine()
        self.embedding = HFEmbeddingEngine() if settings.EMBEDDING_ENABLED else None

    def get_engine(self, name: str):
        engine = (name or "").strip().lower()
        if engine == "ollama":
            return self.ollama
        if engine == "vllm":
            return self.vllm
        raise ValueError(f"Unsupported engine: {name}")

    def resolve_chat_engine(self, model: str):
        """
        Decide which engine should handle chat completion.

        Priority:
        - If config ENGINE=ollama -> always use ollama
        - If Jetson -> always use ollama
        - If dGPU -> use ollama for VL models, vllm for text models
        """

        # If user config chooses ollama engine, force route to ollama
        if getattr(settings, "ENGINE", "").lower() == "ollama":
            return self.ollama

        # Jetson: prefer Ollama for both LLM and VLM
        if settings.HOST_PLATFORM == "js":
            return self.ollama

        # dGPU: route as you prefer
        if "VL" in model or "vl" in model:
            return self.ollama

        return self.vllm

    def map_model_alias(self, model: str) -> str:
        # Resolve chained aliases, e.g. LLM -> Qwen3-4B-Instruct -> qwen3:4b-instruct
        current = model
        seen = set()
        aliases = settings.MODEL_ALIASES

        while isinstance(current, str) and current in aliases and current not in seen:
            seen.add(current)
            nxt = aliases.get(current)
            if not isinstance(nxt, str) or not nxt or nxt == current:
                break
            current = nxt

        return current
