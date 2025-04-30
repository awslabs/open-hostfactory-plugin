import pytest
from moto import mock_aws
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import time

from src.app import Application
from src.domain.template.template_aggregate import Template
from src.domain.request.value_objects import RequestStatus
from src.domain.machine.value_objects import MachineStatus

@pytest.fixture
def app(aws_setup):
    return Application()

@pytest.fixture
def aws_setup(aws_credentials):
    """Setup AWS resources needed for integration tests."""
    with mock_aws():
        ec2_client = boto3.client("ec2", region_name="us-east-1")
        iam_client = boto3.client("iam", region_name="us-east-1")

        # Create VPC
        vpc = ec2_client.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]

        # Create Subnet
        subnet = ec2_client.create_subnet(
            VpcId=vpc_id,
            CidrBlock="10.0.0.0/24",
            AvailabilityZone="us-east-1a"
        )
        subnet_id = subnet["Subnet"]["SubnetId"]

        # Create Security Group
        sg = ec2_client.create_security_group(
            GroupName="test-sg",
            Description="Test security group",
            VpcId=vpc_id
        )
        sg_id = sg["GroupId"]

        # Create IAM role for Spot Fleet
        role_name = "TestSpotFleetRole"
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": "spotfleet.amazonaws.com"}
            }]
        }
        iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy)
        )
        fleet_role_arn = f"arn:aws:iam::123456789012:role/{role_name}"

        # Create template configuration
        os.environ["HF_PROVIDER_CONFDIR"] = str(tmp_path)
        template_config = {
            "templates": [
                {
                    "templateId": "EC2FleetInstant",
                    "awsHandler": "EC2Fleet",
                    "maxNumber": 10,
                    "attributes": {
                        "type": ["String", "X86_64"],
                        "ncores": ["Numeric", "2"],
                        "ncpus": ["Numeric", "1"],
                        "nram": ["Numeric", "4096"]
                    },
                    "imageId": "ami-12345678",
                    "subnetId": subnet_id,
                    "vmType": "t2.micro",
                    "securityGroupIds": [sg_id]
                },
                {
                    "templateId": "SpotFleet",
                    "awsHandler": "SpotFleet",
                    "maxNumber": 10,
                    "attributes": {
                        "type": ["String", "X86_64"],
                        "ncores": ["Numeric", "2"],
                        "ncpus": ["Numeric", "1"],
                        "nram": ["Numeric", "4096"]
                    },
                    "imageId": "ami-12345678",
                    "subnetId": subnet_id,
                    "vmType": "t2.micro",
                    "securityGroupIds": [sg_id],
                    "fleetRole": fleet_role_arn,
                    "maxSpotPrice": "0.05"
                }
            ]
        }
        
        template_file = tmp_path / "awsprov_templates.json"
        template_file.write_text(json.dumps(template_config))

        yield {
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
            "security_group_id": sg_id,
            "fleet_role_arn": fleet_role_arn
        }

@mock_aws
def test_full_machine_lifecycle(app, aws_setup):
    """Test the complete lifecycle of requesting and returning machines."""
    
    # Step 1: Get available templates
    templates_result = app.endpoints["getAvailableTemplates"].execute()
    assert "templates" in templates_result
    assert len(templates_result["templates"]) > 0
    assert templates_result["message"] == "Get available templates success."

    # Step 2: Request machines
    request_data = {
        "template": {
            "templateId": "EC2FleetInstant",
            "machineCount": 2
        }
    }
    request_result = app.endpoints["requestMachines"].execute(request_data)
    assert "requestId" in request_result
    request_id = request_result["requestId"]

    # Step 3: Check request status until complete
    max_attempts = 10
    attempts = 0
    machines = []
    
    while attempts < max_attempts:
        status_data = {
            "requests": [{"requestId": request_id}]
        }
        status_result = app.endpoints["getRequestStatus"].execute(status_data)
        
        if status_result["requests"][0]["status"] == "complete":
            machines = status_result["requests"][0]["machines"]
            break
            
        attempts += 1
        time.sleep(1)

    assert len(machines) == 2
    assert all(m["status"] == "running" for m in machines)

    # Step 4: Return machines
    return_data = {
        "machines": [{"machineId": m["machineId"]} for m in machines]
    }
    return_result = app.endpoints["requestReturnMachines"].execute(return_data)
    assert "requestId" in return_result
    return_request_id = return_result["requestId"]

    # Step 5: Check return request status
    attempts = 0
    while attempts < max_attempts:
        status_data = {
            "requests": [{"requestId": return_request_id}]
        }
        status_result = app.endpoints["getRequestStatus"].execute(status_data)
        
        if status_result["requests"][0]["status"] == "complete":
            break
            
        attempts += 1
        time.sleep(1)

    # Final verification
    final_status = app.endpoints["getRequestStatus"].execute(
        {"requests": [{"requestId": request_id}]}
    )
    assert all(m["status"] == "terminated" for m in final_status["requests"][0]["machines"])

