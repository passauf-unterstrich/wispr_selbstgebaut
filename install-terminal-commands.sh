#!/bin/bash
# Installiert echte Terminal-Befehle und traegt ~/.local/bin passend zur
# Login-Shell in PATH ein. Kann gefahrlos mehrfach ausgefuehrt werden.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
USER_HOME="${WISPR_TEST_HOME:-$HOME}"
BIN_DIR="$USER_HOME/.local/bin"
START_MARKER="# >>> wispr terminal commands >>>"
END_MARKER="# <<< wispr terminal commands <<<"

mkdir -p "$BIN_DIR"
chmod 755 "$SCRIPT_DIR/bin/diktieren" "$SCRIPT_DIR/bin/diktieren-update"

# Beide Schreibweisen starten dieselbe App. Auf den ueblichen, nicht
# case-sensitiven macOS-Dateisystemen funktionieren damit auch Diktieren/Diktiere.
ln -sfn "$SCRIPT_DIR/bin/diktieren" "$BIN_DIR/diktieren"
ln -sfn "$SCRIPT_DIR/bin/diktieren" "$BIN_DIR/diktiere"
ln -sfn "$SCRIPT_DIR/bin/diktieren-update" "$BIN_DIR/diktieren-update"
# Auf einem case-sensitiven Dateisystem auch die exakt grossgeschriebenen
# Varianten anlegen. Auf normalen macOS-Dateisystemen sind sie bereits identisch.
[ -e "$BIN_DIR/Diktieren" ] || ln -s "$SCRIPT_DIR/bin/diktieren" "$BIN_DIR/Diktieren"
[ -e "$BIN_DIR/Diktiere" ] || ln -s "$SCRIPT_DIR/bin/diktieren" "$BIN_DIR/Diktiere"

entferne_alte_aliase() {
    local datei="$1"
    [ -f "$datei" ] || return 0
    local tmp
    tmp="$(mktemp)"
    awk '
        /alias[[:space:]]+diktieren=/ { next }
        /alias[[:space:]]+diktiere=/ { next }
        /alias[[:space:]]+diktieren-update=/ { next }
        { print }
    ' "$datei" > "$tmp"
    cat "$tmp" > "$datei"
    rm -f "$tmp"
}

setze_block() {
    local datei="$1"
    local path_zeile="$2"
    local tmp
    mkdir -p "$(dirname "$datei")"
    touch "$datei"
    entferne_alte_aliase "$datei"
    tmp="$(mktemp)"
    awk -v start="$START_MARKER" -v ende="$END_MARKER" '
        $0 == start { im_block = 1; next }
        $0 == ende  { im_block = 0; next }
        !im_block   { print }
    ' "$datei" > "$tmp"
    cat "$tmp" > "$datei"
    rm -f "$tmp"
    {
        printf '\n%s\n' "$START_MARKER"
        printf '%s\n' "$path_zeile"
        printf '%s\n' "$END_MARKER"
    } >> "$datei"
}

LOGIN_SHELL="$(basename "${SHELL:-/bin/zsh}")"
case "$LOGIN_SHELL" in
    zsh)
        setze_block "$USER_HOME/.zshrc" 'export PATH="$HOME/.local/bin:$PATH"'
        SHELL_DATEIEN="~/.zshrc"
        ;;
    bash)
        # Terminal.app startet Bash normalerweise als Login-Shell; andere
        # Terminals verwenden haeufig eine interaktive Nicht-Login-Shell.
        setze_block "$USER_HOME/.bash_profile" 'export PATH="$HOME/.local/bin:$PATH"'
        setze_block "$USER_HOME/.bashrc" 'export PATH="$HOME/.local/bin:$PATH"'
        SHELL_DATEIEN="~/.bash_profile und ~/.bashrc"
        ;;
    fish)
        setze_block "$USER_HOME/.config/fish/config.fish" 'set -gx PATH "$HOME/.local/bin" $PATH'
        SHELL_DATEIEN="~/.config/fish/config.fish"
        ;;
    ksh)
        setze_block "$USER_HOME/.profile" 'export PATH="$HOME/.local/bin:$PATH"'
        setze_block "$USER_HOME/.kshrc" 'export PATH="$HOME/.local/bin:$PATH"'
        SHELL_DATEIEN="~/.profile und ~/.kshrc"
        ;;
    csh|tcsh)
        setze_block "$USER_HOME/.${LOGIN_SHELL}rc" 'setenv PATH "$HOME/.local/bin:$PATH"'
        SHELL_DATEIEN="~/.${LOGIN_SHELL}rc"
        ;;
    *)
        # POSIX-Fallback fuer sh, dash und andere kompatible Login-Shells.
        setze_block "$USER_HOME/.profile" 'export PATH="$HOME/.local/bin:$PATH"'
        SHELL_DATEIEN="~/.profile (Fallback fuer $LOGIN_SHELL)"
        ;;
esac

echo "✓ Login-Shell erkannt: $LOGIN_SHELL"
echo "✓ Terminal-Pfad eingerichtet: $SHELL_DATEIEN"
echo "✓ Befehle installiert: diktieren, diktiere, diktieren-update"
