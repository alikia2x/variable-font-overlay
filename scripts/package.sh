#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUNDLE="$PROJECT_DIR/Variable Font Overlay.glyphsPlugin"
PLIST="$BUNDLE/Contents/Info.plist"
VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST")"
ARCHIVE="$PROJECT_DIR/Variable Font Overlay-$VERSION.zip"

cp "$PROJECT_DIR/LICENSE" "$BUNDLE/Contents/Resources/LICENSE.txt"

python3 "$PROJECT_DIR/scripts/validate_bundle.py"
python3 -m unittest discover -s "$PROJECT_DIR/tests" -v
plutil -lint "$PLIST"

xattr -cr "$BUNDLE"
ditto --norsrc --noextattr -c -k --keepParent "$BUNDLE" "$ARCHIVE"
unzip -t "$ARCHIVE"
shasum -a 256 "$ARCHIVE"

echo "Created $ARCHIVE"
