# Plan: SSH Bridge Decorator for `query_runner.py`

**TL;DR** — Add a single `@ssh_dispatch` decorator (in a new `ssh_bridge.py` module) that routes the `run()` function's execution based on an `SSH_MODE` env var. Two modes: `tunnel` (sshtunnel/Paramiko — for local testing with a private DB) and `remote` (Fabric — for invoking the pipeline from your laptop without deploying). Without `SSH_MODE` set, the decorator is a complete no-op, so all existing monkey-patch tests continue to work unchanged.

---

**Why one decorator instead of two:**
Both Fabric and sshtunnel address the same question — *"how should this function reach its resource?"* — so one `@ssh_dispatch` dispatcher is cleaner than stacking `@ssh_tunnel @run_on_server` and having to remember which one is active.

---

## Steps

### Phase 1 — New module `ssh_bridge.py`

1. Create `src/pipeline/ssh_bridge.py` with three things:
   - `_run_via_tunnel(func, *args, **kwargs)` — wraps the call in an `SSHTunnelForwarder` context, temporarily injects `SRC_DB_HOST=127.0.0.1` and `SRC_DB_PORT=<local_port>` into `os.environ`, then calls the function. Uses a `finally` block to restore originals.
   - `_run_on_server(func, *args, **kwargs)` — builds a `fabric.Connection`, extracts `start`/`end`/`output` from the call args, runs the existing CLI command remotely (`cd $SSH_REMOTE_PROJECT && python -m pipeline query --start ... --end ...`). If `output` is a file path, SFTPs the result back locally.
   - `ssh_dispatch` decorator — reads `SSH_MODE`, dispatches to the two helpers or falls through.

2. New env vars (read inside the two helpers, not globally):

| Var | Mode | Purpose |
|---|---|---|
| `SSH_MODE` | both | `tunnel` or `remote`; absent = local direct |
| `SSH_HOST` | both | Server hostname/IP |
| `SSH_USER` | both | SSH username |
| `SSH_KEY` | both | Path to local private key |
| `SSH_REMOTE_PROJECT` | `remote` only | Absolute project path on server |

`SRC_DB_HOST` / `SRC_DB_PORT` already exist; the tunnel helper borrows them to know what to forward.

### Phase 2 — Apply decorator to `query_runner.py`

3. Import `ssh_dispatch` from `ssh_bridge` and apply it to `run()` only. `run_query(conn, …)` is explicitly excluded — it already receives a live connection, so tunneling or remote-exec at that level is not meaningful.

### Phase 3 — Dependencies

4. Add `sshtunnel` and `fabric` to `requirements.txt` and `pyproject.toml [project.dependencies]`.

### Phase 4 — Tests

5. Add `tests/test_ssh_bridge.py`:
   - Verify `@ssh_dispatch` is a no-op when `SSH_MODE` is unset (function is called directly → existing mock/monkeypatch tests unaffected)
   - Mock `sshtunnel.SSHTunnelForwarder` → assert env vars `SRC_DB_HOST`/`SRC_DB_PORT` are patched during the call and restored afterward
   - Mock `fabric.Connection` → assert the remote command string contains the correct `--start`, `--end`, `--output` values

---

## Relevant files

- `src/pipeline/query_runner.py` — add `@ssh_dispatch` to `run()` only
- `src/pipeline/ssh_bridge.py` — **new file** (decorator + two private helpers)
- `requirements.txt` — add `sshtunnel`, `fabric`
- `pyproject.toml` — add same to `[project.dependencies]`
- `tests/test_ssh_bridge.py` — **new file** (unit tests for bridge)

---

## Verification

1. Run existing tests without `SSH_MODE` set — all pass, no change in behavior.
2. In tunnel mode: set `SSH_MODE=tunnel` + SSH vars + valid `SRC_DB_*` vars → confirm `mysql.connector` receives `host=127.0.0.1` and the tunnel port.
3. In remote mode: set `SSH_MODE=remote` + SSH vars → confirm Fabric is called with the correct CLI command string.
4. Manual smoke test from laptop with `SSH_MODE=remote` against the real droplet → CSV returned locally.

---

## Decisions

- **Only `run()` is decorated** — `run_query(conn, …)` takes a live connection argument so it can't be meaningfully tunneled or remote-exec'd at the function level.
- **Private key auth only** — no password-based SSH; key path via `SSH_KEY` env var.
- **Remote mode constructs the CLI command** from the args passed to `run()`, mapping directly to the existing `pipeline query --start … --end …` CLI in `src/pipeline/cli.py`. No extra CLI changes needed.
- **Out of scope**: `importer.py`, `validator.py`, `cli.py` — no changes.

---

## Further considerations

1. **`run_query()` for local testing** — If you want to use `run_query` locally with a tunneled connection, the tunnel would need to be set up *before* the connection is built and passed in. A context manager (`with ssh_tunnel() as port: conn = connect(127.0.0.1, port)`) is more natural here than a decorator. Worth considering if you want to write tests that hit the real DB through a tunnel.
2. **Remote file paths** — In `remote` mode, if `output` is a local relative path, the plan proposes using a temp path on the server then SFTPing it back. You'll need `SSH_REMOTE_PROJECT` to be set to the absolute project path on the droplet. Confirm this matches where the pipeline is installed.
