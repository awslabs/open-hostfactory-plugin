# src/application/template/service.py
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from src.domain.template.template_repository import TemplateRepository
from src.domain.template.template_aggregate import Template
from src.domain.template.value_objects import TemplateId, AWSHandlerType
from src.domain.template.exceptions import TemplateNotFoundError, TemplateValidationError
from src.domain.core.events import EventPublisher, ResourceStateChangedEvent
from src.infrastructure.aws.aws_client import AWSClient

class TemplateApplicationService:
    """Enhanced application service for template operations."""

    def __init__(self, 
                 template_repository: TemplateRepository,
                 event_publisher: EventPublisher,
                 config: Dict[str, Any],
                 aws_client: Optional[AWSClient] = None):
        self._repository = template_repository
        self._event_publisher = event_publisher
        self._config = config
        self._aws_client = aws_client
        self._logger = logging.getLogger(__name__)

    def get_available_templates(self, long: bool = False) -> Dict[str, Any]:
        """Get all available templates without validation."""
        try:
            templates = self._repository.find_all()
            
            return {
                "templates": [
                    self.format_template_response(t, long) 
                    for t in templates
                ],
                "message": "Get available templates success."
            }
        except Exception as e:
            self._logger.error(f"Failed to get templates: {str(e)}")
            raise TemplateNotFoundError(f"Failed to get templates: {str(e)}")

    def get_template(self, template_id: str) -> Template:
        """Get template by ID with validation."""
        template = self._repository.find_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(template_id)

        # If it's a SpotFleet template, ensure it has the fleet role
        if template.aws_handler.startswith('SpotFleet') and not template.fleet_role:
            fleet_role = self._config.get('AWS_SPOT_FLEET_ROLE_ARN')
            self._logger.debug(f"Setting fleet role from config: {fleet_role}")
            if fleet_role:
                template.fleet_role = fleet_role
            else:
                self._logger.error("AWS_SPOT_FLEET_ROLE_ARN not found in config")

        return template

    def create_template(self, template_data: Dict[str, Any]) -> Template:
        """Create a new template with validation."""
        try:
            # If it's a SpotFleet template, inject fleet role if not provided
            if (template_data.get('awsHandler', '').startswith('SpotFleet') and 
                not template_data.get('fleetRole')):
                fleet_role = self._config.get('AWS_SPOT_FLEET_ROLE_ARN')
                if fleet_role:
                    template_data['fleetRole'] = fleet_role
                    self._logger.debug(f"Injecting fleet role from config: {fleet_role}")

            # Create template instance
            template = Template.from_dict(template_data)
            
            # Validate template
            self._validate_template_configuration(template)
            
            # Check for duplicate
            if self._repository.exists(template.template_id):
                raise TemplateValidationError(
                    str(template.template_id),
                    {"templateId": "Template ID already exists"}
                )
            
            # Save template
            self._repository.save(template)
            
            # Publish event
            self._event_publisher.publish(
                ResourceStateChangedEvent(
                    resource_id=str(template.template_id),
                    resource_type="Template",
                    old_state="none",
                    new_state="active",
                    details=template.to_dict()
                )
            )
            
            return template
            
        except Exception as e:
            self._logger.error(f"Failed to create template: {str(e)}")
            raise

    def update_template(self, template_id: str, template_data: Dict[str, Any]) -> Template:
        """Update an existing template."""
        try:
            # Check if template exists
            existing_template = self.get_template(template_id)
            
            # Create new template instance
            updated_template = Template.from_dict({
                **existing_template.to_dict(),
                **template_data,
                "templateId": template_id  # Ensure ID doesn't change
            })
            
            # Validate template
            self._validate_template_configuration(updated_template)
            
            # Save template
            self._repository.save(updated_template)
            
            # Publish event
            self._event_publisher.publish(
                ResourceStateChangedEvent(
                    resource_id=str(template_id),
                    resource_type="Template",
                    old_state="active",
                    new_state="updated",
                    details={"old": existing_template.to_dict(), "new": updated_template.to_dict()}
                )
            )
            
            return updated_template
            
        except Exception as e:
            self._logger.error(f"Failed to update template: {str(e)}")
            raise

    def delete_template(self, template_id: str) -> None:
        """Delete a template."""
        try:
            template = self.get_template(template_id)
            self._repository.delete(template.template_id)
            
            # Publish event
            self._event_publisher.publish(
                ResourceStateChangedEvent(
                    resource_id=str(template_id),
                    resource_type="Template",
                    old_state="active",
                    new_state="deleted",
                    details=template.to_dict()
                )
            )
            
        except Exception as e:
            self._logger.error(f"Failed to delete template: {str(e)}")
            raise

    def validate_template_request(self, template: Template, num_machines: int) -> None:
        """Validate template for a request."""
        errors: Dict[str, str] = {}

        # Validate machine count
        if num_machines <= 0:
            errors["num_machines"] = "Must be greater than zero"
        if num_machines > template.max_number:
            errors["num_machines"] = f"Exceeds template maximum of {template.max_number}"

        # Validate template configuration
        try:
            template.validate()
        except TemplateValidationError as e:
            errors.update(e.errors)

        if errors:
            raise TemplateValidationError(str(template.template_id), errors)

    def _validate_template_configuration(self, template: Template) -> None:
        """Enhanced template configuration validation."""
        try:
            # Basic validation
            template.validate()
            
            # Additional AWS-specific validation if AWS client is available
            if self._aws_client:
                self._validate_aws_resources(template)
                
        except Exception as e:
            raise TemplateValidationError(
                str(template.template_id),
                {"validation": str(e)}
            )

    def _validate_aws_resources(self, template: Template) -> None:
        """Validate AWS resources referenced in template."""
        errors = []
        
        try:
            # Validate AMI
            if template.image_id.startswith('ami-'):
                self._aws_client.ec2_client.describe_images(ImageIds=[template.image_id])
            
            # Validate subnet(s)
            subnets = [template.subnet_id] if template.subnet_id else template.subnet_ids or []
            if subnets:
                self._aws_client.ec2_client.describe_subnets(SubnetIds=subnets)
            
            # Validate security groups
            if template.security_group_ids:
                self._aws_client.ec2_client.describe_security_groups(
                    GroupIds=template.security_group_ids
                )
            
            # Validate instance types
            instance_types = [template.vm_type] if template.vm_type else list(template.vm_types.keys() if template.vm_types else [])
            for instance_type in instance_types:
                self._aws_client.ec2_client.describe_instance_types(
                    InstanceTypes=[instance_type]
                )
            
            # Validate IAM role for Spot Fleet
            if template.aws_handler in ['SpotFleet', 'SpotFleetRequest'] and template.fleet_role:
                self._aws_client.iam_client.get_role(RoleName=template.fleet_role.split('/')[-1])
                
        except Exception as e:
            errors.append(str(e))
            
        if errors:
            raise TemplateValidationError(
                str(template.template_id),
                {"aws_validation": errors}
            )

    def format_template_response(self, template: Template, long: bool = False) -> Dict[str, Any]:
        """Format template for API response with enhanced information."""
        if long:
            response = template.to_dict()
            # Add additional information for long format
            if self._aws_client:
                try:
                    # Add pricing information
                    if template.vm_type:
                        response['pricing'] = self._get_instance_pricing(template.vm_type)
                    # Add subnet information
                    if template.subnet_id:
                        response['subnet_info'] = self._get_subnet_info(template.subnet_id)
                    # Add security group information
                    if template.security_group_ids:
                        response['security_group_info'] = self._get_security_group_info(
                            template.security_group_ids
                        )
                except Exception as e:
                    self._logger.warning(f"Failed to get additional AWS info: {str(e)}")
            return response
        
        return {
            "templateId": template.template_id,
            "awsHandler": template.aws_handler,
            "maxNumber": template.max_number,
            "attributes": template.attributes
        }

    def _get_instance_pricing(self, instance_type: str) -> Dict[str, Any]:
        """Get pricing information for instance type."""
        try:
            pricing = self._aws_client.pricing_client.get_products(
                ServiceCode='AmazonEC2',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': 'US East (N. Virginia)'}
                ]
            )
            return json.loads(pricing['PriceList'][0])
        except Exception as e:
            self._logger.warning(f"Failed to get pricing info: {str(e)}")
            return {}

    def _get_subnet_info(self, subnet_id: str) -> Dict[str, Any]:
        """Get subnet information."""
        try:
            subnet = self._aws_client.ec2_client.describe_subnets(
                SubnetIds=[subnet_id]
            )['Subnets'][0]
            return {
                'vpc_id': subnet['VpcId'],
                'availability_zone': subnet['AvailabilityZone'],
                'available_ips': subnet['AvailableIpAddressCount'],
                'cidr_block': subnet['CidrBlock']
            }
        except Exception as e:
            self._logger.warning(f"Failed to get subnet info: {str(e)}")
            return {}

    def _get_security_group_info(self, security_group_ids: List[str]) -> List[Dict[str, Any]]:
        """Get security group information."""
        try:
            groups = self._aws_client.ec2_client.describe_security_groups(
                GroupIds=security_group_ids
            )['SecurityGroups']
            return [{
                'group_id': group['GroupId'],
                'name': group['GroupName'],
                'description': group['Description'],
                'vpc_id': group['VpcId'],
                'inbound_rules': group['IpPermissions'],
                'outbound_rules': group['IpPermissionsEgress']
            } for group in groups]
        except Exception as e:
            self._logger.warning(f"Failed to get security group info: {str(e)}")
            return []