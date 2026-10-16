#!/usr/bin/env bash
# ==============================================================================
# setup_and_translate.sh
# Script reproducible para instalar uv / dependencias y traducir los JSON
# usando modelos neuronales locales (Softcatalà NMT CTranslate2 o SalamandraTA-7B)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

echo "=================================================================="
echo " Sistema de Traducción Neuronal Local (ES <-> CA) con uv          "
echo "=================================================================="

# 1. Verificar o instalar uv automáticamente
if ! command -v uv &> /dev/null; then
    echo "[INFO] 'uv' no encontrado en PATH. Instalando uv automáticamente..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

echo "[INFO] Usando uv: $(uv --version)"

# 2. Ejecutar el traductor neuronal (uv descarga Python 3.12 y las ruedas de
#    ctranslate2 / sentencepiece / huggingface-hub de forma aislada y automática)
cd "$REPO_DIR"
uv run "$SCRIPT_DIR/translate_json.py" "$@"
