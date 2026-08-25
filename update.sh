#!/bin/bash
# ─────────────────────────────────────────
# Wispr Update – zieht neuen Code, aktualisiert Pakete + Modelle
# ─────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

/bin/bash "$SCRIPT_DIR/check-platform.sh"

echo ""
echo "🔄 Wispr Update"
echo "═══════════════"
echo ""

# ── 1. Läuft die App gerade? ──
if pgrep -f "diktieren.py" > /dev/null; then
    echo "⚠️  Die App läuft gerade."
    echo "Bitte beende sie (Menüleiste → 🎤 → Beenden), dann Enter drücken."
    read -p ""
fi

# ── 2. Auf neuesten Release-Tag springen (kein main-HEAD) ──
echo "• Hole neuen Code von GitHub..."
git fetch --tags --quiet origin
LETZTER_TAG=$(git tag --sort=-v:refname | head -n1)
if [ -z "$LETZTER_TAG" ]; then
    echo "⚠ Kein Release-Tag gefunden – Update abgebrochen."
    exit 1
fi
AKTUELLER_TAG=$(git describe --tags --exact-match 2>/dev/null || echo "keiner")
if [ "$AKTUELLER_TAG" = "$LETZTER_TAG" ]; then
    echo "✓ Schon auf neuestem Release: $LETZTER_TAG"
else
    echo "• Wechsle von $AKTUELLER_TAG auf $LETZTER_TAG"
    git checkout --quiet "$LETZTER_TAG"
fi
echo ""

# ── 3. Festgelegtes lokales whisper.cpp bauen oder prüfen ──
echo "• Prüfe lokalen Whisper-Kern..."
/bin/bash "$SCRIPT_DIR/install-whisper-cli.sh"
echo ""

# ── 4. Python-Pakete: atomar und nur aus geprüftem Lock aktualisieren ──
if git diff "$AKTUELLER_TAG" "$LETZTER_TAG" --name-only 2>/dev/null | grep -Eq "^(requirements\.txt|vendor/)"; then
    echo "• Der geprüfte Python-Lock hat sich geändert – aktualisiere sicher..."
    /bin/bash "$SCRIPT_DIR/install-python-deps.sh"
else
    # Prüft den Fingerprint und lädt bei identischem Lock nichts neu.
    /bin/bash "$SCRIPT_DIR/install-python-deps.sh"
fi
echo ""

# ── 5. Config-Dateien: nur neue Vorlagen-Werte übernehmen ──
# Wenn config.json.example neue Keys hat, die in config.json fehlen, ergänzen
if [ -f config.json ] && [ -f config.json.example ]; then
    "$SCRIPT_DIR/.venv/bin/python3" <<PYEND
import json
from pathlib import Path
cfg = json.loads(Path("config.json").read_text())
ex  = json.loads(Path("config.json.example").read_text())
neu = {k: v for k, v in ex.items() if k not in cfg}
if neu:
    cfg.update(neu)
    Path("config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    print(f"✓ {len(neu)} neue Config-Werte übernommen: {list(neu.keys())}")
else:
    print("✓ Config ist aktuell.")
PYEND
fi
echo ""

# ── 6. Native macOS-Starter-App bauen oder prüfen ──
echo "• Prüfe native Wispr.app..."
/bin/bash "$SCRIPT_DIR/build-macos-app.sh"
echo ""

# ── 7. Terminal-Befehle reparieren/aktualisieren ──
if [ -f "$SCRIPT_DIR/install-terminal-commands.sh" ]; then
    echo "• Prüfe Terminal-Kurzbefehle..."
    /bin/bash "$SCRIPT_DIR/install-terminal-commands.sh"
    echo ""
fi

# ── 8. Fertig ──
echo "🎉 Update fertig."
echo ""
echo "Zum Starten: neues Terminal-Fenster öffnen und 'diktieren' oder 'diktiere' tippen."
echo "Nach erfolgreichem Funktionstest können alte technische Sicherungen mit"
echo "'./cleanup-old-installation.sh' wiederherstellbar in den Papierkorb verschoben werden."
