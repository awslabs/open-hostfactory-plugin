# src/app.py
import argparse
import json
import sys
import os
from typing import Dict, Any

# Domain imports
from src.domain.template.template_repository import TemplateRepository, FileTemplateRepository
from src.domain.request.request_repository import RequestRepository
from src.domain.machine.machine_repository import MachineRepository

# Application service imports
from src.application.template.service import TemplateApplicationService
from src.application.request.service import RequestApplicationService
from src.application.machine.service import MachineApplicationService

# API endpoint imports
from src.api.get_available_templates import GetAvailableTemplates
from src.api.request_machines import RequestMachines
from src.api.request_return_machines import RequestReturnMachines
from src.api.get_request_status import GetRequestStatus
from src.api.get_return_requests import GetReturnRequests

# Infrastructure imports
from src.infrastructure.aws.aws_client import AWSClient
from src.infrastructure.aws.ec2_fleet_handler import EC2FleetHandler
from src.infrastructure.aws.spot_fleet_handler import SpotFleetHandler
from src.infrastructure.aws.asg_handler import ASGHandler
from src.infrastructure.aws.run_instances_handler import RunInstancesHandler
from src.infrastructure.persistence.repository_factory import RepositoryFactory
from src.infrastructure.event.event_publisher import EventPublisher
from src.infrastructure.exceptions import InfrastructureError

# Helper imports
from src.helpers.logger import setup_logging
from src.helpers.utils import load_json_data
from src.helpers.repository_migrator import RepositoryMigrator

# Configuration imports
from src.config.defaults import ConfigurationManager

class Application:
    """Main application class that handles initialization and routing."""
    
    def __init__(self):
        # Initialize configuration
        self.config_manager = ConfigurationManager()
        self.config = self.config_manager.get_config()

        # Set up logging
        self.logger = setup_logging(self.config)

        # Initialize infrastructure
        self.event_publisher = EventPublisher()
        self.aws_client = self._create_aws_client()
        
        # Initialize repositories
        self.template_repository = FileTemplateRepository()
        self.request_repository = self._create_request_repository()
        self.machine_repository = self._create_machine_repository()

        # Initialize AWS handlers
        self.aws_handlers = self._create_aws_handlers()

        # Initialize application services
        self.template_service = TemplateApplicationService(
            template_repository=self.template_repository,
            event_publisher=self.event_publisher,
            config=self.config

        )
        self.machine_service = MachineApplicationService(
            machine_repository=self.machine_repository,
            event_publisher=self.event_publisher
        )
        self.request_service = RequestApplicationService(
            request_repository=self.request_repository,
            template_service=self.template_service,
            machine_service=self.machine_service,
            aws_handlers=self.aws_handlers,
            aws_client=self.aws_client,
            event_publisher=self.event_publisher
        )

        # Initialize API endpoints
        self.endpoints = {
            "getAvailableTemplates": GetAvailableTemplates(self.template_service),
            "requestMachines": RequestMachines(self.request_service),
            "requestReturnMachines": RequestReturnMachines(self.request_service),
            "getRequestStatus": GetRequestStatus(self.request_service),
            "getReturnRequests": GetReturnRequests(self.request_service)
        }

    def _create_aws_client(self) -> AWSClient:
        """Create AWS client with configuration."""
        try:
            config = self.config
            region = config.get('AWS_REGION')
            self.logger.info(f"Initializing AWS client with region: {region}")
            
            aws_client = AWSClient(
                region_name=region,
                config=config
            )

            # Configure proxy if needed
            if config.get('AWS_PROXY_HOST'):
                aws_client._configure_proxy(config)

            return aws_client
            
        except Exception as e:
            self.logger.error(f"Failed to create AWS client: {str(e)}")
            raise InfrastructureError(f"Failed to create AWS client: {str(e)}")

    def _create_aws_handlers(self) -> Dict[str, Any]:
        """Create AWS handler instances."""
        return {
            "EC2Fleet": EC2FleetHandler(self.aws_client),
            "SpotFleet": SpotFleetHandler(self.aws_client),
            "ASG": ASGHandler(self.aws_client),
            "RunInstances": RunInstancesHandler(self.aws_client)
        }

    def _create_request_repository(self) -> RequestRepository:
        """Create request repository based on configuration."""
        from src.domain.request.request_aggregate import Request
        return RepositoryFactory.create_repository(
            collection_name='requests',
            entity_class=Request,
            config=self.config
        )

    def _create_machine_repository(self) -> MachineRepository:
        """Create machine repository based on configuration."""
        from src.domain.machine.machine_aggregate import Machine
        return RepositoryFactory.create_repository(
            collection_name='machines',
            entity_class=Machine,
            config=self.config
        )

    def _create_template_repository(self) -> TemplateRepository:
        """Create template repository based on configuration."""
        from src.domain.template.template_aggregate import Template
        return RepositoryFactory.create_repository(
            collection_name='templates',
            entity_class=Template,
            config=self.config
        )

    def run(self, args: argparse.Namespace) -> None:
        """
        Run the application with the given arguments.
        
        Args:
            args: Parsed command line arguments
        """
        try:
            # Handle repository migration if requested
            if args.action == "migrateRepository":
                if not (args.source_type and args.target_type):
                    raise ValueError("Both --source-type and --target-type are required for migration")
                
                migrator = RepositoryMigrator(self._load_config())
                result = migrator.migrate(
                    args.source_type,
                    args.target_type,
                    not args.no_backup
                )
                print(json.dumps(result, indent=2))
                return

            # Load input data if provided
            input_data = None
            if args.data or args.file:
                input_data = load_json_data(json_str=args.data, json_file=args.file)

            # Get the appropriate endpoint
            endpoint = self.endpoints.get(args.action)
            if not endpoint:
                raise ValueError(f"Unknown action: {args.action}")

            # Execute the endpoint
            result = endpoint.execute(
                input_data=input_data,
                all_flag=getattr(args, 'all', False),
                long=getattr(args, 'long', False),
                clean=getattr(args, 'clean', False)
            )

            # Print the result
            print(json.dumps(result, indent=2))

        except Exception as e:
            self.logger.error(f"Error executing {args.action}: {e}", exc_info=True)
            print(json.dumps({
                "error": str(e),
                "message": f"Failed to execute {args.action}"
            }, indent=2))
            sys.exit(1)

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="AWS Host Factory Plugin")
    
    # Add action argument
    parser.add_argument(
        "action",
        choices=[
            "getAvailableTemplates",
            "requestMachines",
            "requestReturnMachines",
            "getRequestStatus",
            "getReturnRequests",
            "migrateRepository"
        ],
        help="Action to perform"
    )

    # Add common arguments
    parser.add_argument("--data", help="JSON string input")
    parser.add_argument("-f", "--file", help="Path to JSON file input")
    parser.add_argument("--all", action="store_true", help="Apply to all")
    parser.add_argument("--long", action="store_true", help="Include all details")
    parser.add_argument("--clean", action="store_true", help="Clean up all resources")

    # Add migration-specific arguments
    parser.add_argument(
        "--source-type",
        choices=["json", "sqlite", "dynamodb"],
        help="Source repository type for migration"
    )
    parser.add_argument(
        "--target-type",
        choices=["json", "sqlite", "dynamodb"],
        help="Target repository type for migration"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation during migration"
    )

    args = parser.parse_args()

    # Run the application
    app = Application()
    app.run(args)

if __name__ == "__main__":
    main()
