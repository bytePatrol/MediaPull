#!/usr/bin/env bash
# Post-build: apply custom icon to DMG files

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ICON="$PROJECT_DIR/src-tauri/icons/icon.png"

if ! command -v fileicon &>/dev/null; then
    echo "[post-build] fileicon not found, skipping DMG icon. Install with: brew install fileicon"
    exit 0
fi

# Apply icon to all built DMGs (debug + release)
for dmg in "$PROJECT_DIR"/src-tauri/target/*/bundle/dmg/*.dmg; do
    if [ -f "$dmg" ]; then
        echo "[post-build] Setting icon on $(basename "$dmg")"
        fileicon set "$dmg" "$ICON"
    fi
done
