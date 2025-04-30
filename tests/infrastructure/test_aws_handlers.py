import pytest
import json
from typing import Dict, Any, Optional, List
import boto3
from moto import mock_aws
from datetime import datetime

from src.infrastructure.aws.ec2_fleet_handler import EC2FleetHandler
from src.infrastructure.aws.spot_fleet_handler import SpotFleetHandler
from src.infrastructure.aws.asg_handler import ASGHandler
from src.infrastructure.aws.run_instances_handler import RunInstancesHandler
from src.domain.request.request_aggregate import Request
from src.domain.request.value_objects import RequestId, RequestType
from src.domain.template.template_aggregate import Template
from src.infrastructure.exceptions import InfrastructureError

@pytest.fixture
def aws_setup(aws_credentials):
    """Setup common AWS resources needed for tests."""
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

        # Create Launch Template
        launch_template = ec2_client.create_launch_template(
            LaunchTemplateName="test-template",
            LaunchTemplateData={
                "ImageId": "ami-12345678",
                "InstanceType": "t2.micro",
                "NetworkInterfaces": [
                    {
                        "DeviceIndex": 0,
                        "SubnetId": subnet_id,
                        "Groups": [sg_id]
                    }
                ]
            }
        )
        launch_template_id = launch_template["LaunchTemplate"]["LaunchTemplateId"]

        yield {
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
            "security_group_id": sg_id,
            "fleet_role_arn": fleet_role_arn,
            "launch_template_id": launch_template_id
        }

@pytest.fixture
def template(aws_setup):
    """Create a test template."""
    return Template.from_dict({
        "templateId": "test-template",
        "awsHandler": "EC2Fleet",
        "maxNumber": 2,
        "attributes": {
            "type": ["String", "X86_64"],
            "ncores": ["Numeric", "2"],
            "ncpus": ["Numeric", "1"],
            "nram": ["Numeric", "4096"]
        },
        "imageId": "ami-12345678",
        "subnetId": aws_setup["subnet_id"],
        "vmType": "t2.micro",
        "securityGroupIds": [aws_setup["security_group_id"]],
        "fleetRole": aws_setup["fleet_role_arn"]
    })

@pytest.fixture
def request_obj(template):
    """Create a test request."""
    return Request.create_acquire_request(
        template_id=template.template_id,
        num_machines=2,
        aws_handler=template.aws_handler
    )

@mock_aws
def test_ec2_fleet_handler_acquire_hosts(aws_client, template, request_obj):
    # Arrange
    handler = EC2FleetHandler(aws_client)

    # Act
    fleet_id = handler.acquire_hosts(request_obj, template)

    # Assert
    assert fleet_id is not None
    fleet_response = aws_client.ec2_client.describe_fleets(FleetIds=[fleet_id])
    assert len(fleet_response["Fleets"]) == 1
    assert fleet_response["Fleets"][0]["TargetCapacitySpecification"]["TotalTargetCapacity"] == 2

@mock_aws
def test_spot_fleet_handler_acquire_hosts(aws_client, template, request_obj, aws_setup):
    # Arrange
    handler = SpotFleetHandler(aws_client)
    template.aws_handler = "SpotFleet"
    template.fleet_role = aws_setup["fleet_role_arn"]
    template.max_spot_price = "0.05"

    # Act
    fleet_id = handler.acquire_hosts(request_obj, template)

    # Assert
    assert fleet_id is not None
    response = aws_client.ec2_client.describe_spot_fleet_requests(
        SpotFleetRequestIds=[fleet_id]
    )
    assert len(response["SpotFleetRequestConfigs"]) == 1

@mock_aws
def test_asg_handler_acquire_hosts(aws_client, template, request_obj):
    # Arrange
    handler = ASGHandler(aws_client)
    template.aws_handler = "ASG"

    # Act
    asg_name = handler.acquire_hosts(request_obj, template)

    # Assert
    assert asg_name is not None
    response = aws_client.autoscaling_client.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name]
    )
    assert len(response["AutoScalingGroups"]) == 1
    assert response["AutoScalingGroups"][0]["DesiredCapacity"] == 2

@mock_aws
def test_run_instances_handler_acquire_hosts(aws_client, template, request_obj):
    # Arrange
    handler = RunInstancesHandler(aws_client)
    template.aws_handler = "RunInstances"

    # Act
    reservation_id = handler.acquire_hosts(request_obj, template)

    # Assert
    assert reservation_id is not None
    response = aws_client.ec2_client.describe_instances(
        Filters=[{"Name": "reservation-id", "Values": [reservation_id]}]
    )
    assert len(response["Reservations"]) == 1
    assert len(response["Reservations"][0]["Instances"]) == 2

