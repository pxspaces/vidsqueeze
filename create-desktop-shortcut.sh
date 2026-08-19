#!/bin/bash
# Adds HalveIt to the Linux applications menu, so you can launch it the
# same way as any other program. Run once: ./create-desktop-shortcut.sh
# To undo, delete ~/.local/share/applications/halveit.desktop

set -e
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/halveit.desktop"

mkdir -p "$DESKTOP_DIR"
chmod +x "$APP_DIR/start-halveit.sh"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=HalveIt
GenericName=Video Compressor
Comment=Make video files smaller
Exec="$APP_DIR/start-halveit.sh"
Path=$APP_DIR
Terminal=true
Categories=AudioVideo;Video;
Keywords=video;compress;convert;ffmpeg;
EOF

chmod +x "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo
echo "  HalveIt has been added to your applications menu."
echo "  Look for it by name, or run: $APP_DIR/start-halveit.sh"
echo
