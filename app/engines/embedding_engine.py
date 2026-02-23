# app/engines/embedding_engine.py
from typing import List
from app.config import settings

class HFEmbeddingEngine:
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

    def embed(self, inputs: List[str]) -> List[List[float]]:
        model = self._ensure_model()
        vecs = model.encode(inputs, normalize_embeddings=True)
        return vecs.tolist()
