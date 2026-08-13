#!/usr/bin/env bash
# © 2026 Martín Viera. Todos los derechos reservados.

# MV DAX Lab — arranque en un comando.
set -e
cd "$(dirname "$0")"
if [ "$1" = "test" ]; then
    python3 -m pytest tests/ -q
elif [ "$1" = "mcp" ]; then
    python3 mcp/servidor.py
else
    pip install -q -r requirements.txt
    streamlit run app/app.py
fi
