import socket
import pytest
from sshtunnel import BaseSSHTunnelForwarderError
from db_injector import establish_ssh

pytestmark = pytest.mark.integration


def droplet_reachable(timeout=3) -> bool:
    """Is the droplet's sshd answering? Skip rather than fail when offline."""
    try:
        config = establish_ssh.ssh_config()
        with socket.create_connection((config["host"], 22), timeout):
            return True
    except Exception:
        return False


def test_tunnel_opens_forwards_and_closes():
    if not droplet_reachable():
        pytest.skip("droplet unreachable or credentials missing")

    with establish_ssh.db_tunnel() as tunnel:
        # 1. the SSH transport itself came up
        assert tunnel.is_active

        # 2. the forward is actually established, not just requested
        tunnel.check_tunnels()
        assert all(tunnel.tunnel_is_up.values()), tunnel.tunnel_is_up

        # Capture now: this property raises once the transport is torn down.
        port = tunnel.local_bind_port
        assert port > 0

        # 3. prove traffic reaches MySQL on the far side. The server sends a
        #    greeting packet on connect: 4-byte header, then protocol version 10.
        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            greeting = sock.recv(64)
        assert greeting[4] == 10, f"not a MySQL handshake: {greeting[:16]!r}"

    # 4. teardown: transport down, local port no longer accepting
    assert not tunnel.is_active
    with pytest.raises(BaseSSHTunnelForwarderError):
        tunnel.local_bind_port
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=2)