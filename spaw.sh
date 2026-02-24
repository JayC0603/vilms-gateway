#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${CONFIG_FILE:-./app/configs/config.yaml}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yaml}"
INCLUDE_GATEWAY_BUILD="${INCLUDE_GATEWAY_BUILD:-no}"  # yes | no
GATEWAY_PULL_POLICY="${GATEWAY_PULL_POLICY:-missing}"  # always | missing | never | ''

yq_get() {
    local expr="$1"
    yq eval -r "$expr" "$CONFIG_FILE"
}

require_non_empty() {
    local name="$1"
    local val="$2"
    if [[ -z "$val" || "$val" == "null" ]]; then
        echo "Error: Missing required config value: $name"
        exit 1
    fi
}

# ================================================================
# 1. AUTO-CHECK AND INSTALL YQ
# ================================================================
if ! command -v yq >/dev/null 2>&1; then
    echo "Warning: 'yq' not found. Installing..."
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)  BINARY="yq_linux_amd64" ;;
        aarch64) BINARY="yq_linux_arm64" ;;
        *)       echo "Error: Architecture $ARCH is not supported."; exit 1 ;;
    esac
    if command -v curl >/dev/null 2>&1; then
        sudo curl -fsSL "https://github.com/mikefarah/yq/releases/latest/download/$BINARY" -o /usr/bin/yq
    elif command -v wget >/dev/null 2>&1; then
        sudo wget "https://github.com/mikefarah/yq/releases/latest/download/$BINARY" -O /usr/bin/yq
    else
        echo "Error: neither curl nor wget is available to install yq."
        exit 1
    fi
    sudo chmod +x /usr/bin/yq
fi

# ================================================================
# 2. CHECK CONFIG FILE AND CONFIRM Y/N
# ================================================================
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found: $CONFIG_FILE"
    exit 1
fi

ENGINE="$(yq_get '.serving.engine')"
if [[ "$ENGINE" != "vllm" && "$ENGINE" != "ollama" ]]; then
    echo "Error: Engine '$ENGINE' is not supported. Use 'vllm' or 'ollama' in config.yaml"
    exit 1
fi

if [ -f "$COMPOSE_FILE" ]; then
    echo "Warning: File $COMPOSE_FILE already exists."
    read -p "Do you want to delete and recreate it? (y/n): " confirm
    if [[ ! $confirm =~ ^[yY](es)?$ ]]; then
        echo "Canceled."
        exit 0
    fi
    rm -f "$COMPOSE_FILE"
fi

echo "Engine detected: $ENGINE. Initializing..."

# ================================================================
# 3. READ COMMON SETTINGS
# ================================================================
REGISTRY="$(yq_get '.docker.docker-registry')"
PROJECT="$(yq_get '.docker.docker-project')"
NET_NAME="$(yq_get '.docker.docker-network')"
GW_TAG="$(yq_get '.docker.tag.gateway')"
ENGINE_TAG="$(yq_get '.docker.tag.engine')"
HOST_PLATFORM="$(yq_get '.host.platform')"
OLLAMA_IMAGE_CFG="$(yq_get '.docker.image.ollama')"
MODEL_COUNT="$(yq_get '.serving.models | length')"
EMBEDDING_ENABLED="$(yq_get '.embedding.enabled')"
EMBEDDING_MODEL="$(yq_get '.embedding.model')"

require_non_empty "docker.docker-registry" "$REGISTRY"
require_non_empty "docker.docker-project" "$PROJECT"
require_non_empty "docker.docker-network" "$NET_NAME"
require_non_empty "docker.tag.gateway" "$GW_TAG"
require_non_empty "docker.tag.engine" "$ENGINE_TAG"

if [[ -z "$HOST_PLATFORM" || "$HOST_PLATFORM" == "null" ]]; then
    HOST_PLATFORM="dgpu"
fi

# Optional override for Ollama image repository (useful for Jetson/aarch64 builds).
# Priority: env OLLAMA_IMAGE > config docker.image.ollama > default repo.
if [[ -n "${OLLAMA_IMAGE:-}" ]]; then
    OLLAMA_IMAGE_REPO="$OLLAMA_IMAGE"
