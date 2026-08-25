# Wispr (selbstgebaut)

Eine lokale Diktierfunktion für macOS. Audio wird mit `whisper.cpp` auf dem
eigenen Mac transkribiert und der fertige Text an der aktuellen Cursorposition
eingefügt. Der optionale KI-Assistent nutzt standardmäßig ein lokales
Ollama-Modell.

## Installation

Im Terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/passauf-unterstrich/wispr_selbstgebaut/main/install.sh | bash
```

Das geführte Setup erkennt die Login-Shell (Zsh, Bash, Fish, Ksh, Csh/Tcsh
und POSIX-kompatible Shells) und richtet echte Befehle in `~/.local/bin` ein.
Danach ein neues Terminal-Fenster öffnen:

```bash
diktieren
# oder gleichwertig:
diktiere
```

Ein Update wird mit `diktieren-update` gestartet.

Im Menü der laufenden App kann **Bei Anmeldung starten** ein- und ausgeschaltet
werden. Die Option ist zunächst aus und wird von macOS unter **Systemeinstellungen
→ Allgemein → Anmeldeobjekte & Erweiterungen** verwaltet. Es werden dafür weder
Administratorrechte noch ein versteckter LaunchAgent verwendet.

## Datenschutz und Berechtigungen

- Mikrofon- und Barrierefreiheitszugriff werden für Aufnahme, globale
  Tastenkürzel und das Einfügen des Textes benötigt.
- Die normale Diktierfunktion sendet Audio und Text nicht an einen Cloud-Dienst.
- Ollama ist lokal unter `127.0.0.1:11434` vorgesehen. `OLLAMA_HOST` sollte
  nicht auf `0.0.0.0` oder eine Netzwerkadresse gesetzt werden.
- Der optionale Modus **Claude API** sendet den jeweiligen Befehl an Anthropic.
  Er sollte nur bewusst aktiviert und niemals mit einem API-Key im Repository
  konfiguriert werden.
- Diktat-Historie wird lokal in `.historie.json` gespeichert. Das Mitschneiden
  der allgemeinen Zwischenablage ist bei Neuinstallationen standardmäßig aus
  und kann im Menü aktiviert werden.
- Persönliche Dateien (`config.json`, `assistant_style.md`, `vocabulary.csv`,
  `.historie.json`, `.env`) dürfen nicht committed werden und stehen in
  `.gitignore`.

## Einordnung

Dies ist ein privates, nicht professionell auditiertes Projekt. Installationen
verwenden veröffentlichte Release-Tags, nicht automatisch den neuesten Stand
des Entwicklungsbranches. Vor einer Weitergabe sollte ein Release bewusst
erstellt und auf einem frischen Benutzerkonto getestet werden.
