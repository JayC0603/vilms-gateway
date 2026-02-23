#!/bin/bash

CONFIG_FILE="./app/configs/config.yaml"

# Check for the existence of config.yaml
if [ ! -f "$CONFIG_FILE" ]; then
    echo "================================================"
    echo "Config file not found: $CONFIG_FILE"
    echo "Please check again"
    echo "================================================"
    exit 1
fi

# Check whether yq exists
if ! command -v yq &> /dev/null; then
    echo "================================================"
    echo "Error: 'yq' command not found"
    echo "Please install yq to read config.yaml"
    echo "================================================"
    exit 1
fi

# Read variables from config.yaml
HOST_PLATFORM=$(yq '.host.platform' $CONFIG_FILE)
ENGINE_TYPE=$(yq '.serving.engine' $CONFIG_FILE)
DOCKER_NETWORK=$(yq '.docker.docker-network' $CONFIG_FILE)

# Validate required variables
if [ -z "$HOST_PLATFORM" ] || [ "$HOST_PLATFORM" == "null" ] || \
   [ -z "$ENGINE_TYPE" ] || [ "$ENGINE_TYPE" == "null" ] || \
   [ -z "$DOCKER_NETWORK" ] || [ "$DOCKER_NETWORK" == "null" ]; then
    echo "================================================"
    echo "Missing required variables in config.yaml"
    echo "host.platform, serving.engine, and docker.docker-network are required"
    echo "================================================"
    exit 1
fi

# Ensure the Docker network exists
if ! docker network ls | grep -q ${DOCKER_NETWORK}; then
    echo "================================================"
    echo "Docker network ${DOCKER_NETWORK} not found"
    echo "Creating docker network ${DOCKER_NETWORK}"
    echo "================================================"
    docker network create ${DOCKER_NETWORK}
fi

# Count models
MODEL_COUNT=$(yq '.serving.models | length' $CONFIG_FILE)
EMBEDDING_ENABLED=$(yq '.embedding.enabled' $CONFIG_FILE)

TOTAL_MODEL_COUNT=$MODEL_COUNT
if [ "$EMBEDDING_ENABLED" = "true" ]; then
    TOTAL_MODEL_COUNT=$((MODEL_COUNT + 1))
fi

echo "================================================"
echo "Starting ViLMS service ..."
echo "Platform: ${HOST_PLATFORM}"
echo "Engine: ${ENGINE_TYPE}"
echo "Network: ${DOCKER_NETWORK}"
echo "Models: ${TOTAL_MODEL_COUNT}"

# Start containers and orphans
docker compose up -d --remove-orphans

echo "ViLMS service has been started and resources allocated"
echo "================================================"
