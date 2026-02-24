# ViLMS Gateway

FastAPI gateway tuong thich OpenAI API de phuc vu `LLM` / `VLM` qua `ollama` hoac `vllm`.

## 1. Summary

Repo nay tap trung vao:
- Gateway API (`/v1/chat/completions`, `/v1/embeddings`)
- Routing model theo config
- Sinh `docker-compose.yaml` tu `config.yaml`
- Toi uu chay thuc te cho `dGPU` va `Jetson` (muc inference)

Repo nay chua bao gom pipeline train `finetune / LoRA / QLoRA` (xem phan cuoi README).

## 2. Quick Start

### WSL (recommended on Windows)

```bash
cd "/mnt/c/Users/Admin/Downloads/vilms-main (1)/vilms-main"
chmod +x spaw.sh start.sh stop.sh yq
export PATH="$PWD:$PATH"
python3 -c "import yaml" || pip3 install pyyaml
GATEWAY_PULL_POLICY=never AUTO_UP=yes AUTO_BUILD=no bash spaw.sh
curl http://localhost:8989/health_check
```

Expected:

```json
{"status":"ok"}
```

### Standard flow

```bash
bash spaw.sh
bash start.sh
curl http://localhost:8989/health_check
```

Stop:

```bash
bash stop.sh
```

## 3. Project Files

- `app/configs/config.yaml`: host, engine, model, alias, network config
- `spaw.sh`: generate `docker-compose.yaml` from config
- `start.sh`: create network (if missing) and start stack
- `stop.sh`: stop stack
- `app/routes.py`: API routes
- `app/cores/factory.py`: engine routing / alias resolution
- `app/services/validator.py`: config validation

## 4. Configuration (`app/configs/config.yaml`)

Check these keys before running:

- `host.platform`: `dgpu` or `js` (`js` = Jetson)
- `serving.engine`: `ollama` or `vllm`
- `serving.base-url`: primary backend endpoint
- `serving.ollama-base-url`, `serving.vllm-base-url`: split backend endpoints (optional)
- `serving.models`: chat model list
- `embedding.enabled`: enable/disable embeddings
- `embedding.model`: embedding model
- `docker.docker-network`: shared Docker network
- `docker.tag.gateway`, `docker.tag.engine`
- `docker.image.ollama`: Ollama image repo override (important for Jetson/ARM64)

### Config-based model expansion (supported)

Each item in `serving.models` can include metadata:

- `type`: model type (`llm`, `vlm`, `embedding`, `reranker`, ...)
- `engine`: force backend for that model (`ollama` / `vllm`)
- `aliases`: local aliases at model entry level
- `params`: runtime params (`temperature`, `max-tokens`, `max-frames`, ...)

Example:

```yaml
serving:
  engine: vllm
  models:
    - name: qwen3:4b-instruct
      type: llm
      engine: vllm
      aliases: [LLM, LLM_SMALL]
      params:
        - temperature: 0.7
        - max-tokens: 1024

    - name: qwen3-vl:4b-instruct
      type: vlm
      engine: ollama
      aliases: [VLM, VLM_SMALL]
      params:
        - max-frames: 8
        - max-tokens: 1024
```

Chat routing priority:
1. `serving.engine=ollama` -> force all chat requests to Ollama (backward compatible)
2. `host.platform=js` -> prefer Ollama on Jetson
3. `serving.models[*].engine` -> per-model override
4. `serving.models[*].type` -> route by model type (`vlm` -> Ollama)
5. Fallback legacy heuristic (model name contains `vl`)

### Alias model

Repo supports 2 alias layers:
- `model-aliases` (global map)
- `serving.models[*].aliases` (local aliases, auto-merged)

API examples:
- `"model": "LLM"`
- `"model": "VLM_SMALL"`

## 5. Jetson (ARM64) Guide

Current Jetson-oriented optimizations:
- `host.platform: js` -> prefer routing chat to `ollama`
- Auto-trim image frames in VLM requests using `serving.default-max-frames`
- `spaw.sh` auto-reduces `uvicorn --workers` to `1` to reduce memory pressure

Recommended Jetson config:
- `host.platform: js`
- `serving.engine: ollama`
- `docker.image.ollama`: ARM64/Jetson-compatible Ollama image
- Start with small models (`4B`)
- Set `embedding.enabled: false` during initial bring-up if resources are limited

Override Ollama image at runtime (without editing YAML):