elif [[ -n "$OLLAMA_IMAGE_CFG" && "$OLLAMA_IMAGE_CFG" != "null" ]]; then
    OLLAMA_IMAGE_REPO="$OLLAMA_IMAGE_CFG"
else
    OLLAMA_IMAGE_REPO="ollama/ollama"
fi

GATEWAY_WORKERS="2"
if [[ "$HOST_PLATFORM" == "js" ]]; then
    GATEWAY_WORKERS="1"
fi

# ================================================================
# 4. CREATE GATEWAY SERVICE
# ================================================================
GATEWAY_BUILD_BLOCK=""
if [[ "$INCLUDE_GATEWAY_BUILD" =~ ^(yes|YES|Yes|y|Y|1|true|TRUE)$ ]]; then
    GATEWAY_BUILD_BLOCK=$'    build:\n      context: .\n      dockerfile: ./docker/Dockerfile.vilms-gateway\n'
fi

GATEWAY_PULL_POLICY_BLOCK=""
if [[ -n "$GATEWAY_PULL_POLICY" ]]; then
    GATEWAY_PULL_POLICY_BLOCK="    pull_policy: $GATEWAY_PULL_POLICY"
fi

cat <<EOF > "$COMPOSE_FILE"
services:
  vilms-gateway:
    image: $REGISTRY/$PROJECT/vilms-gateway:$GW_TAG
    container_name: vilms-gateway
$GATEWAY_BUILD_BLOCK$GATEWAY_PULL_POLICY_BLOCK
    volumes:
      - ./app:/workspace/app
      - ./assets/models/hf:/root/.cache/huggingface
    ports:
      - 8989:8000
    command: >
      uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers $GATEWAY_WORKERS
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health_check"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - vilms-network

EOF

# ================================================================
# 5. ENGINE SERVICES
# ================================================================
if [ "$ENGINE" == "ollama" ]; then
    # ------------------------------------------------------------
    # OLLAMA MODE: RUN A SINGLE OLLAMA SERVICE
    # Gateway should point base-url to: http://vilms-ollama:11434
    # Models are selected by request payload "model"
    # ------------------------------------------------------------
    echo "Configuring SINGLE Ollama service (engine=ollama). Models in config: $MODEL_COUNT"

    cat <<EOF >> "$COMPOSE_FILE"
  vilms-ollama:
    image: $OLLAMA_IMAGE_REPO:$ENGINE_TAG
    container_name: vilms-ollama
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=all
    volumes:
      - ./assets/models/ollama:/root/.ollama
      - ./assets/models/hf:/models/hf
      - ./assets/models/gguf:/models/gguf
    command: serve
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [ gpu, utility, compute ]
    networks:
      - vilms-network

EOF

    # Optional: print model names for clarity
    echo " - Host platform: $HOST_PLATFORM"
    echo " - Ollama image: $OLLAMA_IMAGE_REPO:$ENGINE_TAG"
    if [[ "$HOST_PLATFORM" == "js" && "$EMBEDDING_ENABLED" == "true" ]]; then
        echo "Warning: embedding.enabled=true on Jetson may exceed RAM/VRAM (default embedding model is large)."
        echo "         Consider setting embedding.enabled=false for first bring-up."
    fi
    for ((i=0; i<$MODEL_COUNT; i++)); do
        M_NAME="$(yq_get ".serving.models[$i].name")"
        echo " - Model declared in config: $M_NAME"
    done

