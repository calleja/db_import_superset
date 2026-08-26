from db_injector import establish_ssh
from pathlib import Path
from dotenv import load_dotenv

#testing the filepath of the .env file
def test_env_path():
    print(f' this is the parent: {Path(__file__).resolve().parents[1]}')
    env_path = Path(__file__).resolve().parents[1] / "secrets" / ".env"
    assert env_path.exists()
    assert env_path.is_file()

#after testing the filepath, check that load_dotenv loads it
def test_find_keys():
    env_path = Path(__file__).resolve().parents[1] / "secrets" / ".env"
    assert True == load_dotenv(env_path)
    #required = ("VM_URL", "VM_USER", "VM_PASSWORD")
    

# ══ APPENDED TESTS ═══════════════════════════════════════════════════════════
# SSHTunnelForwarder is swapped for a fake, so none of these touch the network.

import pytest


class FakeForwarder:
    """Stands in for SSHTunnelForwarder: records its kwargs, tracks teardown."""

    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.local_bind_port = 49152  # pretend the OS handed us this port
        self.closed = False
        FakeForwarder.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.closed = True
        return False  # never swallow exceptions


@pytest.fixture
def fake_forwarder(monkeypatch):
    FakeForwarder.instances = []
    monkeypatch.setattr(establish_ssh, "SSHTunnelForwarder", FakeForwarder)
    return FakeForwarder


def test_ssh_config_returns_credentials():
    config = establish_ssh.ssh_config()
    assert set(config) == {"host", "user", "password"}
    assert all(config.values())


def test_ssh_config_rejects_blank_credential(monkeypatch):
    # load_dotenv does not override existing vars, so a blank VM_URL survives.
    monkeypatch.setenv("VM_URL", "")
    with pytest.raises(RuntimeError, match="VM_URL"):
        establish_ssh.ssh_config()


def test_db_tunnel_yields_forwarder_and_closes_it(fake_forwarder):
    with establish_ssh.db_tunnel() as tunnel:
        assert tunnel.local_bind_port == 49152
        assert not tunnel.closed
    assert tunnel.closed


def test_db_tunnel_closes_when_body_raises(fake_forwarder):
    with pytest.raises(ValueError):
        with establish_ssh.db_tunnel() as tunnel:
            raise ValueError("boom")
    assert tunnel.closed


def test_db_tunnel_requests_os_assigned_local_port(fake_forwarder):
    with establish_ssh.db_tunnel():
        pass
    kwargs = fake_forwarder.instances[0].kwargs
    assert kwargs["local_bind_address"] == ("127.0.0.1", 0)
    assert kwargs["remote_bind_address"] == ("localhost", 3306)


