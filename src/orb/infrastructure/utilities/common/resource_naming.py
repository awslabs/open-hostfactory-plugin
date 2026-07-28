"""Resource naming helper functions."""

from typing import Optional

from orb.config.schemas.common_schema import ResourceConfig


def get_resource_prefix(resource_type: str, config: Optional[ResourceConfig] = None) -> str:
    """
    Get the prefix for a specific resource type.

    Args:
        resource_type: Type of resource (launch_template, instance, fleet, asg, tag)
        config: Resource configuration. Required — raises if not provided.

    Returns:
        The explicitly configured prefix for ``resource_type`` when present,
        otherwise an empty string. An unset per-type prefix does NOT inherit
        ``default_prefix`` — a global default must not silently prefix per-type
        resource names.

    Raises:
        ValueError: If config is not provided
    """
    if config is None:
        raise ValueError(
            f"get_resource_prefix() requires a config argument. "
            f"Use config_port.get_resource_prefix('{resource_type}') instead."
        )

    if hasattr(config.prefixes, resource_type):
        return getattr(config.prefixes, resource_type)

    return ""
