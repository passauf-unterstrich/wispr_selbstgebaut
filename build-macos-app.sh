#!/bin/bash
# Baut einen kleinen nativen Apple-Silicon-Starter als Wispr.app.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR/Wispr.app"
NEUE_APP="$SCRIPT_DIR/.Wispr.app.neu"
BUILD_CACHE="$SCRIPT_DIR/.build-wispr-app/module-cache"
FINGERPRINT_DATEI="$APP_DIR/Contents/Resources/build.sha256"

/bin/bash "$SCRIPT_DIR/check-platform.sh"

BUILD_HASH="$(shasum -a 256 \
    "$SCRIPT_DIR/native/WisprLauncher.swift" \
    "$SCRIPT_DIR/native/Info.plist" \
    "$SCRIPT_DIR/build-macos-app.sh" | shasum -a 256 | awk '{print $1}')"

if [ -f "$FINGERPRINT_DATEI" ]; then
    VORHANDENER_HASH="$(tr -d '[:space:]' < "$FINGERPRINT_DATEI")"
    if [ "$VORHANDENER_HASH" = "$BUILD_HASH" ] && \
       codesign --verify --strict "$APP_DIR" >/dev/null 2>&1; then
        echo "✓ Wispr.app ist bereits aktuell und gültig signiert."
        exit 0
    fi
fi

if ! xcrun --find swiftc >/dev/null 2>&1; then
    echo "✗ Apples Swift-Compiler fehlt."
    echo "  Installiere zuerst die Command Line Tools: xcode-select --install"
    exit 1
fi

# Ein abgebrochener früherer Bau darf nie als fertige App erscheinen.
if [ -e "$NEUE_APP" ]; then
    mv "$NEUE_APP" "$SCRIPT_DIR/.Wispr.app.unvollstaendig-$(date +%Y%m%d-%H%M%S)"
fi

mkdir -p "$NEUE_APP/Contents/MacOS"
mkdir -p "$NEUE_APP/Contents/Resources"
mkdir -p "$BUILD_CACHE"
cp "$SCRIPT_DIR/native/Info.plist" "$NEUE_APP/Contents/Info.plist"

echo "• Kompiliere nativen Apple-Silicon-Starter..."
xcrun swiftc \
    -parse-as-library \
    -target arm64-apple-macos13.0 \
    -module-cache-path "$BUILD_CACHE" \
    -framework AppKit \
    -framework ApplicationServices \
    -framework AVFoundation \
    "$SCRIPT_DIR/native/WisprLauncher.swift" \
    -o "$NEUE_APP/Contents/MacOS/WisprLauncher"

printf '%s\n' "$BUILD_HASH" > "$NEUE_APP/Contents/Resources/build.sha256"

# Kostenloser lokaler Build: ad-hoc signiert. Eine später eingerichtete lokale
# Signieridentität kann diesen Schritt ersetzen und Rechte über Updates halten.
codesign --force --sign - --identifier de.passaufunterstrich.wispr "$NEUE_APP"
codesign --verify --strict --verbose=2 "$NEUE_APP"

if [ -e "$APP_DIR" ]; then
    ALTE_APP="$SCRIPT_DIR/.Wispr.app.vorher-$(date +%Y%m%d-%H%M%S)"
    mv "$APP_DIR" "$ALTE_APP"
    echo "• Vorherige Starter-App gesichert: $ALTE_APP"
fi
mv "$NEUE_APP" "$APP_DIR"

echo "✓ Wispr.app wurde sicher gebaut."
