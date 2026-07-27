"""Unit tests for canonical authorization-claim extraction.

Covers :func:`extract_authz_claims` and the normalisation contract that every
JWT-based strategy relies on to avoid substring-matching authorization
bypasses (a scalar ``roles`` claim must never be stored as a bare string).
"""

from __future__ import annotations

import pytest

from orb.infrastructure.auth.claims import _normalise_claim_list, extract_authz_claims

pytestmark = pytest.mark.unit


class TestNormaliseClaimList:
    def test_none_yields_empty_list(self):
        assert _normalise_claim_list(None) == []

    def test_scalar_string_becomes_single_element_list(self):
        # Critical: a bare string must never be iterated char-by-char, and must
        # never be stored where ``in`` would do substring matching.
        assert _normalise_claim_list("admin") == ["admin"]

    def test_list_of_strings_preserved(self):
        assert _normalise_claim_list(["admin", "operator"]) == ["admin", "operator"]

    def test_tuple_is_accepted(self):
        assert _normalise_claim_list(("admin", "viewer")) == ["admin", "viewer"]

    def test_non_string_entries_dropped(self):
        assert _normalise_claim_list(["admin", 1, None, {"x": 1}, "viewer"]) == [
            "admin",
            "viewer",
        ]

    def test_entries_are_stripped(self):
        assert _normalise_claim_list(["  admin  ", "\toperator\n"]) == ["admin", "operator"]

    def test_empty_and_whitespace_entries_dropped(self):
        assert _normalise_claim_list(["", "   ", "admin"]) == ["admin"]

    def test_duplicates_removed_order_preserved(self):
        assert _normalise_claim_list(["admin", "viewer", "admin"]) == ["admin", "viewer"]

    def test_dict_yields_empty_list(self):
        assert _normalise_claim_list({"roles": "admin"}) == []

    def test_int_yields_empty_list(self):
        assert _normalise_claim_list(42) == []


class TestExtractAuthzClaims:
    def test_missing_both_claims(self):
        roles, perms = extract_authz_claims({"sub": "u1"})
        assert roles == []
        assert perms == []

    def test_both_claims_present(self):
        roles, perms = extract_authz_claims(
            {"roles": ["operator"], "permissions": ["templates.read"]}
        )
        assert roles == ["operator"]
        assert perms == ["templates.read"]

    def test_scalar_role_claim_does_not_enable_substring_bypass(self):
        # A malicious token with roles="administrator" must not satisfy an
        # ``in`` check for the substring "admin".
        roles, _ = extract_authz_claims({"roles": "administrator"})
        assert roles == ["administrator"]
        assert "admin" not in roles

    def test_malformed_permissions_type_fails_closed(self):
        roles, perms = extract_authz_claims({"roles": ["viewer"], "permissions": 123})
        assert roles == ["viewer"]
        assert perms == []
