#!/bin/bash

CONFIG_FILE="./app/configs/config.yaml"

# Check for the existence of config.yaml
if [ ! -f "$CONFIG_FILE" ]; then
    echo "================================================"
    echo "Config file not found: $CONFIG_FILE"
    echo "Performing general down command for all services"
    docker compose down --remove-orphans
    echo "All services have been stopped and resources released"
    echo "================================================"
    exit 0
fi

# Check whether yq exists
if ! command -v yq &> /dev/null; then
    echo "================================================"
    echo "Warning: 'yq' command not found"
    echo "Performing general down command for all services"
    docker compose down --remove-orphans
    echo "All services have been stopped and resources released"
    echo "================================================"
    exit 0
fi

# Read variables from config.yaml
ENGINE_TYPE=$(yq '.serving.engine' $CONFIG_FILE)
HOST_PLATFORM=$(yq '.host.platform' $CONFIG_FILE)

echo "================================================"
echo "Stopping ViLMS service ..."
if [ "$ENGINE_TYPE" != "null" ] && [ -n "$ENGINE_TYPE" ]; then
    echo "Engine: ${ENGINE_TYPE}"
fi
if [ "$HOST_PLATFORM" != "null" ] && [ -n "$HOST_PLATFORM" ]; then
    echo "Platform: ${HOST_PLATFORM}"
fi

# Stop containers and orphans
docker compose down --remove-orphans

echo "ViLMS service has been stopped and resources released"
echo "================================================"
