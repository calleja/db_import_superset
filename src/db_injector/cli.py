"""Command-line interface for the activity-pipeline package.

This python package should run in terminal and accept the following arguments: `name of file`, `name of table` (to create or override on the server), `path to yaml file` (tbd, might be optional)
when it finishes, it should state whether the injection was a failure or success, and if a success print the fields and datatypes in the terminal

uv run db-injector '/Users/casita/Documents/2026 Spoilage - Sheet1.csv' table_name --if-exists replace
"""

# ══ ORIGINAL CODE (unchanged) ════════════════════════════════════════════════
# Preserved as written, down to the "APPENDED CODE" banner. Two notes: the flat
# import below is commented out because it only resolves when the interpreter is
# already inside this folder (the appended section uses a package-relative
# import instead), and main() still references argparse/query_runner/validator/
# importer, which are not imported or present in this package.

# %%
from argparse import ArgumentParser

# import db_interactor, establish_ssh   # ← original; see package-relative import below

'''
ask myself if I need a subcommand, and if I do, should it accept arguments
'''

''' my legacy code
parser = ArgumentParser(prog="db_injector")
#these help arguments show up on the command line when I run the program with --help or -h
#in this case, because filepath and table_name are required, those are referred to as positional arguments, while yaml_path is an "optional argument"
parser.add_argument("filepath", help="path to the file to be injected")
parser.add_argument("table_name", help="name of the table to be injected into")
parser.add_argument("yaml_path", help="path to the yaml file containing the schema")
args = parser.parse_args(['/here','nombre','yaml']) #delivers a namespace object that contains all the user's arguments in the form of properties (I may have multiple arguments)
#ostensibly, I'll have a args.filepath, args.table_name, args.yaml_path
args
'''
# %%

# ── ORIGINAL main(): sketch carried over from the activity-pipeline package.
# Left intact; the working entry point is inject() in the appended section.
def pre_main(): #main() is found at bottom
    """Parse CLI arguments and dispatch to the appropriate pipeline stage."""
    parser = ArgumentParser(prog="db_injector")
    sub = parser.add_subparsers(dest="cmd")

    #three arguments: name of file, name of table, path to yaml file (optional)
    s = sub.add_parser(
        "name of file, name of table, path to yaml file",
        help="in order, provide name of file, name of table, path to yaml file",
    )

    # ── validate: CI smoke test against source DB ─────────────────────
    sub.add_parser(
        "validate",
        help="smoke-test: query source DB with hardcoded dates, assert rows > 0",
    )

    args = parser.parse_args()

    if args.cmd == "sync":
        # Convert YYYYMMDD → YYYYMMDDhhmmss timestamps
        start_ts = query_runner.to_timestamp(args.start, is_start=True)
        end_ts = query_runner.to_timestamp(args.end, is_start=False)

        # Step 1: query source database
        print(f"[sync] Querying source DB for range {args.start}–{args.end} …")
        try:
            cols, rows = query_runner.run(start_ts, end_ts)
        except Exception as e:
            print(f"[sync] Query phase failed: {e}")
            raise SystemExit(1)

        print(f"[sync] Received {len(rows)} rows, {len(cols)} columns")

        # Step 2: validate resultset shape
        try:
            validator.run(rows=rows, cols=cols)
        except Exception as e:
            print(f"[sync] Validation failed: {e}")
            raise SystemExit(1)

        print("[sync] Validation passed")

        # Step 3: insert into target (skip if --dry-run)
        if args.dry_run:
            print("[sync] --dry-run: skipping INSERT into target DB")
        else:
            try:
                count = importer.run(rows=rows, cols=cols)
                print(f"[sync] Done — {count} rows written to target")
            except Exception as e:
                print(f"[sync] Import phase failed: {e}")
                raise SystemExit(1)

    elif args.cmd == "validate":
        # CI smoke test — no arguments, queries source with hardcoded dates
        try:
            validator.run()
            print("[validate] Smoke test passed")
        except Exception as e:
            print(f"[validate] Smoke test failed: {e}")
            raise SystemExit(1)

    else:
        parser.print_help()


