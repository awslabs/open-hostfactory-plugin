"""AWS Instance Manager implementation."""
from typing import List, Dict, Any

from src.domain.base.dependency_injection import injectable
from src.domain.base.ports import LoggingPort
from src.providers.aws.configuration.config import AWSProviderConfig
from src.providers.aws.infrastructure.aws_client import AWSClient
from src.providers.aws.infrastructure.dry_run_adapter import aws_dry_run_context
from src.infrastructure.interfaces.instance_manager import (
    InstanceSpec, 
    Instance, 
    InstanceState, 
    InstanceStatusResponse
)


@injectable
class AWSInstanceManager:
    """AWS implementation of InstanceManagerPort."""
    
    def __init__(self, aws_client: AWSClient, config: AWSProviderConfig, logger: LoggingPort):
        """Initialize AWS instance manager."""
        self._aws_client = aws_client
        self._config = config
        self._logger = logger
    
    
    def create_instances(self, template_config: Dict[str, Any], count: int) -> List[str]:
        """Create instances based on template configuration."""
        with aws_dry_run_context():
            try:
                ec2_client = self._aws_client.get_client('ec2')
                
                # Build run_instances parameters from template config
                params = {
                    'ImageId': template_config.get('image_id', template_config.get('imageId')),
                    'InstanceType': template_config.get('vm_type', template_config.get('instance_type')),
                    'MinCount': count,
                    'MaxCount': count
                }
                
                if template_config.get('user_data'):
                    params['UserData'] = template_config['user_data']
                
                # Create instances (mocked if dry-run is active)
                response = ec2_client.run_instances(**params)
                
                # Return list of instance IDs (as expected by the strategy)
                instance_ids = [instance['InstanceId'] for instance in response['Instances']]
                
                # Add tags if specified
                if template_config.get('tags') and instance_ids:
                    tags = [{'Key': k, 'Value': v} for k, v in template_config['tags'].items()]
                    ec2_client.create_tags(Resources=instance_ids, Tags=tags)
                
                return instance_ids
                
            except Exception as e:
                self._logger.error(f"Failed to create instances: {e}")
                return []
    
    
    def terminate_instances(self, instance_ids: List[str]) -> bool:
        """Terminate instances by ID."""
        with aws_dry_run_context():
            try:
                ec2_client = self._aws_client.get_client('ec2')
                # Terminate instances (mocked if dry-run is active)
                response = ec2_client.terminate_instances(InstanceIds=instance_ids)
                
                # Check if all instances are terminating
                terminating_count = len(response.get('TerminatingInstances', []))
                return terminating_count == len(instance_ids)
                
            except Exception as e:
                self._logger.error(f"Failed to terminate instances: {e}")
                return False
    
    
    def get_instance_status(self, instance_ids: List[str]) -> Dict[str, str]:
        """Get status of instances."""
        with aws_dry_run_context():
            try:
                ec2_client = self._aws_client.get_client('ec2')
                # Describe instances (mocked if dry-run is active)
                response = ec2_client.describe_instances(InstanceIds=instance_ids)
                
                status_map = {}
                for reservation in response['Reservations']:
                    for aws_instance in reservation['Instances']:
                        instance_id = aws_instance['InstanceId']
                        state = aws_instance['State']['Name']
                        status_map[instance_id] = state
                
                return status_map
                
            except Exception as e:
                self._logger.error(f"Failed to get instance status: {e}")
                return {instance_id: "error" for instance_id in instance_ids}
    
    
    def start_instances(self, instance_ids: List[str]) -> Dict[str, bool]:
        """Start stopped instances."""
        try:
            ec2_client = self._aws_client.get_client('ec2')
            response = ec2_client.start_instances(InstanceIds=instance_ids)
            
            results = {}
            for instance in response.get('StartingInstances', []):
                instance_id = instance['InstanceId']
                current_state = instance['CurrentState']['Name']
                results[instance_id] = current_state in ['pending', 'running']
            
            return results
            
        except Exception as e:
            self._logger.error(f"Failed to start instances: {e}")
            return {instance_id: False for instance_id in instance_ids}
    
    
    def stop_instances(self, instance_ids: List[str]) -> Dict[str, bool]:
        """Stop running instances."""
        try:
            ec2_client = self._aws_client.get_client('ec2')
            response = ec2_client.stop_instances(InstanceIds=instance_ids)
            
            results = {}
            for instance in response.get('StoppingInstances', []):
                instance_id = instance['InstanceId']
                current_state = instance['CurrentState']['Name']
                results[instance_id] = current_state in ['stopping', 'stopped']
            
            return results
            
        except Exception as e:
            self._logger.error(f"Failed to stop instances: {e}")
            return {instance_id: False for instance_id in instance_ids}
    
    
    def get_instances_by_tags(self, tags: Dict[str, str]) -> List[str]:
        """Find instance IDs by tags."""
        with aws_dry_run_context():
            try:
                ec2_client = self._aws_client.get_client('ec2')
                
                # Build filters for tags
                filters = []
                for key, value in tags.items():
                    filters.append({
                        'Name': f'tag:{key}',
                        'Values': [value]
                    })
                
                response = ec2_client.describe_instances(Filters=filters)
                
                instance_ids = []
                for reservation in response['Reservations']:
                    for aws_instance in reservation['Instances']:
                        instance_ids.append(aws_instance['InstanceId'])
                
                return instance_ids
                
            except Exception as e:
                self._logger.error(f"Failed to get instances by tags: {e}")
                return []
