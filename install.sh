#!/bin/sh
set -eu

REPOSITORY="faisaljs/Moviebox-API"
REF="${MOVIEBOX_REF:-main}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="$DATA_HOME/moviebox"
BIN_DIR="$HOME/.local/bin"
TMP_DIR=""

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  PINK="$(printf '\033[38;5;205m')"
  GREEN="$(printf '\033[38;5;82m')"
  DIM="$(printf '\033[2m')"
  RESET="$(printf '\033[0m')"
else
  PINK=""
  GREEN=""
  DIM=""
  RESET=""
fi

step() {
  printf '  %s•%s %s\n' "$PINK" "$RESET" "$1"
}

done_step() {
  printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$1"
}

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

printf '\n%sMovieBox%s %sInstaller%s\n\n' "$PINK" "$RESET" "$DIM" "$RESET"
step "Downloading source ($REF)"
curl -fsSL "https://codeload.github.com/$REPOSITORY/tar.gz/refs/heads/$REF" -o "$TMP_DIR/source.tar.gz"
mkdir -p "$TMP_DIR/source" "$INSTALL_DIR" "$BIN_DIR"
tar -xzf "$TMP_DIR/source.tar.gz" --strip-components=1 -C "$TMP_DIR/source"
done_step "Source downloaded"

step "Installing app files"
mkdir -p "$INSTALL_DIR/source"
cp -R "$TMP_DIR/source/." "$INSTALL_DIR/source/"
done_step "App files installed"

if [ ! -x "$INSTALL_DIR/venv/bin/python" ]; then
  step "Creating an isolated Python environment"
  python3 -m venv "$INSTALL_DIR/venv"
  done_step "Python environment ready"
fi

step "Installing required components"
"$INSTALL_DIR/venv/bin/python" -m pip install --quiet --disable-pip-version-check -r "$INSTALL_DIR/source/requirements.txt"
done_step "Components installed"

step "Adding the moviebox command"
cat > "$BIN_DIR/moviebox" <<'LAUNCHER'
#!/bin/sh
set -eu
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
exec "$DATA_HOME/moviebox/venv/bin/python" "$DATA_HOME/moviebox/source/cli.py" "$@"
LAUNCHER
chmod 755 "$BIN_DIR/moviebox"
done_step "Command installed"

printf '\n%sInstallation complete.%s Run %smoviebox%s to open your local app.\n' "$GREEN" "$RESET" "$PINK" "$RESET"
case ":${PATH:-}:" in
  *":$BIN_DIR:"*) ;;
  *) printf '%sAdd %s to PATH if the command is not found.%s\n' "$DIM" "$BIN_DIR" "$RESET" ;;
esac
