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
MIN_AUFNAHME_SEK = 0.8
HALLUZINATION_BLOCKLISTE = []
VAD_CHUNK_ZIEL_SEK = 20
VAD_CHUNK_MAX_SEK = 45
VAD_MIN_PAUSE_MS = 600
TOGGLE_TASTE_NAME = "alt_r"
DOPPEL_TAP_MS = 400
BLINK_MS = 500
CHUNKING_MODUS = "live"  # "live" oder "klassisch"

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
        MIN_AUFNAHME_SEK        = _cfg.get("min_aufnahme_sekunden", 0.8)
        HALLUZINATION_BLOCKLISTE = _cfg.get("halluzination_blockliste", [])
        VAD_CHUNK_ZIEL_SEK = int(_cfg.get("vad_chunk_ziel_sek", 20))
        VAD_CHUNK_MAX_SEK  = int(_cfg.get("vad_chunk_max_sek", 45))
        VAD_MIN_PAUSE_MS   = int(_cfg.get("vad_min_pause_ms", 600))
        TOGGLE_TASTE_NAME  = _cfg.get("toggle_taste", "alt_r")
        DOPPEL_TAP_MS      = int(_cfg.get("doppel_tap_ms", 400))
        BLINK_MS           = int(_cfg.get("blink_ms", 500))
        CHUNKING_MODUS     = _cfg.get("chunking_modus", "live")
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
# MIKROFON-ERKENNUNG
# ─────────────────────────────────────────
def liste_mikrofone():
    """Fragt ffmpeg nach allen verfügbaren Audio-Eingaben.
    Rückgabe: Liste von (index, name)-Tupeln."""
    import subprocess as _sp
    try:
        r = _sp.run(
            [FFMPEG, "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True, text=True, timeout=5,
        )
        ausgabe = r.stderr  # ffmpeg schreibt Geräteliste auf stderr
    except Exception:
        return []
    mikros = []
    in_audio_block = False
    for zeile in ausgabe.splitlines():
        if "AVFoundation audio devices" in zeile:
            in_audio_block = True
            continue
        if in_audio_block:
            m = re.search(r"\[(\d+)\]\s+(.+)$", zeile)
            if m:
                mikros.append((m.group(1), m.group(2).strip()))
            elif "AVFoundation" in zeile:
                break  # nächster Block startet
    return mikros

def finde_mikrofon_index(gewuenschter_name):
    """Sucht Index zu einem Mikrofon-Namen. 'default' → macOS-Standard.
    Fällt zurück auf ersten gefundenen Eingang, falls Name nicht da ist."""
    if gewuenschter_name == "default":
        return "default"
    mikros = liste_mikrofone()
    for idx, name in mikros:
        if gewuenschter_name.lower() in name.lower():
            return idx
    # Fallback: ersten Eingang nehmen
    if mikros:
        return mikros[0][0]
    return "default"

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
# TOGGLE-TASTE AUFLÖSEN
# ─────────────────────────────────────────
def _key_aus_name(name):
    """Wandelt Config-String wie 'alt_r' in keyboard.Key.alt_r um."""
    try:
        return getattr(keyboard.Key, name)
    except AttributeError:
        try:
            return keyboard.KeyCode.from_char(name)
        except Exception:
            return keyboard.Key.alt_r

TOGGLE_TASTE = _key_aus_name(TOGGLE_TASTE_NAME)

# ─────────────────────────────────────────
# VAD-INITIALISIERUNG (Silero via soundfile, umgeht torchaudio-Bug)
# ─────────────────────────────────────────
_vad_modell = None
_vad_verfuegbar = False
try:
    import soundfile as _sf
    import torch as _torch
    from silero_vad import load_silero_vad as _load_vad, get_speech_timestamps as _vad_stamps
    _vad_modell = _load_vad()
    _vad_verfuegbar = True
except Exception as _e:
    print(f"⚠️  VAD nicht verfügbar ({_e}) – Fallback auf Alt-Verhalten")

# ─────────────────────────────────────────
# DEBUG-LOGGING
# ─────────────────────────────────────────
DEBUG = False
try:
    DEBUG = bool(_json.loads((SCRIPT_DIR / "config.json").read_text()).get("debug", False))
except Exception:
    pass

DEBUG_LOG = "/tmp/diktieren-debug.log"

def _debug_log(msg):
    if not DEBUG:
        return
    try:
        import datetime as _dt
        with open(DEBUG_LOG, "a") as f:
            f.write(f"[{_dt.datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        pass

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



def _applescript_escape(text):
    """Escapt Text für sichere Einbettung in AppleScript-String-Literal.
    Verhindert Injektion durch Backslash, Anführungszeichen, Zeilenumbrüche."""
    if text is None:
        return ""
    # Erst Backslash (muss zuerst!), dann Anführungszeichen
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    # Zeilenumbrüche und andere Kontrollzeichen entfernen
    text = text.replace("\n", " ").replace("\r", " ")
    # Länge begrenzen (Dialog kann eh nicht mehr sinnvoll anzeigen)
    if len(text) > 200:
        text = text[:200] + "…"
    return text


def _sieht_aus_wie_passwort(text):
    """Heuristik: erkennt typische Passwort/Token-Muster.
    Konservativ – erwischt Passwort-Manager-Ausgaben, aber keine URLs oder Namen."""
    if not text or len(text) < 4 or len(text) > 200:
        return False
    # Leerzeichen? Dann kein Passwort (Sätze, Namen mit Leerzeichen)
    if " " in text or "\n" in text or "\t" in text:
        return False
    # URLs durchlassen
    if text.startswith(("http://", "https://", "www.", "ftp://", "file://")):
        return False
    # E-Mail-Adressen durchlassen
    if "@" in text and "." in text and len(text.split("@")) == 2:
        return False
    # Zähle Sonderzeichen (nicht alphanumerisch, nicht . oder -)
    sonderzeichen = sum(1 for c in text if not c.isalnum() and c not in ".-_/:")
    ziffern = sum(1 for c in text if c.isdigit())
    buchstaben = sum(1 for c in text if c.isalpha())
    # Klassisches Passwort: Sonderzeichen drin und gemischt
    if sonderzeichen >= 1 and ziffern >= 1 and buchstaben >= 1:
        return True
    # API-Key/Token: sehr lang, alphanumerisch, hoher Ziffern-Anteil
    if len(text) >= 20 and ziffern >= 3 and buchstaben >= 3 and " " not in text:
        # Häufig: sk-..., ghp_..., xoxb-... etc.
        if text[:4].lower() in ("sk-a", "sk-p", "ghp_", "gho_", "xoxb", "xoxp", "pk_l", "pk_t"):
            return True
        # Oder: nur base64/hex-ähnliche Zeichen
        if all(c.isalnum() or c in "-_=" for c in text) and len(text) >= 32:
            return True
    return False

def fuege_text_ein(text, zu_historie=True):
    """Fügt Text ein und stellt die alte Zwischenablage danach wieder her.
    zu_historie=False verhindert Aufnahme in Diktier-Historie (bei Historie-Klick)."""
    if not text or not text.strip():
        return
    # Historie-Aufnahme (nur bei echten Diktaten, nicht bei Historie-Klicks)
    if zu_historie:
        try:
            _historie_hinzufuegen(text.strip(), DIKTIER_HISTORIE)
            _speichere_historie()
            if _app_instanz is not None:
                _app_instanz._aktualisiere_diktier_menu()
        except Exception as e:
            _debug_log(f"Historie-Aufnahme fehlgeschlagen: {e}")
    # Alte Zwischenablage merken
    try:
        alte_zwischenablage = pyperclip.paste()
    except Exception:
        alte_zwischenablage = None
    # Diktat in Zwischenablage → Cmd+V
    pyperclip.copy(text + " ")
    time.sleep(0.1)
    with _kb.pressed(keyboard.Key.cmd):
        _kb.press('v')
        _kb.release('v')
    # Kurz warten bis Cmd+V durch ist, dann Original zurückschreiben
    time.sleep(0.25)
    if alte_zwischenablage is not None:
        try:
            pyperclip.copy(alte_zwischenablage)
        except Exception:
            pass


def _beende_ffmpeg_sauber(prozess, timeout=2.0):
    """Sendet 'q' auf stdin – ffmpeg schreibt den Buffer noch fertig raus.
    Fallback auf terminate() falls das nicht klappt."""
    if not prozess:
        return
    try:
        if prozess.stdin:
            prozess.stdin.write(b"q\n")
            prozess.stdin.flush()
            prozess.stdin.close()
        prozess.wait(timeout=timeout)
    except Exception:
        try:
            prozess.terminate()
            prozess.wait(timeout=1.0)
        except Exception:
            prozess.kill()

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


# ─── Historie (Diktate + Clipboard) ───────────────────────────────
try:
    HISTORIE_MAX = int(_json.loads(_config_path.read_text()).get("historie_max", 20))
except Exception:
    HISTORIE_MAX = 20
HISTORIE_DATEI = SCRIPT_DIR / ".historie.json"
DIKTIER_HISTORIE = []
CLIPBOARD_HISTORIE = []
_app_instanz = None
_letzter_eigener_copy = ""

def _lade_historie():
    global DIKTIER_HISTORIE, CLIPBOARD_HISTORIE
    if HISTORIE_DATEI.exists():
        try:
            d = json.loads(HISTORIE_DATEI.read_text())
            DIKTIER_HISTORIE = d.get("diktate", [])[:HISTORIE_MAX]
            CLIPBOARD_HISTORIE = d.get("clipboard", [])[:HISTORIE_MAX]
        except Exception as e:
            _debug_log(f"Historie-Laden fehlgeschlagen: {e}")

def _speichere_historie():
    try:
        HISTORIE_DATEI.write_text(json.dumps({
            "diktate": DIKTIER_HISTORIE,
            "clipboard": CLIPBOARD_HISTORIE,
        }, ensure_ascii=False, indent=2))
    except Exception as e:
        _debug_log(f"Historie-Speichern fehlgeschlagen: {e}")

def _historie_hinzufuegen(text, liste):
    if not text or not text.strip():
        return
    text = text.strip()
    # Zu große Einträge (>50 KB) nicht speichern – nur ins Menü käme das trotzdem
    # nicht sinnvoll rein und die .historie.json würde aufblähen
    if len(text) > 5_000_000:  # 5 MB pro Eintrag – erst bei absurd großen Blöcken abbrechen
        return
    if text in liste:
        liste.remove(text)
    liste.insert(0, text)
    del liste[HISTORIE_MAX:]

def _historie_kuerzen(text, laenge=60):
    t = text.replace("\n", " ").replace("\r", " ").strip()
    t = " ".join(t.split())
    if len(t) > laenge:
        t = t[:laenge] + "…"
    return t

_lade_historie()
# ──────────────────────────────────────────────────────────────────

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

        # Mikrofon-Untermenü aufbauen
        mikrofon_menu = rumps.MenuItem("Mikrofon")
        gefundene = liste_mikrofone()
        # "Standard" (macOS-Default) immer als erste Option
        item_default = rumps.MenuItem("Standard (macOS)", callback=self.wechsle_mikrofon)
        if MIKROFON == "default":
            item_default.state = True
        mikrofon_menu.add(item_default)
        for _idx, _name in gefundene:
            item = rumps.MenuItem(_name, callback=self.wechsle_mikrofon)
            if MIKROFON != "default" and MIKROFON.lower() in _name.lower():
                item.state = True
            mikrofon_menu.add(item)

        self.menu = [
            rumps.MenuItem(f"Diktat: {shortcut_als_text(SHORTCUT)}  |  KI: {shortcut_als_text(SHORTCUT_KI)}"),
            rumps.separator,
            modell_menu,
            ki_modus_menu,
            mikrofon_menu,
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

        # Toggle-Modus State
        self.toggle_aktiv = False
        self.toggle_start_zeit = 0
        self.letzter_tap_zeit = 0
        self.clipboard_poller_aktiv = True

        self.title = "🎤"

        threading.Thread(target=self.starte_keyboard_listener, daemon=True).start()
        threading.Thread(target=self.lade_alles, daemon=True).start()

        # Chunking-Modus
        self._chunking_modus_item = rumps.MenuItem(
            f"Modus: {'Live-Chunking' if CHUNKING_MODUS == 'live' else 'Klassisch (am Ende)'}",
            callback=self.wechsle_chunking_modus,
        )
        try:
            self.menu.add(self._chunking_modus_item)
        except Exception as e:
            _debug_log(f"Modus-Menü-Anhängen fehlgeschlagen: {e}")

        # Historie-Untermenüs
        global _app_instanz
        _app_instanz = self
        self._baue_historie_menues()
        threading.Thread(target=self._clipboard_poller, daemon=True).start()
        self._clipboard_toggle_item = rumps.MenuItem(
            "📋 Zwischenablage: mitschneiden",
            callback=self.wechsle_clipboard_poller,
        )
        try:
            self.menu.add(rumps.separator)
            self.menu.add(self._diktier_submenu)
            self.menu.add(self._clipboard_submenu)
            self.menu.add(self._clipboard_toggle_item)
        except Exception as e:
            _debug_log(f"Historie-Menü-Anhängen fehlgeschlagen: {e}")

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

        # AppleScript-Dialog öffnen (Text escapen gegen Injektion!)
        falsch_anzeige = _applescript_escape(falsches_wort if falsches_wort else "?")
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

    def wechsle_chunking_modus(self, sender):
        global CHUNKING_MODUS
        CHUNKING_MODUS = "klassisch" if CHUNKING_MODUS == "live" else "live"
        # Config speichern
        try:
            cfg = json.loads((SCRIPT_DIR / "config.json").read_text())
            cfg["chunking_modus"] = CHUNKING_MODUS
            (SCRIPT_DIR / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        except Exception as e:
            _debug_log(f"Modus-Speichern fehlgeschlagen: {e}")
        # Menü-Label updaten
        if hasattr(self, "_chunking_modus_item"):
            self._chunking_modus_item.title = f"Modus: {'Live-Chunking' if CHUNKING_MODUS == 'live' else 'Klassisch (am Ende)'}"
        rumps.notification("Chunking-Modus geändert",
                           "",
                           "Live-Chunking aktiv" if CHUNKING_MODUS == "live" else "Klassisch: Text kommt komplett am Ende")

    def wechsle_clipboard_poller(self, sender):
        self.clipboard_poller_aktiv = not getattr(self, "clipboard_poller_aktiv", True)
        # Menü-Label updaten
        if hasattr(self, "_clipboard_toggle_item"):
            self._clipboard_toggle_item.title = (
                "📋 Zwischenablage: mitschneiden" if self.clipboard_poller_aktiv
                else "📋 Zwischenablage: pausiert"
            )
        _debug_log(f"Clipboard-Poller: {'aktiv' if self.clipboard_poller_aktiv else 'pausiert'}")

    def wechsle_kleinschreibung(self, sender):
        self.kleinschreibung_aktiv = not self.kleinschreibung_aktiv
        sender.state = self.kleinschreibung_aktiv
        status = "an" if self.kleinschreibung_aktiv else "aus"
        rumps.notification("Kleinschreibung", "", f"Kleinschreibung {status}")

    def wechsle_mikrofon(self, sender):
        global MIKROFON
        # Alte Häkchen entfernen
        for item in self.menu["Mikrofon"].values():
            item.state = False
        sender.state = True
        # Wert bestimmen: "default" oder Gerätename
        MIKROFON = "default" if sender.title == "Standard (macOS)" else sender.title
        # In config.json speichern
        import json as _j
        cfg_path = SCRIPT_DIR / "config.json"
        try:
            cfg = _j.loads(cfg_path.read_text()) if cfg_path.exists() else {}
            cfg["mikrofon"] = MIKROFON
            cfg_path.write_text(_j.dumps(cfg, indent=2, ensure_ascii=False))
        except Exception as e:
            rumps.notification("Fehler", "Config speichern", str(e))
            return
        rumps.notification("Mikrofon gewechselt", "", MIKROFON)

# ─────────────────────────────────────────
# TASTATUR LISTENER
# ─────────────────────────────────────────

    def starte_keyboard_listener(self):
        def on_press(taste):
            try:
                self.aktuelle_tasten.add(taste)

                # Doppel-Tap-Erkennung für Toggle
                if taste == TOGGLE_TASTE:
                    jetzt = time.time()
                    delta_ms = (jetzt - self.letzter_tap_zeit) * 1000
                    if delta_ms < DOPPEL_TAP_MS:
                        self.letzter_tap_zeit = 0
                        if self.toggle_aktiv:
                            if jetzt - self.toggle_start_zeit > 1.0:
                                self.beende_toggle()
                        else:
                            if not self.aufnahme_aktiv and not self.ki_aufnahme_aktiv:
                                if self._diktat_timer:
                                    self._diktat_timer.cancel()
                                    self._diktat_timer = None
                                self.starte_toggle()
                        return
                    else:
                        self.letzter_tap_zeit = jetzt

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
                elif self.aufnahme_aktiv and taste in SHORTCUT and not self.toggle_aktiv:
                    self.beende_aufnahme()

            except Exception:
                pass

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

    def _starte_diktat_wenn_solo(self):
        self._diktat_timer = None
        if not self.ki_aufnahme_aktiv and not self.aufnahme_aktiv and not self.toggle_aktiv:
            self.starte_aufnahme()

# ─────────────────────────────────────────
# AUFNAHME STARTEN UND BEENDEN
# ─────────────────────────────────────────

    def starte_aufnahme(self):
        self.aufnahme_aktiv = True
        self.aufnahme_start_zeit = time.time()
        self.title = "🔴"

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self.tmp_pfad = tmp.name
        tmp.close()

        # Byte-Offset in der WAV, ab dem beim nächsten Schnitt gemessen wird
        # (fürs Restsegment am Ende)
        self.schnitt_offset_sample = 0

        befehl = [
            FFMPEG,
            "-f", "avfoundation",
            "-i", f":{finde_mikrofon_index(MIKROFON)}",
            "-ar", "16000",
            "-ac", "1",
            "-flush_packets", "1",
            "-avioflags", "direct",
            "-y",
            self.tmp_pfad
        ]
        self.ffmpeg_prozess = subprocess.Popen(
            befehl,
            stdin=subprocess.PIPE,
            stderr=(open("/tmp/diktieren-ffmpeg.log", "a") if DEBUG else subprocess.DEVNULL),
        )
        _debug_log(f"Aufnahme Diktat gestartet, VAD={_vad_verfuegbar}")

        # VAD-Cutter-Thread starten (nur wenn VAD verfügbar)
        if _vad_verfuegbar and CHUNKING_MODUS == "live":
            self._cutter_stop = threading.Event()
            self._cutter_thread = threading.Thread(target=self._vad_cutter, daemon=True)
            self._cutter_thread.start()
        # 45s-Warnung nur im klassischen Modus (Live-Chunking braucht sie nicht)
        if CHUNKING_MODUS == "klassisch":
            self._warn_timer = threading.Timer(45.0, self._zeige_limit_warnung)
            self._warn_timer.daemon = True
            self._warn_timer.start()

    def _zeige_limit_warnung(self):
            if self.aufnahme_aktiv or self.ki_aufnahme_aktiv:
                self.title = "⚠️"

    def beende_aufnahme(self):
        self.aufnahme_aktiv = False
        dauer = time.time() - getattr(self, "aufnahme_start_zeit", 0)
        self.title = "⏳"

        # Cutter zuerst stoppen (nicht mitten im Zyklus schneiden)
        if hasattr(self, "_cutter_stop"):
            self._cutter_stop.set()

        if self.ffmpeg_prozess:
            _beende_ffmpeg_sauber(self.ffmpeg_prozess)

        # Zu kurz → verwerfen
        if dauer < MIN_AUFNAHME_SEK:
            self.title = "🎤"
            try:
                if self.tmp_pfad and os.path.exists(self.tmp_pfad):
                    os.unlink(self.tmp_pfad)
            except Exception:
                pass
            return

        # Restlichen Teil (ab schnitt_offset_sample bis Ende) transkribieren
        threading.Thread(target=self.transkribiere, daemon=True).start()

# ─────────────────────────────────────────
# KI-ASSISTENT – AUFNAHME
# ─────────────────────────────────────────

    def starte_ki_aufnahme(self):
        # Zwischenablage als Kontext lesen (Nutzer kopiert vorher manuell mit Cmd+C)
        self.ki_kontext = pyperclip.paste().strip()

        self.ki_aufnahme_aktiv = True
        self.ki_aufnahme_start_zeit = time.time()
        self.title = "🟣"

        self.ki_aufnahme_aktiv = True
        self.title = "🟣"
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self.tmp_pfad_ki = tmp.name
        tmp.close()
        befehl = [FFMPEG, "-f", "avfoundation", "-i", f":{finde_mikrofon_index(MIKROFON)}",
                  "-ar", "16000", "-ac", "1", "-flush_packets", "1", "-avioflags", "direct",
                  "-y", self.tmp_pfad_ki]
        self.ffmpeg_prozess_ki = subprocess.Popen(befehl, stdin=subprocess.PIPE, stderr=(open("/tmp/diktieren-ffmpeg.log", "a") if DEBUG else subprocess.DEVNULL))
        _debug_log("Aufnahme KI gestartet")
        self._warn_timer = threading.Timer(25.0, self._zeige_limit_warnung)
        self._warn_timer.start()

    def beende_ki_aufnahme(self):
        self.ki_aufnahme_aktiv = False
        dauer = time.time() - getattr(self, "ki_aufnahme_start_zeit", 0)
        self.title = "⏳"
        if hasattr(self, '_warn_timer'):
            self._warn_timer.cancel()
        if self.ffmpeg_prozess_ki:
            _beende_ffmpeg_sauber(self.ffmpeg_prozess_ki)
        if dauer < MIN_AUFNAHME_SEK:
            self.title = "🎤"
            try:
                if self.tmp_pfad_ki and os.path.exists(self.tmp_pfad_ki):
                    os.unlink(self.tmp_pfad_ki)
            except Exception:
                pass
            return
        threading.Thread(target=self.transkribiere_ki, daemon=True).start()

# ─────────────────────────────────────────
# TRANSKRIPTION
# ─────────────────────────────────────────

    def transkribiere(self):
        """Wird beim Aufnahme-Ende aufgerufen: verarbeitet den Rest ab letztem VAD-Schnitt.
        Wenn VAD nicht verfügbar war, wird die komplette WAV verarbeitet."""
        try:
            if not os.path.exists(self.tmp_pfad):
                return
            # Bei VAD: nur den Teil ab schnitt_offset_sample nehmen
            if _vad_verfuegbar and getattr(self, "schnitt_offset_sample", 0) > 0:
                try:
                    audio_np, sr = _sf.read(self.tmp_pfad, dtype="float32")
                    rest = audio_np[self.schnitt_offset_sample:]
                    if len(rest) / sr < 0.5:
                        # Rest zu kurz zum Transkribieren
                        try: os.unlink(self.tmp_pfad)
                        except: pass
                        self.title = "🎤"
                        return
                    # VAD-Vorprüfung auch für den Rest
                    if _vad_verfuegbar:
                        try:
                            rest_torch = _torch.from_numpy(rest)
                            rest_segmente = _vad_stamps(
                                rest_torch, _vad_modell,
                                sampling_rate=sr,
                                min_silence_duration_ms=VAD_MIN_PAUSE_MS,
                                min_speech_duration_ms=250,
                                return_seconds=True,
                            )
                            rest_sprech = sum(s["end"] - s["start"] for s in rest_segmente)
                            if rest_sprech < 0.5:
                                _debug_log(f"Rest verworfen (nur {rest_sprech:.2f}s Sprache)")
                                try: os.unlink(self.tmp_pfad)
                                except: pass
                                self.title = "🎤"
                                return
                        except Exception as e:
                            _debug_log(f"Rest-VAD-Fehler: {e}")
                    tmp2 = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                    _sf.write(tmp2.name, rest, sr, subtype="PCM_16")
                    tmp2.close()
                    self._transkribiere_wav(tmp2.name, ausschnitt=False)
                    try: os.unlink(self.tmp_pfad)
                    except: pass
                    self.title = "🎤"
                    return
                except Exception as e:
                    _debug_log(f"Rest-Fallback: {e}")
                    # Fallback auf komplette Datei
            if berechne_audio_energie(self.tmp_pfad) < 150:
                os.unlink(self.tmp_pfad)
                return

            # VAD-Vorprüfung auch für die komplette WAV (Push-to-Talk-Fall)
            if _vad_verfuegbar:
                try:
                    audio_np, sr = _sf.read(self.tmp_pfad, dtype="float32")
                    audio_torch = _torch.from_numpy(audio_np)
                    segmente = _vad_stamps(
                        audio_torch, _vad_modell,
                        sampling_rate=sr,
                        min_silence_duration_ms=VAD_MIN_PAUSE_MS,
                        min_speech_duration_ms=250,
                        return_seconds=True,
                    )
                    sprech_dauer = sum(s["end"] - s["start"] for s in segmente)
                    if sprech_dauer < 0.5:
                        _debug_log(f"Aufnahme verworfen (nur {sprech_dauer:.2f}s Sprache)")
                        os.unlink(self.tmp_pfad)
                        return
                except Exception as e:
                    _debug_log(f"Voll-VAD-Fehler: {e}")

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

            wav_size = os.path.getsize(self.tmp_pfad) if os.path.exists(self.tmp_pfad) else 0
            _debug_log(f"Whisper start, WAV={wav_size} bytes, Modell={self.aktives_modell}")
            _t0 = time.time()
            ergebnis = subprocess.run(
                befehl,
                capture_output=True,
                text=True
            )
            _debug_log(f"Whisper fertig in {time.time()-_t0:.1f}s, returncode={ergebnis.returncode}")
            if ergebnis.stderr and DEBUG:
                _debug_log(f"Whisper stderr: {ergebnis.stderr.strip()[:500]}")

            text = ergebnis.stdout.strip()

            # Whisper-Halluzinationen bei Stille filtern
            if text.strip() in HALLUZINATION_BLOCKLISTE:
                os.unlink(self.tmp_pfad)
                return

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
            wav_size_ki = os.path.getsize(self.tmp_pfad_ki) if os.path.exists(self.tmp_pfad_ki) else 0
            _debug_log(f"Whisper-KI start, WAV={wav_size_ki} bytes")
            _t0 = time.time()
            ergebnis = subprocess.run(befehl, capture_output=True, text=True)
            _debug_log(f"Whisper-KI fertig in {time.time()-_t0:.1f}s, returncode={ergebnis.returncode}")
            if ergebnis.stderr and DEBUG:
                _debug_log(f"Whisper-KI stderr: {ergebnis.stderr.strip()[:500]}")
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


    # ─────────────────────────────────────────
    # TOGGLE-MODUS (Doppel-Tap Aufnahme)
    # ─────────────────────────────────────────

    def starte_toggle(self):
        """Startet Dauer-Aufnahme (Doppel-Tap). Läuft bis nächster Doppel-Tap.
        Icon blinkt zwischen 🔴 und ⭕."""
        self.toggle_aktiv = True
        self.toggle_start_zeit = time.time()
        self.aufnahme_aktiv = True
        self.aufnahme_start_zeit = time.time()
        self.title = "🔴"
        self.schnitt_offset_sample = 0

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self.tmp_pfad = tmp.name
        tmp.close()

        befehl = [
            FFMPEG, "-f", "avfoundation",
            "-i", f":{finde_mikrofon_index(MIKROFON)}",
            "-ar", "16000", "-ac", "1",
            "-flush_packets", "1", "-avioflags", "direct",
            "-y", self.tmp_pfad,
        ]
        self.ffmpeg_prozess = subprocess.Popen(
            befehl,
            stdin=subprocess.PIPE,
            stderr=(open("/tmp/diktieren-ffmpeg.log", "a") if DEBUG else subprocess.DEVNULL),
        )
        _debug_log(f"Toggle-Aufnahme gestartet, VAD={_vad_verfuegbar}")

        if _vad_verfuegbar and CHUNKING_MODUS == "live":
            self._cutter_stop = threading.Event()
            self._cutter_thread = threading.Thread(target=self._vad_cutter, daemon=True)
            self._cutter_thread.start()
        # 45s-Warnung nur im klassischen Modus (Live-Chunking braucht sie nicht)
        if CHUNKING_MODUS == "klassisch":
            self._warn_timer = threading.Timer(45.0, self._zeige_limit_warnung)
            self._warn_timer.daemon = True
            self._warn_timer.start()

        # Blink-Thread starten
        self._blink_stop = threading.Event()
        self._blink_thread = threading.Thread(target=self._blink_loop, daemon=True)
        self._blink_thread.start()

        rumps.notification("Toggle-Aufnahme", "", "Läuft bis zum nächsten Doppel-Tap")

    def beende_toggle(self):
        """Beendet Dauer-Aufnahme."""
        _debug_log("Toggle-Aufnahme beendet")
        self.toggle_aktiv = False
        if hasattr(self, "_blink_stop"):
            self._blink_stop.set()
        self.beende_aufnahme()

    def _blink_loop(self):
        """Wechselt Titel zwischen 🔴 und ⭕ solange Toggle läuft."""
        an = True
        while not self._blink_stop.is_set():
            if self.toggle_aktiv:
                self.title = "🔴" if an else "⭕"
                an = not an
            self._blink_stop.wait(BLINK_MS / 1000.0)

    # ─────────────────────────────────────────
    # VAD-BASIERTES LIVE-CHUNKING
    # ─────────────────────────────────────────

    def _vad_cutter(self):
        """Läuft parallel zur Aufnahme. Prüft alle 2s, ob geschnitten werden soll."""
        SAMPLE_RATE = 16000
        while not self._cutter_stop.is_set():
            self._cutter_stop.wait(2.0)
            if self._cutter_stop.is_set():
                break
            try:
                if not os.path.exists(self.tmp_pfad):
                    continue
                try:
                    audio_np, sr = _sf.read(self.tmp_pfad, dtype="float32")
                except Exception as e:
                    _debug_log(f"VAD-Read-Fehler: {e}")
                    continue
                if sr != SAMPLE_RATE:
                    continue
                offset = self.schnitt_offset_sample
                aktuell = audio_np[offset:]
                dauer_sek = len(aktuell) / SAMPLE_RATE
                _debug_log(f"Cutter: {dauer_sek:.1f}s seit letztem Schnitt")
                if dauer_sek < VAD_CHUNK_ZIEL_SEK:
                    continue
                schnitt_sample = self._finde_schnittstelle(aktuell, dauer_sek)
                if schnitt_sample is None:
                    continue
                start_sample = offset
                end_sample   = offset + schnitt_sample
                ausschnitt = audio_np[start_sample:end_sample]
                # Overlap: nächster Chunk beginnt 400ms VOR dem Schnitt,
                # damit leise Randwörter nicht in die Ritze fallen
                overlap = int(0.4 * 16000)
                self.schnitt_offset_sample = max(0, end_sample - overlap)
                threading.Thread(
                    target=self._transkribiere_ausschnitt,
                    args=(ausschnitt, sr),
                    daemon=True,
                ).start()
            except Exception as e:
                _debug_log(f"Cutter-Fehler: {e}")

    def _finde_schnittstelle(self, audio_np, dauer_sek):
        """Sucht Pause im Bereich ZIEL..MAX. Rückgabe: Sample-Index oder None."""
        SAMPLE_RATE = 16000
        try:
            audio_torch = _torch.from_numpy(audio_np)
            segmente = _vad_stamps(
                audio_torch, _vad_modell,
                sampling_rate=SAMPLE_RATE,
                min_silence_duration_ms=VAD_MIN_PAUSE_MS,
                min_speech_duration_ms=250,
                return_seconds=False,
            )
        except Exception as e:
            _debug_log(f"VAD-Analyse-Fehler: {e}")
            return None
        ziel_sample = VAD_CHUNK_ZIEL_SEK * SAMPLE_RATE
        max_sample  = VAD_CHUNK_MAX_SEK  * SAMPLE_RATE
        _debug_log(f"VAD: {len(segmente)} Segmente, dauer={dauer_sek:.1f}s")
        for seg in reversed(segmente):
            ende = seg["end"]
            if ziel_sample <= ende <= max_sample:
                schnitt = ende + int(0.8 * SAMPLE_RATE)  # großzügig damit leise Satzenden mitkommen
                schnitt = min(schnitt, len(audio_np))
                _debug_log(f"VAD-Schnitt bei {schnitt/SAMPLE_RATE:.1f}s")
                return schnitt
        if dauer_sek >= VAD_CHUNK_MAX_SEK:
            _debug_log(f"Notfall-Schnitt bei {VAD_CHUNK_MAX_SEK}s")
            return max_sample
        return None

    def _transkribiere_ausschnitt(self, audio_np, sr):
        """Prüft erst per VAD ob überhaupt Sprache drin ist, dann Whisper."""
        try:
            # VAD-Vorprüfung: enthält der Ausschnitt überhaupt Sprache?
            if _vad_verfuegbar:
                try:
                    audio_torch = _torch.from_numpy(audio_np)
                    segmente = _vad_stamps(
                        audio_torch, _vad_modell,
                        sampling_rate=sr,
                        min_silence_duration_ms=VAD_MIN_PAUSE_MS,
                        min_speech_duration_ms=250,
                        return_seconds=True,
                    )
                    # Gesamt-Sprech-Dauer im Ausschnitt
                    sprech_dauer = sum(s["end"] - s["start"] for s in segmente)
                    if sprech_dauer < 0.5:
                        _debug_log(f"Ausschnitt verworfen (nur {sprech_dauer:.2f}s Sprache)")
                        return
                except Exception as e:
                    _debug_log(f"VAD-Vorprüfung fehlgeschlagen: {e}")
                    # Fallback: trotzdem an Whisper schicken
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            _sf.write(tmp.name, audio_np, sr, subtype="PCM_16")
            tmp.close()
            self._transkribiere_wav(tmp.name, ausschnitt=True)
        except Exception as e:
            _debug_log(f"Ausschnitt-Fehler: {e}")

    def _transkribiere_wav(self, wav_pfad, ausschnitt=False):
        """Whisper-Aufruf + Text einfügen."""
        try:
            if not os.path.exists(wav_pfad):
                return
            if berechne_audio_energie(wav_pfad) < 150:
                try: os.unlink(wav_pfad)
                except: pass
                return
            befehl = [
                WHISPER_CLI,
                "--language", LANGUAGE,
                "--model", MODELLE[self.aktives_modell],
                "--no-timestamps", "--no-prints",
                "--no-speech-thold", "0.8",
                "--file", wav_pfad,
            ]
            full_prompt = self.initial_prompt
            if self.session_prompt_words:
                extra = ", ".join(self.session_prompt_words)
                full_prompt = (full_prompt + ", " + extra) if full_prompt else extra
            if full_prompt:
                befehl += ["--prompt", full_prompt]
            _t0 = time.time()
            ergebnis = subprocess.run(befehl, capture_output=True, text=True)
            _debug_log(f"Whisper-{'Chunk' if ausschnitt else 'Rest'} in {time.time()-_t0:.1f}s")
            text = ergebnis.stdout.strip()
            if not text or any(bl.lower() in text.lower() for bl in HALLUZINATION_BLOCKLISTE):
                try: os.unlink(wav_pfad)
                except: pass
                return
            if self.replacements:
                text = wende_replacements_an(text, self.replacements)
            if self.session_replacements:
                text = wende_replacements_an(text, self.session_replacements)
            if self.kleinschreibung_aktiv:
                text = text.lower()
            if text.strip():
                fuege_text_ein(text)
            try: os.unlink(wav_pfad)
            except: pass
        except Exception as e:
            _debug_log(f"Whisper-Fehler: {e}")


    def _baue_historie_menues(self):
        self._diktier_submenu = rumps.MenuItem("📝 Letzte Diktate")
        self._clipboard_submenu = rumps.MenuItem("📋 Zwischenablage")
        self._aktualisiere_diktier_menu()
        self._aktualisiere_clipboard_menu()

    def _aktualisiere_diktier_menu(self):
        if not hasattr(self, "_diktier_submenu"):
            return
        try: self._diktier_submenu.clear()
        except (AttributeError, KeyError): pass
        if not DIKTIER_HISTORIE:
            self._diktier_submenu.add(rumps.MenuItem("(noch leer)", callback=None))
        else:
            for eintrag in DIKTIER_HISTORIE:
                label = _historie_kuerzen(eintrag)
                item = rumps.MenuItem(label, callback=self._make_historie_callback(eintrag))
                self._diktier_submenu.add(item)
            self._diktier_submenu.add(rumps.separator)
            self._diktier_submenu.add(rumps.MenuItem("🗑 Historie leeren", callback=self._leere_diktier_historie))

    def _aktualisiere_clipboard_menu(self):
        if not hasattr(self, "_clipboard_submenu"):
            return
        try: self._clipboard_submenu.clear()
        except (AttributeError, KeyError): pass
        if not CLIPBOARD_HISTORIE:
            self._clipboard_submenu.add(rumps.MenuItem("(noch leer)", callback=None))
        else:
            for eintrag in CLIPBOARD_HISTORIE:
                label = _historie_kuerzen(eintrag)
                item = rumps.MenuItem(label, callback=self._make_historie_callback(eintrag))
                self._clipboard_submenu.add(item)
            self._clipboard_submenu.add(rumps.separator)
            self._clipboard_submenu.add(rumps.MenuItem("🗑 Historie leeren", callback=self._leere_clipboard_historie))

    def _make_historie_callback(self, text):
        def _cb(sender):
            fuege_text_ein(text, zu_historie=False)
        return _cb

    def _clipboard_poller(self):
        """Beobachtet die System-Zwischenablage und ergänzt die Historie."""
        letzter = ""
        try: letzter = pyperclip.paste() or ""
        except: pass
        while True:
            time.sleep(1.0)
            if not getattr(self, "clipboard_poller_aktiv", True):
                continue
            try:
                aktuell = pyperclip.paste() or ""
            except Exception:
                continue
            if not aktuell or aktuell == letzter:
                continue
            letzter = aktuell
            if aktuell == _letzter_eigener_copy:
                continue
            if DIKTIER_HISTORIE and aktuell.strip() == DIKTIER_HISTORIE[0]:
                continue
            # Passwörter/Tokens nicht in Historie
            if _sieht_aus_wie_passwort(aktuell.strip()):
                _debug_log("Clipboard-Eintrag sieht aus wie Passwort – übersprungen")
                continue
            _historie_hinzufuegen(aktuell, CLIPBOARD_HISTORIE)
            _speichere_historie()
            try:
                self._aktualisiere_clipboard_menu()
            except Exception as e:
                _debug_log(f"Clipboard-Menu-Update-Fehler: {e}")

    def _leere_diktier_historie(self, sender):
        DIKTIER_HISTORIE.clear()
        _speichere_historie()
        self._aktualisiere_diktier_menu()

    def _leere_clipboard_historie(self, sender):
        CLIPBOARD_HISTORIE.clear()
        _speichere_historie()
        self._aktualisiere_clipboard_menu()

if __name__ == "__main__":
    app = DiktierApp()
    app.run()

