"""Tests for AuthAuditLogger — structured security-event audit logging."""

import json
import logging

import pytest

from orb.infrastructure.logging.logger import (
    AuthAuditLogger,
    JsonFormatter,
    setup_audit_logger,
)


@pytest.mark.unit
class TestAuthAuditLogger:
    """The auth audit logger emits structured records for all 5 event types."""

    def test_uses_orb_audit_logger_name(self) -> None:
        """Audit records must go to the dedicated 'orb.audit' logger for routing."""
        al = AuthAuditLogger()
        assert al.logger.name == "orb.audit"

    def _capture(self, caplog, fn) -> dict:
        """Run *fn* and return the single emitted 'orb.audit' record's fields.

        The 'orb.audit' logger may have ``propagate=False`` (set by
        ``setup_audit_logger``), so attach caplog's handler directly to it
        rather than relying on propagation to the root logger.  The record's
        ``__dict__`` is returned so the structured ``extra`` fields can be read
        with dict access (they are dynamic attributes not known to type checkers).
        """
        audit_log = logging.getLogger("orb.audit")
        prev_level = audit_log.level
        prev_propagate = audit_log.propagate
        audit_log.addHandler(caplog.handler)
        audit_log.setLevel(logging.INFO)
        # Disable propagation so the record is not also captured via the root
        # logger's caplog handler (which would produce duplicate records).
        audit_log.propagate = False
        try:
            fn()
        finally:
            audit_log.removeHandler(caplog.handler)
            audit_log.setLevel(prev_level)
            audit_log.propagate = prev_propagate
        records = [r for r in caplog.records if r.name == "orb.audit"]
        assert len(records) == 1
        return dict(records[0].__dict__)

    def test_auth_success_fields(self, caplog) -> None:
        al = AuthAuditLogger()
        rec = self._capture(
            caplog,
            lambda: al.log_auth_success(
                user_id="alice",
                client_ip="10.0.0.1",
                path="/api/v1/machines",
                method="POST",
                auth_strategy="enhanced_bearer_token",
            ),
        )
        assert rec["event_type"] == "AUTH_SUCCESS"
        assert rec["user_id"] == "alice"
        assert rec["client_ip"] == "10.0.0.1"
        assert rec["path"] == "/api/v1/machines"
        assert rec["method"] == "POST"
        assert rec["auth_strategy"] == "enhanced_bearer_token"
        assert rec["timestamp"]  # ISO timestamp present
        assert rec["levelno"] == logging.INFO

    def test_anonymous_user_defaulted(self, caplog) -> None:
        """A missing user_id is recorded as 'anonymous', never None."""
        al = AuthAuditLogger()
        rec = self._capture(
            caplog,
            lambda: al.log_auth_failure(
                client_ip=None,
                path="/api/v1/machines",
                method="POST",
                reason="invalid",
            ),
        )
        assert rec["event_type"] == "AUTH_FAILURE"
        assert rec["user_id"] == "anonymous"
        assert rec["client_ip"] == "unknown"
        assert rec["reason"] == "invalid"

    def test_auth_failure_reason_has_no_token(self, caplog) -> None:
        """Failure reason is a generic classification, never credential content."""
        al = AuthAuditLogger()
        rec = self._capture(
            caplog,
            lambda: al.log_auth_failure(
                client_ip="1.2.3.4",
                path="/x",
                method="GET",
                reason="expired",
            ),
        )
        assert rec["reason"] == "expired"

    def test_auth_expired_event(self, caplog) -> None:
        al = AuthAuditLogger()
        rec = self._capture(
            caplog,
            lambda: al.log_auth_expired(
                client_ip="1.2.3.4",
                path="/x",
                method="GET",
                user_id="bob",
            ),
        )
        assert rec["event_type"] == "AUTH_EXPIRED"
        assert rec["user_id"] == "bob"

    def test_token_revoked_event(self, caplog) -> None:
        al = AuthAuditLogger()
        rec = self._capture(
            caplog,
            lambda: al.log_token_revoked(
                user_id="carol",
                auth_strategy="enhanced_bearer_token",
            ),
        )
        assert rec["event_type"] == "TOKEN_REVOKED"
        assert rec["user_id"] == "carol"

    def test_permission_denied_event(self, caplog) -> None:
        al = AuthAuditLogger()
        rec = self._capture(
            caplog,
            lambda: al.log_permission_denied(
                user_id="dave",
                client_ip="1.2.3.4",
                path="/api/v1/admin",
                method="POST",
            ),
        )
        assert rec["event_type"] == "PERMISSION_DENIED"
        assert rec["user_id"] == "dave"
        assert rec["path"] == "/api/v1/admin"


