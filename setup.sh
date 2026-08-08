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
echo ""
echo "Zwei Wege:"
echo ""
echo "  [A] Alles automatisch nachladen aus dem Internet (Standard)"
echo "      Braucht ~7 GB Download, dauert je nach Internet 15–60 Min."
echo ""
echo "  [B] ZIP-Dateien mit den Modellen habe ich schon im Downloads-Ordner"
echo "      Namen der Dateien: wispr-whisper.zip + wispr-ollama.zip"
echo "      Dann geht das Setup deutlich schneller (nur ~5 Min)."
echo ""
read -p "A oder B eingeben und Enter drücken: " MODUS
MODUS=$(echo "$MODUS" | tr '[:lower:]' '[:upper:]')
if [ "$MODUS" != "B" ]; then MODUS="A"; fi
echo ""
echo "Gewählt: Modus $MODUS"
echo ""
if [ "$MODUS" = "A" ]; then
    echo "Alles läuft jetzt automatisch durch – zurücklehnen und warten."
    echo "Bei Homebrew-Installation wird einmal dein Passwort abgefragt."
fi
sleep 2

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
sleep 1.5

# ────────────────────────────────────────────────────────────
# SCHRITT 2: Programme
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 2 von 7 – Programme (whisper-cli, ffmpeg, ollama)"
echo "──────────────────────────────────────────────────────────"

for pkg in whisper-cpp ffmpeg ollama; do
    if brew list "$pkg" &>/dev/null; then
        echo "✓ $pkg ist installiert."
    else
        echo ""
        echo "• Installiere $pkg via brew (kann 5–20 Minuten dauern beim ersten Mal)..."
        echo "  Fortschritt wird direkt von Homebrew angezeigt:"
        echo ""
        brew install "$pkg"
        echo "✓ $pkg installiert."
    fi
done
echo ""
sleep 1.5

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
sleep 1.5

# venv anlegen (isoliert vom System-Python)
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "• Lege virtuelle Python-Umgebung an..."
    python3 -m venv "$VENV_DIR"
fi

VENV_PIP="$VENV_DIR/bin/pip"
mit_spinner "pip aktualisieren" "$VENV_PIP" install --upgrade pip --quiet
mit_spinner "Python-Pakete installieren (torch, rumps, silero-vad, ...)" \
    "$VENV_PIP" install --quiet -r "$SCRIPT_DIR/requirements.txt"
sleep 1.5

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

# ── Modus B: Vor dem Download-Versuch die ZIPs aus Downloads entpacken ──
if [ "$MODUS" = "B" ] && [ ! -f "$MEDIUM" ]; then
    WHISPER_ZIP="$HOME/Downloads/wispr-whisper.zip"
    OLLAMA_ZIP="$HOME/Downloads/wispr-ollama.zip"
    if [ ! -f "$WHISPER_ZIP" ] || [ ! -f "$OLLAMA_ZIP" ]; then
        echo ""
        echo "✗ ZIP-Dateien nicht gefunden im Downloads-Ordner:"
        echo "  Erwartet: $WHISPER_ZIP"
        echo "  Erwartet: $OLLAMA_ZIP"
        echo ""
        echo "Bitte beide ZIPs nach ~/Downloads/ legen und dann"
        echo "im Terminal erneut ausführen:"
        echo ""
        echo "  cd $SCRIPT_DIR && bash setup.sh"
        echo ""
        exit 1
    fi
    echo "• Entpacke Whisper-Modell aus $WHISPER_ZIP ..."
    unzip -o -q "$WHISPER_ZIP" -d "$SCRIPT_DIR"
    echo "• Entpacke Ollama-Modell aus $OLLAMA_ZIP ..."
    unzip -o -q "$OLLAMA_ZIP" -d "$HOME"
    echo "✓ ZIPs entpackt."

    # Ollama-Service neu starten, damit er die frisch entpackten Modelle einliest
    echo "• Aktualisiere Ollama-Modell-Registry ..."
    brew services restart ollama &>/dev/null || true
    sleep 3

    # Prüfen ob das Modell jetzt erkannt wird
    if ollama list 2>/dev/null | grep -q "llama3.1:8b"; then
        echo "✓ Ollama erkennt llama3.1:8b."
    else
        echo ""
        echo "⚠ Ollama erkennt das Modell noch nicht. Versuche zweiten Neustart..."
        brew services stop ollama &>/dev/null || true
        sleep 2
        brew services start ollama &>/dev/null || true
        sleep 4
        if ollama list 2>/dev/null | grep -q "llama3.1:8b"; then
            echo "✓ Ollama erkennt llama3.1:8b."
        else
            echo ""
            echo "✗ Ollama findet das entpackte Modell nicht."
            echo "  Bitte manuell prüfen: ollama list"
            echo "  Falls leer: ollama pull llama3.1:8b (5 GB Download)"
            exit 1
        fi
    fi
    echo ""
