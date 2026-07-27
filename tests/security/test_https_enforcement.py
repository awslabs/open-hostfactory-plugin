"""HTTPS enforcement wiring in create_fastapi_app: redirect + HSTS gating."""

import pytest
from fastapi.testclient import TestClient

from orb.api.server import create_fastapi_app
from orb.config.schemas.server_schema import ServerConfig


def _build_config(require_https: bool, hsts_max_age: int = 31536000) -> ServerConfig:
    return ServerConfig(  # type: ignore[call-arg]
        require_https=require_https,
        hsts_max_age=hsts_max_age,
    )


class TestHTTPSRedirect:
    """When require_https is True, HTTP requests must be redirected to HTTPS."""

    def test_http_request_redirects_to_https_307(self):
        app = create_fastapi_app(_build_config(require_https=True))
        # base_url must be an http:// origin so the redirect middleware triggers;
        # 'testserver' is in the default trusted_hosts allowlist.
        client = TestClient(app, base_url="http://testserver")
        resp = client.get("/health", follow_redirects=False)
        assert resp.status_code == 307
        assert resp.headers["location"].startswith("https://")

    def test_https_request_not_redirected(self):
        app = create_fastapi_app(_build_config(require_https=True))
        client = TestClient(app, base_url="https://testserver")
        resp = client.get("/health", follow_redirects=False)
        assert resp.status_code != 307
        assert resp.headers.get("strict-transport-security", "").startswith("max-age=")

    def test_no_redirect_when_require_https_false(self):
        app = create_fastapi_app(_build_config(require_https=False))
        client = TestClient(app, base_url="http://testserver")
        resp = client.get("/health", follow_redirects=False)
        assert resp.status_code != 307
        # HSTS must not be advertised for an HTTP-only origin.
        assert "strict-transport-security" not in resp.headers


class TestHSTSMaxAgeWiring:
    """The configured hsts_max_age must reach the emitted HSTS header."""

    def test_custom_max_age_reaches_header(self):
        app = create_fastapi_app(_build_config(require_https=True, hsts_max_age=120))
        client = TestClient(app, base_url="https://testserver")
        resp = client.get("/health", follow_redirects=False)
        assert "max-age=120" in resp.headers.get("strict-transport-security", "")


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
