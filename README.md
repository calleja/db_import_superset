Direct csv injections into tables you name into the mysql db. Once there, you can pull up the table in Superset and build dashboards on it.

Effectively, you'll be making a copy of the package directory in your own machine, then "building" up some of the configs (handled by uv), then running it.

### Note: do not clone into iCloud Drive, Dropbox, or pCloud on your local; this messes with the path discovery within uv. A safe spot is within your Home directory, away from 'Documents'
### On Windows the same applies to OneDrive, which by default redirects 'Documents' into the synced folder. Clone to something like C:\dev\db_injector instead.

Installing uv: https://docs.astral.sh/uv/getting-started/installation/

Overview of steps:
1. git clone git@github.com:<you>/db_injector.git
2. cd db_injector
3. uv sync    # builds .venv from uv.lock, installs the CLI
4. obtain secrets out of band, place at secrets/.env
5. uv run db-injector data.csv my_table --if-exists replace

git clone

run `uv sync`

## Secrets and .env/.yaml
'secrets' is the directory and .env or secrets.yaml is the file. This file contains the credentials to 1) ssh into the droplet and 2) access the mysql db

NOTE: ssh will also rely on public/private keys that you store on your local. SSH tech wil automatically surface those credentials for authentication along with the credentials in 1)

place secrets either as a .env or .yaml file; 3 options:
  - secrets/.env directly on the path or project directory
  - a .yaml file in your filesystem which must be explicitly cited with --yaml-path
  - as environmental variables
  - (or point at a .env anywhere with --env-path, which skips the directory search)
You can track how this is handled on config.py

The .env needs `KEY=value` lines. The .yaml needs `KEY: value` — with a space
after the colon, or YAML reads the whole file as one string.

### Windows: the .env filename
File Explorer hides known extensions and Notepad appends `.txt` on save, so a
file you believe is `.env` is often really `.env.txt`, and downloads of a dotfile
often arrive as `env` or `_env`. Check the real names from PowerShell, which
never renames anything:

    Get-ChildItem -Force .\secrets | Select-Object Name, Length
    uv run python -c "from dotenv import dotenv_values; print(list(dotenv_values(r'secrets\.env')))"

The second command must list all nine keys. If it prints `[]` the file is empty
or not in `KEY=value` form. Writing the file from Windows PowerShell 5.1 with
`-Encoding utf8` adds a BOM that corrupts the first key — use `-Encoding ascii`
there, or `utf8NoBOM` on PowerShell 7.

Setting the env var on Windows is `$env:DB_INJECTOR_ENV = "C:\path\to\.env"`,
not `export`.


## Commands
uv run db-injector '/Users/casita/Downloads/2026 Spoilage - Sheet1.csv' spoilage_v1 --if-exists replace

command example:

command options:

command help:

### Warning on SSH connection
The ssh_config_file defaults to '~/.ssh/config', so any Host 67.207.80.236 stanza on the user's machine can silently substitute a different username, port, identity file, or proxy.

Server-side, this only works while the droplet's sshd_config has PasswordAuthentication yes. Standard hardening turns that off, and the moment someone does, the package breaks with an authentication error rather than anything descriptive. This can be checked at /etc/ssh/sshd_config on the server.

Option for SSH password:
I can switch over to ssh keypair and away from a password approach by:
1. have the user create an ssh public/private key and add it to the server's 
2. swap the parameters on establish_ssh.db_tunnel() SSHTunnelForwarder:
ssh_password=cfg["password"] for ssh_pkey='~/.ssh/db_injector_droplet'
