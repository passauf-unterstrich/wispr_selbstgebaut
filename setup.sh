#!/bin/bash
# ─────────────────────────────────────────
# Setup – Diktierfunktion + KI-Assistent
# ─────────────────────────────────────────
# Einmalig ausführen: bash setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "🎤 Setup: Diktierfunktion + KI-Assistent"
echo "─────────────────────────────────────────"
echo ""

# ── Homebrew ────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "📦 Installiere Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "✓ Homebrew bereits installiert"
fi

# ── Abhängigkeiten ──────────────────────────────────────────
echo ""
echo "📦 Installiere whisper-cli, ffmpeg, ollama..."
brew install whisper-cli ffmpeg ollama

# ── Python venv ─────────────────────────────────────────────
echo ""
echo "🐍 Erstelle virtuelle Python-Umgebung (venv)..."
python3 -m venv "$SCRIPT_DIR/venv"
echo "✓ venv erstellt"

# ── Python-Pakete in venv ───────────────────────────────────
echo ""
echo "🐍 Installiere Python-Pakete..."
"$SCRIPT_DIR/venv/bin/pip" install --upgrade pip --quiet
"$SCRIPT_DIR/venv/bin/pip" install rumps pyperclip requests pynput anthropic --quiet
echo "✓ Pakete installiert"

# ── Ollama als Dienst ───────────────────────────────────────
echo ""
echo "🤖 Starte Ollama-Dienst..."
brew services start ollama

# ── Alias in ~/.zshrc ───────────────────────────────────────
echo ""
ALIAS_LINE="alias diktieren=\"cd '$SCRIPT_DIR' && '$SCRIPT_DIR/venv/bin/python3' diktieren.py\""

if grep -q "alias diktieren=" ~/.zshrc 2>/dev/null; then
    echo "✓ Alias bereits vorhanden"
else
    echo "$ALIAS_LINE" >> ~/.zshrc
    echo "✓ Alias 'diktieren' zu ~/.zshrc hinzugefügt"
fi

# ── Barrierefreiheit ────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────"
echo "⚠️  Wichtig: Barrierefreiheit aktivieren"
echo ""
echo "   Systemeinstellungen → Datenschutz & Sicherheit"
echo "   → Barrierefreiheit → Terminal hinzufügen"
echo ""
echo "   Ohne diese Einstellung funktionieren die"
echo "   Tastatur-Shortcuts nicht."
echo "─────────────────────────────────────────"

# ── Claude API Key (optional) ────────────────────────────────
echo ""
echo "Claude API (optional):"
echo "Falls du Claude API nutzen möchtest:"
echo ""
echo "  echo 'export ANTHROPIC_API_KEY=\"sk-ant-...\"' >> ~/.zshrc"
echo "  source ~/.zshrc"
echo ""

# ── Fertig ──────────────────────────────────────────────────
echo "─────────────────────────────────────────"
echo "✅ Setup abgeschlossen!"
echo ""
echo "Neues Terminal öffnen, dann starten mit:"
echo ""
echo "  diktieren"
echo ""
echo "Beim ersten Start werden Whisper- und KI-Modelle"
echo "automatisch heruntergeladen (~6 GB, einmalig)."
echo ""