```bash
OLLAMA_IMAGE=<your-jetson-ollama-image-repo> AUTO_UP=yes AUTO_BUILD=no bash spaw.sh
```

## 6. Running Services with `spaw.sh`

### Common modes

Start immediately, no local build:

```bash
AUTO_UP=yes AUTO_BUILD=no bash spaw.sh
```

Start and build locally:

```bash
AUTO_UP=yes AUTO_BUILD=yes bash spaw.sh
```

Do not pull from registry:

```bash
GATEWAY_PULL_POLICY=never AUTO_UP=yes AUTO_BUILD=no bash spaw.sh
```

Generate compose with gateway `build` block:

```bash
INCLUDE_GATEWAY_BUILD=yes GATEWAY_PULL_POLICY=never AUTO_UP=yes AUTO_BUILD=yes bash spaw.sh
```

### `spaw.sh` runtime variables

- `AUTO_UP`: `ask` (default), `yes`, `no`
- `AUTO_BUILD`: `no` (default), `yes`
- `INCLUDE_GATEWAY_BUILD`: `no` (default), `yes`
- `GATEWAY_PULL_POLICY`: `missing` (default), `always`, `never`, or empty
- `CONFIG_FILE`: config path (default `./app/configs/config.yaml`)
- `COMPOSE_FILE`: output compose path (default `docker-compose.yaml`)
- `OLLAMA_IMAGE`: runtime override for Ollama image repo

## 7. API Examples

### Health Check

```bash
curl http://localhost:8989/health_check
```

### Chat Completion (LLM)

```bash
curl -X POST http://localhost:8989/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "LLM",
    "messages": [{"role": "user", "content": "Tra loi ngan: 1+1=?"}],
    "stream": false
  }'
```

### Chat Completion (VLM - OpenAI style `image_url`)

```bash
curl -X POST http://localhost:8989/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "VLM",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "Mo ta ngan buc anh nay bang tieng Viet."},
          {"type": "image_url", "image_url": {"url": "https://picsum.photos/512"}}
        ]
      }
    ],
    "stream": false
  }'
```

### Embeddings

```bash
curl -X POST http://localhost:8989/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Embbeding",
    "input": "xin chao"
  }'
```

## 8. Validation and Debug

### Docker logs

```bash
docker compose ps
docker compose logs -f vilms-gateway
docker compose logs -f vilms-ollama
```

### API route tests

```bash
python -m unittest tests/test_api.py -v
```

### Routing metadata tests

```bash
python -m unittest tests.test_factory_routing -v
```

### Validate config before generating compose

```bash
python -m app.services.validator --config app/configs/config.yaml
```

## 9. Operational Notes

- After changing `config.yaml`, rerun `bash spaw.sh` to regenerate `docker-compose.yaml`
- `docker-compose.yaml` uses an external network; `start.sh` auto-creates it if missing
- In `vllm` mode, `spaw.sh` generates one service per model in `serving.models`
- `GET /v1/chat/completions` and `GET /v1/embeddings` return hints; actual calls must use `POST`
- Gateway mounts HF cache (`./assets/models/hf`) so downloads persist across restarts
- First embedding request may be slow due to lazy loading of a large model
- If Ollama returns `500` for VLM, common cause is insufficient RAM/VRAM or CPU fallback

### WSL + GPU troubleshooting (VLM failures)

If VLM requests return `400` from gateway and backend `500` + Ollama logs show memory errors:

- Check NVIDIA driver on Windows: `nvidia-smi`
- Check Docker runtime includes `nvidia`
- Increase WSL RAM/swap (`C:\Users\<User>\.wslconfig`)
- Run `wsl --shutdown`, then restart Docker Desktop
- Retest models sequentially

### Registry TLS error

If you see:
- `tls: failed to verify certificate`
- `x509: certificate has expired or is not yet valid`

Temporary workaround:

```bash
GATEWAY_PULL_POLICY=never AUTO_UP=yes AUTO_BUILD=no bash spaw.sh
```

## 10. Finetune / LoRA Status

Current status:
- This repo is a `serving gateway` (API + routing + Docker orchestration)
- A training pipeline for `finetune / LoRA / QLoRA` is not implemented in this codebase

Done to support future expansion:
- Added clear status + roadmap docs
- Improved config-based model expansion (`type`, `engine`, `aliases`)

If LoRA is needed later:
- Train in a separate pipeline
- Merge/export artifacts
- Point gateway to the fine-tuned model or merged artifact

See detailed plan:
- `docs/finetune-lora-status.md`
