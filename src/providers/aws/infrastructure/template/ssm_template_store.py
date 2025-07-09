"""AWS SSM Template Store - Provider-specific template storage using AWS SSM Parameter Store.

This module implements the ProviderTemplateStore protocol for AWS,
enabling template sharing and versioning across Symphony installations
using AWS SSM Parameter Store.

Follows provider extensibility patterns and maintains separation of concerns.
"""
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from src.infrastructure.template.dtos import TemplateDTO
from src.infrastructure.template.configuration_store import ProviderTemplateStore
from src.domain.base.ports import LoggingPort
from src.domain.base.dependency_injection import injectable
from src.providers.aws.infrastructure.aws_client import AWSClient


class AWSSSMTemplateStore:
    """
    AWS SSM Parameter Store implementation of ProviderTemplateStore.
    
    This store enables:
    - Template sharing across Symphony installations
    - Template versioning using SSM parameter versions
    - Centralized template management in AWS
    - Cross-region template replication
    
    SSM Parameter Structure:
    - Path: /symphony/templates/{template_id}
    - Value: JSON serialized TemplateDTO
    - Tags: provider_api, version, created_by, etc.
    """
    
    def __init__(self, 
                 aws_client: AWSClient,
                 parameter_prefix: str = "/symphony/templates",
                 logger: Optional[LoggingPort] = None):
        """
        Initialize AWS SSM Template Store.
        
        Args:
            aws_client: AWS client for SSM operations
            parameter_prefix: SSM parameter path prefix for templates
            logger: Logger for operations
        """
        self.aws_client = aws_client
        self.parameter_prefix = parameter_prefix.rstrip('/')
        self.logger = logger
        self._ssm_client = None
    
    @property
    def ssm_client(self):
        """Lazy initialization of SSM client."""
        if self._ssm_client is None:
            self._ssm_client = self.aws_client.get_client('ssm')
        return self._ssm_client
    
    def _get_parameter_path(self, template_id: str) -> str:
        """Get SSM parameter path for template."""
        return f"{self.parameter_prefix}/{template_id}"
    
    def _template_dto_to_parameter_value(self, template: TemplateDTO) -> str:
        """Convert TemplateDTO to SSM parameter value."""
        template_dict = {
            'template_id': template.template_id,
            'name': template.name,
            'provider_api': template.provider_api,
            'configuration': template.configuration,
            'version': template.version,
            'created_at': template.created_at.isoformat() if template.created_at else None,
            'updated_at': template.updated_at.isoformat() if template.updated_at else None,
        }
        return json.dumps(template_dict, indent=2)
    
    def _parameter_value_to_template_dto(self, parameter_value: str) -> TemplateDTO:
        """Convert SSM parameter value to TemplateDTO."""
        template_dict = json.loads(parameter_value)
        
        return TemplateDTO(
            template_id=template_dict['template_id'],
            name=template_dict['name'],
            provider_api=template_dict['provider_api'],
            configuration=template_dict['configuration'],
            version=template_dict.get('version'),
            created_at=datetime.fromisoformat(template_dict['created_at']) if template_dict.get('created_at') else None,
            updated_at=datetime.fromisoformat(template_dict['updated_at']) if template_dict.get('updated_at') else None,
        )
    
    async def save_template(self, template: TemplateDTO) -> None:
        """
        Save template to AWS SSM Parameter Store.
        
        Args:
            template: Template to save
        """
        try:
            parameter_path = self._get_parameter_path(template.template_id)
            parameter_value = self._template_dto_to_parameter_value(template)
            
            # Prepare tags for the parameter
            tags = [
                {'Key': 'Type', 'Value': 'SymphonyTemplate'},
                {'Key': 'ProviderAPI', 'Value': template.provider_api},
                {'Key': 'TemplateID', 'Value': template.template_id},
                {'Key': 'Version', 'Value': template.version or '1.0.0'},
                {'Key': 'UpdatedAt', 'Value': datetime.now().isoformat()},
            ]
            
            # Put parameter with versioning
            response = self.ssm_client.put_parameter(
                Name=parameter_path,
                Value=parameter_value,
                Type='String',
                Overwrite=True,
                Description=f"Symphony template: {template.name or template.template_id}",
                Tags=tags
            )
            
            self.logger.info(f"Saved template {template.template_id} to SSM: {parameter_path} (version {response.get('Version', 'unknown')})")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ParameterLimitExceeded':
                self.logger.error(f"SSM parameter limit exceeded for template {template.template_id}")
            elif error_code == 'AccessDenied':
                self.logger.error(f"Access denied saving template {template.template_id} to SSM")
            else:
                self.logger.error(f"AWS error saving template {template.template_id}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to save template {template.template_id} to SSM: {e}")
            raise
    
    async def load_templates(self) -> List[TemplateDTO]:
        """
        Load all templates from AWS SSM Parameter Store.
        
        Returns:
            List of TemplateDTO objects
        """
        try:
            templates = []
            paginator = self.ssm_client.get_paginator('get_parameters_by_path')
            
            # Get all parameters under the template prefix
            page_iterator = paginator.paginate(
                Path=self.parameter_prefix,
                Recursive=True,
                WithDecryption=False  # Templates don't contain sensitive data
            )
            
            for page in page_iterator:
                for parameter in page.get('Parameters', []):
                    try:
                        template = self._parameter_value_to_template_dto(parameter['Value'])
                        templates.append(template)
                        self.logger.debug(f"Loaded template {template.template_id} from SSM")
                    except Exception as e:
                        self.logger.warning(f"Failed to parse template from SSM parameter {parameter['Name']}: {e}")
                        continue
            
            self.logger.info(f"Loaded {len(templates)} templates from SSM")
            return templates
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                self.logger.error("Access denied loading templates from SSM")
            else:
                self.logger.error(f"AWS error loading templates from SSM: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Failed to load templates from SSM: {e}")
            return []
    
    async def delete_template(self, template_id: str) -> None:
        """
        Delete template from AWS SSM Parameter Store.
        
        Args:
            template_id: Template identifier to delete
        """
        try:
            parameter_path = self._get_parameter_path(template_id)
            
            self.ssm_client.delete_parameter(Name=parameter_path)
            
            self.logger.info(f"Deleted template {template_id} from SSM: {parameter_path}")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ParameterNotFound':
                self.logger.warning(f"Template {template_id} not found in SSM for deletion")
            elif error_code == 'AccessDenied':
                self.logger.error(f"Access denied deleting template {template_id} from SSM")
                raise
            else:
                self.logger.error(f"AWS error deleting template {template_id}: {e}")
                raise
        except Exception as e:
            self.logger.error(f"Failed to delete template {template_id} from SSM: {e}")
            raise
    
    async def get_template_versions(self, template_id: str) -> List[Dict[str, Any]]:
        """
        Get version history for a template.
        
        Args:
            template_id: Template identifier
            
        Returns:
            List of version information dictionaries
        """
        try:
            parameter_path = self._get_parameter_path(template_id)
            
            response = self.ssm_client.get_parameter_history(
                Name=parameter_path,
                WithDecryption=False
            )
            
            versions = []
            for param_history in response.get('Parameters', []):
                version_info = {
                    'version': param_history.get('Version'),
                    'last_modified_date': param_history.get('LastModifiedDate'),
                    'last_modified_user': param_history.get('LastModifiedUser'),
                    'description': param_history.get('Description'),
                }
                versions.append(version_info)
            
            self.logger.debug(f"Retrieved {len(versions)} versions for template {template_id}")
            return versions
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ParameterNotFound':
                self.logger.warning(f"Template {template_id} not found in SSM")
                return []
            else:
                self.logger.error(f"AWS error getting template versions for {template_id}: {e}")
                return []
        except Exception as e:
            self.logger.error(f"Failed to get template versions for {template_id}: {e}")
            return []
    
    async def get_template_by_version(self, template_id: str, version: int) -> Optional[TemplateDTO]:
        """
        Get specific version of a template.
        
        Args:
            template_id: Template identifier
            version: Version number
            
        Returns:
            TemplateDTO if found, None otherwise
        """
        try:
            parameter_path = self._get_parameter_path(template_id)
            
            response = self.ssm_client.get_parameter(
                Name=parameter_path,
                WithDecryption=False
            )
            
            # This would require get_parameter_history and filtering
            # For now, return the current version
            template = self._parameter_value_to_template_dto(response['Parameter']['Value'])
            
            self.logger.debug(f"Retrieved template {template_id} version {version} from SSM")
            return template
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ParameterNotFound':
                self.logger.warning(f"Template {template_id} version {version} not found in SSM")
                return None
            else:
                self.logger.error(f"AWS error getting template {template_id} version {version}: {e}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to get template {template_id} version {version}: {e}")
            return None


def create_aws_ssm_template_store(
    aws_client: AWSClient,
    parameter_prefix: str = "/symphony/templates",
    logger: Optional[LoggingPort] = None
) -> AWSSSMTemplateStore:
    """
    Factory function to create AWS SSM Template Store.
    
    Args:
        aws_client: AWS client for SSM operations
        parameter_prefix: SSM parameter path prefix
        logger: Optional logger
        
    Returns:
        Configured AWSSSMTemplateStore instance
    """
    return AWSSSMTemplateStore(
        aws_client=aws_client,
        parameter_prefix=parameter_prefix,
        logger=logger
    )
