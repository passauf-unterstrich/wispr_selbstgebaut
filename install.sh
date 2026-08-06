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
    cd "$APP_DIR" && git fetch --tags --quiet
else
    echo "• Klone Wispr nach $APP_DIR..."
    git clone --quiet "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR" && git fetch --tags --quiet
fi

# ── Auf neuesten Release-Tag springen (kein main-HEAD) ──
LETZTER_TAG=$(git tag --sort=-v:refname | head -n1)
if [ -z "$LETZTER_TAG" ]; then
    echo "⚠ Kein Release-Tag gefunden – Setup abgebrochen."
    echo "  Wende dich an den Betreuer (passauf-unterstrich)."
    exit 1
fi
echo "• Verwende Release: $LETZTER_TAG"
git checkout --quiet "$LETZTER_TAG"

# ── setup.sh in neuem Terminal-Fenster starten ──
# Der Weg über curl|bash blockiert stdin – deshalb öffnen wir ein frisches
# Terminal-Fenster in dem setup.sh interaktiv laufen kann.
cd "$APP_DIR"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Wispr wurde heruntergeladen."
echo "  Setup startet in einem neuen Terminal-Fenster..."
echo "═══════════════════════════════════════════════════════════"
echo ""

osascript <<APPLESCRIPT
tell application "Terminal"
    activate
    do script "cd \"$APP_DIR\" && bash setup.sh"
end tell
APPLESCRIPT

echo "✓ Setup läuft im neuen Terminal-Fenster. Dieses Fenster kann geschlossen werden."
