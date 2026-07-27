"""Unit test for the request_handlers re-export module.

request_handlers.py aggregates the request command handlers from their focused
modules for backward-compatible imports. This test pins that public surface so a
handler cannot be dropped from the aggregate without a failing test.
"""

from __future__ import annotations

import pytest

from orb.application.commands import request_handlers


@pytest.mark.unit
def test_all_declared_handlers_are_exported():
    expected = {
        "CreateMachineRequestHandler",
        "CreateReturnRequestHandler",
        "UpdateRequestStatusHandler",
        "CancelRequestHandler",
        "CompleteRequestHandler",
        "PopulateMachineIdsHandler",
        "SyncRequestHandler",
    }
    assert set(request_handlers.__all__) == expected


@pytest.mark.unit
def test_exported_names_resolve_to_handler_classes():
    for name in request_handlers.__all__:
        obj = getattr(request_handlers, name)
        assert isinstance(obj, type)
        assert name.endswith("Handler")