fi

if [ -f "$MEDIUM" ]; then
    echo "✓ Whisper-medium schon da."
else
    echo ""
    echo "Whisper wandelt deine Sprache in Text um – komplett auf deinem Mac."
    echo "Download ~1.5 GB, dauert je nach Internet 3–10 Minuten."
    echo ""
    read -p "Enter drücken um Download zu starten..."
    curl -L --progress-bar --retry 5 --retry-delay 3 --retry-connrefused \
      -o "$MEDIUM" \
      "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin"

    # SHA256-Prüfung – schützt vor manipuliertem Download
    ERWARTET="6c14d5adee5f86394037b4e4e8b59f1673b6cee10e3cf0b11bbdbee79c156208"
    ERHALTEN=$(shasum -a 256 "$MEDIUM" | awk '"'"'{print $1}'"'"')
    if [ "$ERHALTEN" != "$ERWARTET" ]; then
        echo ""
        echo "✗ SHA256-Prüfung fehlgeschlagen!"
        echo "  Erwartet: $ERWARTET"
        echo "  Erhalten: $ERHALTEN"
        echo "  Datei gelöscht. Setup abgebrochen."
        rm -f "$MEDIUM"
        exit 1
    fi
    echo "✓ Whisper-medium geladen und geprüft."
fi
echo ""
sleep 1.5

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
sleep 1.5

# ────────────────────────────────────────────────────────────
# SCHRITT 6: Config-Dateien anlegen
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 6 von 7 – Persönliche Config-Dateien"
echo "─────────────────────────────────────────────"

# Auf älteren Apple-Chips (vor M5) Whisper auf CPU zwingen (Metal-Bug)
CHIP_INFO=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "unknown")
if echo "$CHIP_INFO" | grep -qE "M1|M2|M3|M4"; then
    NEED_NO_GPU=true
    echo "• Erkannter Chip: $CHIP_INFO → Whisper läuft auf CPU (Metal-Kompatibilität)"
else
    NEED_NO_GPU=false
fi

for f in config.json assistant_style.md vocabulary.csv; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        echo "✓ $f existiert schon (nicht überschrieben)."
    elif [ -f "$SCRIPT_DIR/$f.example" ]; then
        cp "$SCRIPT_DIR/$f.example" "$SCRIPT_DIR/$f"
        echo "✓ $f aus Vorlage angelegt."
    else
        if [ "$f" = "vocabulary.csv" ]; then
            echo "word,replacement" > "$SCRIPT_DIR/$f"
            echo "✓ $f leer angelegt."
        fi
    fi
done

# whisper_no_gpu in Config setzen, falls Chip vor M5
if [ "$NEED_NO_GPU" = "true" ] && [ -f "$SCRIPT_DIR/config.json" ]; then
    python3 -c "
import json
p='$SCRIPT_DIR/config.json'
c=json.load(open(p))
c['whisper_no_gpu']=True
json.dump(c,open(p,'w'),indent=2,ensure_ascii=False)
"
    echo "✓ Whisper-Modus auf CPU gesetzt (config.json: whisper_no_gpu=true)"
fi
echo ""
sleep 1.5

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

ALIAS_START="alias diktieren=\"cd '$SCRIPT_DIR' && '$VENV_DIR/bin/python3' diktieren.py\""
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
sleep 1.5

# ────────────────────────────────────────────────────────────
# FERTIG
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "🎉 Setup abgeschlossen!"
echo "═══════════════════════"
echo ""
echo "Wichtig: ZWEI Berechtigungen aktivieren"
echo "════════════════════════════════════════"
echo ""
echo "1) BARRIEREFREIHEIT (damit Tastatur-Shortcuts funktionieren):"
echo ""
echo "   Systemeinstellungen"
echo "   → Datenschutz & Sicherheit"
echo "   → Barrierefreiheit"
echo "   → Terminal hinzufügen (Häkchen setzen)"
echo ""
echo "2) MIKROFON (damit Aufnahmen funktionieren):"
echo ""
echo "   Systemeinstellungen"
echo "   → Datenschutz & Sicherheit"
echo "   → Mikrofon"
echo "   → Terminal hinzufügen (Häkchen setzen)"
echo ""
echo "   Hinweis: Falls Terminal in der Liste fehlt, einmal 'diktieren' starten"
echo "   und Aufnahme-Taste drücken → macOS fragt dann selbst und Terminal"
echo "   erscheint in der Mikrofon-Liste."
echo ""
echo "   Nach dem Setzen der Häkchen: Terminal komplett schließen und"
echo "   neu öffnen (macOS aktualisiert Berechtigungen nicht live)."
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
echo ""
echo "═══════════════════════════════════════════════"
echo "  Du kannst dieses Fenster jetzt schließen."
echo "═══════════════════════════════════════════════"
echo ""
