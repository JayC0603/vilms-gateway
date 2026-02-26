# app/routes.py
from fastapi import APIRouter, HTTPException
from app.cores.factory import EngineFactory
from app.services.optimizer import optimize_payload
from app.schemas.openai import ChatRequest, EmbeddingRequest, EmbeddingResponse, EmbeddingObject

router = APIRouter()
factory = EngineFactory()

@router.get("/health_check")
def health_check():
    return {"status": "ok"}

@router.get("/v1/chat/completions")
def chat_completions_get_hint():
    return {
        "detail": "Method Not Allowed",
        "hint": "Use POST /v1/chat/completions with JSON body.",
    }

@router.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    requested_model = req.model
    payload = req.model_dump()
    try:
        # map alias: Qwen3-4B-Instruct -> qwen3:4b-instruct ...
        payload["model"] = factory.map_model_alias(payload["model"])
        payload = optimize_payload(payload)

        engine = factory.resolve_chat_engine(req.model)
        result = await engine.chat_completion(payload)
        if isinstance(result, dict):
            result["model"] = requested_model
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/v1/embeddings")
def embeddings_get_hint():
    return {
        "detail": "Method Not Allowed",
        "hint": "Use POST /v1/embeddings with JSON body.",
    }

@router.post("/v1/embeddings", response_model=EmbeddingResponse)
def embeddings(req: EmbeddingRequest):
    model_mapped = factory.map_model_alias(req.model)
    inputs = req.input if isinstance(req.input, list) else [req.input]

    try:
        if factory.embedding is None:
            raise HTTPException(status_code=400, detail="Embedding is disabled in config.")
        vecs = factory.embedding.embed(inputs, model_name=model_mapped)
        data = [EmbeddingObject(index=i, embedding=v) for i, v in enumerate(vecs)]
        return EmbeddingResponse(data=data, model=model_mapped, usage={"prompt_tokens": 0, "total_tokens": 0})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
