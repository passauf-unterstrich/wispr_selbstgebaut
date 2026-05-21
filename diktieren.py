#!/usr/bin/env python3
"""
Lokale Diktierfunktion – Menu Bar App
======================================
Läuft als Icon in der Menüleiste.
Globaler Shortcut: Cmd+Shift+D halten → aufnehmen → loslassen → Text erscheint.
Startet automatisch beim Mac-Start.
"""

import os
import sys
import csv
import time
import tempfile
import subprocess
import threading
import warnings
warnings.filterwarnings("ignore")

import rumps
import pyperclip
import pyautogui
import re
from pynput import keyboard

# ─────────────────────────────────────────
# KONFIGURATION
# ─────────────────────────────────────────

# Verfügbare Modelle – hier neue einfach hinzufügen
MODELLE = {
    "medium": "/Users/linus/Desktop/Tech/Diktierfunktion(lokal)/Selbstgebaut/modelle/ggml-medium.bin",
    "large-v3": "/Users/linus/Desktop/Tech/Diktierfunktion(lokal)/Selbstgebaut/modelle/ggml-large-v3.bin",
}

# Standardmodell beim Start
AKTIVES_MODELL = "medium"

WHISPER_CLI = "/opt/homebrew/bin/whisper-cli"
LANGUAGE = "de"
VOCABULARY_CSV = "/Users/linus/Desktop/Tech/Diktierfunktion(lokal)/Selbstgebaut/vocabulary.csv"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
MIKROFON = "1" # MacBook Pro Microphone
# [0] ZoomAudioDevice
# [1] MacBook Pro Microphone  ← das wollen wir
# [2] Microsoft Teams Audio

# ─────────────────────────────────────────
# SHORTCUT KONFIGURATION
# Hier einfach ändern:
# Cmd+Shift+D:  {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('d')}
# Ctrl+Space:   {keyboard.Key.ctrl, keyboard.Key.space}
# Fn-Taste:     {keyboard.Key.f17}  ← testen ob das klappt
# Control-Taste:  {keyboard.Key.ctrl_l}
# ─────────────────────────────────────────

SHORTCUT = SHORTCUT = {keyboard.Key.alt_r}

# ─────────────────────────────────────────
# VOCABULARY
# ─────────────────────────────────────────

