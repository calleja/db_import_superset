"""Covers the four ways a secrets file can fail to load.

load_dotenv() answers False for all of them, which is what made the original
"Could not load environment file" message unable to say which one happened.
"""

import pytest

from db_injector.config import load_env_file, load_yaml_file


def test_missing_file_lists_the_directory_contents(tmp_path):
    # The Windows case: Explorer or Notepad appended .txt without showing it.
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / ".env.txt").write_text("VM_URL=1.2.3.4\n")
    with pytest.raises(FileNotFoundError, match=r"\.env\.txt"):
        load_env_file(secrets / ".env")


def test_missing_directory_is_reported_as_such(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing or unreadable"):
        load_env_file(tmp_path / "secrets" / ".env")


@pytest.mark.parametrize(
    "content", ["", "# only a comment\n", "VM_URL: 1.2.3.4\n"], ids=["empty", "comments", "yaml"]
)
def test_unparseable_file_is_distinguished_from_a_missing_one(tmp_path, content):
    env = tmp_path / ".env"
    env.write_text(content)
    with pytest.raises(RuntimeError, match="yielded no variables"):
        load_env_file(env)


def test_yaml_without_a_space_after_the_colon_is_rejected(tmp_path):
    # 'KEY:value' is a plain scalar, so safe_load returns a str and .get() blows up.
    bad = tmp_path / "secrets.yaml"
    bad.write_text("VM_URL:1.2.3.4\nVM_USER:bob\n")
    with pytest.raises(RuntimeError, match="space after each colon"):
        load_yaml_file(bad, ("VM_URL",))


def test_yaml_returns_none_for_absent_keys(tmp_path):
    good = tmp_path / "secrets.yaml"
    good.write_text("VM_URL: 1.2.3.4\n")
    assert load_yaml_file(good, ("VM_URL", "VM_USER")) == {"VM_URL": "1.2.3.4", "VM_USER": None}
