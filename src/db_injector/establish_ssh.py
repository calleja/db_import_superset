#client resource: https://docs.paramiko.org/en/latest/api/client.html

# ══ ORIGINAL CODE (unchanged) ════════════════════════════════════════════════
# Everything from here down to the "APPENDED CODE" banner is your original
# exploratory work, preserved as written. The only structural change is the
# `if __name__ == "__main__":` guard added below, which stops the demo tunnel
# from opening every time another module imports this one.

#%%
from sshtunnel import SSHTunnelForwarder
from dotenv import load_dotenv
import os
from pathlib import Path

# ── ORIGINAL credential load — moved under the __main__ guard below. At module
# level it raised on import whenever secrets/.env was absent, which made even
# `db-injector --help` crash, and parents[2] points somewhere meaningless when
# the package is installed non-editably. ssh_config() now does this lazily via
# config.find_env_file(). Preserved verbatim for the direct-execution path:
if __name__ == "__main__":
    #parents[2] means skip two levels up from directory of this file
    env_path = Path(__file__).resolve().parents[2] / "secrets" / ".env"
    if not load_dotenv(env_path):
        raise FileNotFoundError(f"Could not load environment file: {env_path}")
    required = ("VM_URL", "VM_USER", "VM_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")


# ── ORIGINAL demo tunnel — now runs only when this file is executed directly
# (`python establish_ssh.py`) or cell-by-cell, not on `import establish_ssh`.
if __name__ == "__main__":
    with SSHTunnelForwarder(
        ssh_address_or_host=(os.getenv('VM_URL'),22),
        ssh_username=os.getenv('VM_USER'),
        ssh_password=os.getenv('VM_PASSWORD'),
        # target server host, port
        # local host, port
        remote_bind_address=("localhost", 3306),  # Forward to remote MySQL
        local_bind_address=("127.0.0.1", 5433),  # Listen on all local interfaces
    ) as tunnel:
        print(f"Tunnel active. Local port: {tunnel.local_bind_port}")
        print("Press enter to stop...")
        # Keep the tunnel open
        # input()

# %%
# ── ORIGINAL path-inspection cell — also guarded so importing stays silent.
from pathlib import Path

if __name__ == "__main__":
    print(Path(__file__).name)
    print(Path(__file__).parent)
    print(Path(__file__).resolve().parents[1])
    print(Path(__file__).resolve().parents[2])
    print(Path(__file__).resolve().parents[2] / "secrets" / ".env")

# %%
# ── ORIGINAL paramiko one-shot command runner. Not used by the new tunnel API
# below (that one uses sshtunnel for port forwarding rather than remote exec).
import paramiko

def ssh_tunnel(ip, username, password, command):

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #connect(hostname, port=22, username=None, password=None)
        client.connect(ip, username=username, password=password)
        print(f"[+] Connected to {ip}")
        stdin, stdout, stderr = client.exec_command(command)
        print(f"[+] Output:\n {stdout.read().decode()}")
        print(f"[-] Errors:\n {stderr.read().decode()}")
        client.close()
    except Exception as e:
        print(f"[!] SSH connection failed: {e}")
        return None
    finally:
        client.close()
    return client
# %%


# ══ APPENDED CODE ════════════════════════════════════════════════════════════
# Reusable, import-safe tunnel API. Nothing here runs at import time, so cli.py
# (and tests) can import this module freely.
#
# Layer boundary: this module knows about SSH and nothing about SQL. It hands
# back a local port; db_interactor.build_engine() turns that port into an
# engine. Neither module imports the other — cli.py wires them together.

from contextlib import contextmanager
from typing import Any

from .config import find_env_file


def ssh_config(env_path: Path | None = None) -> dict[str, Any]:
    """Load and validate the three credentials needed to open the tunnel.

    Parameters
    ----------
    env_path
        Override the secrets location. When omitted, config.find_env_file()
        checks $DB_INJECTOR_ENV and then searches upward from the current
        directory, so this works from anywhere and under a non-editable install.

    Returns a dict with "host", "user" and "password" keys. Called by
    db_tunnel() below — callers of db_tunnel() never need this directly.
    Raises early (before any network I/O) if a credential is missing.
    """
    path = find_env_file(env_path) #function simply returns a likely viable full path string
    if not load_dotenv(path):
        raise FileNotFoundError(f"Could not load environment file: {path}")
    required = ("VM_URL", "VM_USER", "VM_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
    return {
        "host": os.getenv("VM_URL"),
        "user": os.getenv("VM_USER"),
        "password": os.getenv("VM_PASSWORD"),
    }


@contextmanager
def db_tunnel(remote_port: int = 3306, local_port: int = 0, env_path: Path | None = None):
    """Open an SSH tunnel to the droplet and yield the live forwarder.

    Parameters
    ----------
    remote_port
        Port the database listens on *on the droplet* (MySQL's 3306).
    local_port
        Local port to listen on. 0 asks the OS for any free port, which avoids collisions with a stale listener on 5433; read the port the OS actually
        assigned back from `tunnel.local_bind_port`.
    env_path
        Passed straight through to ssh_config().

    Downstream usage — cli.py wraps the whole injection in this block and feeds the assigned port to db_interactor.build_engine():

        with db_tunnel() as tunnel:
            engine = build_engine(port=tunnel.local_bind_port)
            ...

    Every database operation must finish inside the block. The forwarder is torn down on exit and any connection opened through it dies with it, so dispose of engines before leaving.
    """
    cfg = ssh_config(env_path)
    #since the parent function carries the @contextmanager decorator, this will function like a context manager object (will implicitly contain an __enter__ and __exit__ method)
    with SSHTunnelForwarder(
        ssh_address_or_host=(cfg["host"], 22),
        ssh_username=cfg["user"],
        ssh_password=cfg["password"],
        remote_bind_address=("localhost", remote_port),
        local_bind_address=("127.0.0.1", local_port), 
        allow_agent=False,
        host_pkey_directories=[]
    ) as tunnel:
    #the function does not return at the yield. It suspends. Its stack frame — including the half-finished with SSHTunnelForwarder(...) — stays alive on the heap while your with block runs, and gets resumed later. 
    #in a contextmanager Class, everything appearing after "yield" is the "teardown" or __exit__ method
    #yield is used for generators as opposed to "return" which typically terminates a function
        yield tunnel
