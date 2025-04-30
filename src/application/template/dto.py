from dataclasses import dataclass
from typing import Dict, Any, List, Optional

@dataclass
class TemplateDTO:
    """Data Transfer Object for template responses."""
    template_id: str
    aws_handler: str
    max_number: int
    attributes: Dict[str, Any]
    image_id: str
    subnet_id: Optional[str] = None
    subnet_ids: Optional[List[str]] = None
    vm_type: Optional[str] = None
    vm_types: Optional[Dict[str, int]] = None
    key_name: Optional[str] = None
    security_group_ids: List[str] = None
    instance_tags: Dict[str, str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "templateId": self.template_id,
            "awsHandler": self.aws_handler,
            "maxNumber": self.max_number,
            "attributes": self.attributes,
            "imageId": self.image_id,
            "subnetId": self.subnet_id,
            "subnetIds": self.subnet_ids,
            "vmType": self.vm_type,
            "vmTypes": self.vm_types,
            "keyName": self.key_name,
            "securityGroupIds": self.security_group_ids,
            "instanceTags": self.instance_tags
        }

@dataclass
class TemplateListResponse:
    """Response object for template list operations."""
    templates: List[TemplateDTO]
    message: str = "Get available templates success."

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "templates": [t.to_dict() for t in self.templates],
            "message": self.message
        }
