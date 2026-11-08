#!/bin/sh
set -eu

REPOSITORY="faisaljs/Moviebox-API"
REF="${MOVIEBOX_REF:-main}"
REF_TYPE="${MOVIEBOX_REF_TYPE:-branch}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="$DATA_HOME/moviebox"
SOURCE_DIR="$INSTALL_DIR/source"
NEXT_DIR="$INSTALL_DIR/source.next.$$"
BACKUP_DIR="$INSTALL_DIR/source.backup.$$"
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

cleanup() {
  if [ -d "$BACKUP_DIR" ] && [ ! -d "$SOURCE_DIR" ]; then
    mv "$BACKUP_DIR" "$SOURCE_DIR"
  fi
  if [ -n "$TMP_DIR" ]; then
    rm -rf "$TMP_DIR"
  fi
  rm -rf "$NEXT_DIR"
}

case "$REF" in
  ""|/*|*..*|*[!A-Za-z0-9._/-]*)
    echo "Invalid MOVIEBOX_REF: $REF" >&2
    exit 1
    ;;
esac

case "$REF_TYPE" in
  branch) REF_PATH="refs/heads/$REF" ;;
  tag) REF_PATH="refs/tags/$REF" ;;
  *) echo "MOVIEBOX_REF_TYPE must be 'branch' or 'tag'." >&2; exit 1 ;;
esac

for tool in curl tar python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Required command not found: $tool" >&2
    exit 1
  fi
done

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
  echo "Python 3.10+ is required (union syntax in type hints)." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap cleanup EXIT HUP INT TERM

printf '\n%sMovieBox API%s %sInstaller%s\n\n' "$PINK" "$RESET" "$DIM" "$RESET"
step "Downloading source ($REF)"
curl -fsSL "https://codeload.github.com/$REPOSITORY/tar.gz/$REF_PATH" -o "$TMP_DIR/source.tar.gz"
mkdir -p "$TMP_DIR/source" "$NEXT_DIR" "$INSTALL_DIR"
tar -xzf "$TMP_DIR/source.tar.gz" --strip-components=1 -C "$NEXT_DIR"
done_step "Source downloaded"

if [ ! -x "$INSTALL_DIR/venv/bin/python" ]; then
  step "Creating an isolated Python environment"
  python3 -m venv "$INSTALL_DIR/venv"
  done_step "Python environment ready"
fi

step "Installing required components"
"$INSTALL_DIR/venv/bin/python" -m pip install --quiet --disable-pip-version-check -r "$NEXT_DIR/requirements.txt"
done_step "Components installed"

step "Installing app files"
if [ -d "$SOURCE_DIR" ]; then
  mv "$SOURCE_DIR" "$BACKUP_DIR"
fi
if ! mv "$NEXT_DIR" "$SOURCE_DIR"; then
  if [ -d "$BACKUP_DIR" ]; then
    mv "$BACKUP_DIR" "$SOURCE_DIR"
  fi
  echo "Could not replace the installed app files." >&2
  exit 1
fi
rm -rf "$BACKUP_DIR"
done_step "App files installed"

printf '\n%sMovieBox API is ready.%s\n\n' "$GREEN" "$RESET"
printf 'Run it with:\n'
printf '  %s%s/moviebox/venv/bin/python %s/moviebox/source/main.py%s\n\n' \
  "$DIM" "$DATA_HOME" "$DATA_HOME" "$RESET"
printf 'Or inside docker:\n'
printf '  %sdocker compose up%s\n' "$DIM" "$RESET"