#!/bin/bash
# Frühe, verständliche Plattformprüfung für Setup und Updates.
set -e

MIN_MACOS_MAJOR=14

if [ "$(uname -s)" != "Darwin" ]; then
    echo "✗ Wispr unterstützt ausschließlich macOS."
    exit 1
fi

ARCHITEKTUR="$(uname -m)"
if [ "$ARCHITEKTUR" != "arm64" ]; then
    echo "✗ Dieser Mac verwendet die Architektur '$ARCHITEKTUR'."
    echo "  Unterstützt werden Apple-Silicon-Macs (M1 oder neuer, arm64)."
    exit 1
fi

MACOS_VERSION="$(sw_vers -productVersion)"
MACOS_MAJOR="${MACOS_VERSION%%.*}"
case "$MACOS_MAJOR" in
    ''|*[!0-9]*)
        echo "✗ macOS-Version konnte nicht zuverlässig erkannt werden: $MACOS_VERSION"
        exit 1
        ;;
esac

if [ "$MACOS_MAJOR" -lt "$MIN_MACOS_MAJOR" ]; then
    echo "✗ Installiert ist macOS $MACOS_VERSION."
    echo "  Wispr benötigt macOS 14 Sonoma oder neuer."
    echo "  Bitte macOS zuerst über Systemeinstellungen → Allgemein"
    echo "  → Softwareupdate aktualisieren."
    exit 1
fi

echo "✓ macOS erkannt: $MACOS_VERSION"
echo "✓ Apple Silicon erkannt: $ARCHITEKTUR"
echo "✓ Plattform wird unterstützt."
