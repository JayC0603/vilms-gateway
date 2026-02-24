# ViLMS Test Report

## 1. Summary

- Runtime validation (WSL/Docker, `2026-02-23`) completed for `LLM`, `VLM`, `VLM_SMALL`, `Embedding`
- Code regression checks (unit tests + config validation, `2026-02-24`) completed after Jetson/config-routing updates
- Current runtime bottleneck remains environment/resource limits (CPU-only Ollama in WSL)

## 2. Runtime Validation (WSL/Docker, 2026-02-23)

### Environment Summary

- Runtime: WSL + Docker Desktop
- Engine mode: `ollama`
- Gateway workers: tested with `1` and `2`
- Limitation: Ollama running on `CPU` (GPU not available in Windows/WSL at test time)

### Configured Models

- `LLM` -> `Qwen3-4B-Instruct` -> `qwen3:4b-instruct`
- `VLM` -> `Qwen3VL-4B-Instruct` -> `qwen3-vl:4b-instruct`
- `VLM_SMALL` -> `Moondream` -> `moondream`
- `Embedding` / `Embbeding` -> `Qwen3-Embedding-4B` -> `Qwen/Qwen3-Embedding-4B`

### Runtime Results

#### LLM (`LLM`)

- Status: `PASS`
- Result: `POST /v1/chat/completions` returns valid response
- Notes: Works on current machine in CPU mode

#### VLM (`VLM` = `qwen3-vl:4b-instruct`)

- Status: `FAIL (environment/resource)`
- Result: Gateway returns `400` because Ollama backend returns `500`
- Root cause from logs:
  - Ollama runs on `CPU`
  - Insufficient system memory to load VLM model
  - Errors observed: `cannot allocate memory`, `model request too large for system`

#### VLM Small (`VLM_SMALL` = `moondream`)

- Status: `PASS (infrastructure)`
- Text-only test:
  - Returns `200 OK`
  - Output may be empty / wrong language (model behavior issue, not infra issue)
- Image + text test:
  - Returns `200 OK`
  - Vision pipeline works through gateway after payload conversion fix

#### Embedding (`Embedding` / `Embbeding`)

- Status: `PARTIAL / HEAVY`
- Result:
  - Config and alias mapping are correct
  - First load is very slow (large HF model, CPU)
  - API calls may timeout during initial download/load
- Notes:
  - Hugging Face cache mount is used to persist downloads across restarts

## 3. Code Regression Checks (2026-02-24)

### Scope Verified

- Jetson-oriented `Ollama` image override in `spaw.sh` (`docker.image.ollama` / `OLLAMA_IMAGE`)
- Jetson worker auto-tuning (`host.platform=js` -> `uvicorn --workers 1`)
- Config-based model expansion metadata (`serving.models[*].type`, `engine`, `aliases`)
- Routing logic in `EngineFactory` (global force, Jetson preference, per-model metadata, fallback heuristic)
- README rewrite and Finetune/LoRA status docs

### Automated Checks

- `python -m unittest tests.test_factory_routing tests.test_api -v`
  - Status: `PASS`
  - Result: `8/8` tests passed
- `python -m app.services.validator --config app/configs/config.yaml`
  - Status: `PASS`
  - Result: `Config validation PASSED`

### Notes

- `tests/test_api.py` was updated to match current route behavior:
  - `GET /v1/chat/completions` returns `200` + JSON hint (not framework-generated `405`)
- No new runtime deployment test on Jetson hardware was performed in this verification cycle

## 4. Code / Config Changes Applied During Testing

- `docker-compose.yaml`
  - toggled `uvicorn --workers` for sequential/parallel testing
  - added HF cache mount for gateway (`HF_HOME`, `./assets/models/hf:/root/.cache/huggingface`)
- `spaw.sh`
  - worker setting logic aligned with runtime needs
  - added configurable Ollama image repo override for Jetson/ARM64
  - added Jetson-friendly worker auto-tuning and logging
- `start.sh`
  - display total models including embedding when enabled
- `yq`
  - use `python3` instead of `python` for WSL compatibility
- `app/routes.py`
  - GET hints for `/v1/chat/completions` and `/v1/embeddings` (avoid raw 405)
- `app/engines/ollama_engine.py`
  - added image support for Ollama via `/api/chat`
  - convert OpenAI-style `image_url` payload to Ollama native `images`
  - convert native Ollama response back to OpenAI-like response
  - follow redirects when fetching image URLs
- `app/configs/config.yaml`
  - added `moondream` and alias `VLM_SMALL`
  - added Jetson-oriented config examples/fields (`docker.image.ollama`, metadata support)
- `app/config.py`, `app/cores/factory.py`, `app/services/validator.py`
  - added config-based model metadata normalization/validation/routing (`type`, `engine`, `aliases`)
- `README.md`
  - rewritten for clearer onboarding, Jetson usage, and config-based expansion

## 5. Open Risks / Gaps

- Jetson hardware runtime test has not been executed yet after recent changes
- `Qwen3VL-4B-Instruct` still requires GPU-enabled runtime and sufficient memory
- Embedding model remains heavy for CPU-only bring-up scenarios
- Finetune/LoRA pipeline is not implemented in this repo (serving-only scope for now)

## 6. Recommendations

1. For stable validation on current machine, use `LLM` and `VLM_SMALL`; test `Embedding` separately.
2. For `Qwen3VL-4B-Instruct`, enable GPU on Windows/WSL/Docker and/or increase WSL RAM + swap.
3. For Jetson bring-up, start with `host.platform=js`, small models (`4B`), and `embedding.enabled=false`.
4. Run a real Jetson end-to-end smoke test after selecting a compatible ARM64 Ollama image.
