#!/bin/bash
# ─────────────────────────────────────────
# Wispr Update – zieht neuen Code, aktualisiert Pakete + Modelle
# ─────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

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

# ── 2. Code aktualisieren ──
echo "• Hole neuen Code von GitHub..."
git pull
echo ""

# ── 3. Python-Pakete: nur aktualisieren wenn requirements.txt sich geändert hat ──
if git diff HEAD~1 HEAD --name-only 2>/dev/null | grep -q "requirements.txt"; then
    echo "• requirements.txt hat sich geändert – installiere Pakete..."
    pip3 install --break-system-packages -r requirements.txt
else
    echo "✓ Keine neuen Pakete nötig."
fi
echo ""

# ── 4. Config-Dateien: nur neue Vorlagen-Werte übernehmen ──
# Wenn config.json.example neue Keys hat, die in config.json fehlen, ergänzen
if [ -f config.json ] && [ -f config.json.example ]; then
    python3 <<PYEND
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

# ── 5. Fertig ──
echo "🎉 Update fertig."
echo ""
echo "Zum Starten: neues Terminal-Fenster öffnen und 'diktieren' tippen."
