"""Single owner of "where do the secrets live?".

Both establish_ssh (VM_* keys) and db_interactor (DB_* keys) resolve their
.env file through find_env_file(), so the lookup rules live in exactly one
place. This module imports neither of them, which keeps the dependency
direction one-way: transport -> config, data -> config, never sideways.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ENV_VAR = "DB_INJECTOR_ENV"


def find_env_file(explicit: str | Path | None = None) -> Path:
    """Locate the .env file in the secrets folder, trying the most specific source first.

    1. parse the "explicit" argument, if it exists, it will look there and return the full path; 
    |
    |
    V
    2. it will look at the environmental variable named "DB_INJECTOR_ENV"; user will need to export it first in their shell (a user would have to run these two:
    > echo 'export DB_INJECTOR_ENV="$HOME/.config/db_injector/.env"' >> ~/.zshrc
    > source ~/.zshrc
    > (to verify) echo "$DB_INJECTOR_ENV"
     |
     |
     V
    3. it will traverse the ancestor directories for a file named .env inside a directory named secrets, ex. ./secrets/.env
      |
      |
      V
    4. traverses up from the source directory path two levels and searches for a secrets directory and /env file.

    Returns a path that may not exist; callers report the failure.
    """
    if explicit:
        #the function would end here if explicit is provided
        #expanduser() expands ~ to the user's home directory (makes it full path)
        return Path(explicit).expanduser()

    override = os.getenv(ENV_VAR)
    if override:
        return Path(override).expanduser()

    cwd = Path.cwd().resolve()
    for directory in (cwd, *cwd.parents):
        candidate = directory / "secrets" / ".env"
        if candidate.is_file():
            return candidate

    return Path(__file__).resolve().parents[2] / "secrets" / ".env"


def load_env_file(path: Path) -> None:
    """Read `path` into os.environ, separating "absent" from "present but unreadable".

    load_dotenv() answers False for a missing file, an empty file, a
    comments-only file and a file written in YAML syntax alike, so its return
    value alone cannot say which happened — and step 4 of find_env_file() hands
    back the project-root path whether or not anything was found there, so the
    path in the message is no help either. The missing-file branch lists the
    directory's real contents because the usual cause on Windows is an extension
    Explorer or Notepad appended without showing it, e.g. `.env.txt`.
    """
    if not path.is_file():
        try:
            siblings = sorted(p.name for p in path.parent.iterdir())
        except OSError:
            detail = f"and its directory {path.parent} is missing or unreadable"
        else:
            detail = (
                f"— {path.parent} holds: {', '.join(siblings)}"
                if siblings
                else f"— {path.parent} is empty"
            )
        raise FileNotFoundError(f"No secrets file at {path} {detail}")

    if not load_dotenv(path):
        raise RuntimeError(
            f"{path} exists but yielded no variables. It is empty, all comments, "
            f"or written as YAML (KEY: value); this file needs KEY=value lines."
        )


def load_yaml_file(path: str | Path, keys: tuple[str, ...]) -> dict[str, Any]:
    """Pull `keys` out of a YAML secrets file, the --yaml-path alternative to .env.

    Kept here beside load_env_file() so both credential consumers — establish_ssh
    for the VM_* keys and db_interactor for the DB_* keys — read either format
    through the same two functions. Absent keys come back as None for the caller
    to report alongside its own required-key list.
    """
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        raise FileNotFoundError(f"No YAML secrets file at {resolved}")
    with open(resolved, "r") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise RuntimeError(
            f"{resolved} did not parse as a mapping. YAML needs a space after each "
            f"colon — 'KEY: value', not 'KEY:value', which reads as one long string."
        )
    return {key: data.get(key) for key in keys}
