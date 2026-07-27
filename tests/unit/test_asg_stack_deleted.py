"""Verify the dead ASG query stack has been fully removed."""

import importlib

import pytest


def test_asg_query_port_not_importable():
    """ASGQueryPort should not exist in domain ports."""
    with pytest.raises(ImportError):
        importlib.import_module("orb.domain.base.ports.asg_query_port")


def test_asg_query_adapter_not_importable():
    """ASGQueryAdapter should not exist in infrastructure adapters."""
    with pytest.raises(ImportError):
        importlib.import_module("orb.infrastructure.adapters.asg_query_adapter")


def test_asg_metadata_service_not_importable():
    """ASGMetadataService should not exist in application services."""
    with pytest.raises(ImportError):
        importlib.import_module("orb.application.services.asg_metadata_service")


def test_sync_request_handler_has_no_asg_query_port_param():
    """SyncRequestHandler should not require asg_query_port."""
    import inspect

    from orb.application.commands.request_sync_handlers import SyncRequestHandler

    sig = inspect.signature(SyncRequestHandler.__init__)
    assert "asg_query_port" not in sig.parameters, (
        "SyncRequestHandler still has asg_query_port parameter"
    )
