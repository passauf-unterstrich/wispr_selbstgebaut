#!/usr/bin/env python3
"""
Lokale Diktierfunktion – Menu Bar App
======================================
Läuft als Icon in der Menüleiste.
Globaler Shortcut: alt_r halten → aufnehmen → loslassen → Text erscheint.
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
import requests
from pynput.keyboard import Controller as KeyboardController
import re
from pynput import keyboard

import urllib.request

# ─────────────────────────────────────────
# KONFIGURATION
# ─────────────────────────────────────────
from pathlib import Path
import shutil

# Ordner in dem dieses Skript liegt – App-Dateien werden relativ dazu gefunden
SCRIPT_DIR  = Path(__file__).resolve().parent
MODELLE_DIR = SCRIPT_DIR / "modelle"

# Verfügbare Whisper-Modelle
MODELLE = {
    "medium":   str(MODELLE_DIR / "ggml-medium.bin"),
    "large-v3": str(MODELLE_DIR / "ggml-large-v3.bin"),
}
AKTIVES_MODELL = "medium"

# Externe Programme im PATH suchen (funktioniert egal wo Homebrew liegt)
WHISPER_CLI = shutil.which("whisper-cli") or "/opt/homebrew/bin/whisper-cli"
FFMPEG      = shutil.which("ffmpeg")      or "/opt/homebrew/bin/ffmpeg"

LANGUAGE       = "de"
VOCABULARY_CSV = str(SCRIPT_DIR / "vocabulary.csv")

# Mikrofon: "default" = macOS System-Standard (später im Menü umstellbar)
MIKROFON = "default"

# ─────────────────────────────────────────
# CONFIG-DATEI LADEN (überschreibt Defaults oben)
# ─────────────────────────────────────────
import json as _json
_config_path = SCRIPT_DIR / "config.json"
if _config_path.exists():
    try:
        _cfg = _json.loads(_config_path.read_text())
        AKTIVES_MODELL = _cfg.get("aktives_modell", AKTIVES_MODELL)
        LANGUAGE       = _cfg.get("sprache",        LANGUAGE)
        MIKROFON       = _cfg.get("mikrofon",       MIKROFON)
    except Exception as _e:
        print(f"⚠️  config.json konnte nicht gelesen werden: {_e}")

# ─────────────────────────────────────────
# KONFIGURATION – KI-ASSISTENT
# ─────────────────────────────────────────

ASSISTANT_STYLE_FILE = str(SCRIPT_DIR / "assistant_style.md")

# Ollama (lokal) – ollama pull llama3.1:8b
OLLAMA_URL    = "http://localhost:11434/api/chat"
OLLAMA_MODELL = "llama3.1:8b"

# Claude API – API-Key eintragen oder als Umgebungsvariable setzen
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODELL     = "claude-haiku-4-5-20251001"

KI_MODI          = ["Lokal (Ollama)", "Claude API"]
AKTIVER_KI_MODUS = "Lokal (Ollama)"

# KI-Modelle aus config.json (falls vorhanden)
if _config_path.exists():
    try:
        _cfg2 = _json.loads(_config_path.read_text())
        OLLAMA_MODELL = _cfg2.get("ollama_modell", OLLAMA_MODELL)
        CLAUDE_MODELL = _cfg2.get("claude_modell", CLAUDE_MODELL)
        AKTIVER_KI_MODUS = _cfg2.get("aktiver_ki_modus", AKTIVER_KI_MODUS)
    except Exception:
        pass

# ─────────────────────────────────────────
# SHORTCUT KONFIGURATION
# Hier einfach ändern:
# Cmd+Shift+D:  {keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('d')}
# Ctrl+Space:   {keyboard.Key.ctrl, keyboard.Key.space}
# Fn-Taste:     {keyboard.Key.f17}  ← testen ob das klappt
# Control-Taste:  {keyboard.Key.ctrl_l}
# ─────────────────────────────────────────

SHORTCUT           = {keyboard.Key.alt_r}
SHORTCUT_KI        = {keyboard.Key.ctrl_l}
SHORTCUT_KORREKTUR = {keyboard.Key.cmd_r,  keyboard.Key.shift_r}

DIKTAT_TIMER_DELAY = 0.10  # Sekunden Wartezeit bevor Diktat startet

def shortcut_als_text(shortcut):
    namen = {
        keyboard.Key.alt_r:   "opt-r",
        keyboard.Key.ctrl_l:  "ctrl-l",
        keyboard.Key.ctrl_r:  "ctrl-r",
        keyboard.Key.cmd_r:   "cmd-r",
        keyboard.Key.shift_r: "shift-r",
        keyboard.Key.shift:   "shift",
    }
    return " + ".join(namen.get(k, str(k)) for k in shortcut)

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

def lade_style_prompt(pfad):
    if not pfad or not os.path.exists(pfad):
        return ""
    with open(pfad, encoding="utf-8") as f:
        return f.read().strip()

# ─────────────────────────────────────────
# AUFNAHME UND EINFÜGEN
# ─────────────────────────────────────────


_kb = KeyboardController()

def berechne_audio_energie(pfad):
    import wave, struct
    with wave.open(pfad, 'rb') as wf:
        frames = wf.readframes(wf.getnframes())
    if len(frames) < 2:
        return 0
    samples = struct.unpack(f'{len(frames)//2}h', frames)
    return (sum(s**2 for s in samples) / len(samples)) ** 0.5


def fuege_text_ein(text):
    if not text or not text.strip():
        return
    pyperclip.copy(text + " ")
    time.sleep(0.1)
    with _kb.pressed(keyboard.Key.cmd):
        _kb.press('v')
        _kb.release('v')

# ─────────────────────────────────────────
# KI-ANFRAGEN
# ─────────────────────────────────────────

SYSTEM_PROMPT_BASIS = (
    "Du bist ein persönlicher Assistent. "
    "Gib AUSSCHLIESSLICH den fertigen Text zurück – nichts weiter. "
    "Keine Einleitung, kein Kommentar, keine Erklärung, kein Abschluss. "
    "Nur der Text selbst, so wie er direkt verwendet werden kann. "
    "Antworte immer auf Deutsch, außer der Befehl verlangt ausdrücklich eine andere Sprache."
)


def frage_ollama(befehl: str, style_prompt: str) -> str:
    system = SYSTEM_PROMPT_BASIS
    if style_prompt:
        system += f"\n\n---\nMein Stil und Beispiele:\n{style_prompt}"
    payload = {
        "model": OLLAMA_MODELL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": befehl},
        ],
        "stream": False,
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def frage_claude(befehl: str, style_prompt: str) -> str:
    import anthropic
    system = SYSTEM_PROMPT_BASIS
    if style_prompt:
        system += f"\n\n---\nMein Stil und Beispiele:\n{style_prompt}"
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODELL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": befehl}],
    )
    return message.content[0].text.strip()

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

        ki_modus_menu = rumps.MenuItem("KI-Modus")
        for name in KI_MODI:
            item = rumps.MenuItem(name, callback=self.wechsle_ki_modus)
            if name == AKTIVER_KI_MODUS:
                item.state = True
            ki_modus_menu.add(item)

        self.menu = [
            rumps.MenuItem(f"Diktat: {shortcut_als_text(SHORTCUT)}  |  KI: {shortcut_als_text(SHORTCUT_KI)}"),
            rumps.separator,
            modell_menu,
            ki_modus_menu,
            rumps.MenuItem("Kleinschreibung", callback=self.wechsle_kleinschreibung),
        ]

        self.aufnahme_aktiv = False
        self.aktuelle_tasten = set()
        self.style_prompt = ""
        self.ffmpeg_prozess = None
        self.tmp_pfad = None
        self.aktives_modell = AKTIVES_MODELL

        self._diktat_timer     = None

        # KI-State
        self.ki_aufnahme_aktiv = False
        self.ffmpeg_prozess_ki = None
        self.tmp_pfad_ki       = None
        self.aktiver_ki_modus  = AKTIVER_KI_MODUS
        self.ki_kontext        = ""

        #Kleinschreibung State
        self.kleinschreibung_aktiv = bool(_json.loads((SCRIPT_DIR/"config.json").read_text()).get("kleinschreibung_default", False)) if (SCRIPT_DIR/"config.json").exists() else False

        self.session_replacements = {}
        self.session_prompt_words = []
        self.korrektur_aktiv = False

        self.title = "🎤"

        threading.Thread(target=self.starte_keyboard_listener, daemon=True).start()
        threading.Thread(target=self.lade_alles, daemon=True).start()

    def lade_alles(self):
        self.replacements   = lade_vocabulary(VOCABULARY_CSV)
        self.initial_prompt = baue_initial_prompt(VOCABULARY_CSV)
        self.style_prompt   = lade_style_prompt(ASSISTANT_STYLE_FILE)
        self.pruefe_setup()
        self.title = "🎤"
        rumps.notification("Diktierfunktion", "", f"Bereit – {shortcut_als_text(SHORTCUT)}: Diktat  |  {shortcut_als_text(SHORTCUT_KI)}: KI")

    def pruefe_setup(self):
        # ── Whisper-Modelle ──────────────────────────────────
        for name, pfad in MODELLE.items():
            if not os.path.exists(pfad):
                self.title = "⬇️"
                rumps.notification("Setup", f"Lade Whisper-Modell '{name}'...", "Bitte warten (~1–3 GB)")
                os.makedirs(os.path.dirname(pfad), exist_ok=True)
                url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{name}.bin"
                try:
                    urllib.request.urlretrieve(url, pfad)
                    rumps.notification("Setup", f"Whisper '{name}' bereit ✓", "")
                except Exception as e:
                    rumps.notification("Setup Fehler", f"Whisper '{name}' fehlgeschlagen", str(e))

        # ── Ollama installiert? ──────────────────────────────
        if subprocess.run(["which", "ollama"], capture_output=True).returncode != 0:
            rumps.notification("Setup", "Ollama fehlt", "Terminal: brew install ollama")
            return

        # ── Ollama läuft? ────────────────────────────────────
        try:
            requests.get("http://localhost:11434", timeout=2)
        except Exception:
            rumps.notification("Setup", "Starte Ollama...", "")
            subprocess.Popen(["ollama", "serve"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(4)

        # ── KI-Modell vorhanden? ─────────────────────────────
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if OLLAMA_MODELL not in result.stdout:
            self.title = "⬇️"
            rumps.notification("Setup", f"Lade '{OLLAMA_MODELL}'...", "Dauert einige Minuten (~5 GB)")
            subprocess.run(["ollama", "pull", OLLAMA_MODELL])
            rumps.notification("Setup", f"'{OLLAMA_MODELL}' bereit ✓", "")

    def lade_vocabulary_neu(self):
        self.replacements = lade_vocabulary(VOCABULARY_CSV)
        self.initial_prompt = baue_initial_prompt(VOCABULARY_CSV)

    def speichere_session(self, falsch, korrekt):
        if falsch:
            self.session_replacements[falsch] = korrekt
        self.session_prompt_words.append(korrekt)
        rumps.notification("Session", "", f'"{korrekt}" für diese Sitzung gemerkt')

    def speichere_global(self, falsch, korrekt):
        with open(VOCABULARY_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if falsch and falsch not in self.replacements:
                writer.writerow([falsch, korrekt])
            if korrekt not in self.replacements:
                writer.writerow([korrekt, korrekt])
        self.lade_vocabulary_neu()
        rumps.notification("Global gespeichert", "", f'"{korrekt}" zur Vokabelliste hinzugefügt')

    def oeffne_korrektur_fenster(self):
        # Warten bis Shortcut-Tasten losgelassen
        start = time.time()
        while SHORTCUT_KORREKTUR.intersection(self.aktuelle_tasten):
            time.sleep(0.05)
            if time.time() - start > 2:
                break
        time.sleep(0.1)

        # Markiertes Wort per Cmd+C abgreifen
        with _kb.pressed(keyboard.Key.cmd):
            _kb.press('c')
            _kb.release('c')
        time.sleep(0.15)
        falsches_wort = pyperclip.paste().strip()

        # AppleScript-Dialog öffnen
        falsch_anzeige = falsches_wort if falsches_wort else "?"
        script = f'''
        tell application "System Events"
            set frontApp to name of first process whose frontmost is true
            set r to display dialog "Korrektur: \\"{falsch_anzeige}\\"\\n\\nKorrektes Wort:" ¬
                default answer "" ¬
                buttons {{"Abbrechen", "Nur Session", "Global"}} ¬
                default button "Global" ¬
                cancel button "Abbrechen" ¬
                with title "Diktierfunktion"
            tell process frontApp
                set frontmost to true
            end tell
            return (button returned of r) & "|" & (text returned of r)
        end tell
        '''
        ergebnis = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)

        if ergebnis.returncode != 0:
            self.korrektur_aktiv = False
            return

        teile = ergebnis.stdout.strip().split("|", 1)
        if len(teile) != 2:
            self.korrektur_aktiv = False
            return

        button, korrektes_wort = teile
        korrektes_wort = korrektes_wort.strip()

        if korrektes_wort:
            time.sleep(0.15)
            pyperclip.copy(korrektes_wort + " ")
            time.sleep(0.1)
            with _kb.pressed(keyboard.Key.cmd):
                _kb.press('v')
                _kb.release('v')
            time.sleep(0.1)
            if button == "Global":
                self.speichere_global(falsches_wort, korrektes_wort)
            elif button == "Nur Session":
                self.speichere_session(falsches_wort, korrektes_wort)

        self.korrektur_aktiv = False

    def wechsle_modell(self, sender):
        self.menu["Modell"][self.aktives_modell].state = False
        self.aktives_modell = sender.title
        self.menu["Modell"][self.aktives_modell].state = True
        rumps.notification("Modell gewechselt", "", f"Aktiv: {self.aktives_modell}")

    def wechsle_ki_modus(self, sender):
        self.menu["KI-Modus"][self.aktiver_ki_modus].state = False
        self.aktiver_ki_modus = sender.title
        self.menu["KI-Modus"][self.aktiver_ki_modus].state = True
        rumps.notification("KI-Modus", "", f"Aktiv: {self.aktiver_ki_modus}")

    def wechsle_kleinschreibung(self, sender):
        self.kleinschreibung_aktiv = not self.kleinschreibung_aktiv
        sender.state = self.kleinschreibung_aktiv
        status = "an" if self.kleinschreibung_aktiv else "aus"
        rumps.notification("Kleinschreibung", "", f"Kleinschreibung {status}")

# ─────────────────────────────────────────
# TASTATUR LISTENER
# ─────────────────────────────────────────

    def starte_keyboard_listener(self):
        def on_press(taste):
            try:
                self.aktuelle_tasten.add(taste)

                if SHORTCUT_KI.issubset(self.aktuelle_tasten):
                    if self._diktat_timer:
                        self._diktat_timer.cancel()
                        self._diktat_timer = None
                    if not self.ki_aufnahme_aktiv and not self.aufnahme_aktiv:
                        self.starte_ki_aufnahme()

                elif SHORTCUT_KORREKTUR.issubset(self.aktuelle_tasten):
                    if not self.aufnahme_aktiv and not self.korrektur_aktiv:
                        self.korrektur_aktiv = True
                        threading.Thread(target=self.oeffne_korrektur_fenster, daemon=True).start()

                elif SHORTCUT.issubset(self.aktuelle_tasten):
                    if not self.aufnahme_aktiv and not self.ki_aufnahme_aktiv and self._diktat_timer is None:
                        self._diktat_timer = threading.Timer(DIKTAT_TIMER_DELAY, self._starte_diktat_wenn_solo)
                        self._diktat_timer.start()

            except Exception:
                pass

        def on_release(taste):
            try:
                self.aktuelle_tasten.discard(taste)

                if taste in SHORTCUT and self._diktat_timer:
                    self._diktat_timer.cancel()
                    self._diktat_timer = None

                if self.ki_aufnahme_aktiv and taste in SHORTCUT_KI:
                    self.beende_ki_aufnahme()
                elif self.aufnahme_aktiv and taste in SHORTCUT:
                    self.beende_aufnahme()

            except Exception:
                pass

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

    def _starte_diktat_wenn_solo(self):
        self._diktat_timer = None
        if not self.ki_aufnahme_aktiv and not self.aufnahme_aktiv:
            self.starte_aufnahme()

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
        self._warn_timer = threading.Timer(25.0, self._zeige_limit_warnung)
        self._warn_timer.start()

    def _zeige_limit_warnung(self):
            if self.aufnahme_aktiv or self.ki_aufnahme_aktiv:
                self.title = "⚠️"

    def beende_aufnahme(self):
        self.aufnahme_aktiv = False
        self.title = "⏳"

        # Timer canceln falls noch läuft
        if hasattr(self, '_warn_timer'):
            self._warn_timer.cancel()

        if self.ffmpeg_prozess:
            self.ffmpeg_prozess.terminate()
            self.ffmpeg_prozess.wait()

        threading.Thread(target=self.transkribiere, daemon=True).start()

# ─────────────────────────────────────────
# KI-ASSISTENT – AUFNAHME
# ─────────────────────────────────────────

    def starte_ki_aufnahme(self):
        # Zwischenablage als Kontext lesen (Nutzer kopiert vorher manuell mit Cmd+C)
        self.ki_kontext = pyperclip.paste().strip()

        self.ki_aufnahme_aktiv = True
        self.title = "🟣"

        self.ki_aufnahme_aktiv = True
        self.title = "🟣"
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self.tmp_pfad_ki = tmp.name
        tmp.close()
        befehl = [FFMPEG, "-f", "avfoundation", "-i", f":{MIKROFON}",
                  "-ar", "16000", "-ac", "1", "-y", self.tmp_pfad_ki]
        self.ffmpeg_prozess_ki = subprocess.Popen(befehl, stderr=subprocess.DEVNULL)
        self._warn_timer = threading.Timer(25.0, self._zeige_limit_warnung)
        self._warn_timer.start()

    def beende_ki_aufnahme(self):
        self.ki_aufnahme_aktiv = False
        self.title = "⏳"
        if hasattr(self, '_warn_timer'):
            self._warn_timer.cancel()
        if self.ffmpeg_prozess_ki:
            self.ffmpeg_prozess_ki.terminate()
            self.ffmpeg_prozess_ki.wait()
        threading.Thread(target=self.transkribiere_ki, daemon=True).start()

# ─────────────────────────────────────────
# TRANSKRIPTION
# ─────────────────────────────────────────

    def transkribiere(self):
        try:
            if not os.path.exists(self.tmp_pfad):
                return
            if berechne_audio_energie(self.tmp_pfad) < 150:
                os.unlink(self.tmp_pfad)
                return

            befehl = [
                WHISPER_CLI,
                "--language", LANGUAGE,
                "--model", MODELLE[self.aktives_modell],
                "--no-timestamps",
                "--no-prints",
                "--no-speech-thold", "0.8",
                "--file", self.tmp_pfad,
            ]

            full_prompt = self.initial_prompt
            if self.session_prompt_words:
                extra = ", ".join(self.session_prompt_words)
                full_prompt = (full_prompt + ", " + extra) if full_prompt else extra
            if full_prompt:
                befehl += ["--prompt", full_prompt]

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
            if self.session_replacements:
                text = wende_replacements_an(text, self.session_replacements)

            if self.kleinschreibung_aktiv:
                text = text.lower()

            if text.strip():
                fuege_text_ein(text)

            os.unlink(self.tmp_pfad)

        except Exception as e:
            rumps.notification("Fehler", "", str(e))

        finally:
            self.title = "🎤"

# ─────────────────────────────────────────
# KI-ASSISTENT – TRANSKRIPTION + KI-ANFRAGE
# ─────────────────────────────────────────

    def transkribiere_ki(self):
        try:
            if not os.path.exists(self.tmp_pfad_ki):
                return
            if berechne_audio_energie(self.tmp_pfad_ki) < 150:
                os.unlink(self.tmp_pfad_ki)
                return

            befehl = [
                WHISPER_CLI,
                "--language", LANGUAGE,
                "--model", MODELLE[self.aktives_modell],
                "--no-timestamps",
                "--no-prints",
                "--no-speech-thold", "0.8",
                "--file", self.tmp_pfad_ki,
            ]
            ergebnis = subprocess.run(befehl, capture_output=True, text=True)
            sprachbefehl = ergebnis.stdout.strip()

            if not sprachbefehl:
                os.unlink(self.tmp_pfad_ki)
                return

            self.title = "🤖"
            self.style_prompt = lade_style_prompt(ASSISTANT_STYLE_FILE)

            if self.ki_kontext:
                prompt = (
                    f"Der Nutzer hat folgenden Text auf dem Bildschirm markiert:\n"
                    f"\"\"\"\n{self.ki_kontext}\n\"\"\"\n\n"
                    f"Aufgabe des Nutzers: {sprachbefehl}"
                )
            else:
                prompt = sprachbefehl

            if self.aktiver_ki_modus == "Claude API":
                antwort = frage_claude(sprachbefehl, self.style_prompt)
            else:
                antwort = frage_ollama(sprachbefehl, self.style_prompt)

            if antwort:
                fuege_text_ein(antwort)
            os.unlink(self.tmp_pfad_ki)

        except Exception as e:
            rumps.notification("Fehler (KI)", "", str(e))
        finally:
            self.title = "🎤"

# ─────────────────────────────────────────
# HAUPTPROGRAMM
# ─────────────────────────────────────────

if __name__ == "__main__":
    app = DiktierApp()
    app.run()