@mock_aws
def test_handler_check_status(aws_client, template, request_obj):
    # Arrange
    handler = RunInstancesHandler(aws_client)
    reservation_id = handler.acquire_hosts(request_obj, template)
    request_obj.resource_id = reservation_id

    # Act
    status = handler.check_hosts_status(request_obj)

    # Assert
    assert len(status) == 2
    assert all(i["State"]["Name"] in ["pending", "running"] for i in status)

@mock_aws
def test_handler_release_hosts(aws_client, template, request_obj):
    # Arrange
    handler = RunInstancesHandler(aws_client)
    reservation_id = handler.acquire_hosts(request_obj, template)
    request_obj.resource_id = reservation_id

    # Act
    handler.release_hosts(request_obj)

    # Assert
    response = aws_client.ec2_client.describe_instances(
        Filters=[{"Name": "reservation-id", "Values": [reservation_id]}]
    )
    instances = response["Reservations"][0]["Instances"]
    assert all(i["State"]["Name"] in ["shutting-down", "terminated"] for i in instances)

@mock_aws
def test_handler_error_handling(aws_client, template, request_obj):
    # Arrange
    handler = RunInstancesHandler(aws_client)
    request_obj.resource_id = "invalid-id"

    # Act & Assert
    with pytest.raises(InfrastructureError):
        handler.release_hosts(request_obj)

@mock_aws
def test_ec2_fleet_handler_with_multiple_instance_types(aws_client, template, request_obj):
    # Arrange
    handler = EC2FleetHandler(aws_client)
    template.vm_type = None
    template.vm_types = {"t2.micro": 1, "t2.small": 1}

    # Act
    fleet_id = handler.acquire_hosts(request_obj, template)

    # Assert
    assert fleet_id is not None
    fleet_response = aws_client.ec2_client.describe_fleets(FleetIds=[fleet_id])
    assert len(fleet_response["Fleets"]) == 1

@mock_aws
def test_spot_fleet_handler_with_spot_price(aws_client, template, request_obj, aws_setup):
    # Arrange
    handler = SpotFleetHandler(aws_client)
    template.aws_handler = "SpotFleet"
    template.fleet_role = aws_setup["fleet_role_arn"]
    template.max_spot_price = "0.05"

    # Act
    fleet_id = handler.acquire_hosts(request_obj, template)

    # Assert
    assert fleet_id is not None
    response = aws_client.ec2_client.describe_spot_fleet_requests(
        SpotFleetRequestIds=[fleet_id]
    )
    config = response["SpotFleetRequestConfigs"][0]
    assert "SpotPrice" in config["SpotFleetRequestConfig"]
    assert config["SpotFleetRequestConfig"]["SpotPrice"] == "0.05"

@mock_aws
def test_asg_handler_with_tags(aws_client, template, request_obj):
    # Arrange
    handler = ASGHandler(aws_client)
    template.aws_handler = "ASG"
    template.instance_tags = {"Environment": "test", "Project": "symphony"}

    # Act
    asg_name = handler.acquire_hosts(request_obj, template)

    # Assert
    assert asg_name is not None
    response = aws_client.autoscaling_client.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name]
    )
    tags = response["AutoScalingGroups"][0]["Tags"]
    assert any(t["Key"] == "Environment" and t["Value"] == "test" for t in tags)
    assert any(t["Key"] == "Project" and t["Value"] == "symphony" for t in tags)

@mock_aws
def test_run_instances_handler_with_user_data(aws_client, template, request_obj):
    # Arrange
    handler = RunInstancesHandler(aws_client)
    template.aws_handler = "RunInstances"
    template.user_data = "#!/bin/bash\necho 'Hello, World!'"

    # Act
    reservation_id = handler.acquire_hosts(request_obj, template)

    # Assert
    assert reservation_id is not None
    response = aws_client.ec2_client.describe_instances(
        Filters=[{"Name": "reservation-id", "Values": [reservation_id]}]
    )
    instances = response["Reservations"][0]["Instances"]
    assert len(instances) == 2

@mock_aws
def test_handler_check_status_no_instances(aws_client, template, request_obj):
    # Arrange
    handler = RunInstancesHandler(aws_client)
    request_obj.resource_id = "non-existent"

    # Act
    status = handler.check_hosts_status(request_obj)

    # Assert
    assert len(status) == 0