@pytest.mark.unit
class TestAuditJsonSerialization:
    """The JSON sink must serialize the structured security fields.

    Guards against the audit trail becoming non-attributable: security fields
    passed via stdlib ``extra=`` land as top-level LogRecord attributes, and the
    JSON formatter must surface them rather than dropping them.  Formatting goes
    THROUGH ``JsonFormatter.format`` (not ``record.__dict__``) so the assertion
    reflects exactly what is written to the audit file / SIEM.
    """

    def _format_event(self, fn) -> dict:
        """Emit one audit event via *fn* and return the serialized JSON as a dict."""
        formatter = JsonFormatter(log_type="audit")
        captured: dict[str, logging.LogRecord] = {}

        class _Grab(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured["record"] = record

        audit_log = logging.getLogger("orb.audit")
        prev_level = audit_log.level
        prev_propagate = audit_log.propagate
        handler = _Grab()
        audit_log.addHandler(handler)
        audit_log.setLevel(logging.INFO)
        audit_log.propagate = False
        try:
            fn()
        finally:
            audit_log.removeHandler(handler)
            audit_log.setLevel(prev_level)
            audit_log.propagate = prev_propagate
        assert "record" in captured, "no audit record was emitted"
        return json.loads(formatter.format(captured["record"]))

    def test_auth_failure_security_fields_present_in_json(self) -> None:
        """AUTH_FAILURE serialized JSON must carry the attributable security fields."""
        al = AuthAuditLogger()
        payload = self._format_event(
            lambda: al.log_auth_failure(
                user_id="alice",
                client_ip="10.0.0.7",
                path="/api/v1/machines",
                method="POST",
                reason="invalid_token",
                auth_strategy="enhanced_bearer_token",
            )
        )
        # These fields would all be DROPPED by a formatter that only merges a
        # non-existent ``record.extra`` sub-dict.
        assert payload["event_type"] == "AUTH_FAILURE"
        assert payload["client_ip"] == "10.0.0.7"
        assert payload["user_id"] == "alice"
        assert payload["reason"] == "invalid_token"
        assert payload["path"] == "/api/v1/machines"
        assert payload["method"] == "POST"
        assert payload["auth_strategy"] == "enhanced_bearer_token"

    def test_reason_is_status_name_not_token_content(self) -> None:
        """The serialized reason is a generic classification, never credential material."""
        al = AuthAuditLogger()
        payload = self._format_event(
            lambda: al.log_auth_failure(
                client_ip="1.2.3.4",
                path="/x",
                method="GET",
                reason="expired",
            )
        )
        assert payload["reason"] == "expired"


@pytest.mark.unit
class TestAuditLevelIndependence:
    """Audit events must emit regardless of the application's root log level."""

    def test_audit_events_emit_when_root_level_is_warning(self) -> None:
        """With root=WARNING, an INFO audit event must still reach the sink."""
        root = logging.getLogger()
        audit_log = logging.getLogger("orb.audit")
        prev_root_level = root.level
        prev_audit_level = audit_log.level
        prev_handlers = list(audit_log.handlers)
        prev_propagate = audit_log.propagate

        received: list[logging.LogRecord] = []

        class _Grab(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                received.append(record)

        try:
            # Simulate a production config where the app log level filters INFO.
            root.setLevel(logging.WARNING)
            # Reset the audit logger so setup_audit_logger performs its wiring.
            for h in prev_handlers:
                audit_log.removeHandler(h)
            audit_log.setLevel(logging.NOTSET)

            setup_audit_logger(None)
            # setEffectiveLevel must be INFO despite root being WARNING.
            assert audit_log.getEffectiveLevel() == logging.INFO

            audit_log.addHandler(_Grab())
            AuthAuditLogger().log_auth_failure(
                client_ip="1.2.3.4",
                path="/x",
                method="GET",
                reason="invalid",
            )
            assert len(received) == 1, "audit event was silenced when root level > INFO"
            assert received[0].levelno == logging.INFO
        finally:
            root.setLevel(prev_root_level)
            for h in list(audit_log.handlers):
                audit_log.removeHandler(h)
            for h in prev_handlers:
                audit_log.addHandler(h)
            audit_log.setLevel(prev_audit_level)
            audit_log.propagate = prev_propagate
