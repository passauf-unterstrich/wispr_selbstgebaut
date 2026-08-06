#!/bin/bash
# ─────────────────────────────────────────
# Wispr Setup – installiert alles was für die App gebraucht wird
# Läuft geführt Schritt für Schritt, prüft was schon da ist,
# lädt nur das Fehlende nach.
# ─────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Spinner für stille Downloads/Installations ──
mit_spinner() {
    # Nutzung: mit_spinner "Nachricht" befehl arg1 arg2 ...
    local nachricht="$1"; shift
    local log=$(mktemp)
    "$@" > "$log" 2>&1 &
    local pid=$!
    local chars="⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    local i=0
    local start=$(date +%s)
    while kill -0 $pid 2>/dev/null; do
        local elapsed=$(($(date +%s) - start))
        local c=${chars:$((i % ${#chars})):1}
        printf "\r  %s %s  (%ss)" "$c" "$nachricht" "$elapsed"
        i=$((i+1))
        sleep 0.1
    done
    wait $pid
    local status=$?
    local elapsed=$(($(date +%s) - start))
    if [ $status -eq 0 ]; then
        printf "\r  ✓ %s  (%ss)                    \n" "$nachricht" "$elapsed"
    else
        printf "\r  ✗ %s  (Fehler)                  \n" "$nachricht"
        echo ""
        echo "── Log ──"
        cat "$log"
        rm -f "$log"
        exit 1
    fi
    rm -f "$log"
}


clear
echo ""
echo "🎤 Wispr Setup"
echo "══════════════"
echo ""
echo "Dieses Skript prüft was schon installiert ist"
echo "und richtet nur das Fehlende ein."
echo ""
echo "Geschätzte Dauer bei jungfräulichem Mac: 20–30 Minuten"
echo "(davon ~15 Min Downloads: Whisper-Modell + KI-Modell)"
echo ""
read -p "Enter drücken um zu starten..."

# ────────────────────────────────────────────────────────────
# SCHRITT 1: Homebrew
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 1 von 7 – Homebrew"
echo "──────────────────────────"

if command -v brew &>/dev/null; then
    echo "✓ Homebrew ist installiert."
else
    echo ""
    echo "Homebrew fehlt. Es ist der App Store für Terminal-Programme."
    echo "Wir brauchen es zum Installieren von whisper-cli, ffmpeg, ollama."
    echo ""
    read -p "Enter drücken um Homebrew zu installieren..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Homebrew-PATH aktivieren
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    echo "✓ Homebrew installiert."
fi
echo ""
read -p "Weiter mit Enter..."

# ────────────────────────────────────────────────────────────
# SCHRITT 2: Programme
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 2 von 7 – Programme (whisper-cli, ffmpeg, ollama)"
echo "──────────────────────────────────────────────────────────"

for pkg in whisper-cli ffmpeg ollama; do
    if brew list "$pkg" &>/dev/null; then
        echo "✓ $pkg ist installiert."
    else
        mit_spinner "Installiere $pkg via brew" brew install "$pkg"
    fi
done
echo ""
read -p "Weiter mit Enter..."

# ────────────────────────────────────────────────────────────
# SCHRITT 3: Python-Pakete
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 3 von 7 – Python-Pakete"
echo "────────────────────────────────"
echo ""
echo "Installiert die Python-Bibliotheken aus requirements.txt"
echo "(rumps, pynput, silero-vad, torch, ...)"
echo ""
read -p "Enter drücken..."

mit_spinner "pip aktualisieren" pip3 install --break-system-packages --upgrade pip --quiet
mit_spinner "Python-Pakete installieren (torch, rumps, silero-vad, ...)" \
    pip3 install --break-system-packages --quiet -r "$SCRIPT_DIR/requirements.txt"
read -p "Weiter mit Enter..."

# ────────────────────────────────────────────────────────────
# SCHRITT 4: Whisper-Modell (medium)
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 4 von 7 – Whisper-Modell (medium, ~1.5 GB)"
echo "──────────────────────────────────────────────────"

MODELL_DIR="$SCRIPT_DIR/modelle"
MEDIUM="$MODELL_DIR/ggml-medium.bin"
mkdir -p "$MODELL_DIR"

if [ -f "$MEDIUM" ]; then
    echo "✓ Whisper-medium schon da."
else
    echo ""
    echo "Whisper wandelt deine Sprache in Text um – komplett auf deinem Mac."
    echo "Download ~1.5 GB, dauert je nach Internet 3–10 Minuten."
    echo ""
    read -p "Enter drücken um Download zu starten..."
    curl -L --progress-bar \
      -o "$MEDIUM" \
      "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin"
    echo "✓ Whisper-medium geladen."
fi
echo ""
read -p "Weiter mit Enter..."

# ────────────────────────────────────────────────────────────
# SCHRITT 5: Ollama starten + Modell laden
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 5 von 7 – KI-Modell (Ollama llama3.1:8b, ~5 GB)"
echo "───────────────────────────────────────────────────────"

# Ollama-Dienst starten
brew services start ollama &>/dev/null || true
sleep 2

if ollama list 2>/dev/null | grep -q "llama3.1:8b"; then
    echo "✓ llama3.1:8b schon geladen."
else
    echo ""
    echo "llama3.1:8b ist das KI-Modell für den Sprach-Assistenten (ctrl_l-Shortcut)."
    echo "Läuft komplett lokal, ohne Internet."
    echo "Download ~5 GB, dauert je nach Internet 5–15 Minuten."
    echo ""
    read -p "Enter drücken um Download zu starten..."
    ollama pull llama3.1:8b
    echo "✓ llama3.1:8b geladen."
fi
echo ""
read -p "Weiter mit Enter..."

# ────────────────────────────────────────────────────────────
# SCHRITT 6: Config-Dateien anlegen
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 6 von 7 – Persönliche Config-Dateien"
echo "─────────────────────────────────────────────"

for f in config.json assistant_style.md vocabulary.csv; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        echo "✓ $f existiert schon (nicht überschrieben)."
    elif [ -f "$SCRIPT_DIR/$f.example" ]; then
        cp "$SCRIPT_DIR/$f.example" "$SCRIPT_DIR/$f"
        echo "✓ $f aus Vorlage angelegt."
    else
        # vocabulary.csv hat keine .example – leer anlegen
        if [ "$f" = "vocabulary.csv" ]; then
            echo "word,replacement" > "$SCRIPT_DIR/$f"
            echo "✓ $f leer angelegt."
        fi
    fi
done
echo ""
read -p "Weiter mit Enter..."

# ────────────────────────────────────────────────────────────
# SCHRITT 7: Terminal-Kurzbefehle
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 7 von 7 – Terminal-Kurzbefehle"
echo "───────────────────────────────────────"
echo ""
echo "Ab jetzt kannst du im Terminal tippen:"
echo ""
echo "  diktieren         → startet die App"
echo "  diktieren-update  → aktualisiert auf neueste Version"
echo ""

ALIAS_START="alias diktieren=\"cd '$SCRIPT_DIR' && python3 diktieren.py\""
ALIAS_UPDATE="alias diktieren-update=\"bash '$SCRIPT_DIR/update.sh'\""

# Alte Einträge entfernen (falls Setup schon mal lief)
if [ -f ~/.zshrc ]; then
    sed -i.bak '/alias diktieren=/d; /alias diktieren-update=/d' ~/.zshrc
    rm -f ~/.zshrc.bak
fi

echo "$ALIAS_START"  >> ~/.zshrc
echo "$ALIAS_UPDATE" >> ~/.zshrc
echo "✓ Kurzbefehle in ~/.zshrc eingetragen."
echo ""
read -p "Weiter mit Enter..."

# ────────────────────────────────────────────────────────────
# FERTIG
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "🎉 Setup abgeschlossen!"
echo "═══════════════════════"
echo ""
echo "Wichtig: Barrierefreiheit aktivieren"
echo "─────────────────────────────────────"
echo "Damit die App Tastatureingaben erkennen kann:"
echo ""
echo "  Systemeinstellungen"
echo "  → Datenschutz & Sicherheit"
echo "  → Barrierefreiheit"
echo "  → Terminal hinzufügen (Häkchen setzen)"
echo ""
echo "─────────────────────────────────────"
echo "So startest du die App:"
echo ""
echo "  1. Terminal-Fenster schließen"
echo "  2. Neues Terminal-Fenster öffnen"
echo "  3. Tippe:  diktieren"
echo ""
echo "Bei Fragen: passauf-unterstrich auf GitHub"
echo ""
