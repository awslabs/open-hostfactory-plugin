# src/domain/machine/machine_service.py

from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from src.domain.machine.machine_aggregate import Machine
from src.domain.machine.value_objects import (
    MachineId, MachineStatus, PriceType, 
    MachineConfiguration, MachineEvent, HealthCheck
)
from src.domain.machine.exceptions import (
    MachineNotFoundError, InvalidMachineStateError, 
    MachineValidationError
)
from src.domain.request.value_objects import RequestId
from src.domain.core.events import EventPublisher
from src.infrastructure.aws.aws_client import AWSClient

class MachineService:
    """Domain service for machine operations."""

    def __init__(self, 
                 machine_repository,
                 event_publisher: Optional[EventPublisher] = None,
                 aws_client: Optional[AWSClient] = None):
        self._repository = machine_repository
        self._event_publisher = event_publisher
        self._aws_client = aws_client
        self._logger = logging.getLogger(__name__)

    def register_machine(self, 
                        aws_instance_data: Dict[str, Any],
                        request_id: str,
                        aws_handler: str,
                        resource_id: str) -> Machine:
        """Register a new machine from AWS instance data."""
        try:
            # Create machine instance
            machine = Machine(
                machine_id=MachineId(aws_instance_data['InstanceId']),
                request_id=RequestId(request_id),
                name=aws_instance_data.get('PrivateDnsName', ''),
                status=MachineStatus.from_aws_state(aws_instance_data['State']['Name']),
                instance_type=aws_instance_data['InstanceType'],
                private_ip=aws_instance_data['PrivateIpAddress'],
                public_ip=aws_instance_data.get('PublicIpAddress'),
                aws_handler=aws_handler,
                resource_id=resource_id,
                price_type=PriceType.SPOT if aws_instance_data.get('InstanceLifecycle') == 'spot' 
                          else PriceType.ON_DEMAND,
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
            if self._event_publisher:
                self._event_publisher.publish_machine_created(machine)

            return machine

        except Exception as e:
            self._logger.error(f"Failed to register machine: {str(e)}")
            raise MachineValidationError(
                aws_instance_data.get('InstanceId', 'unknown'),
                str(e)
            )

    def get_machine(self, machine_id: str) -> Machine:
        """Get machine by ID with health check."""
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
        machines = self._repository.find_by_status(MachineStatus.RUNNING)
        
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
        machine = self.get_machine(machine_id)
        
        if not machine.status.can_transition_to(new_status):
            raise InvalidMachineStateError(
                str(machine.machine_id),
                machine.status.value,
                new_status.value
            )

        machine.update_status(new_status, reason)
        self._repository.save(machine)

        if self._event_publisher:
            self._event_publisher.publish_machine_status_changed(
                machine_id=machine_id,
                old_status=machine.status,
                new_status=new_status,
                reason=reason
            )

        return machine

    def mark_machine_as_returned(self, machine_id: str, return_id: str) -> Machine:
        """Mark machine as returned with cleanup."""
        machine = self.get_machine(machine_id)
        
        if not machine.status.can_transition_to(MachineStatus.RETURNED):
            raise InvalidMachineStateError(
                str(machine.machine_id),
                machine.status.value,
                MachineStatus.RETURNED.value
            )

        # Perform cleanup tasks
        self._cleanup_machine_resources(machine)
        
        machine.mark_as_returned(return_id)
        self._repository.save(machine)

        if self._event_publisher:
            self._event_publisher.publish_machine_returned(
                machine_id=machine_id,
                return_id=return_id
            )

        return machine

    def update_machine_health(self,
                            machine_id: str,
                            check_type: str,
                            status: bool,
                            details: Optional[Dict[str, Any]] = None) -> Machine:
        """Update machine health check status."""
        machine = self.get_machine(machine_id)
        
        health_check = HealthCheck(
            check_type=check_type,
            status=status,
            timestamp=datetime.utcnow(),
            details=details
        )
        
        machine.update_health_check(health_check)
        self._repository.save(machine)
        
        if not status and self._event_publisher:
            self._event_publisher.publish_machine_health_degraded(
                machine_id=machine_id,
                check_type=check_type,
                details=details
            )
        
        return machine

    def format_machine_response(self, machine: Machine, long: bool = False) -> Dict[str, Any]:
        """Format machine for API response with enhanced information."""
        response = machine.to_dict(long=long)
        
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

    def cleanup_terminated_machines(self, age_hours: int = 24) -> None:
        """Clean up old terminated machines."""
        try:
            self._repository.cleanup_terminated_machines(age_hours)
        except Exception as e:
            self._logger.error(f"Failed to cleanup terminated machines: {str(e)}")
            raise

    def _should_perform_health_check(self, machine: Machine) -> bool:
        """Determine if health check should be performed."""
        if not machine.is_running:
            return False

        last_check = machine.metadata.get('last_health_check')
        if not last_check:
            return True

        last_check_time = datetime.fromisoformat(last_check)
        return (datetime.utcnow() - last_check_time).total_seconds() > 300  # 5 minutes

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