def lade_vocabulary(pfad):
    replacements = {}
    if not pfad or not os.path.exists(pfad):
        return replacements
    with open(pfad, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wort = row.get("word", "").strip()
            ersetzung = row.get("replacement", "").strip()
            if wort and ersetzung:
                replacements[wort] = ersetzung
    return replacements


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
    return ", ".join(woerter)


def wende_replacements_an(text, replacements):
    # Whisper Annotationen entfernen: [Lachen], [Musik] etc.
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    text = text.strip()
    
    for wort, ersetzung in replacements.items():
        text = text.replace(wort, ersetzung)
    return text


# ─────────────────────────────────────────
# AUFNAHME UND EINFÜGEN
# ─────────────────────────────────────────

def nehme_auf(pfad):
    befehl = [
        FFMPEG,
        "-f", "avfoundation",
        "-i", ":0",
        "-ar", "16000",
        "-ac", "1",
        "-y",
        pfad
    ]
    subprocess.run(befehl, stderr=subprocess.DEVNULL)


def stoppe_aufnahme(prozess):
    prozess.terminate()


def fuege_text_ein(text):
    pyperclip.copy(text + " ") # Leerzeichen am Ende
    time.sleep(0.1)
    pyautogui.hotkey("command", "v")

# ─────────────────────────────────────────
# MENU BAR APP
# ─────────────────────────────────────────

class DiktierApp(rumps.App):
    def __init__(self):
        super().__init__("🎤", quit_button="Beenden")

        # Modell-Untermenü aufbauen
        modell_menu = rumps.MenuItem("Modell")
        for name in MODELLE:
            item = rumps.MenuItem(name, callback=self.wechsle_modell)
            if name == AKTIVES_MODELL:
                item.state = True  # Häkchen
            modell_menu.add(item)

        self.menu = [
            rumps.MenuItem("Diktierfunktion aktiv"),
            rumps.separator,
            modell_menu,
            rumps.MenuItem("Sprache: " + LANGUAGE),
        ]

        self.aufnahme_aktiv = False
        self.aktuelle_tasten = set()
        self.ffmpeg_prozess = None
        self.tmp_pfad = None
        self.aktives_modell = AKTIVES_MODELL

        self.title = "🎤"
        rumps.notification("Diktierfunktion", "", "Bereit – option-rechts zum Diktieren")

        threading.Thread(target=self.starte_keyboard_listener, daemon=True).start()
        threading.Thread(target=self.lade_modell, daemon=True).start()

    def lade_modell(self):
        self.replacements = lade_vocabulary(VOCABULARY_CSV)
        self.initial_prompt = baue_initial_prompt(VOCABULARY_CSV)
        self.title = "🎤"
        rumps.notification("Diktierfunktion", "", "Bereit – option-rechts zum Diktieren")

    def wechsle_modell(self, sender):
        # Häkchen von altem Modell entfernen
        self.menu["Modell"][self.aktives_modell].state = False
        
        # Neues Modell aktivieren
        self.aktives_modell = sender.title
        self.menu["Modell"][self.aktives_modell].state = True
        
        rumps.notification("Modell gewechselt", "", f"Aktiv: {self.aktives_modell}")

# ─────────────────────────────────────────
# TASTATUR LISTENER
# ─────────────────────────────────────────

    def starte_keyboard_listener(self):
        def on_press(taste):
            try:
                self.aktuelle_tasten.add(taste)
                if SHORTCUT.issubset(self.aktuelle_tasten):
                    if not self.aufnahme_aktiv:
                        self.starte_aufnahme()
            except Exception:
                pass

        def on_release(taste):
            try:
                self.aktuelle_tasten.discard(taste)
                if self.aufnahme_aktiv:
                    # Prüfen ob eine Shortcut-Taste losgelassen wurde
                    if taste in SHORTCUT:
                        self.beende_aufnahme()
            except Exception:
                pass

        listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        listener.start()

# ─────────────────────────────────────────
# AUFNAHME STARTEN UND BEENDEN
# ─────────────────────────────────────────

    def starte_aufnahme(self):
        self.aufnahme_aktiv = True
        self.title = "🔴"

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self.tmp_pfad = tmp.name
        tmp.close()

        befehl = [
            FFMPEG,
            "-f", "avfoundation",
            "-i", f":{MIKROFON}",
            "-ar", "16000",
            "-ac", "1",
            "-y",
            self.tmp_pfad
        ]
        self.ffmpeg_prozess = subprocess.Popen(
            befehl,
            stderr=subprocess.DEVNULL
        )

        # Timer für 25 Sekunden Warnung
        self.warn_timer = threading.Timer(25.0, self.zeige_limit_warnung)
        self.warn_timer.start()

    def zeige_limit_warnung(self):
        if self.aufnahme_aktiv:
            self.title = "⚠️"

    def beende_aufnahme(self):
        self.aufnahme_aktiv = False
        self.title = "⏳"

        # Timer canceln falls noch läuft
        if hasattr(self, 'warn_timer'):
            self.warn_timer.cancel()

        if self.ffmpeg_prozess:
            self.ffmpeg_prozess.terminate()
            self.ffmpeg_prozess.wait()

        threading.Thread(target=self.transkribiere, daemon=True).start()

# ─────────────────────────────────────────
# TRANSKRIPTION
# ─────────────────────────────────────────

    def transkribiere(self):
        try:
            if not os.path.exists(self.tmp_pfad):
                return

            befehl = [
                WHISPER_CLI,
                "--language", LANGUAGE,
                "--model", MODELLE[self.aktives_modell],
                "--no-timestamps",
                "--no-prints",
                "--file", self.tmp_pfad,
            ]

            ergebnis = subprocess.run(
                befehl,
                capture_output=True,
                text=True
            )

            text = ergebnis.stdout.strip()

            if not text:
                return

            if self.replacements:
                text = wende_replacements_an(text, self.replacements)

            if text:
                fuege_text_ein(text)

            os.unlink(self.tmp_pfad)

        except Exception as e:
            rumps.notification("Fehler", "", str(e))

        finally:
            self.title = "🎤"

# ─────────────────────────────────────────
# APP STARTEN
# ─────────────────────────────────────────

    def application_did_finish_launching(self, notification):
        threading.Thread(
            target=self.starte_keyboard_listener,
            daemon=True
        ).start()



# ─────────────────────────────────────────
# HAUPTPROGRAMM
# ─────────────────────────────────────────

if __name__ == "__main__":
    app = DiktierApp()
    app.run()

