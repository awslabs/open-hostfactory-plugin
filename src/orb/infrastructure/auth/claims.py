"""Canonical extraction of authorization claims from token payloads.

This module defines the single, canonical way ORB reads authorization claims
(roles and permissions) out of a decoded token payload.  Every JWT-based
authentication strategy MUST route its claim reads through
:func:`extract_authz_claims` so that role/permission handling is identical
regardless of which strategy validated the token.

Canonical claim names
---------------------
- ``roles``: the principal's role names.  Expanded to ORB roles by the
  strategy (bearer tokens forward them verbatim; Cognito maps
  ``cognito:groups`` first).
- ``permissions``: explicitly-granted, two-segment permission strings
  (e.g. ``"templates.read"``).  Unioned with any role-derived permissions
  by the enforcement layer.

Both claims are OPTIONAL.  A missing claim yields an empty list.

Security normalisation
----------------------
Token payloads are attacker-influenced input.  A claim that is expected to be
a list may arrive as a bare string (``"roles": "admin"``), a list containing
non-string entries, or an entirely wrong type.  Storing a bare string in
``AuthResult.user_roles`` is dangerous: ``AuthResult.has_role`` and
``has_permission`` use the ``in`` operator, which performs *substring* matching
on a string (``"adm" in "admin"`` is ``True``).  That is a fail-open
authorization bypass.

:func:`extract_authz_claims` therefore:

- coerces a scalar string claim into a single-element list,
- drops any non-string / empty entries,
- strips surrounding whitespace,
- de-duplicates while preserving first-seen order,
- returns an empty list for any other (unexpected) type.
"""

from __future__ import annotations

from typing import Any


def _normalise_claim_list(value: Any) -> list[str]:
    """Coerce a raw claim value into a clean list of non-empty role/permission strings.

    See the module docstring for the security rationale.  This never raises:
    unexpected types collapse to an empty list (fail-closed).

    Args:
        value: The raw claim value read from a decoded token payload.

    Returns:
        A de-duplicated, order-preserving list of stripped, non-empty strings.
    """
    # A bare string is wrapped so it is never treated as an iterable of
    # characters and never stored where substring matching could apply.
    if isinstance(value, str):
        candidates: list[Any] = [value]
    elif isinstance(value, (list, tuple)):
        candidates = list(value)
    else:
        # dict, int, None, or anything else → no claims.
        return []

    seen: set[str] = set()
    result: list[str] = []
    for item in candidates:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def extract_authz_claims(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Extract normalised ``(roles, permissions)`` from a decoded token payload.

    This is the canonical claim-extraction seam shared by all JWT-based
    authentication strategies.  It reads the ``roles`` and ``permissions``
    claims and normalises each per :func:`_normalise_claim_list`.

    Args:
        payload: Decoded (already signature-verified) JWT claims.

    Returns:
        A ``(roles, permissions)`` tuple of clean string lists.  Either may be
        empty when the corresponding claim is absent or malformed.
    """
    roles = _normalise_claim_list(payload.get("roles"))
    permissions = _normalise_claim_list(payload.get("permissions"))
    return roles, permissions
