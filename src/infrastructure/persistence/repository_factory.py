# src/infrastructure/persistence/repository_factory.py
from typing import Dict, Any, Type, Optional
import os
import logging
from src.infrastructure.persistence.base_repository import BaseRepository
from src.infrastructure.persistence.json_repository import JSONRepository
from src.infrastructure.persistence.sqlite_repository import SQLiteRepository
from src.infrastructure.persistence.dynamodb_repository import DynamoDBRepository
from src.infrastructure.persistence.exceptions import StorageError
from src.domain.core.exceptions import ConfigurationError

class RepositoryFactory:
    """
    Factory for creating repository instances based on configuration.
    
    This factory handles:
    - Repository type selection
    - Configuration parsing and validation
    - Repository initialization
    - Storage setup and validation
    
    The factory ensures proper repository initialization while maintaining
    DDD separation of concerns by handling all configuration and setup
    logic at the infrastructure layer.
    """

    @staticmethod
    def create_repository(
        collection_name: str,
        entity_class: Type[Any],
        config: Dict[str, Any]
    ) -> BaseRepository:
        """
        Create a repository instance based on configuration.
        
        Args:
            collection_name: Name of the collection (e.g., 'templates', 'requests', 'machines')
            entity_class: The entity class for the repository
            config: Configuration dictionary from ConfigurationManager
            
        Returns:
            BaseRepository: Configured repository instance
            
        Raises:
            ConfigurationError: If configuration is invalid or missing required fields
            StorageError: If storage initialization fails
        """
        try:
            repo_config = config.get('REPOSITORY_CONFIG')
            if not repo_config:
                raise ConfigurationError("Missing REPOSITORY_CONFIG in configuration")

            repo_type = repo_config.get('type')
            if not repo_type:
                raise ConfigurationError("Repository type not specified in configuration")

            # Parse storage configuration
            storage_config = RepositoryFactory._parse_storage_config(
                repo_type, 
                repo_config,
                collection_name
            )

            # Create repository instance with parsed configuration
            if repo_type == "json":
                return JSONRepository(
                    entity_class=entity_class,
                    storage_path=storage_config['storage_path'],
                    is_single_file=storage_config['is_single_file'],
                    collection_name=collection_name
                )
            elif repo_type == "sqlite":
                return SQLiteRepository(
                    entity_class=entity_class,
                    db_path=storage_config['db_path'],
                    collection_name=collection_name
                )
            elif repo_type == "dynamodb":
                return DynamoDBRepository(
                    entity_class=entity_class,
                    table_prefix=storage_config['table_prefix'],
                    region=storage_config['region'],
                    collection_name=collection_name
                )
            else:
                raise ConfigurationError(f"Unsupported repository type: {repo_type}")

        except Exception as e:
            raise ConfigurationError(f"Failed to create repository: {str(e)}")

    @staticmethod
    def _parse_storage_config(
        repo_type: str,
        repo_config: Dict[str, Any],
        collection_name: str
    ) -> Dict[str, Any]:
        """
        Parse storage configuration based on repository type.
        
        Args:
            repo_type: Type of repository (json, sqlite, dynamodb)
            repo_config: Repository configuration dictionary
            collection_name: Name of the collection
            
        Returns:
            Dict containing parsed storage configuration
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        if repo_type == "json":
            json_config = repo_config.get('json')
            if not json_config:
                raise ConfigurationError("Missing JSON configuration")

            storage_type = json_config.get('storage_type')
            base_path = os.path.expandvars(json_config.get('base_path'))
            filenames = json_config.get('filenames')

            if not all([storage_type, base_path, filenames]):
                raise ConfigurationError("Incomplete JSON repository configuration")

            # Determine storage path based on configuration
            if storage_type == 'single_file':
                storage_path = os.path.join(base_path, filenames['single_file'])
                is_single_file = True
            else:
                storage_path = os.path.join(
                    base_path, 
                    filenames['split_files'][collection_name]
                )
                is_single_file = False

            return {
                'storage_path': storage_path,
                'is_single_file': is_single_file
            }

        elif repo_type == "sqlite":
            sqlite_config = repo_config.get('sqlite')
            if not sqlite_config:
                raise ConfigurationError("Missing SQLite configuration")

            db_path = os.path.expandvars(sqlite_config.get('database_path'))
            if not db_path:
                raise ConfigurationError("Missing database_path in SQLite configuration")

            return {'db_path': db_path}

        elif repo_type == "dynamodb":
            dynamodb_config = repo_config.get('dynamodb')
            if not dynamodb_config:
                raise ConfigurationError("Missing DynamoDB configuration")

            required_fields = ['table_prefix', 'region']
            missing_fields = [f for f in required_fields if f not in dynamodb_config]
            if missing_fields:
                raise ConfigurationError(f"Missing DynamoDB configuration fields: {missing_fields}")

            return {
                'table_prefix': dynamodb_config['table_prefix'],
                'region': dynamodb_config['region'],
                'endpoint_url': dynamodb_config.get('endpoint_url')
            }

        raise ConfigurationError(f"Unsupported repository type: {repo_type}")

    @staticmethod
    def create_all_repositories(config: Dict[str, Any]) -> Dict[str, BaseRepository]:
        """
        Create all required repositories.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Dict[str, BaseRepository]: Dictionary of repository instances
            
        Raises:
            ConfigurationError: If repository creation fails
        """
        from src.domain.template.template_aggregate import Template
        from src.domain.request.request_aggregate import Request
        from src.domain.machine.machine_aggregate import Machine

        return {
            'templates': RepositoryFactory.create_repository('templates', Template, config),
            'requests': RepositoryFactory.create_repository('requests', Request, config),
            'machines': RepositoryFactory.create_repository('machines', Machine, config)
        }