#!/bin/bash
# ─────────────────────────────────────────
# Wispr Setup – installiert alles was für die App gebraucht wird
# Läuft geführt Schritt für Schritt, prüft was schon da ist,
# lädt nur das Fehlende nach.
# ─────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Prüfe Mac-Kompatibilität..."
/bin/bash "$SCRIPT_DIR/check-platform.sh"
sleep 1

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
echo "Schritt 2 von 7 – Programme (Python 3.13, ffmpeg, ollama)"
echo "─────────────────────────────────────────────────────────"

for pkg in cmake ffmpeg ollama python@3.13; do
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

# ── whisper.cpp selbst bauen (feste Version, chip-unabhängig) ──
WHISPER_DIR="$SCRIPT_DIR/whisper.cpp"
WHISPER_BIN="$WHISPER_DIR/build/bin/whisper-cli"
WHISPER_TAG="v1.7.5"  # getestete Version, läuft auf allen Apple Silicon

if [ -f "$WHISPER_BIN" ]; then
    echo "✓ whisper-cli schon gebaut."
else
    echo ""
    echo "• Baue whisper.cpp aus Quellcode (~3 Min beim ersten Mal)..."
    if [ ! -d "$WHISPER_DIR" ]; then
        git clone --quiet --depth 1 --branch "$WHISPER_TAG" \
            https://github.com/ggml-org/whisper.cpp.git "$WHISPER_DIR"
    fi
    cd "$WHISPER_DIR"
    mit_spinner "Konfiguriere Build (cmake)" cmake -B build -DCMAKE_BUILD_TYPE=Release
    mit_spinner "Kompiliere whisper-cli (~3 Min)" cmake --build build --config Release -j
    cd "$SCRIPT_DIR"
    if [ ! -f "$WHISPER_BIN" ]; then
        echo "✗ whisper-cli-Build fehlgeschlagen"
        exit 1
    fi
    echo "✓ whisper-cli gebaut."
fi

mit_spinner "Geprüfte Python-Pakete installieren und testen" \
    /bin/bash "$SCRIPT_DIR/install-python-deps.sh"
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
    ERHALTEN=$(shasum -a 256 "$MEDIUM" | awk '{print $1}')
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

# Persönliche Texte und Einstellungen sind nicht für andere lokale Accounts.
for f in config.json assistant_style.md vocabulary.csv .historie.json; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        chmod 600 "$SCRIPT_DIR/$f"
    fi
done

echo ""
sleep 1.5

# ────────────────────────────────────────────────────────────
# SCHRITT 7: Native App + Terminal-Kurzbefehle
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 7 von 7 – Wispr.app + Terminal-Kurzbefehle"
echo "───────────────────────────────────────────────"
echo ""
echo "Die kleine native Wispr.app sorgt dafür, dass macOS Mikrofon- und"
echo "Bedienungshilfenrechte Wispr statt dem gesamten Terminal zuordnet."
echo ""
/bin/bash "$SCRIPT_DIR/build-macos-app.sh"
echo ""
echo "Ab jetzt kannst du im Terminal tippen:"
echo ""
echo "  diktieren         → startet die App"
echo "  diktiere          → startet ebenfalls die App"
echo "  diktieren-update  → aktualisiert auf neueste Version"
echo ""
/bin/bash "$SCRIPT_DIR/install-terminal-commands.sh"
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
echo "   → Wispr hinzufügen bzw. den Schalter bei Wispr aktivieren"
echo ""
echo "2) MIKROFON (damit Aufnahmen funktionieren):"
echo ""
echo "   Systemeinstellungen"
echo "   → Datenschutz & Sicherheit"
echo "   → Mikrofon"
echo "   → Den Schalter bei Wispr aktivieren"
echo ""
echo "   Hinweis: Beim ersten Start mit 'diktieren' fragt macOS selbst nach"
echo "   beiden Rechten. Dabei erscheint Wispr in den Listen."
echo ""
echo "   Nach dem Setzen der Häkchen: Wispr über das Menüleisten-Symbol"
echo "   beenden und mit 'diktieren' neu starten."
echo ""
echo "─────────────────────────────────────"
echo "So startest du die App:"
echo ""
echo "  1. Terminal-Fenster schließen"
echo "  2. Neues Terminal-Fenster öffnen"
echo "  3. Tippe:  diktieren   (oder: diktiere)"
echo ""
echo "Das Setup hat deine Login-Shell automatisch erkannt und den"
echo "Terminal-Pfad passend eingerichtet. Nach einem Neustart kannst du"
echo "die App mit beiden Befehlen jederzeit wieder starten."
echo ""
echo "Datenschutz: Normale Diktate und der lokale KI-Modus bleiben auf"
echo "diesem Mac. Das Mitschneiden der allgemeinen Zwischenablage ist bei"
echo "Neuinstallationen aus. Nur der optionale Claude-Modus sendet Text an"
echo "einen externen API-Dienst."
echo ""
echo "Bei Fragen: passauf-unterstrich auf GitHub"
echo ""
echo ""
echo "═══════════════════════════════════════════════"
echo "  Du kannst dieses Fenster jetzt schließen."
echo "═══════════════════════════════════════════════"
echo ""
