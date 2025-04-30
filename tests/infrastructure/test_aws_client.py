import pytest
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from moto import mock_aws
from src.infrastructure.aws.aws_client import AWSClient
from src.infrastructure.exceptions import InfrastructureError

@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    """Mocked AWS Credentials for moto."""
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    monkeypatch.setenv('AWS_SECURITY_TOKEN', 'testing')
    monkeypatch.setenv('AWS_SESSION_TOKEN', 'testing')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')

@pytest.fixture
def aws_client():
    """Create AWS client with test configuration."""
    config = {
        'AWS_REGION': 'us-east-1',
        'AWS_REQUEST_RETRY_ATTEMPTS': 3,
        'AWS_CONNECTION_TIMEOUT_MS': 1000
    }
    with mock_aws():
        return AWSClient(region_name='us-east-1', config=config)

@pytest.fixture
def ec2_instance(aws_client):
    """Create a test EC2 instance."""
    with mock_aws():
        # Create VPC
        vpc = aws_client.ec2_client.create_vpc(CidrBlock='10.0.0.0/16')
        vpc_id = vpc['Vpc']['VpcId']

        # Create Subnet
        subnet = aws_client.ec2_client.create_subnet(
            VpcId=vpc_id,
            CidrBlock='10.0.0.0/24'
        )

        # Create Security Group
        sg = aws_client.ec2_client.create_security_group(
            GroupName='test-sg',
            Description='Test security group',
            VpcId=vpc_id
        )

        # Launch instance
        response = aws_client.ec2_client.run_instances(
            ImageId='ami-12345678',
            InstanceType='t2.micro',
            MinCount=1,
            MaxCount=1,
            SubnetId=subnet['Subnet']['SubnetId'],
            SecurityGroupIds=[sg['GroupId']]
        )
        instance_id = response['Instances'][0]['InstanceId']

        # Wait for instance to be running
        aws_client.ec2_client.get_waiter('instance_running').wait(
            InstanceIds=[instance_id]
        )

        return instance_id

@mock_aws
def test_describe_instances(aws_client, ec2_instance):
    # Act
    instances = aws_client.describe_instances([ec2_instance])

    # Assert
    assert len(instances) == 1
    assert instances[0]['InstanceId'] == ec2_instance
    assert instances[0]['State']['Name'] in ['pending', 'running']

@mock_aws
def test_terminate_instances(aws_client, ec2_instance):
    # Act
    aws_client.terminate_instances([ec2_instance])

    # Assert
    response = aws_client.ec2_client.describe_instances(InstanceIds=[ec2_instance])
    state = response['Reservations'][0]['Instances'][0]['State']['Name']
    assert state in ['shutting-down', 'terminated']

@mock_aws
def test_create_tags(aws_client, ec2_instance):
    # Arrange
    tags = {'Name': 'test-instance', 'Environment': 'testing'}

    # Act
    aws_client.create_tags([ec2_instance], tags)

    # Assert
    response = aws_client.ec2_client.describe_instances(InstanceIds=[ec2_instance])
    instance_tags = {
        tag['Key']: tag['Value']
        for tag in response['Reservations'][0]['Instances'][0]['Tags']
    }
    assert instance_tags == tags

@mock_aws
def test_describe_instances_error(aws_client):
    # Act & Assert
    with pytest.raises(InfrastructureError) as exc:
        aws_client.describe_instances(['i-nonexistent'])
    assert "Failed to describe instances" in str(exc.value)

@mock_aws
def test_aws_client_with_proxy_config():
    # Arrange
    config = {
        'AWS_PROXY_HOST': 'proxy.example.com',
        'AWS_PROXY_PORT': 8080,
        'AWS_REQUEST_RETRY_ATTEMPTS': 3,
        'AWS_CONNECTION_TIMEOUT_MS': 1000
    }

    # Act
    client = AWSClient(region_name='us-east-1', config=config)

    # Assert
    assert client.config.retries['max_attempts'] == 3
    assert client.config.connect_timeout == 1

@mock_aws
def test_aws_client_initialization():
    # Act
    client = AWSClient(region_name='us-east-1')

    # Assert
    assert client.region_name == 'us-east-1'
    assert client.ec2_client is not None
    assert client.ec2_resource is not None
    assert client.autoscaling_client is not None

@mock_aws
def test_describe_launch_template(aws_client):
    # Arrange
    response = aws_client.ec2_client.create_launch_template(
        LaunchTemplateName='test-template',
        LaunchTemplateData={
            'ImageId': 'ami-12345678',
            'InstanceType': 't2.micro'
        }
    )
    template_id = response['LaunchTemplate']['LaunchTemplateId']

    # Act
    template = aws_client.describe_launch_template(template_id)

    # Assert
    assert template['LaunchTemplateId'] == template_id
    assert template['LaunchTemplateName'] == 'test-template'

@mock_aws
def test_describe_launch_template_error(aws_client):
    # Act & Assert
    with pytest.raises(InfrastructureError) as exc:
        aws_client.describe_launch_template('lt-nonexistent')
    assert "Failed to describe launch template" in str(exc.value)

@mock_aws
def test_create_tags_error(aws_client):
    # Act & Assert
    with pytest.raises(InfrastructureError) as exc:
        aws_client.create_tags(['i-nonexistent'], {'Key': 'Value'})
    assert "Failed to create tags" in str(exc.value)

@mock_aws
def test_terminate_instances_error(aws_client):
    # Act & Assert
    with pytest.raises(InfrastructureError) as exc:
        aws_client.terminate_instances(['i-nonexistent'])
    assert "Failed to terminate instances" in str(exc.value)

@mock_aws
def test_aws_client_with_retry_config():
    # Arrange
    config = {
        'AWS_REQUEST_RETRY_ATTEMPTS': 5,
        'AWS_CONNECTION_TIMEOUT_MS': 2000
    }

    # Act
    client = AWSClient(region_name='us-east-1', config=config)

    # Assert
    assert client.config.retries['max_attempts'] == 5
    assert client.config.connect_timeout == 2

@mock_aws
def test_aws_client_default_config():
    # Act
    client = AWSClient(region_name='us-east-1', config={})

    # Assert
    assert client.config.retries['max_attempts'] == 3  # Default value
    assert client.config.connect_timeout == 1  # Default value

@mock_aws
def test_describe_instances_with_filters(aws_client, ec2_instance):
    # Arrange
    aws_client.create_tags([ec2_instance], {'Environment': 'test'})

    # Act
    instances = aws_client.describe_instances(
        [ec2_instance],
        Filters=[{'Name': 'tag:Environment', 'Values': ['test']}]
    )

    # Assert
    assert len(instances) == 1
    assert instances[0]['InstanceId'] == ec2_instance

@mock_aws
def test_describe_instances_batch(aws_client):
    # Arrange
    instance_ids = []
    for _ in range(3):
        response = aws_client.ec2_client.run_instances(
            ImageId='ami-12345678',
            InstanceType='t2.micro',
            MinCount=1,
            MaxCount=1
        )
        instance_ids.append(response['Instances'][0]['InstanceId'])

    # Act
    instances = aws_client.describe_instances(instance_ids)

    # Assert
    assert len(instances) == 3
    assert all(i['InstanceId'] in instance_ids for i in instances)
