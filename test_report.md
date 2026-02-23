# ViLMS Model Test Report (WSL/Docker, 2026-02-23)

## Environment Summary

- Runtime: WSL + Docker Desktop
- Engine mode: `ollama`
- Gateway workers: tested with `1` and `2`
- Current limitation: Ollama is running on `CPU` (GPU not available in Windows/WSL yet)

## Configured Models

- `LLM` -> `Qwen3-4B-Instruct` -> `qwen3:4b-instruct`
- `VLM` -> `Qwen3VL-4B-Instruct` -> `qwen3-vl:4b-instruct`
- `VLM_SMALL` -> `Moondream` -> `moondream`
- `Embedding` / `Embbeding` -> `Qwen3-Embedding-4B` -> `Qwen/Qwen3-Embedding-4B`

## Test Results

### 1. LLM (`LLM`)

- Status: `PASS`
- Result: `POST /v1/chat/completions` returns valid response
- Notes: Works on current machine in CPU mode

### 2. VLM (`VLM` = `qwen3-vl:4b-instruct`)

- Status: `FAIL (environment/resource)`
- Result: Gateway returns `400` because Ollama backend returns `500`
- Root cause from logs:
  - Ollama runs on `CPU`
  - Insufficient system memory to load VLM model
  - Errors observed: `cannot allocate memory`, `model request too large for system`

### 3. VLM Small (`VLM_SMALL` = `moondream`)

- Status: `PASS (infrastructure)`
- Text-only test:
  - Returns `200 OK`
  - Output content may be empty or wrong language (model behavior, not infra issue)
- Image + text test:
  - Returns `200 OK`
  - Vision pipeline works through gateway after Ollama image payload conversion fix

### 4. Embedding (`Embedding` / `Embbeding`)

- Status: `PARTIAL / HEAVY`
- Result:
  - Config and alias mapping are correct
  - First load is very slow (large HF model, CPU)
  - API calls may timeout during initial download/load
- Notes:
  - Hugging Face cache mount added to persist downloads across restarts

## Code/Config Changes Applied During Testing

- `docker-compose.yaml`
  - toggled `uvicorn --workers` for sequential/parallel testing
  - added HF cache mount for gateway (`HF_HOME`, `./assets/models/hf:/root/.cache/huggingface`)
- `spaw.sh`
  - kept worker setting aligned with compose
  - added HF cache mount for generated gateway service
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

## Next Recommendations

1. For stable testing on current machine: use `LLM` and `VLM_SMALL`, test `Embedding` separately.
2. To run `Qwen3VL-4B-Instruct`: enable GPU on Windows/WSL/Docker and/or increase WSL RAM+swap.
3. To improve `VLM_SMALL` language quality: try a different small VLM model (for example, a newer/lightweight Ollama VLM with better multilingual support).

