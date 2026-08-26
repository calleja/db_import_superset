Direct csv injections into tables you name into the mysql db. Once there, you can pull up the table in Superset and build dashboards on it.

Effectively, you'll be making a copy of the package directory in your own machine, then "building" up some of the configs (handled by uv), then running it.

### Note: do not clone into iCloud Drive, Dropbox, or pCloud on your local; this messes with the path discovery within uv. A safe spot is within your Home directory, away from 'Documents'

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
  - a .yaml file in your filesystem which must be explicitly cited 
  - as environmental variables 
You can track how this is handled on config.py


## Commands
uv run db-injector '/Users/casita/Downloads/2026 Spoilage - Sheet1.csv' test_spoilage --if-exists replace

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
