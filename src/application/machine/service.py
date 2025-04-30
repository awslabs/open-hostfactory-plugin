# src/application/machine/service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from src.domain.machine.machine_repository import MachineRepository
from src.domain.machine.machine_aggregate import Machine
from src.domain.machine.value_objects import MachineId, MachineStatus, PriceType
from src.domain.machine.exceptions import MachineNotFoundError, InvalidMachineStateError
from src.domain.request.value_objects import RequestId
from src.domain.core.common_types import IPAddress
from src.domain.core.events import EventPublisher, ResourceStateChangedEvent
from src.infrastructure.aws.aws_client import AWSClient

class MachineApplicationService:
    """Enhanced application service for machine operations."""

    def __init__(self,
                 machine_repository: MachineRepository,
                 event_publisher: EventPublisher,
                 aws_client: Optional[AWSClient] = None,
                 health_check_interval: int = 300):  # 5 minutes default
        self._repository = machine_repository
        self._event_publisher = event_publisher
        self._aws_client = aws_client
        self._health_check_interval = health_check_interval
        self._logger = logging.getLogger(__name__)

    def register_machine(self, 
                        aws_instance_data: Dict[str, Any],
                        request_id: str,
                        aws_handler: str,
                        resource_id: str) -> Machine:
        """Register a new machine with enhanced validation and monitoring."""
        try:
            # Create machine instance
            machine = Machine(
                machine_id=MachineId(aws_instance_data['InstanceId']),
                request_id=RequestId(request_id),
                name=aws_instance_data.get('PrivateDnsName', ''),
                status=MachineStatus.from_aws_state(aws_instance_data['State']['Name']),
                instance_type=aws_instance_data['InstanceType'],
                private_ip=IPAddress(aws_instance_data['PrivateIpAddress']),
                public_ip=IPAddress(aws_instance_data.get('PublicIpAddress', '')) if 'PublicIpAddress' in aws_instance_data else None,
                aws_handler=aws_handler,
                resource_id=resource_id,
                price_type=PriceType.SPOT if aws_instance_data.get('InstanceLifecycle') == 'spot' else PriceType.ON_DEMAND,
                cloud_host_id=aws_instance_data.get('Placement', {}).get('HostId')
            )

            # Add metadata
            machine.metadata.update({
                'availability_zone': aws_instance_data['Placement']['AvailabilityZone'],
                'subnet_id': aws_instance_data['SubnetId'],
                'vpc_id': aws_instance_data['VpcId'],
                'ami_id': aws_instance_data['ImageId'],
                'ebs_optimized': aws_instance_data.get('EbsOptimized', False),
                'monitoring': aws_instance_data.get('Monitoring', {}).get('State', 'disabled'),
                'tags': {tag['Key']: tag['Value'] for tag in aws_instance_data.get('Tags', [])}
            })

            # Perform initial health check
            self._perform_health_check(machine)

            # Save machine
            self._repository.save(machine)

            # Publish event
            self._event_publisher.publish(
                ResourceStateChangedEvent(
                    resource_id=str(machine.machine_id),
                    resource_type="Machine",
                    old_state="none",
                    new_state=machine.status.value,
                    details=machine.to_dict()
                )
            )

            return machine

        except Exception as e:
            self._logger.error(f"Failed to register machine: {str(e)}")
            raise

    def get_machine(self, machine_id: str) -> Machine:
        """Get machine details with health check."""
        machine = self._repository.find_by_id(MachineId(machine_id))
        if not machine:
            raise MachineNotFoundError(machine_id)

        # Perform health check if needed
        if self._should_perform_health_check(machine):
            self._perform_health_check(machine)
            self._repository.save(machine)

        return machine

    def get_machines_by_request(self, request_id: str) -> List[Machine]:
        """Get all machines for a request with health checks."""
        machines = self._repository.find_by_request_id(request_id)
        
        # Perform health checks if needed
        for machine in machines:
            if self._should_perform_health_check(machine):
                self._perform_health_check(machine)
                self._repository.save(machine)

        return machines

    def get_active_machines(self) -> List[Machine]:
        """Get all active machines with health checks."""
        # Get all machines and filter for running ones at domain level
        machines = [
            machine for machine in self._repository.find_all()
            if machine.status == MachineStatus.RUNNING
        ]
        
        # Perform health checks if needed
        for machine in machines:
            if self._should_perform_health_check(machine):
                self._perform_health_check(machine)
                self._repository.save(machine)

        return machines

    def update_machine_status(self,
                            machine_id: str,
                            new_status: MachineStatus,
                            reason: Optional[str] = None) -> Machine:
        """Update machine status with validation and event publishing."""
        try:
            machine = self.get_machine(machine_id)
            old_status = machine.status
            
            machine.update_status(new_status, reason)
            self._repository.save(machine)

            # Publish event
            self._event_publisher.publish(
                ResourceStateChangedEvent(
                    resource_id=str(machine_id),
                    resource_type="Machine",
                    old_state=old_status.value,
                    new_state=new_status.value,
                    details={'reason': reason} if reason else None
                )
            )

            return machine

        except Exception as e:
            self._logger.error(f"Failed to update machine status: {str(e)}")
            raise

    def mark_machine_as_returned(self, machine_id: str, return_id: str) -> Machine:
        """Mark machine as returned with cleanup."""
        try:
            machine = self.get_machine(machine_id)
            machine.mark_as_returned(return_id)
            
            # Perform cleanup tasks
            self._cleanup_machine_resources(machine)
            
            self._repository.save(machine)

            # Publish event
            self._event_publisher.publish(
                ResourceStateChangedEvent(
                    resource_id=str(machine_id),
                    resource_type="Machine",
                    old_state="active",
                    new_state="returned",
                    details={'return_id': return_id}
                )
            )

            return machine

        except Exception as e:
            self._logger.error(f"Failed to mark machine as returned: {str(e)}")
            raise

    def _should_perform_health_check(self, machine: Machine) -> bool:
        """Determine if health check should be performed."""
        if not machine.is_running:
            return False

        last_check = machine.metadata.get('last_health_check')
        if not last_check:
            return True

        last_check_time = datetime.fromisoformat(last_check)
        return (datetime.utcnow() - last_check_time).total_seconds() > self._health_check_interval

    def _perform_health_check(self, machine: Machine) -> None:
        """Perform comprehensive health check on machine."""
        try:
            if not self._aws_client:
                return

            # Get instance status
            status = self._aws_client.ec2_client.describe_instance_status(
                InstanceIds=[str(machine.machine_id)]
            )

            if not status['InstanceStatuses']:
                machine.update_health_check('system', False, {
                    'reason': 'Instance not found'
                })
                return

            instance_status = status['InstanceStatuses'][0]

            # Check system status
            system_status = instance_status['SystemStatus']['Status'] == 'ok'
            machine.update_health_check('system', system_status, {
                'status': instance_status['SystemStatus']['Status'],
                'details': instance_status['SystemStatus'].get('Details', [])
            })

            # Check instance status
            instance_health = instance_status['InstanceStatus']['Status'] == 'ok'
            machine.update_health_check('instance', instance_health, {
                'status': instance_status['InstanceStatus']['Status'],
                'details': instance_status['InstanceStatus'].get('Details', [])
            })

            # Check CloudWatch metrics
            metrics = self._get_cloudwatch_metrics(machine)
            machine.update_health_check('metrics', 
                all(metric['Status'] == 'ok' for metric in metrics),
                {'metrics': metrics}
            )

            # Update last check timestamp
            machine.metadata['last_health_check'] = datetime.utcnow().isoformat()

        except Exception as e:
            self._logger.warning(f"Failed to perform health check: {str(e)}")
            machine.update_health_check('system', False, {
                'error': str(e)
            })

    def _get_cloudwatch_metrics(self, machine: Machine) -> List[Dict[str, Any]]:
        """Get CloudWatch metrics for machine."""
        try:
            if not self._aws_client:
                return []

            metrics = []
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=5)

            # CPU Utilization
            cpu = self._aws_client.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': str(machine.machine_id)}],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average']
            )
            metrics.append({
                'Name': 'CPUUtilization',
                'Value': cpu['Datapoints'][0]['Average'] if cpu['Datapoints'] else None,
                'Status': 'ok' if cpu['Datapoints'] else 'insufficient_data'
            })

            # Status Check Failed
            status_check = self._aws_client.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='StatusCheckFailed',
                Dimensions=[{'Name': 'InstanceId', 'Value': str(machine.machine_id)}],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Maximum']
            )
            metrics.append({
                'Name': 'StatusCheckFailed',
                'Value': status_check['Datapoints'][0]['Maximum'] if status_check['Datapoints'] else None,
                'Status': 'ok' if status_check['Datapoints'] and status_check['Datapoints'][0]['Maximum'] == 0 else 'failed'
            })

            return metrics

        except Exception as e:
            self._logger.warning(f"Failed to get CloudWatch metrics: {str(e)}")
            return []

    def _cleanup_machine_resources(self, machine: Machine) -> None:
        """Clean up AWS resources associated with machine."""
        try:
            if not self._aws_client:
                return

            # Detach and delete EBS volumes
            volumes = self._aws_client.ec2_client.describe_volumes(
                Filters=[{'Name': 'attachment.instance-id', 'Value': [str(machine.machine_id)]}]
            )
            for volume in volumes['Volumes']:
                if volume['State'] == 'in-use':
                    self._aws_client.ec2_client.detach_volume(VolumeId=volume['VolumeId'])
                    self._aws_client.ec2_client.delete_volume(VolumeId=volume['VolumeId'])

            # Delete network interfaces
            nics = self._aws_client.ec2_client.describe_network_interfaces(
                Filters=[{'Name': 'attachment.instance-id', 'Value': [str(machine.machine_id)]}]
            )
            for nic in nics['NetworkInterfaces']:
                if nic['Status'] == 'in-use':
                    self._aws_client.ec2_client.detach_network_interface(
                        AttachmentId=nic['Attachment']['AttachmentId']
                    )
                    self._aws_client.ec2_client.delete_network_interface(
                        NetworkInterfaceId=nic['NetworkInterfaceId']
                    )

        except Exception as e:
            self._logger.warning(f"Failed to cleanup machine resources: {str(e)}")

    def cleanup_terminated_machines(self, age_hours: int = 24) -> None:
        """Clean up old terminated machines."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=age_hours)
            terminated_machines = [
                machine for machine in self._repository.find_by_status(MachineStatus.TERMINATED)
                if machine.terminated_time and machine.terminated_time < cutoff_time
            ]

            for machine in terminated_machines:
                self._repository.delete(machine.machine_id)
                self._logger.info(f"Cleaned up terminated machine: {machine.machine_id}")

        except Exception as e:
            self._logger.error(f"Failed to cleanup terminated machines: {str(e)}")
            raise

    def format_machine_response(self, machine: Machine, long: bool = False) -> Dict[str, Any]:
        """Format machine for API response with enhanced information."""
        response = machine.to_dict()
        
        if long and self._aws_client:
            try:
                # Add CloudWatch metrics
                response['metrics'] = self._get_cloudwatch_metrics(machine)
                
                # Add cost information
                response['cost'] = self._get_machine_cost(machine)
                
                # Add detailed instance information
                instance_info = self._aws_client.ec2_client.describe_instances(
                    InstanceIds=[str(machine.machine_id)]
                )['Reservations'][0]['Instances'][0]
                
                response['aws_details'] = {
                    'placement': instance_info['Placement'],
                    'network': {
                        'vpc_id': instance_info['VpcId'],
                        'subnet_id': instance_info['SubnetId'],
                        'security_groups': instance_info['SecurityGroups']
                    },
                    'block_devices': instance_info['BlockDeviceMappings'],
                    'ebs_optimized': instance_info['EbsOptimized'],
                    'monitoring': instance_info['Monitoring'],
                    'iam_instance_profile': instance_info.get('IamInstanceProfile', {})
                }
                
            except Exception as e:
                self._logger.warning(f"Failed to get additional AWS info: {str(e)}")
        
        return response

    def _get_machine_cost(self, machine: Machine) -> Dict[str, Any]:
        """Calculate machine cost information."""
        try:
            if not self._aws_client:
                return {}

            end_time = datetime.utcnow()
            start_time = machine.launch_time

            cost_data = self._aws_client.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_time.strftime('%Y-%m-%d'),
                    'End': end_time.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                Filter={
                    'Dimensions': {
                        'Key': 'RESOURCE_ID',
                        'Values': [str(machine.machine_id)]
                    }
                }
            )

            return {
                'start_date': start_time.isoformat(),
                'end_date': end_time.isoformat(),
                'total_cost': sum(
                    float(result['Total']['UnblendedCost']['Amount'])
                    for result in cost_data['ResultsByTime']
                ),
                'currency': cost_data['ResultsByTime'][0]['Total']['UnblendedCost']['Unit'],
                'daily_costs': [
                    {
                        'date': result['TimePeriod']['Start'],
                        'cost': float(result['Total']['UnblendedCost']['Amount'])
                    }
                    for result in cost_data['ResultsByTime']
                ]
            }

        except Exception as e:
            self._logger.warning(f"Failed to get machine cost: {str(e)}")
            return {}