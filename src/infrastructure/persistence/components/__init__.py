"""Storage strategy components package with consistent naming."""

# Base interfaces
from .resource_manager import StorageResourceManager, QueryManager, DataConverter

# Generic components (truly reusable across storage types)
from .lock_manager import LockManager, ReaderWriterLock
from .serialization_manager import SerializationManager, JSONSerializer
from .transaction_manager import TransactionManager, MemoryTransactionManager, NoOpTransactionManager
from .file_manager import FileManager

# SQL-specific components (clearly prefixed)
from .sql_connection_manager import SQLConnectionManager
from .sql_query_builder import SQLQueryBuilder
from .sql_serializer import SQLSerializer

# DynamoDB-specific components (clearly prefixed)
from .dynamodb_client_manager import DynamoDBClientManager
from .dynamodb_converter import DynamoDBConverter
from .dynamodb_transaction_manager import DynamoDBTransactionManager

__all__ = [
    # Base interfaces
    'ResourceManager',
    'QueryManager', 
    'DataConverter',
    
    # Generic components
    'LockManager',
    'ReaderWriterLock', 
    'SerializationManager',
    'JSONSerializer',
    'TransactionManager',
    'MemoryTransactionManager',
    'NoOpTransactionManager',
    'FileManager',
    
    # SQL components
    'SQLConnectionManager',
    'SQLQueryBuilder',
    'SQLSerializer',
    
    # DynamoDB components
    'DynamoDBClientManager',
    'DynamoDBConverter',
    'DynamoDBTransactionManager'
]
