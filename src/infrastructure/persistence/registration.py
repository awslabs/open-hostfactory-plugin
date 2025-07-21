"""Central Storage Registration Module.

This module provides centralized registration of all storage types,
ensuring all storage implementations are registered with the storage registry.

CLEAN ARCHITECTURE: Only registers storage strategies, no repository knowledge.
"""

from src.infrastructure.logging.logger import get_logger


def register_all_storage_types() -> None:
    """
    Register all available storage types with the storage registry.

    This function attempts to register all known storage types. If a storage
    type fails to register (e.g., due to missing dependencies), it logs the
    error but continues with other storage types.

    CLEAN ARCHITECTURE: Only registers storage strategies.
    """
    logger = get_logger(__name__)

    # Track registration results
    registered_types = []
    failed_types = []

    # Register JSON storage
    try:
        from src.infrastructure.persistence.json.registration import register_json_storage

        register_json_storage()
        registered_types.append("json")
        logger.debug("JSON storage registered successfully")
    except Exception as e:
        failed_types.append(("json", str(e)))
        logger.warning(f"Failed to register JSON storage: {e}")

    # Register SQL storage
    try:
        from src.infrastructure.persistence.sql.registration import register_sql_storage

        register_sql_storage()
        registered_types.append("sql")
        logger.debug("SQL storage registered successfully")
    except Exception as e:
        failed_types.append(("sql", str(e)))
        logger.warning(f"Failed to register SQL storage: {e}")

    # Register DynamoDB storage
    try:
        from src.providers.aws.persistence.dynamodb.registration import register_dynamodb_storage

        register_dynamodb_storage()
        registered_types.append("dynamodb")
        logger.debug("DynamoDB storage registered successfully")
    except Exception as e:
        failed_types.append(("dynamodb", str(e)))
        logger.warning(f"Failed to register DynamoDB storage: {e}")

    # Log summary
    if registered_types:
        logger.info(f"Successfully registered storage types: {', '.join(registered_types)}")

    if failed_types:
        failed_summary = ", ".join([f"{name} ({error})" for name, error in failed_types])
        logger.warning(f"Failed to register storage types: {failed_summary}")

    if not registered_types:
        logger.error("No storage types were successfully registered!")
        raise RuntimeError("Failed to register any storage types")


def register_storage_type_on_demand(storage_type: str) -> bool:
    """
    Register a specific storage type on demand (Phase 3 optimization).

    Args:
        storage_type: Name of the storage type to register

    Returns:
        True if registration was successful, False otherwise
    """
    logger = get_logger(__name__)

    # Check if already registered
    from src.infrastructure.registry.storage_registry import get_storage_registry

    registry = get_storage_registry()

    if hasattr(registry, "is_registered") and registry.is_registered(storage_type):
        logger.debug(f"Storage type '{storage_type}' already registered")
        return True

    try:
        if storage_type == "json":
            from src.infrastructure.persistence.json.registration import register_json_storage

            register_json_storage()
        elif storage_type == "sql":
            from src.infrastructure.persistence.sql.registration import register_sql_storage

            register_sql_storage()
        elif storage_type == "dynamodb":
            from src.providers.aws.persistence.dynamodb.registration import (
                register_dynamodb_storage,
            )

            register_dynamodb_storage()
        else:
            logger.error(f"Unknown storage type: {storage_type}")
            return False

        logger.info(f"Successfully registered storage type on demand: {storage_type}")
        return True

    except Exception as e:
        logger.error(f"Failed to register storage type '{storage_type}' on demand: {e}")
        return False


def register_minimal_storage_types() -> None:
    """
    Register only essential storage types for faster startup (Phase 3 optimization).

    This registers only JSON storage by default, with other types loaded on demand.
    """
    logger = get_logger(__name__)

    # Register only JSON storage (lightweight, always available)
    try:
        from src.infrastructure.persistence.json.registration import register_json_storage

        register_json_storage()
        logger.info("Minimal storage registration complete: json")
    except Exception as e:
        logger.error(f"Failed to register minimal storage types: {e}")
        raise RuntimeError("Failed to register minimal storage types")


def get_available_storage_types() -> list:
    """
    Get list of available storage types.

    Returns:
        List of storage type names that are available for registration
    """
    available_types = []

    # Check JSON storage availability
    try:
        from src.infrastructure.persistence.json.strategy import JSONStorageStrategy

        available_types.append("json")
    except ImportError:
        pass

    # Check SQL storage availability
    try:
        from src.infrastructure.persistence.sql.strategy import SQLStorageStrategy

        available_types.append("sql")
    except ImportError:
        pass

    # Check DynamoDB storage availability
    try:
        from src.providers.aws.persistence.dynamodb.strategy import DynamoDBStorageStrategy

        available_types.append("dynamodb")
    except ImportError:
        pass

    return available_types


def is_storage_type_available(storage_type: str) -> bool:
    """
    Check if a storage type is available for registration.

    Args:
        storage_type: Name of the storage type to check

    Returns:
        True if storage type is available, False otherwise
    """
    return storage_type in get_available_storage_types()


def register_storage_type(storage_type: str) -> bool:
    """
    Register a specific storage type.

    Args:
        storage_type: Name of the storage type to register

    Returns:
        True if registration was successful, False otherwise
    """
    logger = get_logger(__name__)

    try:
        if storage_type == "json":
            from src.infrastructure.persistence.json.registration import register_json_storage

            register_json_storage()
        elif storage_type == "sql":
            from src.infrastructure.persistence.sql.registration import register_sql_storage

            register_sql_storage()
        elif storage_type == "dynamodb":
            from src.providers.aws.persistence.dynamodb.registration import (
                register_dynamodb_storage,
            )

            register_dynamodb_storage()
        else:
            logger.error(f"Unknown storage type: {storage_type}")
            return False

        logger.info(f"Successfully registered storage type: {storage_type}")
        return True

    except Exception as e:
        logger.error(f"Failed to register storage type '{storage_type}': {e}")
        return False
