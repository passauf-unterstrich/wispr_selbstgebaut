#!/bin/bash
# ─────────────────────────────────────────
# Wispr Installer – Einstiegspunkt für den curl | bash-Einzeiler
# ─────────────────────────────────────────
# Papa führt aus:
#   curl -fsSL https://raw.githubusercontent.com/passauf-unterstrich/wispr_selbstgebaut/main/install.sh | bash
#
# Dieses Skript:
#  1. Prüft/installiert git und Homebrew
#  2. Legt ~/Desktop/linus_apps/ an
#  3. Klont Wispr dorthin (oder aktualisiert falls vorhanden)
#  4. Startet setup.sh im geklonten Ordner

set -e

REPO_URL="https://github.com/passauf-unterstrich/wispr_selbstgebaut.git"
BASE_DIR="$HOME/Desktop/linus_apps"
APP_DIR="$BASE_DIR/Wispr"

clear
echo ""
echo "🎤 Wispr – Installation"
echo "═══════════════════════"
echo ""
echo "Dieses Skript installiert Wispr auf deinem Mac."
echo "Zielordner: $APP_DIR"
echo ""

# ── git prüfen ──
if ! command -v git &>/dev/null; then
    echo "⚠️  git ist nicht installiert."
    echo ""
    echo "git ist ein Programm, mit dem wir die App-Dateien von GitHub laden."
    echo "Es wird beim Klick auf OK durch Apples Entwickler-Tools installiert"
    echo "(dauert 5–15 Minuten)."
    echo ""
    read -p "Enter drücken um zu starten..."
    xcode-select --install || true
    echo ""
    echo "Warte auf Abschluss der Installation..."
    until command -v git &>/dev/null; do sleep 3; done
    echo "✓ git installiert"
fi

# ── Ordner anlegen ──
mkdir -p "$BASE_DIR"

# ── Klonen oder aktualisieren ──
if [ -d "$APP_DIR/.git" ]; then
    echo "• Wispr ist bereits geklont – aktualisiere..."
    cd "$APP_DIR" && git pull
else
    echo "• Klone Wispr nach $APP_DIR..."
    git clone "$REPO_URL" "$APP_DIR"
fi

# ── setup.sh starten ──
cd "$APP_DIR"
bash setup.sh
