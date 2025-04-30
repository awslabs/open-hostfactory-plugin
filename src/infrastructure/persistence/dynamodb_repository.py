# src/infrastructure/persistence/dynamodb_repository.py
from typing import Dict, Any, List, Optional, Type, TypeVar
from datetime import datetime
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import time
import json
from src.infrastructure.persistence.base_repository import BaseRepository, OptimisticLockingMixin, CachingMixin
from src.infrastructure.persistence.exceptions import StorageError, ConcurrencyError

T = TypeVar('T')

class DynamoDBRepository(BaseRepository[T], OptimisticLockingMixin, CachingMixin):
    """
    DynamoDB implementation of repository.
    
    Handles persistence of entities in DynamoDB with support for:
    - Automatic table creation and management
    - Optimistic locking
    - TTL-based cleanup
    - Point-in-time recovery
    - Audit logging
    - Batch operations
    - GSI querying
    """

    def __init__(self, 
                 entity_class: Type[T],
                 collection_name: str,
                 region: str,
                 table_prefix: str = 'hostfactory',
                 endpoint_url: Optional[str] = None,
                 ttl_enabled: bool = True,
                 ttl_attribute: str = 'ttl',
                 backup_enabled: bool = True):
        """Initialize DynamoDB repository."""
        # Initialize all parent classes
        BaseRepository.__init__(self)
        OptimisticLockingMixin.__init__(self)
        CachingMixin.__init__(self)
        
        self._entity_class = entity_class
        self.table_name = f"{table_prefix}_{collection_name}"
        self._dynamodb = boto3.resource('dynamodb', region_name=region, endpoint_url=endpoint_url)
        self._dynamodb_client = boto3.client('dynamodb', region_name=region, endpoint_url=endpoint_url)
        self.table = self._dynamodb.Table(self.table_name)
        self._ensure_table_exists(ttl_enabled, ttl_attribute, backup_enabled)

    def _ensure_table_exists(self, ttl_enabled: bool, ttl_attribute: str, backup_enabled: bool) -> None:
        """Ensure the DynamoDB table exists with proper configuration."""
        try:
            self.table.table_status
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                self._create_table(ttl_enabled, ttl_attribute, backup_enabled)
            else:
                raise StorageError(f"Error checking DynamoDB table: {str(e)}")

    def _create_table(self, ttl_enabled: bool, ttl_attribute: str, backup_enabled: bool) -> None:
        """Create DynamoDB table with indexes and configuration."""
        try:
            table = self._dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'},
                    {'AttributeName': 'sort_key', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'sort_key', 'AttributeType': 'S'},
                    {'AttributeName': 'entity_type', 'AttributeType': 'S'},
                    {'AttributeName': 'updated_at', 'AttributeType': 'S'},
                    {'AttributeName': 'status', 'AttributeType': 'S'}  # Added for status queries
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'entity_type_index',
                        'KeySchema': [
                            {'AttributeName': 'entity_type', 'KeyType': 'HASH'},
                            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    },
                    {
                        'IndexName': 'status_index',
                        'KeySchema': [
                            {'AttributeName': 'status', 'KeyType': 'HASH'},
                            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )

            self._logger.info(f"Created table {self.table_name}")
            
            # Wait for table to be created
            table.meta.client.get_waiter('table_exists').wait(TableName=self.table_name)

            # Enable TTL if requested
            if ttl_enabled:
                self._dynamodb_client.update_time_to_live(
                    TableName=self.table_name,
                    TimeToLiveSpecification={
                        'Enabled': True,
                        'AttributeName': ttl_attribute
                    }
                )
                self._logger.info(f"Enabled TTL on {self.table_name}")

            # Enable point-in-time recovery if backup enabled
            if backup_enabled:
                self._dynamodb_client.update_continuous_backups(
                    TableName=self.table_name,
                    PointInTimeRecoverySpecification={
                        'PointInTimeRecoveryEnabled': True
                    }
                )
                self._logger.info(f"Enabled point-in-time recovery on {self.table_name}")

        except ClientError as e:
            raise StorageError(f"Failed to create DynamoDB table: {str(e)}")

    def save(self, entity: T) -> None:
        """Save an entity with optimistic locking."""
        try:
            entity_id = self._get_entity_id(entity)
            entity_data = self._serialize_entity(entity)
            now = datetime.utcnow().isoformat()

            item = {
                'id': entity_id,
                'sort_key': f"DATA#{entity_id}",
                'entity_type': self._entity_class.__name__,
                'data': entity_data,
                'version': 1,  # Will be incremented if exists
                'created_at': now,
                'updated_at': now,
                'status': entity_data.get('status', 'unknown')  # Extract status for GSI
            }

            # Add TTL if entity supports it
            if hasattr(entity, 'ttl'):
                item['ttl'] = int(entity.ttl.timestamp())

            # Try optimistic locking update if entity exists
            try:
                current_version = self._get_current_version(entity_id)
                if current_version:
                    if hasattr(entity, 'version') and entity.version != current_version:
                        raise ConcurrencyError(f"Entity {entity_id} was modified by another process")
                    item['version'] = current_version + 1
                    
                    # Conditional update
                    self.table.put_item(
                        Item=item,
                        ConditionExpression='version = :current_version',
                        ExpressionAttributeValues={':current_version': current_version}
                    )
                else:
                    # New item
                    self.table.put_item(
                        Item=item,
                        ConditionExpression='attribute_not_exists(id)'
                    )

                # Save audit record
                self._save_audit_record(entity_id, 'UPDATE' if current_version else 'INSERT', item)

            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    raise ConcurrencyError(f"Concurrent modification of entity {entity_id}")
                raise

            # Update cache
            self._add_to_cache(entity)

        except Exception as e:
            raise StorageError(f"Failed to save entity: {str(e)}")

    def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find an entity by ID with caching."""
        # Check cache first
        cached = self._get_from_cache(entity_id)
        if cached:
            return cached

        try:
            response = self.table.get_item(
                Key={
                    'id': str(entity_id),
                    'sort_key': f"DATA#{entity_id}"
                }
            )

            if 'Item' in response:
                entity = self._deserialize_entity(response['Item']['data'])
                self._add_to_cache(entity)
                return entity

            return None

        except ClientError as e:
            raise StorageError(f"Failed to find entity: {str(e)}")

    def find_all(self) -> List[T]:
        """Find all entities using GSI."""
        try:
            paginator = self._dynamodb_client.get_paginator('query')
            
            items = []
            for page in paginator.paginate(
                TableName=self.table_name,
                IndexName='entity_type_index',
                KeyConditionExpression='entity_type = :type',
                ExpressionAttributeValues={':type': {'S': self._entity_class.__name__}}
            ):
                items.extend(page['Items'])

            return [
                self._deserialize_entity(json.loads(item['data']['S']))
                for item in items
            ]

        except ClientError as e:
            raise StorageError(f"Failed to find entities: {str(e)}")

    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[T]:
        """Find entities matching criteria using GSI and filters."""
        try:
            filter_expression = None
            expression_values = {}
            expression_names = {}

            for key, value in criteria.items():
                if filter_expression is None:
                    filter_expression = Attr(f"data.{key}").eq(value)
                else:
                    filter_expression = filter_expression & Attr(f"data.{key}").eq(value)

            response = self.table.scan(
                FilterExpression=filter_expression
            )
            
            return [
                self._deserialize_entity(item['data'])
                for item in response.get('Items', [])
            ]

        except ClientError as e:
            raise StorageError(f"Failed to query by criteria: {str(e)}")

    def batch_save(self, entities: List[T]) -> None:
        """Save multiple entities in a batch."""
        try:
            with self.table.batch_writer() as batch:
                for entity in entities:
                    entity_id = self._get_entity_id(entity)
                    entity_data = self._serialize_entity(entity)
                    now = datetime.utcnow().isoformat()

                    item = {
                        'id': entity_id,
                        'sort_key': f"DATA#{entity_id}",
                        'entity_type': self._entity_class.__name__,
                        'data': entity_data,
                        'version': 1,
                        'created_at': now,
                        'updated_at': now,
                        'status': entity_data.get('status', 'unknown')
                    }
                    
                    batch.put_item(Item=item)

        except ClientError as e:
            raise StorageError(f"Failed to batch save entities: {str(e)}")

    def batch_delete(self, entity_ids: List[str]) -> None:
        """Delete multiple entities in a batch."""
        try:
            with self.table.batch_writer() as batch:
                for entity_id in entity_ids:
                    batch.delete_item(
                        Key={
                            'id': str(entity_id),
                            'sort_key': f"DATA#{entity_id}"
                        }
                    )

        except ClientError as e:
            raise StorageError(f"Failed to batch delete entities: {str(e)}")

    def create_backup(self) -> str:
        """Create an on-demand backup."""
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{self.table_name}_backup_{timestamp}"
            
            response = self._dynamodb_client.create_backup(
                TableName=self.table_name,
                BackupName=backup_name
            )
            
            return response['BackupDetails']['BackupArn']

        except ClientError as e:
            raise StorageError(f"Failed to create backup: {str(e)}")

    def _save_audit_record(self, entity_id: str, operation: str, data: Dict[str, Any]) -> None:
        """Save an audit record."""
        try:
            audit_item = {
                'id': entity_id,
                'sort_key': f"AUDIT#{datetime.utcnow().isoformat()}",
                'operation': operation,
                'data': data,
                'timestamp': datetime.utcnow().isoformat()
            }
            self.table.put_item(Item=audit_item)
        except ClientError as e:
            self._logger.warning(f"Failed to save audit record: {str(e)}")

    def get_audit_log(self, 
                     entity_id: Optional[str] = None,
                     start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get audit log entries with filtering."""
        try:
            if entity_id:
                # Query by entity ID
                key_condition = Key('id').eq(entity_id) & Key('sort_key').begins_with('AUDIT#')
                response = self.table.query(KeyConditionExpression=key_condition)
            else:
                # Scan all audit records
                response = self.table.scan(
                    FilterExpression=Attr('sort_key').begins_with('AUDIT#')
                )

            items = response.get('Items', [])

            # Apply date filters if provided
            if start_date or end_date:
                filtered_items = []
                for item in items:
                    timestamp = datetime.fromisoformat(item['timestamp'])
                    if start_date and timestamp < start_date:
                        continue
                    if end_date and timestamp > end_date:
                        continue
                    filtered_items.append(item)
                return filtered_items

            return items

        except ClientError as e:
            raise StorageError(f"Failed to get audit log: {str(e)}")

    def cleanup_old_entities(self, max_age_hours: int = 24) -> None:
        """Clean up old entities based on age."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            response = self.table.scan(
                FilterExpression=Attr('created_at').lt(cutoff_time.isoformat())
            )

            with self.table.batch_writer() as batch:
                for item in response.get('Items', []):
                    batch.delete_item(
                        Key={
                            'id': item['id'],
                            'sort_key': item['sort_key']
                        }
                    )

        except ClientError as e:
            raise StorageError(f"Failed to cleanup old entities: {str(e)}")

    def _get_current_version(self, entity_id: str) -> Optional[int]:
        """Get current version of an entity."""
        try:
            response = self.table.get_item(
                Key={
                    'id': str(entity_id),
                    'sort_key': f"DATA#{entity_id}"
                },
                ProjectionExpression='version'
            )
            return response.get('Item', {}).get('version')
        except ClientError:
            return None

    def _serialize_entity(self, entity: T) -> Dict[str, Any]:
        """Convert entity to dictionary format."""
        if hasattr(entity, 'to_dict'):
            return entity.to_dict()
        return vars(entity)

    def _deserialize_entity(self, data: Dict[str, Any]) -> T:
        """Convert dictionary to entity."""
        if hasattr(self._entity_class, 'from_dict'):
            return self._entity_class.from_dict(data)
        return self._entity_class(**data)