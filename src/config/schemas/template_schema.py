"""Template configuration schemas."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator


class AMIResolutionConfig(BaseModel):
    """AMI resolution configuration."""
    
    enabled: bool = Field(True, description="Enable AMI resolution from SSM parameters")
    fallback_on_failure: bool = Field(True, description="Return SSM parameter if resolution fails")
    cache_enabled: bool = Field(True, description="Enable runtime caching of resolved AMI IDs")


class TemplateConfig(BaseModel):
    """Template configuration."""
    
    default_image_id: str = Field(..., description="Default AMI ID")
    default_instance_type: str = Field(..., description="Default instance type")
    subnet_ids: List[str] = Field(..., description="Subnet IDs")
    security_group_ids: List[str] = Field(..., description="Security group IDs")
    default_key_name: str = Field("", description="Default key name")
    default_max_number: int = Field(10, description="Default maximum number of instances")
    default_attributes: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Default attributes for templates"
    )
    default_instance_tags: Dict[str, str] = Field(
        default_factory=dict,
        description="Default instance tags"
    )
    ssm_parameter_prefix: str = Field(
        "/hostfactory/templates/",
        description="SSM parameter prefix for templates"
    )
    templates_file_path: str = Field(
        "config/templates.json",
        description="Path to templates file"
    )
    legacy_templates_file_path: str = Field(
        "config/awsprov_templates.json",
        description="Path to legacy templates file"
    )
    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="Tags for templates"
    )
    user_data_script: Optional[str] = Field(None, description="User data script")
    instance_profile: Optional[str] = Field(None, description="Instance profile")
    ami_resolution: AMIResolutionConfig = Field(
        default_factory=AMIResolutionConfig,
        description="AMI resolution configuration"
    )
    
    # Symphony template format fields
    default_price_type: str = Field("ondemand", description="Default pricing type (ondemand, spot, heterogeneous)")
    default_vm_type: Optional[str] = Field(None, description="Default EC2 instance type for ondemand")
    default_vm_types: Optional[Dict[str, int]] = Field(None, description="Default map of instance types and weights for spot/heterogeneous")
    default_vm_types_on_demand: Optional[Dict[str, int]] = Field(None, description="Default On-Demand instance types for heterogeneous")
    default_vm_types_priority: Optional[Dict[str, int]] = Field(None, description="Default priority settings for instance types")
    default_fleet_role: Optional[str] = Field(None, description="Default IAM role for Spot Fleet")
    default_max_spot_price: Optional[float] = Field(None, description="Default maximum price for Spot instances")
    default_spot_fleet_request_expiry: int = Field(30, description="Default time before unfulfilled requests are canceled (minutes)")
    default_allocation_strategy: str = Field("lowestPrice", description="Default strategy for Spot instances")
    default_allocation_strategy_on_demand: str = Field("lowestPrice", description="Default strategy for On-Demand instances")
    default_percent_on_demand: int = Field(0, description="Default percentage of On-Demand capacity in heterogeneous")
    default_pools_count: Optional[int] = Field(None, description="Default number of Spot instance pools to use")
    default_volume_type: str = Field("gp2", description="Default type of EBS volume")
    default_iops: Optional[int] = Field(None, description="Default I/O operations per second for io1/io2 volumes")
    default_root_device_volume_size: Optional[int] = Field(None, description="Default size of EBS root volume in GiB")
    
    @validator('subnet_ids')
    def validate_subnet_ids(cls, v: List[str]) -> List[str]:
        """Validate subnet IDs."""
        if not v:
            raise ValueError("At least one subnet ID is required")
        return v
    
    @validator('security_group_ids')
    def validate_security_group_ids(cls, v: List[str]) -> List[str]:
        """Validate security group IDs."""
        if not v:
            raise ValueError("At least one security group ID is required")
        return v