# ══ APPENDED CODE ════════════════════════════════════════════════════════════
# Working entry point. This is the only module that knows about both layers: it
# opens the tunnel from establish_ssh and hands the resulting port to
# db_interactor. Point the console script at it with, in pyproject.toml:
#     [project.scripts]
#     db-injector = "db_injector.cli:inject"
# acceptable command: db-injector /path/to/file.csv table_name --yaml-path /path/to/yaml.yaml --if-exists replace/append
import sys

from . import db_interactor, establish_ssh


def build_parser() -> ArgumentParser:
    """Define the injection command's arguments.

    filepath and table_name stay positional (both are required); yaml_path
    becomes an optional flag since .env is the default credential source.
    Split out from inject() so tests can parse argument lists without running
    anything.
    """
    parser = ArgumentParser(
        prog="db-injector",
        description="Inject a CSV/Excel file into a table on the droplet's MySQL over an SSH tunnel.",
    )
    parser.add_argument("filepath", help="path to the .csv/.xlsx file to be injected")
    parser.add_argument("table_name", help="name of the destination table")
    parser.add_argument(
        "--yaml-path",
        default=None,
        help="YAML file holding DB credentials; defaults to secrets/.env",
    )
    parser.add_argument(
        "--if-exists",
        choices=("fail", "replace", "append"),
        default="replace",
        help="what to do when the destination table already exists (default: replace)",
    )
    return parser


def inject() -> int:
    # "|" in parameters means "or"
    """Read the source file, then write it to the droplet through a tunnel.

    Arguments come from sys.argv via build_parser(). Returns a process exit code
    (0 success, 1 failure) which main() hands to sys.exit; tests that need to
    drive this directly should monkeypatch sys.argv.
    """
    args = build_parser().parse_args()

    # Read and parse the source file BEFORE opening the tunnel. A bad path or a
    # malformed CSV then fails in milliseconds rather than after the SSH
    # handshake, and we never hold a tunnel open while parsing a large file.
    try:
        df = db_interactor.read_source(args.filepath)
        print(f"[inject] Read {len(df)} rows, {len(df.columns)} columns from {args.filepath}")
    except Exception as e:
        print(f"[inject] Failure — could not read {args.filepath}: {e}")
        return 1

    # Tunnel stays open only for the write itself.
    try:
        #"with" evaluates the content expression to get a context manager object; the object is expected to contain an __enter__() and __exit__() method
        with establish_ssh.db_tunnel() as tunnel:
            #the next few lines are executed after setup of the tunnel; the "yield" statement (of the tunnel) suspends the function until the with block is exited
            print(f"[inject] Tunnel active on 127.0.0.1:{tunnel.local_bind_port}")
            engine = db_interactor.build_engine(
                #find where yaml_path is being handled
                port=tunnel.local_bind_port, yaml_path=args.yaml_path
            )
            try:
                # engine.begin() wraps the write in a transaction, so a partial failure rolls back instead of leaving a half-replaced table.
                # engine = sqlalchemy engine object's native method "begin"
                with engine.begin() as conn:
                    rows = db_interactor.write_table(
                        df, args.table_name, conn, if_exists=args.if_exists
                    )
            finally:
                # Dispose inside the tunnel: pooled sockets must not outlive it.
                engine.dispose()
    except Exception as e:
        print(f"[inject] Failure — injection aborted: {e}")
        return 1

    print(f"[inject] Success — wrote {rows} rows to '{args.table_name}'")
    print("[inject] Fields and datatypes:")
    for name, dtype in df.dtypes.items():
        print(f"    {name}: {dtype}")
    return 0 #return 0 means success to the shell


def main() -> int:
    """Console-script entry point named by [project.scripts] in pyproject.toml.

    Returning inject()'s exit code matters: the generated wrapper (`uv sync` regenerates it from db_injector.cli:main) calls sys.exit(main()), so swallowing it here would make every failed injection
    look successful to the shell ($? == 0).
    """
    return inject()


if __name__ == "__main__":
    #if run as standalone and not imported, exit with the result of main()
    sys.exit(main())
