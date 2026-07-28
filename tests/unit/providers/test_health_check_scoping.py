"""Provider health checks register only for the default/active provider.

A connectivity check must be registered for the default/active provider
instance only — never for a secondary enabled instance.  An unreachable
secondary provider must not even register a check, so it cannot drag the
overall status down.

The default/active instance is determined the same way provider
selection does it: ``provider_config.default_provider_instance`` when set,
otherwise the first enabled instance.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from orb.providers.health_scoping import is_default_provider_instance


def _provider(name: str, ptype: str, enabled: bool = True):
    p = MagicMock()
    p.name = name
    p.type = ptype
    p.enabled = enabled
    return p


def _provider_config(providers, default_instance=None):
    cfg = MagicMock()
    cfg.providers = providers
    cfg.default_provider_instance = default_instance
    return cfg


@pytest.mark.unit
class TestIsDefaultProviderInstance:
    def test_explicit_default_instance_matches(self) -> None:
        providers = [
            _provider("aws-main", "aws"),
            _provider("k8s_ms-karpenter", "k8s"),
        ]
        cfg = _provider_config(providers, default_instance="aws-main")
        assert is_default_provider_instance("aws-main", cfg) is True

    def test_secondary_instance_is_not_default(self) -> None:
        providers = [
            _provider("aws-main", "aws"),
            _provider("k8s_ms-karpenter", "k8s"),
        ]
        cfg = _provider_config(providers, default_instance="aws-main")
        assert is_default_provider_instance("k8s_ms-karpenter", cfg) is False

    def test_first_enabled_is_default_when_unset(self) -> None:
        providers = [
            _provider("aws-main", "aws"),
            _provider("k8s_ms-karpenter", "k8s"),
        ]
        cfg = _provider_config(providers, default_instance=None)
        assert is_default_provider_instance("aws-main", cfg) is True
        assert is_default_provider_instance("k8s_ms-karpenter", cfg) is False

    def test_disabled_first_instance_is_skipped(self) -> None:
        providers = [
            _provider("aws-main", "aws", enabled=False),
            _provider("k8s_ms-karpenter", "k8s", enabled=True),
        ]
        cfg = _provider_config(providers, default_instance=None)
        # aws-main is disabled, so the first *enabled* instance is the default.
        assert is_default_provider_instance("k8s_ms-karpenter", cfg) is True
        assert is_default_provider_instance("aws-main", cfg) is False

    def test_unnamed_instance_registers_by_default(self) -> None:
        """When the instance name is unknown (type-level construction with no
        instance context) the check registers rather than being silently
        dropped — single-provider deployments must keep their probe."""
        providers = [_provider("aws-main", "aws")]
        cfg = _provider_config(providers, default_instance="aws-main")
        assert is_default_provider_instance(None, cfg) is True

    def test_no_config_registers_by_default(self) -> None:
        """With no resolvable provider config, do not suppress the check —
        fall back to registering so single-provider setups still probe."""
        assert is_default_provider_instance("aws-main", None) is True
