#!/bin/bash
# Baut die festgelegte whisper.cpp-Version atomar fuer Apple Silicon.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WHISPER_DIR="$SCRIPT_DIR/whisper.cpp"
NEUER_DIR="$SCRIPT_DIR/whisper.cpp.neu"
WHISPER_BIN="$WHISPER_DIR/build/bin/whisper-cli"
WHISPER_TAG="v1.7.5"
WHISPER_COMMIT="51c6961c7b64b406833f4b6a4a20e67142f69225"

/bin/bash "$SCRIPT_DIR/check-platform.sh"

ist_gepruefte_version() {
    [ -x "$WHISPER_BIN" ] || return 1
    [ -d "$WHISPER_DIR/.git" ] || return 1
    [ "$(git -C "$WHISPER_DIR" rev-parse HEAD 2>/dev/null || true)" = "$WHISPER_COMMIT" ] || return 1
    file "$WHISPER_BIN" | grep -q "Mach-O 64-bit executable arm64"
}

if ist_gepruefte_version; then
    echo "✓ whisper.cpp $WHISPER_TAG ist bereits nativ und geprüft gebaut."
    exit 0
fi

if ! command -v cmake >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
        echo "• cmake fehlt und wird über Homebrew installiert..."
        brew install cmake
    else
        echo "✗ cmake und Homebrew fehlen. Bitte zuerst setup.sh ausführen."
        exit 1
    fi
fi

if [ -e "$NEUER_DIR" ]; then
    UNVOLLSTAENDIG="$SCRIPT_DIR/whisper.cpp.unvollstaendig-$(date +%Y%m%d-%H%M%S)"
    mv "$NEUER_DIR" "$UNVOLLSTAENDIG"
    echo "• Früheren unvollständigen Bau gesichert: $UNVOLLSTAENDIG"
fi

echo "• Lade geprüften whisper.cpp-Quellstand $WHISPER_TAG..."
git clone --quiet --depth 1 --branch "$WHISPER_TAG" \
    https://github.com/ggml-org/whisper.cpp.git "$NEUER_DIR"

GEKLONTER_COMMIT="$(git -C "$NEUER_DIR" rev-parse HEAD)"
if [ "$GEKLONTER_COMMIT" != "$WHISPER_COMMIT" ]; then
    echo "✗ Unerwarteter whisper.cpp-Commit."
    echo "  Erwartet: $WHISPER_COMMIT"
    echo "  Erhalten: $GEKLONTER_COMMIT"
    exit 1
fi

echo "• Kompiliere whisper-cli nativ für Apple Silicon..."
cmake -S "$NEUER_DIR" -B "$NEUER_DIR/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$NEUER_DIR/build" --config Release -j

NEUES_BIN="$NEUER_DIR/build/bin/whisper-cli"
if [ ! -x "$NEUES_BIN" ] || \
   ! file "$NEUES_BIN" | grep -q "Mach-O 64-bit executable arm64"; then
    echo "✗ Der fertige whisper-cli-Build ist nicht arm64 oder nicht ausführbar."
    exit 1
fi

if [ -e "$WHISPER_DIR" ]; then
    BACKUP_DIR="$SCRIPT_DIR/whisper.cpp.backup-$(date +%Y%m%d-%H%M%S)"
    mv "$WHISPER_DIR" "$BACKUP_DIR"
    echo "• Vorherige whisper.cpp-Version gesichert: $BACKUP_DIR"
fi
mv "$NEUER_DIR" "$WHISPER_DIR"

echo "✓ whisper.cpp $WHISPER_TAG wurde geprüft und atomar aktiviert."
