"""Scope provider connectivity health checks to the default/active instance.

Provider-connectivity checks (``aws``, ``ec2``, ``kubernetes_api``) should
only be registered for the default/active provider instance. A secondary
enabled instance — for example a k8s provider pointed at an unreachable
cluster running alongside a primary AWS provider — must not register a
connectivity check, so it cannot drag the overall status down.

The default/active instance is resolved the same way provider selection
resolves it (see ``ProviderSelectionService._select_default_provider``):
``provider_config.default_provider_instance`` when set, otherwise the
first enabled instance.
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = ["is_default_provider_instance"]


def _resolve_default_instance_name(provider_config: Any) -> Optional[str]:
    """Return the name of the default/active provider instance, or ``None``.

    Mirrors provider-selection precedence: an explicit
    ``default_provider_instance`` wins; otherwise the first enabled instance.
    """
    explicit = getattr(provider_config, "default_provider_instance", None)
    if explicit:
        return str(explicit)

    providers = getattr(provider_config, "providers", None) or []
    for instance in providers:
        if getattr(instance, "enabled", True):
            return getattr(instance, "name", None)
    return None


def is_default_provider_instance(provider_name: Optional[str], provider_config: Any) -> bool:
    """Return ``True`` when *provider_name* is the default/active instance.

    Deliberately fails open: when the provider config cannot be resolved, or
    when ``provider_name`` is unknown (type-level construction with no
    instance context), the connectivity check should still register so that
    single-provider deployments keep their probe. Only a *named* secondary
    instance that is demonstrably not the default is suppressed.

    Args:
        provider_name: The instance name the check would be registered for.
            ``None`` means the caller has no instance context.
        provider_config: The resolved provider configuration root, or ``None``.

    Returns:
        ``True`` if the check should register (default/active or ambiguous),
        ``False`` only when *provider_name* is a known non-default instance.
    """
    if provider_config is None:
        return True
    if provider_name is None:
        return True

    default_name = _resolve_default_instance_name(provider_config)
    if default_name is None:
        # No resolvable default — do not suppress.
        return True

    return provider_name == default_name