@mock_aws
def test_error_handling(app, aws_setup):
    """Test error handling in various scenarios."""
    
    # Test invalid template ID
    request_data = {
        "template": {
            "templateId": "non-existent-template",
            "machineCount": 1
        }
    }
    result = app.endpoints["requestMachines"].execute(request_data)
    assert "error" in result

    # Test invalid request ID
    status_data = {
        "requests": [{"requestId": "invalid-request-id"}]
    }
    result = app.endpoints["getRequestStatus"].execute(status_data)
    assert "error" in result

    # Test invalid machine ID
    return_data = {
        "machines": [{"machineId": "invalid-machine-id"}]
    }
    result = app.endpoints["requestReturnMachines"].execute(return_data)
    assert "error" in result

@mock_aws
def test_concurrent_requests(app, aws_setup):
    """Test handling multiple concurrent requests."""
    
    # Create multiple requests simultaneously
    request_data = {
        "template": {
            "templateId": "EC2FleetInstant",
            "machineCount": 1
        }
    }
    
    request_ids = []
    for _ in range(3):  # Create 3 concurrent requests
        result = app.endpoints["requestMachines"].execute(request_data)
        assert "requestId" in result
        request_ids.append(result["requestId"])

    # Check all requests
    status_data = {
        "requests": [{"requestId": rid} for rid in request_ids]
    }
    status_result = app.endpoints["getRequestStatus"].execute(status_data)
    
    assert len(status_result["requests"]) == 3
    assert all(r["requestId"] in request_ids for r in status_result["requests"])

@mock_aws
def test_aws_service_integration(app, aws_setup):
    """Test integration with various AWS services."""
    
    # Test with different AWS handlers
    handlers = ["EC2FleetInstant", "SpotFleet"]
    
    for handler in handlers:
        request_data = {
            "template": {
                "templateId": handler,
                "machineCount": 1
            }
        }
        result = app.endpoints["requestMachines"].execute(request_data)
        assert "requestId" in result
        assert "error" not in result

@mock_aws
def test_template_operations(app, aws_setup):
    """Test template-related operations."""
    
    # Get available templates
    templates = app.endpoints["getAvailableTemplates"].execute()
    assert "templates" in templates
    assert len(templates["templates"]) > 0

    # Get template details
    template_id = templates["templates"][0]["templateId"]
    template_data = app.endpoints["getAvailableTemplates"].execute(long=True)
    template = next(t for t in template_data["templates"] if t["templateId"] == template_id)
    assert "imageId" in template
    assert "securityGroupIds" in template

@mock_aws
def test_return_requests(app, aws_setup):
    """Test return request functionality."""
    
    # First create and provision machines
    request_data = {
        "template": {
            "templateId": "EC2FleetInstant",
            "machineCount": 2
        }
    }
    request_result = app.endpoints["requestMachines"].execute(request_data)
    request_id = request_result["requestId"]

    # Wait for machines to be ready
    max_attempts = 10
    attempts = 0
    while attempts < max_attempts:
        status_result = app.endpoints["getRequestStatus"].execute(
            {"requests": [{"requestId": request_id}]}
        )
        if status_result["requests"][0]["status"] == "complete":
            break
        attempts += 1
        time.sleep(1)

    # Get return requests
    return_requests = app.endpoints["getReturnRequests"].execute()
    assert "requests" in return_requests

    # Return all machines
    return_result = app.endpoints["requestReturnMachines"].execute(all_flag=True)
    assert "requestId" in return_result

@mock_aws
def test_request_status_monitoring(app, aws_setup):
    """Test request status monitoring functionality."""
    
    # Create a request
    request_data = {
        "template": {
            "templateId": "EC2FleetInstant",
            "machineCount": 1
        }
    }
    request_result = app.endpoints["requestMachines"].execute(request_data)
    request_id = request_result["requestId"]

    # Monitor status changes
    statuses_seen = set()
    max_attempts = 10
    attempts = 0

    while attempts < max_attempts:
        status_result = app.endpoints["getRequestStatus"].execute(
            {"requests": [{"requestId": request_id}]}
        )
        status = status_result["requests"][0]["status"]
        statuses_seen.add(status)
        
        if status == "complete":
            break
            
        attempts += 1
        time.sleep(1)

    # Should see at least pending and complete
    assert len(statuses_seen) >= 2
    assert "pending" in statuses_seen
    assert "complete" in statuses_seen

