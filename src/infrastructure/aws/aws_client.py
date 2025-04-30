import logging
import boto3
from botocore.config import Config
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError
from src.infrastructure.exceptions import InfrastructureError

logger = logging.getLogger(__name__)

class AWSClient:
    """
    Centralized AWS client management.
    Handles AWS client creation and common AWS operations.
    """
    
    def __init__(self, region_name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize AWS client with configuration.
        
        Args:
            region_name: AWS region name
            config: Optional configuration dictionary
        
        Raises:
            InfrastructureError: If AWS credentials validation fails
        """
        self.region_name = region_name
        self.config = Config(
            region_name=region_name,
            retries={
                'max_attempts': config.get('AWS_REQUEST_RETRY_ATTEMPTS', 3),
                'mode': 'standard'
            },
            connect_timeout=config.get('AWS_CONNECTION_TIMEOUT_MS', 1000) / 1000
        )

        # Validate AWS credentials
        try:
            sts = boto3.client('sts')
            sts.get_caller_identity()
        except Exception as e:
            logger.error(f"Failed to validate AWS credentials: {str(e)}")
            raise InfrastructureError(f"Failed to validate AWS credentials: {str(e)}")
        
        # Initialize all required clients
        self.ec2_client = boto3.client('ec2', config=self.config)
        self.ec2_resource = boto3.resource('ec2', config=self.config)
        self.iam_client = boto3.client('iam', config=self.config)  # Add IAM client
        self.autoscaling_client = boto3.client('autoscaling', config=self.config)
        self.ssm_client = boto3.client('ssm', config=self.config)
        self.sts_client = boto3.client('sts', config=self.config)  # Add STS client
        self.cloudwatch_client = boto3.client('cloudwatch', config=self.config)  # Add CloudWatch client
        self.pricing_client = boto3.client('pricing', 
                                         region_name='us-east-1',  # Pricing API is only available in us-east-1
                                         config=self.config)

    def _configure_proxy(self, config: Dict[str, Any]) -> None:
        """Configure proxy settings for AWS clients."""
        if 'AWS_PROXY_HOST' in config and 'AWS_PROXY_PORT' in config:
            proxy_config = {
                'http': f"http://{config['AWS_PROXY_HOST']}:{config['AWS_PROXY_PORT']}",
                'https': f"https://{config['AWS_PROXY_HOST']}:{config['AWS_PROXY_PORT']}"
            }
            boto3.setup_default_session(proxies=proxy_config)

    def describe_instances(self, instance_ids: List[str]) -> List[Dict[str, Any]]:
        """Describe EC2 instances."""
        try:
            response = self.ec2_client.describe_instances(InstanceIds=instance_ids)
            instances = []
            for reservation in response['Reservations']:
                instances.extend(reservation['Instances'])
            return instances
        except ClientError as e:
            raise InfrastructureError(f"Failed to describe instances: {str(e)}")

    def describe_launch_template(self, template_id: str) -> Dict[str, Any]:
        """Describe Launch Template."""
        try:
            response = self.ec2_client.describe_launch_templates(
                LaunchTemplateIds=[template_id]
            )
            return response['LaunchTemplates'][0]
        except ClientError as e:
            raise InfrastructureError(f"Failed to describe launch template: {str(e)}")

    def create_tags(self, resource_ids: List[str], tags: List[Dict[str, str]]) -> None:
        """Create tags for AWS resources."""
        try:
            self.ec2_client.create_tags(
                Resources=resource_ids,
                Tags=[{'Key': k, 'Value': v} for k, v in tags.items()]
            )
        except ClientError as e:
            raise InfrastructureError(f"Failed to create tags: {str(e)}")

    def terminate_instances(self, instance_ids: List[str]) -> None:
        """Terminate EC2 instances."""
        try:
            self.ec2_client.terminate_instances(InstanceIds=instance_ids)
        except ClientError as e:
            raise InfrastructureError(f"Failed to terminate instances: {str(e)}")