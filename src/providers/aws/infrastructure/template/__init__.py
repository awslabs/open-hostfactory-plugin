"""AWS provider template infrastructure components."""

from .ssm_template_store import AWSSSMTemplateStore, create_aws_ssm_template_store

__all__ = [
    'AWSSSMTemplateStore',
    'create_aws_ssm_template_store',
]
