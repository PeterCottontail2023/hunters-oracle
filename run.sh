#!/usr/bin/env bash
# Linux/macOS launcher for Hunter's Oracle.
#
# Fully self-healing: checks for a working virtual environment with the
# right packages installed, and (re)builds it if anything's missing or
# broken -- you should never need to manually delete .venv or pip install
# anything yourself.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

VENV_DIR=".venv"
PY="$VENV_DIR/bin/python"

venv_is_healthy() {
    [[ -x "$PY" ]] && "$PY" -c "import flask, requests" >/dev/null 2>&1
}

ensure_venv_module() {
    if python3 -m venv --help >/dev/null 2>&1; then
        return 0
    fi
    echo "python3's 'venv' module isn't installed. Attempting to install it..."
    if command -v apt-get >/dev/null 2>&1; then
        PYVER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
        if sudo apt-get install -y "python${PYVER}-venv" 2>/dev/null || sudo apt-get install -y python3-venv; then
            return 0
        fi
    fi
    echo
    echo "Couldn't install it automatically. Please run one of:"
    echo "    sudo apt install python3-venv      # Debian/Ubuntu/Mint"
    echo "  then re-run ./run.sh"
    return 1
}

if ! venv_is_healthy; then
    echo "Setting up Hunter's Oracle (first run, or environment needs repair)..."
    if [[ -d "$VENV_DIR" ]]; then
        rm -rf "$VENV_DIR"
    fi
    ensure_venv_module || exit 1
    python3 -m venv "$VENV_DIR" || { echo "FATAL: could not create virtual environment."; exit 1; }
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet -r requirements.txt
    if ! venv_is_healthy; then
        echo "FATAL: dependency install failed. Check your internet connection and try again."
        exit 1
    fi
    echo "Setup complete."
fi

exec "$PY" app.py