else
    # ------------------------------------------------------------
    # VLLM MODE: CREATE ONE SERVICE PER MODEL (SANITIZED NAMES)
    # ------------------------------------------------------------
    echo "Configuring vLLM services per model (engine=vllm). Models: $MODEL_COUNT"

    for ((i=0; i<$MODEL_COUNT; i++)); do
        M_NAME="$(yq_get ".serving.models[$i].name")"
        M_PATH="$(yq_get ".serving.models[$i].path")"
        if [[ -z "$M_NAME" || "$M_NAME" == "null" ]]; then
            echo "Error: serving.models[$i].name is required in vllm mode."
            exit 1
        fi
        if [[ -z "$M_PATH" || "$M_PATH" == "null" ]]; then
            echo "Error: serving.models[$i].path is required in vllm mode for model '$M_NAME'."
            exit 1
        fi

        # Sanitize model name for docker compose identifiers
        SAFE_NAME="$(echo "$M_NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"

        # Build params
        PARAMS_CMD=""
        P_TYPE="$(yq_get ".serving.models[$i].params | type")"

        if [[ "$P_TYPE" == "!!seq" ]]; then
            P_COUNT="$(yq_get ".serving.models[$i].params | length")"
            if [[ "$P_COUNT" != "0" && "$P_COUNT" != "null" ]]; then
                for ((j=0; j<P_COUNT; j++)); do
                    KEY="$(yq_get ".serving.models[$i].params[$j] | keys | .[0]")"
                    VAL="$(yq_get ".serving.models[$i].params[$j][\"$KEY\"]")"
                    PARAMS_CMD="$PARAMS_CMD --$KEY $VAL"
                done
            fi
        elif [[ "$P_TYPE" == "!!map" ]]; then
            while IFS= read -r KEY; do
                [[ -z "$KEY" ]] && continue
                VAL="$(yq_get ".serving.models[$i].params[\"$KEY\"]")"
                PARAMS_CMD="$PARAMS_CMD --$KEY $VAL"
            done < <(yq_get ".serving.models[$i].params | keys | .[]")
        fi

        IMAGE="vllm/vllm-openai:$ENGINE_TAG"
        COMMAND="--model /$M_PATH $PARAMS_CMD"

        echo " - vLLM service for model: $M_NAME (safe: $SAFE_NAME)"

        cat <<EOF >> "$COMPOSE_FILE"
  vilms-$SAFE_NAME:
    image: $IMAGE
    container_name: vilms-$SAFE_NAME
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=all
    volumes:
      - ./assets/models/hf:/models/hf
      - ./assets/models/gguf:/models/gguf
    command: $COMMAND
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [ gpu, utility, compute ]
    networks:
      - vilms-network

EOF
    done
fi

# ================================================================
# 6. NETWORK
# ================================================================
cat <<EOF >> "$COMPOSE_FILE"
networks:
  vilms-network:
    name: $NET_NAME
    external: true
EOF

echo "================================================"
echo "Created $COMPOSE_FILE successfully."
echo "Engine: $ENGINE | Chat models declared: $MODEL_COUNT"
echo "Host platform: $HOST_PLATFORM | Gateway workers: $GATEWAY_WORKERS"
echo "Ollama image repo: $OLLAMA_IMAGE_REPO | Engine tag: $ENGINE_TAG"
echo "Embedding enabled: $EMBEDDING_ENABLED | Embedding model: $EMBEDDING_MODEL"
echo "================================================"

# ================================================================
# 7. OPTIONAL: BUILD AND START STACK
# ================================================================
AUTO_UP="${AUTO_UP:-ask}"  # ask | yes | no
AUTO_BUILD="${AUTO_BUILD:-no}"  # yes | no

run_up() {
    if [[ "$AUTO_BUILD" =~ ^(yes|YES|Yes|y|Y|1|true|TRUE)$ ]]; then
        echo "Running: docker compose -f $COMPOSE_FILE up -d --build"
        docker compose -f "$COMPOSE_FILE" up -d --build
    else
        echo "Running: docker compose -f $COMPOSE_FILE up -d"
        docker compose -f "$COMPOSE_FILE" up -d
    fi
}

case "$AUTO_UP" in
    yes|YES|Yes|y|Y|1|true|TRUE)
        run_up
        ;;
    no|NO|No|n|N|0|false|FALSE)
        echo "Skip docker compose up."
        ;;
    *)
        read -r -p "Start services now? (y/n): " do_up
        if [[ "$do_up" =~ ^[yY](es)?$ ]]; then
            run_up
        else
            echo "Skip docker compose up."
        fi
        ;;
esac
