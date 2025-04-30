import os
import pytest
from unittest.mock import Mock
import boto3
from moto import mock_aws
from typing import Dict, Any
from src.domain.template.template_aggregate import Template
from src.domain.request.request_aggregate import Request
from src.domain.machine.machine_aggregate import Machine
from src.application.template.service import TemplateApplicationService
from src.application.request.service import RequestApplicationService
from src.application.machine.service import MachineApplicationService
from src.infrastructure.aws.aws_client import AWSClient

@pytest.fixture(autouse=True)
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

@pytest.fixture
def aws_client(aws_credentials):
    """Create mocked AWS client."""
    with mock_aws():
        client = AWSClient(
            region_name='us-east-1',
            config={
                'AWS_REQUEST_RETRY_ATTEMPTS': 3,
                'AWS_CONNECTION_TIMEOUT_MS': 1000
            }
        )
        return client

@pytest.fixture
def mock_template_service():
    return Mock(spec=TemplateApplicationService)

@pytest.fixture
def mock_request_service():
    return Mock(spec=RequestApplicationService)

@pytest.fixture
def mock_machine_service():
    return Mock(spec=MachineApplicationService)

@pytest.fixture
def mock_aws_setup(aws_credentials):
    """Setup AWS resources needed for tests."""
    with mock_aws():
        ec2 = boto3.client('ec2', region_name='us-east-1')
        
        # Create VPC
        vpc = ec2.create_vpc(CidrBlock='10.0.0.0/16')
        vpc_id = vpc['Vpc']['VpcId']
        
        # Create Subnet
        subnet = ec2.create_subnet(
            VpcId=vpc_id,
            CidrBlock='10.0.0.0/24'
        )
        subnet_id = subnet['Subnet']['SubnetId']
        
        # Create Security Group
        sg = ec2.create_security_group(
            GroupName='test-sg',
            Description='Test security group',
            VpcId=vpc_id
        )
        sg_id = sg['GroupId']
        
        return {
            'vpc_id': vpc_id,
            'subnet_id': subnet_id,
            'security_group_id': sg_id
        }
