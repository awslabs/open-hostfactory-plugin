"""Infrastructure utilities - common utilities and factories."""

# Import common utilities
# Export abstract interface from canonical location
from src.domain.base import UnitOfWorkFactory
from src.infrastructure.utilities.common.collections import (
    filter_dict,
    group_by,
    transform_list,
    validate_collection,
)
from src.infrastructure.utilities.common.date_utils import (
    format_datetime,
    get_current_timestamp,
    parse_datetime,
)
from src.infrastructure.utilities.common.file_utils import (
    ensure_directory_exists,
    read_json_file,
    write_json_file,
)
from src.infrastructure.utilities.common.resource_naming import (
    generate_resource_name,
    validate_resource_name,
)
from src.infrastructure.utilities.common.serialization import (
    deserialize_datetime,
    serialize_datetime,
    serialize_enum,
)
from src.infrastructure.utilities.common.string_utils import (
    camel_to_snake,
    sanitize_string,
    snake_to_camel,
    truncate_string,
)
from src.infrastructure.utilities.factories.api_handler_factory import APIHandlerFactory

# Import factories (removed legacy ProviderFactory)
from src.infrastructure.utilities.factories.repository_factory import RepositoryFactory
from src.infrastructure.utilities.factories.sql_engine_factory import SQLEngineFactory

__all__ = [
    # String utilities
    "camel_to_snake",
    "snake_to_camel",
    "sanitize_string",
    "truncate_string",
    # Date utilities
    "format_datetime",
    "parse_datetime",
    "get_current_timestamp",
    # File utilities
    "ensure_directory_exists",
    "read_json_file",
    "write_json_file",
    # Collection utilities
    "filter_dict",
    "group_by",
    "transform_list",
    "validate_collection",
    # Resource naming
    "generate_resource_name",
    "validate_resource_name",
    # Serialization
    "serialize_datetime",
    "deserialize_datetime",
    "serialize_enum",
    # Factories (legacy ProviderFactory removed)
    "RepositoryFactory",
    "UnitOfWorkFactory",
    "APIHandlerFactory",
    "SQLEngineFactory",
]
