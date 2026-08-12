"""Regressions for environment variables that arrive set-but-empty.

docker-compose passes several variables through unconditionally (`VAR=${VAR}`),
so a variable the operator never defined reaches the container as "" rather
than being absent. `os.environ.get` only falls back to its default for *absent*
variables, so any config value that must not be empty has to normalize the
empty string itself.

CI runs pytest without these variables set at all, which exercises the
absent-variable path and hides the empty-string one — hence these tests patch
the environment explicitly instead of relying on ambient state.
"""

import importlib
import os

import pytest

import app.config

# Variables docker-compose forwards as a bare `${VAR}` (no `:-default`, which
# would substitute for the empty string too), paired with the value the config
# must produce when they arrive empty. Everything else compose forwards is
# either given a compose-level default or read without a Python-side default,
# where "" is falsy and behaves like the absent value.
EMPTY_ENV_DEFAULTS = [
    ("SERVER_NAME", None),
    ("APPLICATION_ROOT", "/"),
    ("PREFERRED_URL_SCHEME", "https"),
]


@pytest.fixture
def reload_config(monkeypatch):
    """Reload app.config with a patched environment, then restore it."""

    def _reload(**env: str | None):
        for name, value in env.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        return importlib.reload(app.config)

    yield _reload

    # Undo the patched environment before restoring the module, so later tests
    # see the config the session-scoped app fixture was built with.
    monkeypatch.undo()
    importlib.reload(app.config)


@pytest.mark.parametrize(("name", "expected"), EMPTY_ENV_DEFAULTS)
@pytest.mark.parametrize("value", ["", None])
def test_empty_env_var_falls_back_to_default(reload_config, name, expected, value):
    """An empty variable must resolve the same way an absent one does."""
    assert getattr(reload_config(**{name: value}).Config, name) == expected


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SERVER_NAME", "cinetag.example"),
        ("APPLICATION_ROOT", "/cinetagit"),
        ("PREFERRED_URL_SCHEME", "http"),
    ],
)
def test_env_var_passes_through_when_set(reload_config, name, value):
    """Normalizing the empty string must not clobber a real value."""
    assert getattr(reload_config(**{name: value}).Config, name) == value


def test_mail_default_sender_name_is_loaded():
    """send_email() reads MAIL_DEFAULT_SENDER_NAME off the Flask config, so the
    variable compose forwards has to actually be loaded into it."""
    assert hasattr(app.config.Config, "MAIL_DEFAULT_SENDER_NAME")


def test_compose_forwards_the_audited_vars_unconditionally():
    """Guards the premise of the tests above: if compose ever gains a
    `:-default` for one of these, or stops forwarding it, the empty-string case
    is no longer reachable that way and the pairing should be re-audited."""
    compose = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docker-compose.yml",
    )
    with open(compose, encoding="utf-8") as fh:
        content = fh.read()
    for name, _ in EMPTY_ENV_DEFAULTS:
        assert f"{name}=${{{name}}}" in content
