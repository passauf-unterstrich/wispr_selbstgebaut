#!/bin/bash
# Verschiebt ausschliesslich bekannte technische Wispr-Reste in den Papierkorb.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
PAPIERKORB="$HOME/.Trash"
ZEIT="$(date +%Y%m%d-%H%M%S)"
ZIEL="$PAPIERKORB/Wispr-alte-Technik-$ZEIT"

KANDIDATEN=()
for muster in \
    ".venv.backup-"* \
    ".venv.unvollstaendig-"* \
    ".Wispr.app.vorher-"* \
    ".Wispr.app.unvollstaendig-"* \
    "whisper.cpp.backup-"* \
    "whisper.cpp.unvollstaendig-"*; do
    [ -e "$SCRIPT_DIR/$muster" ] && KANDIDATEN+=("$SCRIPT_DIR/$muster")
done

if [ "${#KANDIDATEN[@]}" -eq 0 ]; then
    echo "✓ Keine alten technischen Wispr-Sicherungen gefunden."
    exit 0
fi

echo "Folgende alte technische Sicherungen wurden gefunden:"
for kandidat in "${KANDIDATEN[@]}"; do
    echo "  - $(basename "$kandidat")"
done
echo ""
echo "Geschützt und niemals betroffen: config.json, vocabulary.csv,"
echo "assistant_style.md, .historie.json und modelle/."
echo ""
read -r -p "In den Papierkorb verschieben? [j/N]: " ANTWORT
case "$ANTWORT" in
    j|J|ja|JA|Ja) ;;
    *) echo "Abgebrochen – nichts wurde verändert."; exit 0 ;;
esac

mkdir -p "$ZIEL"
for kandidat in "${KANDIDATEN[@]}"; do
    mv "$kandidat" "$ZIEL/"
done
echo "✓ Alte technische Sicherungen liegen wiederherstellbar in: $ZIEL"
