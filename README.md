# ViLMS Gateway

A FastAPI gateway compatible with the OpenAI API for serving LLM/VLM models through `ollama` or `vllm`.

## 1. Environment Requirements

- Docker + Docker Compose
- NVIDIA GPU + NVIDIA Container Toolkit (when running GPU engines)
- Bash shell to run `spaw.sh`, `start.sh`, `stop.sh`
- `yq` (`spaw.sh` can auto-install it on Linux if missing)
- Python 3 + `PyYAML` (for local `./yq` wrapper used by `start.sh` in WSL)

## 2. Main Files

- `app/configs/config.yaml`: engine, model, and network configuration
- `spaw.sh`: generates `docker-compose.yaml` from `config.yaml`
- `start.sh`: creates Docker network if missing and runs `docker compose up -d`
- `stop.sh`: stops the stack
- `docker-compose.yaml`: compose file currently used to run services

## 3. Configuration Before Running

Open `app/configs/config.yaml` and verify at least:

- `serving.engine`: `ollama` or `vllm`
- `serving.base-url`: backend endpoint called by the gateway
- `serving.models`: model list
- `docker.docker-network`: shared Docker network name (default `qvision`)
- `docker.tag.gateway` and `docker.tag.engine`

Current example uses `ollama` with:
- Gateway public: `http://localhost:8989`
- Gateway container port: `8000`
- Internal Ollama backend: `http://vilms-ollama:11434`

### Preferred Combo (Current Default)

- `LLM`: `Qwen3-4B-Instruct`
- `VLM`: `Qwen3VL-4B-Instruct`
- `Embbeding`: `Qwen3-Embbeding-4B`

Aliases in `app/configs/config.yaml` are configured for this combo:
- `LLM`
- `VLM`
- `Embedding` / `Embbeding`

## 4. Run Services

### Quick Start (WSL + avoid registry TLS issues)

```bash
cd "/mnt/c/Users/Admin/Downloads/vilms-main (1)/vilms-main"
chmod +x spaw.sh start.sh stop.sh yq
export PATH="$PWD:$PATH"
python3 -c "import yaml" || pip3 install pyyaml
GATEWAY_PULL_POLICY=never AUTO_UP=yes AUTO_BUILD=no bash spaw.sh
curl http://localhost:8989/health_check
```

### Recommended Flow

1. Regenerate `docker-compose.yaml` from config:

```bash
bash spaw.sh
```

If `docker-compose.yaml` already exists, `spaw.sh` will ask whether to recreate it.

2. Start stack:

```bash
bash start.sh
```

3. Check health:

```bash
curl http://localhost:8989/health_check
```

Expected response:

```json
{"status":"ok"}
```

### One-Liner Start with `spaw.sh`

Start immediately without local build:

```bash
AUTO_UP=yes AUTO_BUILD=no bash spaw.sh
```

Force local image rebuild:

```bash
AUTO_UP=yes AUTO_BUILD=yes bash spaw.sh
```

Avoid pulling from registry (use local image only):

```bash
GATEWAY_PULL_POLICY=never AUTO_UP=yes AUTO_BUILD=no bash spaw.sh
```

Generate compose with local gateway build block enabled:

```bash
INCLUDE_GATEWAY_BUILD=yes AUTO_UP=yes AUTO_BUILD=yes GATEWAY_PULL_POLICY=never bash spaw.sh
```

### Stop Services

```bash
bash stop.sh
```

### CMD -> WSL Example

From Windows CMD:

```cmd
cd "C:\Users\Admin\Downloads\vilms-main (1)\vilms-main"
wsl
```

Inside WSL:

```bash
cd "/mnt/c/Users/Admin/Downloads/vilms-main (1)/vilms-main"
chmod +x spaw.sh start.sh stop.sh yq
export PATH="$PWD:$PATH"
python3 -c "import yaml" || pip3 install pyyaml
AUTO_UP=yes AUTO_BUILD=no bash spaw.sh
```

## 5. Sample API Calls

### Chat Completions

```bash
curl -X POST http://localhost:8989/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3:4b-instruct",
    "messages": [
      {"role": "user", "content": "Hello"}
    ],
    "stream": false
  }'
```

