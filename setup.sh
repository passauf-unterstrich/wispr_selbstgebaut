#!/bin/bash
# ─────────────────────────────────────────
# Setup – Diktierfunktion + KI-Assistent
# ─────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

clear
echo ""
echo "🎤 Willkommen beim Setup der Diktierfunktion"
echo "════════════════════════════════════════════"
echo ""
echo "Dieses Script führt dich Schritt für Schritt"
echo "durch die Installation. Du wirst immer gefragt"
echo "bevor etwas passiert."
echo ""
read -p "Bereit? Drücke Enter um zu starten..."

# ────────────────────────────────────────────────────────────
# SCHRITT 1: Homebrew
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 1 von 5 – Homebrew"
echo "──────────────────────────"
echo ""
echo "Was ist Homebrew?"
echo "Homebrew ist ein Programm das andere Programme installiert."
echo "Es ist der einfachste Weg, Tools wie whisper-cli auf dem"
echo "Mac zu installieren. Vergleichbar mit dem App Store –"
echo "nur für Terminal-Programme."
echo ""

if command -v brew &>/dev/null; then
    echo "✓ Homebrew ist bereits installiert – kein Download nötig."
else
    echo "⚠️  Homebrew ist noch nicht installiert."
    echo ""
    echo "Was jetzt passiert:"
    echo "→ Homebrew wird von der offiziellen Website geladen"
    echo "→ Apple's Entwickler-Tools werden mitinstalliert"
    echo "→ Das kann 5–15 Minuten dauern"
    echo ""
    read -p "Enter drücken um Homebrew zu installieren..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo ""
    echo "✓ Homebrew installiert."
fi

read -p "Weiter mit Enter..."

# ────────────────────────────────────────────────────────────
# SCHRITT 2: Programme installieren
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 2 von 5 – Programme installieren"
echo "─────────────────────────────────────────"
echo ""
echo "Drei Programme werden installiert:"
echo ""
echo "  whisper-cli  →  wandelt deine Sprache in Text um (lokal, kein Internet nötig)"
echo "  ffmpeg       →  nimmt den Ton vom Mikrofon auf"
echo "  ollama       →  führt das KI-Modell lokal auf deinem Mac aus"
echo ""
echo "Download-Größe: ca. 200–400 MB"
echo ""
read -p "Enter drücken um die Programme zu installieren..."
echo ""

brew install whisper-cli ffmpeg ollama

echo ""
echo "✓ Alle Programme installiert."
read -p "Weiter mit Enter..."

# ────────────────────────────────────────────────────────────
# SCHRITT 3: Python-Umgebung
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 3 von 5 – Python-Umgebung einrichten"
echo "─────────────────────────────────────────────"
echo ""
echo "Was ist eine Python-Umgebung (venv)?"
echo "Die App ist in Python geschrieben und braucht einige"
echo "Zusatz-Bibliotheken. Eine venv ist ein isolierter Ordner"
echo "nur für diese App – so kommt nichts mit dem Rest des"
echo "Computers durcheinander."
echo ""
echo "Was jetzt passiert:"
echo "→ Ein Ordner 'venv' wird im App-Ordner erstellt"
echo "→ Benötigte Bibliotheken werden dort installiert"
echo "→ Dauert ca. 1–2 Minuten"
echo ""
read -p "Enter drücken um fortzufahren..."
echo ""

python3 -m venv "$SCRIPT_DIR/venv"
"$SCRIPT_DIR/venv/bin/pip" install --upgrade pip --quiet
"$SCRIPT_DIR/venv/bin/pip" install rumps pyperclip requests pynput anthropic --quiet

echo ""
echo "✓ Python-Umgebung eingerichtet."
read -p "Weiter mit Enter..."

# ────────────────────────────────────────────────────────────
# SCHRITT 4: Ollama starten
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 4 von 5 – KI-Dienst einrichten"
echo "───────────────────────────────────────"
echo ""
echo "Was ist Ollama?"
echo "Ollama ist ein Dienst der das KI-Modell auf deinem Mac"
echo "ausführt – komplett lokal, ohne Internet, ohne dass"
echo "deine Daten irgendwo hingeschickt werden."
echo ""
echo "Was jetzt passiert:"
echo "→ Ollama wird als Hintergrunddienst eingerichtet"
echo "→ Er startet automatisch bei jedem Mac-Start"
echo "→ Das KI-Modell (~5 GB) wird beim ersten App-Start"
echo "  automatisch heruntergeladen"
echo ""
read -p "Enter drücken um fortzufahren..."
echo ""

brew services start ollama

echo ""
echo "✓ Ollama-Dienst eingerichtet."
read -p "Weiter mit Enter..."

# ────────────────────────────────────────────────────────────
# SCHRITT 5: Startbefehl einrichten
# ────────────────────────────────────────────────────────────
clear
echo ""
echo "Schritt 5 von 5 – Startbefehl einrichten"
echo "─────────────────────────────────────────"
echo ""
echo "Damit du die App immer einfach starten kannst,"
echo "wird ein Kurzbefehl eingerichtet."
echo ""
echo "Ab jetzt reicht im Terminal:"
echo ""
echo "  diktieren"
echo ""
echo "Das funktioniert egal in welchem Ordner du bist."
echo ""
read -p "Enter drücken um fortzufahren..."

ALIAS_LINE="alias diktieren=\"cd '$SCRIPT_DIR' && '$SCRIPT_DIR/venv/bin/python3' diktieren.py\""

if grep -q "alias diktieren=" ~/.zshrc 2>/dev/null; then
    echo ""
    echo "✓ Startbefehl bereits vorhanden."
else
    echo "$ALIAS_LINE" >> ~/.zshrc
    echo ""
    echo "✓ Startbefehl eingerichtet."
fi

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
echo "  → Terminal hinzufügen ✓"
echo ""
echo "─────────────────────────────────────"
echo "So startest du die App:"
echo ""
echo "  1. Dieses Terminal-Fenster schließen"
echo "  2. Neues Terminal-Fenster öffnen"
echo "  3. Eingeben:  diktieren"
echo ""
echo "Beim ersten Start werden automatisch die Sprachmodelle"
echo "heruntergeladen (~6 GB). Das dauert einige Minuten."
echo ""
