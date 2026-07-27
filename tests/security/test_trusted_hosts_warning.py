"""Startup warning when Host-header protection is effectively disabled."""

import logging

import pytest

from orb.api.server import create_fastapi_app
from orb.config.schemas.server_schema import ServerConfig

_WARNING_MARKER = "Host-header protection is effectively DISABLED"


def _build_config(trusted_hosts: list[str]) -> ServerConfig:
    return ServerConfig(trusted_hosts=trusted_hosts)  # type: ignore[call-arg]


class TestTrustedHostsStartupWarning:
    """create_fastapi_app must warn when trusted_hosts disables host protection."""

    def test_empty_trusted_hosts_emits_warning(self, caplog):
        """An empty allowlist leaves the Host header unchecked — warn about it."""
        with caplog.at_level(logging.WARNING, logger="orb.api.server"):
            create_fastapi_app(_build_config([]))

        matches = [r for r in caplog.records if _WARNING_MARKER in r.getMessage()]
        assert matches, "expected a host-protection warning for empty trusted_hosts"
        assert matches[0].levelno == logging.WARNING
        assert "empty" in matches[0].getMessage()

    def test_wildcard_trusted_hosts_emits_warning(self, caplog):
        """A '*' entry accepts any Host header — warn about it."""
        with caplog.at_level(logging.WARNING, logger="orb.api.server"):
            create_fastapi_app(_build_config(["*"]))

        matches = [r for r in caplog.records if _WARNING_MARKER in r.getMessage()]
        assert matches, "expected a host-protection warning for wildcard trusted_hosts"
        assert matches[0].levelno == logging.WARNING
        assert "['*']" in matches[0].getMessage()

    def test_wildcard_among_other_hosts_emits_warning(self, caplog):
        """A '*' anywhere in the list still disables protection."""
        with caplog.at_level(logging.WARNING, logger="orb.api.server"):
            create_fastapi_app(_build_config(["example.com", "*"]))

        matches = [r for r in caplog.records if _WARNING_MARKER in r.getMessage()]
        assert matches, "expected a host-protection warning when '*' is present"

    def test_explicit_hosts_do_not_emit_warning(self, caplog):
        """A concrete allowlist keeps protection on — no warning."""
        with caplog.at_level(logging.WARNING, logger="orb.api.server"):
            create_fastapi_app(_build_config(["localhost", "127.0.0.1", "::1"]))

        matches = [r for r in caplog.records if _WARNING_MARKER in r.getMessage()]
        assert not matches, "did not expect a host-protection warning for an explicit list"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
