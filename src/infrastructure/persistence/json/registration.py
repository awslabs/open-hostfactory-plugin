"""JSON Storage Registration Module.

This module provides registration functions for JSON storage type,
enabling the storage registry pattern for JSON persistence.

CLEAN ARCHITECTURE: Only handles storage strategies, no repository knowledge.
"""

from typing import Any, Dict
from src.infrastructure.registry.storage_registry import get_storage_registry
from src.infrastructure.logging.logger import get_logger


def create_json_strategy(config: Any) -> Any:
    """
    Create JSON storage strategy from configuration.
    
    Args:
        config: Configuration object containing JSON storage settings
        
    Returns:
        JSONStorageStrategy instance
    """
    from src.infrastructure.persistence.json.strategy import JSONStorageStrategy
    
    # Extract configuration parameters
    if hasattr(config, 'json_strategy'):
        json_config = config.json_strategy
        base_path = json_config.base_path
        storage_type = json_config.storage_type
        
        if storage_type == "single_file":
            file_path = f"{base_path}/{json_config.filenames['single_file']}"
        else:
            # For split files, we'll use a base path and let the strategy handle file naming
            file_path = base_path
    else:
        # Fallback for simple config
        file_path = getattr(config, 'file_path', 'data/storage.json')
    
    return JSONStorageStrategy(
        file_path=file_path,
        create_dirs=True,
        entity_type='generic'
    )


def create_json_config(data: Dict[str, Any]) -> Any:
    """
    Create JSON storage configuration from data.
    
    Args:
        data: Configuration data dictionary
        
    Returns:
        JSON configuration object
    """
    from src.config.schemas.storage_schema import JsonStrategyConfig
    
    return JsonStrategyConfig(**data)


def create_json_unit_of_work(config: Any) -> Any:
    """
    Create JSON unit of work.
    
    Args:
        config: Configuration object
        
    Returns:
        JSONUnitOfWork instance
    """
    from src.infrastructure.persistence.json.unit_of_work import JSONUnitOfWork
    from src.config.manager import ConfigurationManager
    from src.infrastructure.logging.logger import get_logger
    
    # Handle different config types
    if isinstance(config, ConfigurationManager):
        config_manager = config
        logger = get_logger(__name__)
    else:
        # For testing or other scenarios
        config_manager = config
        logger = get_logger(__name__)
    
    return JSONUnitOfWork(config_manager, logger)


def register_json_storage() -> None:
    """
    Register JSON storage type with the storage registry.
    
    This function registers JSON storage strategy factory with the global
    storage registry, enabling JSON storage to be used through the
    registry pattern.
    
    CLEAN ARCHITECTURE: Only registers storage strategy, no repository knowledge.
    """
    registry = get_storage_registry()
    logger = get_logger(__name__)
    
    try:
        registry.register_storage(
            storage_type="json",
            strategy_factory=create_json_strategy,
            config_factory=create_json_config,
            unit_of_work_factory=create_json_unit_of_work
        )
        
        logger.info("Successfully registered JSON storage type")
        
    except Exception as e:
        logger.error(f"Failed to register JSON storage type: {e}")
        raise
