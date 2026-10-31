#!/bin/sh
set -eu

REPOSITORY="faisaljs/Moviebox-API"
REF="${MOVIEBOX_REF:-main}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="$DATA_HOME/moviebox"
BIN_DIR="$HOME/.local/bin"
TMP_DIR=""

case "$REF" in
  ""|/*|*..*|*[!A-Za-z0-9._/-]*)
    echo "Invalid MOVIEBOX_REF: $REF" >&2
    exit 1
    ;;
esac

for tool in curl tar python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Required command not found: $tool" >&2
    exit 1
  fi
done

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT HUP INT TERM

echo "Downloading MovieBox ($REF)..."
curl -fsSL "https://codeload.github.com/$REPOSITORY/tar.gz/refs/heads/$REF" -o "$TMP_DIR/source.tar.gz"
mkdir -p "$TMP_DIR/source" "$INSTALL_DIR" "$BIN_DIR"
tar -xzf "$TMP_DIR/source.tar.gz" --strip-components=1 -C "$TMP_DIR/source"

echo "Installing files to $INSTALL_DIR/source..."
mkdir -p "$INSTALL_DIR/source"
cp -R "$TMP_DIR/source/." "$INSTALL_DIR/source/"

if [ ! -x "$INSTALL_DIR/venv/bin/python" ]; then
  python3 -m venv "$INSTALL_DIR/venv"
fi

echo "Installing Python dependencies..."
"$INSTALL_DIR/venv/bin/python" -m pip install --disable-pip-version-check -r "$INSTALL_DIR/source/requirements.txt"

cat > "$BIN_DIR/moviebox" <<'LAUNCHER'
#!/bin/sh
set -eu
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
exec "$DATA_HOME/moviebox/venv/bin/python" "$DATA_HOME/moviebox/source/cli.py" "$@"
LAUNCHER
chmod 755 "$BIN_DIR/moviebox"

echo "MovieBox CLI installed. Run: moviebox"
case ":${PATH:-}:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Add $BIN_DIR to PATH if the moviebox command is not found." ;;
esac
