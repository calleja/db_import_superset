"""Enables `python -m db_injector`.

Independent of the console script: [project.scripts] in pyproject.toml points
at db_injector.cli:main and gives you the `db-injector` command, while this file
is what Python executes for `python -m db_injector`. Both funnel into the same
main(), so the two invocations behave identically.
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
