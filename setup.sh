#!/bin/bash
# ─────────────────────────────────────────
# Setup – Diktierfunktion + KI-Assistent
# ─────────────────────────────────────────
# Einmalig ausführen: bash setup.sh

set -e

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
echo "📦 Installiere Abhängigkeiten (whisper-cli, ffmpeg, ollama)..."
brew install whisper-cli ffmpeg ollama

# ── Python-Pakete ───────────────────────────────────────────
echo ""
echo "🐍 Installiere Python-Pakete..."
pip3 install --break-system-packages rumps pyperclip requests pynput anthropic

# ── Ollama als Dienst ───────────────────────────────────────
echo ""
echo "🤖 Starte Ollama-Dienst..."
brew services start ollama

# ── Barrierefreiheit ────────────────────────────────────────
echo ""
echo "⚠️  Wichtig: Barrierefreiheit aktivieren"
echo "   Systemeinstellungen → Datenschutz & Sicherheit → Barrierefreiheit"
echo "   → Terminal (oder deine Python-App) dort eintragen"
echo ""

# ── Anthropic API Key (optional) ────────────────────────────
echo "─────────────────────────────────────────"
echo "Claude API (optional):"
echo "Falls du Claude API nutzen möchtest, trage deinen Key ein:"
echo ""
echo "  echo 'export ANTHROPIC_API_KEY=\"sk-ant-...\"' >> ~/.zshrc"
echo "  source ~/.zshrc"
echo ""

# ── Fertig ──────────────────────────────────────────────────
echo "─────────────────────────────────────────"
echo "✅ Setup abgeschlossen!"
echo ""
echo "Starten mit:"
echo "  python3 diktieren.py"
echo ""
echo "Beim ersten Start werden Whisper- und KI-Modelle"
echo "automatisch heruntergeladen (~6 GB, einmalig)."
echo ""
