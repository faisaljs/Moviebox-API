import os
from pathlib import Path

from dotenv import load_dotenv


def load_environment() -> None:
    explicit_path = os.environ.get("MOVIEBOX_ENV_FILE")
    if explicit_path:
        load_dotenv(Path(explicit_path).expanduser(), override=False)
        return

    config_home = Path(
        os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    )
    candidates = (
        Path.cwd() / ".env",
        config_home / "moviebox" / ".env",
        Path(__file__).resolve().parent / ".env",
    )
    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)
            return