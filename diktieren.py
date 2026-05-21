#!/usr/bin/env python3
"""
Lokale Diktierfunktion
======================
Nimmt Sprache auf, transkribiert lokal mit Whisper,
wendet Vocabulary-Replacements an, und fügt Text per
Zwischenablage ein wo der Cursor gerade ist.

Modell einfach wechseln: MODEL = "medium" → "large" etc.
"""

import os
import sys
import csv
import time
import tempfile
import subprocess
import pyperclip
import pyautogui
import whisper

import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────
# KONFIGURATION – hier alles anpassen
# ─────────────────────────────────────────
 
# Whisper Modell: "tiny", "base", "small", "medium", "large"
# Einfach hier ändern um ein anderes Modell zu nutzen
MODEL = "medium"
MODEL_DIR = "/Users/linus/Desktop/Tech/Diktierfunktion(lokal)/Selbstgebaut/modelle"
 
# Sprache – "de" für Deutsch, "en" für Englisch
LANGUAGE = "de"
 
# Pfad zur Vocabulary CSV (dieselbe die wir für SuperWhisper gebaut haben)
# Leer lassen wenn keine Vocabulary-Datei vorhanden
VOCABULARY_CSV = "/Users/linus/Desktop/Tech/Diktierfunktion(lokal)/Selbstgebaut/vocabulary.csv"
 
# Aufnahmedauer in Sekunden
# Später können wir das auf Push-to-Talk umbauen
RECORD_SECONDS = 5
 
# Wo ffmpeg liegt (haben wir vorhin rausgefunden)
FFMPEG = "/opt/homebrew/bin/ffmpeg"

# ─────────────────────────────────────────
# VOCABULARY LADEN
# Liest die CSV und baut ein Dictionary:
# {"AGG": "§", "Paragraph": "§", ...}
# ─────────────────────────────────────────

def lade_vocabulary(pfad):
    replacements = {}
    if not pfad or not os.path.exists(pfad):
        print(f"ℹ️  Keine Vocabulary-Datei gefunden unter: {pfad}")
        return replacements

    with open(pfad, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wort = row.get("word", "").strip()
            ersetzung = row.get("replacement", "").strip()
            if wort and ersetzung:
                replacements[wort] = ersetzung

    print(f"✅ {len(replacements)} Replacements geladen")
    return replacements

# ─────────────────────────────────────────
# VOCABULARY ALS INITIAL PROMPT
# ─────────────────────────────────────────

def baue_initial_prompt(pfad):
    woerter = []
    if not pfad or not os.path.exists(pfad):
        return ""

    with open(pfad, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wort = row.get("word", "").strip()
            if wort:
                woerter.append(wort)

    prompt = ", ".join(woerter)
    print(f"ℹ️  Initial Prompt: {len(woerter)} Wörter als Kontext")
    return prompt

    # ─────────────────────────────────────────
# REPLACEMENT ANWENDEN
# ─────────────────────────────────────────

def wende_replacements_an(text, replacements):
    for wort, ersetzung in replacements.items():
        text = text.replace(wort, ersetzung)
    return text


# ─────────────────────────────────────────
# MIKROFON AUFNEHMEN
# ─────────────────────────────────────────

def nehme_auf(sekunden):
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_pfad = tmp.name
    tmp.close()

    print(f"🎤 Aufnahme läuft ({sekunden} Sekunden)...")

    befehl = [
        FFMPEG,
        "-f", "avfoundation",
        "-i", ":0",
        "-t", str(sekunden),
        "-ar", "16000",
        "-ac", "1",
        "-y",
        tmp_pfad
    ]

    subprocess.run(befehl, stderr=subprocess.DEVNULL, check=True)
    print("✅ Aufnahme fertig")
    return tmp_pfad


# ─────────────────────────────────────────
# TEXT EINFÜGEN
# ─────────────────────────────────────────

def fuege_text_ein(text):
    pyperclip.copy(text)
    time.sleep(0.1)
    pyautogui.hotkey("command", "v")
    print(f"✅ Text eingefügt: {text[:50]}...")

# ─────────────────────────────────────────
# HAUPTPROGRAMM
# ─────────────────────────────────────────

def main():
    print("🚀 Diktierfunktion startet...")
    print(f"📦 Lade Whisper Modell '{MODEL}'...")
    print("   (Beim ersten Mal wird das Modell heruntergeladen ~1.5GB)")

    modell = whisper.load_model(MODEL, download_root=MODEL_DIR)
    print(f"✅ Modell '{MODEL}' geladen")

    replacements = lade_vocabulary(VOCABULARY_CSV)
    initial_prompt = baue_initial_prompt(VOCABULARY_CSV)

    print(f"\n⚙️  Konfiguration:")
    print(f"   Modell:   {MODEL}")
    print(f"   Sprache:  {LANGUAGE}")
    print(f"   Dauer:    {RECORD_SECONDS} Sekunden")
    print(f"\nDrücke Enter um Aufnahme zu starten (Ctrl+C zum Beenden)")

    while True:
        try:
            input()

            audio_pfad = nehme_auf(RECORD_SECONDS)

            print("🔄 Transkribiere...")
            ergebnis = modell.transcribe(
                audio_pfad,
                language=LANGUAGE,
                initial_prompt=initial_prompt
            )
            text = ergebnis["text"].strip()
            print(f"📝 Erkannt: {text}")

            if replacements:
                text = wende_replacements_an(text, replacements)
                print(f"✏️  Nach Replacement: {text}")

            fuege_text_ein(text)
            os.unlink(audio_pfad)

            print("\nDrücke Enter für nächste Aufnahme (Ctrl+C zum Beenden)")

        except KeyboardInterrupt:
            print("\n👋 Beendet")
            sys.exit(0)


if __name__ == "__main__":
    main()