#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="${VENV_DIR:-.venv}"
REQ_FILE="${REQ_FILE:-./docker/requirements.vilms-gateway.txt}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_INSTALL="${SKIP_INSTALL:-no}" # yes|no

echo "================================================"
echo "ViLMS dev setup (local Python environment)"
echo "Python: ${PYTHON_BIN}"
echo "Venv:   ${VENV_DIR}"
echo "Reqs:   ${REQ_FILE}"
echo "================================================"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "Error: '${PYTHON_BIN}' not found."
    echo "Install Python 3 first, then rerun."
    exit 1
fi

if [ ! -f "${REQ_FILE}" ]; then
    echo "Error: requirements file not found: ${REQ_FILE}"
    exit 1
fi

# Check if venv module is usable before trying to create a virtual environment.
if ! "${PYTHON_BIN}" -m venv --help >/dev/null 2>&1; then
    echo "Error: Python venv module is unavailable."
    echo "On Ubuntu/WSL, install it with one of:"
    echo "  sudo apt install -y python3-venv"
    echo "  sudo apt install -y python3.12-venv"
    exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating virtual environment: ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
else
    echo "Virtual environment already exists: ${VENV_DIR}"
fi

if [ "${SKIP_INSTALL}" != "yes" ]; then
    # shellcheck disable=SC1090
    source "${VENV_DIR}/bin/activate"
    python -m pip install --upgrade pip
    python -m pip install -r "${REQ_FILE}"
else
    echo "Skipping dependency installation (SKIP_INSTALL=yes)"
fi

echo ""
echo "Done."
echo "Activate venv:"
echo "  source ${VENV_DIR}/bin/activate"
echo ""
echo "Quick checks:"
echo "  python -m app.services.validator --config app/configs/config.yaml"
echo "  python -m unittest tests.test_factory_routing tests.test_api -v"
