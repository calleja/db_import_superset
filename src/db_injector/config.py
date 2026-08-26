"""Single owner of "where do the secrets live?".

Both establish_ssh (VM_* keys) and db_interactor (DB_* keys) resolve their
.env file through find_env_file(), so the lookup rules live in exactly one
place. This module imports neither of them, which keeps the dependency
direction one-way: transport -> config, data -> config, never sideways.
"""

import os
from pathlib import Path

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
