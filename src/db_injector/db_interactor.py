#ingest the connection from establish_ssh.py and test the connection to the db

# ══ ORIGINAL CODE (unchanged) ════════════════════════════════════════════════
# Everything above the "APPENDED CODE" banner is your original work, untouched.
# Note identify_credentials() returns LOCAL_PORT while inject_data() reads
# 'PORT'/'DATABASE' — that mismatch is left as-is; the appended db_config()
# below supersedes it.

# batch-inserts all rows using executemany() 
# connect(user='scott', password='password',host='127.0.0.1' database='employees')

import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import yaml

'''
DB_USER=lcalleja2
VM_USER=lcalleja
VM_URL=67.207.80.236
DB_PASSWORD=3059891242
HOST=127.0.0.1
LOCAL_PORT=5433
'''

def identify_credentials(yaml_path = None):
    if yaml_path is None: #load the relevant .env file and extract credentials here and place in a dictionary for downstream use
        load_dotenv('./secrets/.env')
        credentials = {
            'DB_USER': os.getenv('DB_USER'),
            'DB_PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('HOST'),
            'LOCAL_PORT': os.getenv('LOCAL_PORT')
        }
    else: #parse the yaml file and extract the credentials
        with open(yaml_path, 'r') as file:
            yaml_data = yaml.load(file, Loader=yaml.FullLoader)
        DB_USER = yaml_data['DB_USER']
        DB_PASSWORD = yaml_data['DB_PASSWORD']
        HOST = yaml_data['HOST']
        LOCAL_PORT = yaml_data['LOCAL_PORT']
        credentials = {
            'DB_USER': DB_USER,
            'DB_PASSWORD': DB_PASSWORD,
            'HOST': HOST,
            'LOCAL_PORT': LOCAL_PORT
        }
    return credentials


'''
user = 'lcalleja2'
password = '3059891242'
host = '127.0.0.1' #tailscale IP address 100.102.223.21 for the radish server/droplet
port = 5433
database = 'membership_ard'
def get_connection():
	return sqlalchemy.create_engine(
		url="mysql+pymysql://{0}:{1}@{2}:{3}/{4}".format(
			user, password, host, port, database
		)
	)
'''
def inject_data(filepath, table_name, yaml_path=None):
    # Create SQLAlchemy engine
    credentials = identify_credentials(yaml_path)
    user = 'lcalleja2'
    password = '3059891242'
    host = credentials['HOST'] 
    port = credentials['PORT']
    database = credentials['DATABASE']
    engine = create_engine(
        url=f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    )
    
    return engine


# ══ APPENDED CODE ════════════════════════════════════════════════════════════
# Data layer: credentials -> engine -> table write. This module knows about SQL
# and nothing about SSH. The tunnel's local port arrives as a plain int
# argument, which is what keeps these functions testable against a local or
# in-memory database with no SSH involved.

from pathlib import Path
from typing import Any

from .config import find_env_file, load_env_file, load_yaml_file

DB_KEYS = ("DB_USER", "DB_PASSWORD", "HOST", "PORT", "DATABASE")


def db_config(yaml_path: str | None = None, env_path: str | Path | None = None) -> dict[str, Any]:
    """Collect the full database credential set from .env or a YAML file.

    Parameters
    ----------
    yaml_path
        When None, read the .env located by config.find_env_file(). Otherwise
        read the same five keys from that YAML file — the CLI's --yaml-path.
    env_path
        An explicit .env location, bypassing the upward search entirely — the
        CLI's --env-path.

    Returns all of DB_KEYS, and raises if any is missing or blank, so a typo in
    the secrets file surfaces here rather than as an opaque connection error.
    Consumed by build_engine() below.
    """
    if yaml_path is None:
        load_env_file(find_env_file(env_path))
        config = {key: os.getenv(key) for key in DB_KEYS}
    else:
        config = load_yaml_file(yaml_path, DB_KEYS)

    missing = [key for key, value in config.items() if value in (None, "")]
    if missing:
        raise RuntimeError(f"Missing DB credentials: {', '.join(missing)}")
    return config


def read_source(filepath: str) -> pd.DataFrame:
    """Load the source file into a DataFrame, dispatching on file extension.

    Called by cli.py *before* the tunnel is opened, so a bad path or a malformed
    CSV fails in milliseconds instead of after an SSH handshake.
    """
    try: 
        suffix = Path(filepath).suffix.lower()
    except FileNotFoundError:
        #raising an error will stop execution
        raise FileNotFoundError(f"File not found: {filepath}")
    if suffix == ".csv":
        return pd.read_csv(filepath)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(filepath)
    raise ValueError(
        f"Unsupported source file type '{suffix}' — expected .csv, .xlsx or .xls"
    )


def build_engine(
    port: int | None = None,
    yaml_path: str | None = None,
    env_path: str | Path | None = None,
    **engine_kwargs,
):
    """Build a SQLAlchemy engine aimed at the tunnel's local port.

    Parameters
    ----------
    port
        The live port from `establish_ssh.db_tunnel()` (tunnel.local_bind_port).
        Falls back to the static PORT in the secrets file when omitted, which is
        only correct if you already have a tunnel open on that fixed port.
    yaml_path, env_path
        Forwarded to db_config().
    **engine_kwargs
        Passed to create_engine(); e.g. poolclass=NullPool to avoid pooled
        sockets outliving the tunnel, or echo=True while debugging.

    The engine connects lazily, so it is only usable while the tunnel is open.
    Build it inside the `with db_tunnel()` block and dispose of it before the
    block exits.
    """
    config = db_config(yaml_path, env_path)
    url = (
        f"mysql+pymysql://{config['DB_USER']}:{config['DB_PASSWORD']}"
        f"@{config['HOST']}:{port or config['PORT']}/{config['DATABASE']}"
    )
    return create_engine(url, **engine_kwargs)


def write_table(df: pd.DataFrame, table_name: str, con, if_exists: str = "replace") -> int:
    """Write a DataFrame to table_name over an existing connection.

    Parameters
    ----------
    con
        An open SQLAlchemy Connection or Engine. Taking the connection as an
        argument (rather than building one here) is what keeps this function
        independent of the tunnel; cli.py passes `engine.begin()`'s connection
        so the write runs in a transaction and rolls back on failure.
    if_exists
        'replace' drops and recreates the table, letting pandas re-infer column
        types — any indexes or constraints on the old table are lost. Use
        'append' to preserve the existing schema.

    Returns the number of rows written, which cli.py reports to the user.

    This is the appended counterpart to the original inject_data() above; the
    two are meant to be consolidated once you settle on a name.
    """
    df.to_sql(table_name, con=con, if_exists=if_exists, index=False)
    return len(df)
