#!/usr/bin/env bash
set -euo pipefail

APP_NAME="SmartVideoDownloader"
ENTRY_FILE="app.py"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build"
APPDIR="$PROJECT_DIR/${APP_NAME}.AppDir"
PYI_DIST="$DIST_DIR/$APP_NAME"

echo "==> Project: $PROJECT_DIR"

# -----------------------------
# 1. Ensure venv exists
# -----------------------------
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# -----------------------------
# 2. Install Python deps
# -----------------------------
python -m pip install --upgrade pip
python -m pip install -r "$PROJECT_DIR/requirements.txt"

# -----------------------------
# 3. Clean old outputs
# -----------------------------
rm -rf "$BUILD_DIR" "$DIST_DIR" "$APPDIR"
mkdir -p "$APPDIR"

# -----------------------------
# 4. Build with PyInstaller
#    Use onedir for Linux portability
# -----------------------------
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  "$PROJECT_DIR/$ENTRY_FILE"

# -----------------------------
# 5. Bundle yt-dlp beside app
# -----------------------------
mkdir -p "$PYI_DIST/bin"

YTDLP_BIN="$(command -v yt-dlp || true)"
if [ -z "$YTDLP_BIN" ]; then
  echo "ERROR: yt-dlp not found in PATH"
  exit 1
fi

cp "$YTDLP_BIN" "$PYI_DIST/bin/yt-dlp"
chmod +x "$PYI_DIST/bin/yt-dlp"

# -----------------------------
# 6. Create AppDir structure
# -----------------------------
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -r "$PYI_DIST"/* "$APPDIR/usr/bin/"

# -----------------------------
# 7. Desktop file
# -----------------------------
cat > "$APPDIR/$APP_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Smart Video Downloader
Exec=$APP_NAME
Icon=$APP_NAME
Categories=Utility;Network;AudioVideo;
Terminal=false
EOF

cp "$APPDIR/$APP_NAME.desktop" "$APPDIR/usr/share/applications/$APP_NAME.desktop"

# -----------------------------
# 8. AppRun launcher
# -----------------------------
cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE/usr/bin:$HERE/usr/bin/bin:$PATH"
exec "$HERE/usr/bin/SmartVideoDownloader" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# -----------------------------
# 9. Icon
#    If you have your own icon.png, use it.
# -----------------------------
if [ -f "$PROJECT_DIR/icon.png" ]; then
  cp "$PROJECT_DIR/icon.png" "$APPDIR/$APP_NAME.png"
  cp "$PROJECT_DIR/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
else
  echo "No icon.png found, skipping icon copy."
fi

# -----------------------------
# 10. Download linuxdeploy if missing
# -----------------------------
LINUXDEPLOY="$PROJECT_DIR/linuxdeploy-x86_64.AppImage"
if [ ! -f "$LINUXDEPLOY" ]; then
  echo "==> Downloading linuxdeploy..."
  wget -O "$LINUXDEPLOY" \
    https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
  chmod +x "$LINUXDEPLOY"
fi

# -----------------------------
# 11. Build AppImage
# -----------------------------
echo "==> Building AppImage..."
ARCH=x86_64 "$LINUXDEPLOY" \
  --appdir "$APPDIR" \
  --desktop-file "$APPDIR/$APP_NAME.desktop" \
  ${PROJECT_DIR:+$( [ -f "$PROJECT_DIR/icon.png" ] && echo "--icon-file $PROJECT_DIR/icon.png" )} \
  --output appimage

echo
echo "Done."
echo "AppImage should be in: $PROJECT_DIR"