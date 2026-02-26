# app/factory.py
from app.config import settings
from app.engines.ollama_engine import OllamaEngine
from app.engines.vllm_engine import VLLMEngine
from app.engines.embedding_engine import HFEmbeddingEngine, RemoteEmbeddingEngine


class EngineFactory:
    def __init__(self):
        self.ollama = OllamaEngine(settings.OLLAMA_BASE_URL)
        self.vllm = VLLMEngine()
        if settings.EMBEDDING_ENABLED:
            self.embedding = (
                RemoteEmbeddingEngine(settings.EMBEDDING_BASE_URL)
                if getattr(settings, "EMBEDDING_BASE_URL", "").strip()
                else HFEmbeddingEngine()
            )
        else:
            self.embedding = None

    def get_engine(self, name: str):
        engine = (name or "").strip().lower()
        if engine == "ollama":
            return self.ollama
        if engine == "vllm":
            return self.vllm
        raise ValueError(f"Unsupported engine: {name}")

    def resolve_chat_engine_name(self, model: str) -> str:
        """
        Decide which engine should handle a chat completion.

        Priority:
        - Global serving.engine=ollama -> force ollama
        - Jetson -> prefer ollama
        - Per-model engine override in config (serving.models[*].engine)
        - Per-model type=vlm -> ollama
        - Fallback legacy heuristic on model name ("vl")
        - Default -> vllm
        """
        model = model or ""
        model_cfg = settings.find_model(model)

        # If user config chooses ollama engine, force route to ollama
        if getattr(settings, "ENGINE", "").lower() == "ollama":
            return "ollama"

        # Jetson: prefer Ollama for both LLM and VLM
        if settings.HOST_PLATFORM == "js":
            return "ollama"

        if isinstance(model_cfg, dict):
            model_engine = (model_cfg.get("engine") or "").strip().lower()
            if model_engine in {"ollama", "vllm"}:
                return model_engine

        if isinstance(model_cfg, dict):
            model_type = (model_cfg.get("type") or "").strip().lower()
            if model_type == "vlm":
                return "ollama"
            if model_type == "llm":
                return "vllm"

        # Backward-compatible fallback when model metadata is absent
        if "VL" in model or "vl" in model:
            return "ollama"
        return "vllm"

    def resolve_chat_engine(self, model: str):
        return self.get_engine(self.resolve_chat_engine_name(model))

    def map_model_alias(self, model: str) -> str:
        # Resolve chained aliases, e.g. LLM -> Qwen3-4B-Instruct -> qwen3:4b-instruct
        return settings.resolve_alias(model)