### Chat Completions (Using Aliases From `config.yaml`)

```bash
curl -X POST http://localhost:8989/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "LLM",
    "messages": [
      {"role": "user", "content": "Tra loi ngan: 1+1=?"}
    ],
    "stream": false
  }'
```

### VLM (Image + Text via OpenAI-style `image_url`)

The gateway converts OpenAI-style vision payloads to Ollama native `/api/chat` when using `ollama`.

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
    "model": "Qwen/Qwen3-Embedding-4B",
    "input": ["hello", "world"]
  }'
```

Alias examples also work for embeddings:

```bash
curl -X POST http://localhost:8989/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Embbeding",
    "input": "xin chao"
  }'
```

### Sequential Test (Recommended on Low-RAM / CPU Fallback)

Test one model at a time (especially for `VLM` and `Embbeding`):

```bash
time curl -sS -i --max-time 300 http://localhost:8989/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"LLM","messages":[{"role":"user","content":"Tra loi ngan: 1+1=?"}],"stream":false}'
```

```bash
time curl -sS -i --max-time 900 http://localhost:8989/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"VLM","messages":[{"role":"user","content":"Mo ta ngan chuc nang cua VLM."}],"stream":false}'
```

```bash
time curl -sS -i --max-time 1200 http://localhost:8989/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"Embbeding","input":"xin chao"}'
```

## 6. Quick Check Commands

```bash
docker compose ps
docker compose logs -f vilms-gateway
docker compose logs -f vilms-ollama
```

## 7. Run API Tests

To quickly test gateway routes:

```bash
python -m unittest tests/test_api.py -v
```

## 8. Operational Notes

- If you change `config.yaml`, rerun `bash spaw.sh` to regenerate `docker-compose.yaml`.
- `docker-compose.yaml` uses an external network; `start.sh` auto-creates it if missing.
- In `vllm` mode, `spaw.sh` generates one service per model in `serving.models`.
- `start.sh` displays total models and includes embedding when `embedding.enabled: true`.
- `GET /v1/chat/completions` and `GET /v1/embeddings` return usage hints; actual API calls must use `POST`.
- Gateway mounts Hugging Face cache (`./assets/models/hf`) so embedding downloads persist across restarts.
- First embedding request may be very slow because `Qwen3-Embedding-4B` is large and loads lazily.
- If Ollama returns `500` for a VLM model, check `docker compose logs vilms-ollama`; a common cause is insufficient RAM when Ollama falls back to CPU.

### WSL + GPU Troubleshooting (Common VLM Failure)

If VLM requests return `400` from gateway with backend `500` and Ollama logs show memory errors:

- Confirm NVIDIA driver is installed on Windows (`PowerShell`: `nvidia-smi`)
- Confirm Docker runtime lists `nvidia` (`docker info | grep -i runtime`)
- Increase WSL RAM/swap (for example via `C:\Users\<User>\.wslconfig`)
- Restart WSL (`wsl --shutdown`) and Docker Desktop
- Retest VLM

### `spaw.sh` Runtime Variables

- `AUTO_UP`: `ask` (default), `yes`, `no`
- `AUTO_BUILD`: `no` (default), `yes`
- `INCLUDE_GATEWAY_BUILD`: `no` (default), `yes`
- `GATEWAY_PULL_POLICY`: `missing` (default), `always`, `never`, or empty
- `CONFIG_FILE`: path to config (default `./app/configs/config.yaml`)
- `COMPOSE_FILE`: output compose file (default `docker-compose.yaml`)

### Registry TLS Certificate Error

If you see:
- `tls: failed to verify certificate`
- `x509: certificate has expired or is not yet valid`

This is a registry certificate issue, not a gateway code issue.

Temporary workaround:

```bash
GATEWAY_PULL_POLICY=never AUTO_UP=yes AUTO_BUILD=no bash spaw.sh
```

If you must rebuild gateway locally instead of pulling from registry:

```bash
INCLUDE_GATEWAY_BUILD=yes GATEWAY_PULL_POLICY=never AUTO_UP=yes AUTO_BUILD=yes bash spaw.sh
```
