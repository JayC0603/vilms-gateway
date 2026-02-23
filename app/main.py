# app/main.py
from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cores.factory import EngineFactory
from app.routes import router as api_router

# Load settings/config
# You need app/config.py to provide "settings" or "config".
# In our earlier fix, app/config.py provides "config".
from app.config import config as settings  # alias to keep your old variable name

# Optional: validate config at startup (if you added app/validator.py)
try:
    from app.services.validator import validate_config_file
except Exception:  # pragma: no cover
    validate_config_file = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vilms-gateway")

app = FastAPI(title="ViLMS Gateway")

# Allow browser clients to complete CORS preflight (OPTIONS) and call API routes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

engine = None
models = []


@app.on_event("startup")
def startup() -> None:
    global engine, models

    # Validate config.yaml early (fail fast)
    if validate_config_file is not None:
        res = validate_config_file(str(settings.path) if hasattr(settings, "path") else "./app/configs/config.yaml")
        if not res.ok:
            raise RuntimeError("Invalid config.yaml:\n" + "\n".join(res.errors))

    # Read engine/models from config
    engine_name = None
    if hasattr(settings, "engine"):
        engine_name = settings.engine
    else:
        # fallback if config shape changes
        engine_name = (settings.get("serving", {}) or {}).get("engine", "ollama")

    if hasattr(settings, "models"):
        models = settings.models
    else:
        models = (settings.get("serving", {}) or {}).get("models", [])

    engine = EngineFactory().get_engine(engine_name)
    logger.info("Gateway started. Engine=%s | Models=%s", engine_name, [m.get("name") for m in models if isinstance(m, dict)])
