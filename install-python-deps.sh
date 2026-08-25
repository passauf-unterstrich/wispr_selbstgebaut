#!/bin/bash
# Installiert den geprüften Python-Lock atomar in .venv.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

/bin/bash "$SCRIPT_DIR/check-platform.sh"

if ! command -v brew >/dev/null 2>&1; then
    echo "✗ Homebrew fehlt. Bitte zuerst setup.sh ausführen."
    exit 1
fi

if ! brew list python@3.13 >/dev/null 2>&1; then
    echo "• Installiere die festgelegte Python-Basis 3.13..."
    brew install python@3.13
fi

PYTHON_BIN="$(brew --prefix python@3.13)/bin/python3.13"
if [ ! -x "$PYTHON_BIN" ]; then
    echo "✗ Homebrew-Python 3.13 wurde nicht gefunden: $PYTHON_BIN"
    exit 1
fi

PYTHON_VERSION="$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ "$PYTHON_VERSION" != "3.13" ]; then
    echo "✗ Erwartet wurde Python 3.13, gefunden wurde $PYTHON_VERSION."
    exit 1
fi

LOCK_HASH="$(shasum -a 256 requirements.txt | awk '{print $1}')"
VENV_DIR="$SCRIPT_DIR/.venv"
NEUE_VENV="$SCRIPT_DIR/.venv.neu"
FINGERPRINT_DATEI="$VENV_DIR/.wispr-requirements.sha256"

smoke_test() {
    local python_bin="$1"
    "$python_bin" - <<'PYTEST'
import anthropic
import numpy
import pynput
import pyperclip
import requests
import rumps
import soundfile
import torch
import torchaudio
from silero_vad import load_silero_vad, get_speech_timestamps

model = load_silero_vad()
assert model is not None
assert callable(get_speech_timestamps)
print("✓ Python-Imports und Silero-VAD funktionieren.")
PYTEST
}

# Schneller, downloadfreier Weg für eine bereits exakt passende Umgebung.
if [ -x "$VENV_DIR/bin/python3" ] && [ -f "$FINGERPRINT_DATEI" ]; then
    VENV_VERSION="$($VENV_DIR/bin/python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
    INSTALLIERTER_HASH="$(tr -d '[:space:]' < "$FINGERPRINT_DATEI")"
    if [ "$VENV_VERSION" = "3.13" ] && [ "$INSTALLIERTER_HASH" = "$LOCK_HASH" ]; then
        "$VENV_DIR/bin/python3" -m pip check
        smoke_test "$VENV_DIR/bin/python3"
        echo "✓ Python-Umgebung entspricht bereits exakt dem geprüften Lock."
        exit 0
    fi
fi

# Ein früher abgebrochener Neubau wird aufbewahrt, nicht still überschrieben.
if [ -e "$NEUE_VENV" ]; then
    UNVOLLSTAENDIG="$SCRIPT_DIR/.venv.unvollstaendig-$(date +%Y%m%d-%H%M%S)"
    mv "$NEUE_VENV" "$UNVOLLSTAENDIG"
    echo "• Frühere unvollständige Umgebung gesichert: $UNVOLLSTAENDIG"
fi

echo "• Erzeuge neue isolierte Python-3.13-Umgebung..."
"$PYTHON_BIN" -m venv "$NEUE_VENV"

echo "• Installiere ausschließlich exakt gehashte Binärpakete..."
PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    "$NEUE_VENV/bin/python3" -m pip install \
    --require-hashes --only-binary=:all: -r requirements.txt

"$NEUE_VENV/bin/python3" -m pip check
smoke_test "$NEUE_VENV/bin/python3"
printf '%s\n' "$LOCK_HASH" > "$NEUE_VENV/.wispr-requirements.sha256"
chmod 600 "$NEUE_VENV/.wispr-requirements.sha256"

# Erst nach allen Prüfungen die neue Umgebung atomar aktivieren.
if [ -d "$VENV_DIR" ]; then
    BACKUP_VENV="$SCRIPT_DIR/.venv.backup-$(date +%Y%m%d-%H%M%S)"
    mv "$VENV_DIR" "$BACKUP_VENV"
    echo "• Vorherige Python-Umgebung gesichert: $BACKUP_VENV"
fi
mv "$NEUE_VENV" "$VENV_DIR"

echo "✓ Geprüfte Python-Umgebung wurde aktiviert."
