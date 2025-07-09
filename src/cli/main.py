"""
Main CLI module with argument parsing and command execution.

This module provides the main CLI interface including:
- Command line argument parsing
- Command routing and execution
- Integration with application services
"""
import os
import sys
import argparse
import logging
from typing import Optional, Dict, Any

from src.domain.request.value_objects import RequestStatus
from src.domain.base.exceptions import DomainException
from src.infrastructure.logging.logger import get_logger
from src.cli.formatters import format_output
from src.cli.completion import generate_bash_completion, generate_zsh_completion


def parse_args() -> argparse.Namespace:
    """Parse command line arguments with modern resource-action structure."""
    
    # Main parser with global options
    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        description="Open Host Factory Plugin - Cloud resource management for IBM Symphony",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s templates list                    # List all templates
  %(prog)s templates list --legacy           # List in legacy format
  %(prog)s templates list --format table     # Display as table
  %(prog)s machines create template-id 5     # Create 5 machines
  %(prog)s requests list --status pending    # List pending requests
  
For more information, visit: https://github.com/aws-samples/open-hostfactory-plugin
        """
    )
    
    # Global options
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], 
                       default='INFO', help='Set logging level')
    parser.add_argument('--format', choices=['json', 'yaml', 'table', 'list'], 
                       default='json', help='Output format')
    parser.add_argument('--output', help='Output file (default: stdout)')
    parser.add_argument('--quiet', action='store_true', help='Suppress non-essential output')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without executing')
    parser.add_argument('--completion', choices=['bash', 'zsh'], help='Generate shell completion script')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0')
    
    # Resource subparsers
    subparsers = parser.add_subparsers(dest='resource', help='Available resources')
    
    # Templates resource
    templates_parser = subparsers.add_parser('templates', help='Manage compute templates')
    templates_subparsers = templates_parser.add_subparsers(dest='action', help='Template actions')
    
    # Templates list
    templates_list = templates_subparsers.add_parser('list', help='List all templates')
    templates_list.add_argument('--provider-api', help='Filter by provider API type')
    templates_list.add_argument('--legacy', action='store_true', 
                               help='Use legacy camelCase field names for IBM Symphony compatibility')
    templates_list.add_argument('--long', action='store_true', 
                               help='Include detailed configuration fields')
    templates_list.add_argument('--format', choices=['json', 'yaml', 'table', 'list'], 
                               help='Output format')
    
    # Templates show
    templates_show = templates_subparsers.add_parser('show', help='Show template details')
    templates_show.add_argument('template_id', help='Template ID to show')
    templates_show.add_argument('--format', choices=['json', 'yaml', 'table', 'list'], 
                               help='Output format')
    templates_show.add_argument('--legacy', action='store_true', 
                               help='Use legacy camelCase field names')
    
    # Templates create
    templates_create = templates_subparsers.add_parser('create', help='Create new template')
    templates_create.add_argument('--file', required=True, help='Template configuration file')
    templates_create.add_argument('--validate-only', action='store_true', 
                                 help='Only validate, do not create')
    
    # Templates update
    templates_update = templates_subparsers.add_parser('update', help='Update existing template')
    templates_update.add_argument('template_id', help='Template ID to update')
    templates_update.add_argument('--file', required=True, help='Updated template configuration file')
    
    # Templates delete
    templates_delete = templates_subparsers.add_parser('delete', help='Delete template')
    templates_delete.add_argument('template_id', help='Template ID to delete')
    templates_delete.add_argument('--force', action='store_true', help='Force deletion without confirmation')
    
    # Templates validate
    templates_validate = templates_subparsers.add_parser('validate', help='Validate template')
    templates_validate.add_argument('--file', required=True, help='Template file to validate')
    
    # Machines resource
    machines_parser = subparsers.add_parser('machines', help='Manage compute instances')
    machines_subparsers = machines_parser.add_subparsers(dest='action', help='Machine actions')
    
    # Machines list
    machines_list = machines_subparsers.add_parser('list', help='List all machines')
    machines_list.add_argument('--status', help='Filter by machine status')
    machines_list.add_argument('--template-id', help='Filter by template ID')
    machines_list.add_argument('--format', choices=['json', 'yaml', 'table', 'list'], 
                              help='Output format')
    
    # Machines show
    machines_show = machines_subparsers.add_parser('show', help='Show machine details')
    machines_show.add_argument('machine_id', help='Machine ID to show')
    machines_show.add_argument('--format', choices=['json', 'yaml', 'table', 'list'], 
                              help='Output format')
    
    # Machines create
    machines_create = machines_subparsers.add_parser('create', help='Create new machines')
    machines_create.add_argument('template_id', help='Template ID to use')
    machines_create.add_argument('count', type=int, help='Number of machines to create')
    machines_create.add_argument('--wait', action='store_true', help='Wait for machines to be ready')
    machines_create.add_argument('--timeout', type=int, default=300, help='Wait timeout in seconds')
    
    # Machines terminate
    machines_terminate = machines_subparsers.add_parser('terminate', help='Terminate machines')
    machines_terminate.add_argument('machine_ids', nargs='+', help='Machine IDs to terminate')
    machines_terminate.add_argument('--force', action='store_true', help='Force termination without confirmation')
    
    # Machines status
    machines_status = machines_subparsers.add_parser('status', help='Check machine status')
    machines_status.add_argument('machine_ids', nargs='+', help='Machine IDs to check')
    
    # Requests resource
    requests_parser = subparsers.add_parser('requests', help='Manage provisioning requests')
    requests_subparsers = requests_parser.add_subparsers(dest='action', help='Request actions')
    
    # Requests list
    requests_list = requests_subparsers.add_parser('list', help='List all requests')
    requests_list.add_argument('--status', choices=[s.value for s in RequestStatus], 
                              help='Filter by request status')
    requests_list.add_argument('--template-id', help='Filter by template ID')
    requests_list.add_argument('--format', choices=['json', 'yaml', 'table', 'list'], 
                              help='Output format')
    
    # Requests show
    requests_show = requests_subparsers.add_parser('show', help='Show request details')
    requests_show.add_argument('request_id', help='Request ID to show')
    requests_show.add_argument('--format', choices=['json', 'yaml', 'table', 'list'], 
                              help='Output format')
    
    # Requests create
    requests_create = requests_subparsers.add_parser('create', help='Create new request')
    requests_create.add_argument('template_id', help='Template ID to use')
    requests_create.add_argument('count', type=int, help='Number of machines to request')
    requests_create.add_argument('--priority', type=int, help='Request priority')
    requests_create.add_argument('--wait', action='store_true', help='Wait for request completion')
    
    # Requests cancel
    requests_cancel = requests_subparsers.add_parser('cancel', help='Cancel request')
    requests_cancel.add_argument('request_id', help='Request ID to cancel')
    requests_cancel.add_argument('--force', action='store_true', help='Force cancellation')
    
    # Requests status
    requests_status = requests_subparsers.add_parser('status', help='Check request status')
    requests_status.add_argument('request_ids', nargs='+', help='Request IDs to check')
    
    # System resource
    system_parser = subparsers.add_parser('system', help='System operations')
    system_subparsers = system_parser.add_subparsers(dest='action', help='System actions')
    
    # System status
    system_status = system_subparsers.add_parser('status', help='Show system status')
    system_status.add_argument('--format', choices=['json', 'yaml', 'table', 'list'], 
                              help='Output format')
    
    # System health
    system_health = system_subparsers.add_parser('health', help='Run health check')
    system_health.add_argument('--detailed', action='store_true', help='Show detailed health information')
    
    # System metrics
    system_metrics = system_subparsers.add_parser('metrics', help='Show system metrics')
    system_metrics.add_argument('--format', choices=['json', 'yaml', 'table', 'list'], 
                                help='Output format')
    
    # Config resource
    config_parser = subparsers.add_parser('config', help='Configuration management')
    config_subparsers = config_parser.add_subparsers(dest='action', help='Config actions')
    
    # Config show
    config_show = config_subparsers.add_parser('show', help='Show configuration')
    config_show.add_argument('--format', choices=['json', 'yaml', 'table', 'list'], 
                            help='Output format')
    
    # Config set
    config_set = config_subparsers.add_parser('set', help='Set configuration value')
    config_set.add_argument('key', help='Configuration key')
    config_set.add_argument('value', help='Configuration value')
    
    # Config get
    config_get = config_subparsers.add_parser('get', help='Get configuration value')
    config_get.add_argument('key', help='Configuration key')
    
    # Config validate
    config_validate = config_subparsers.add_parser('validate', help='Validate configuration')
    config_validate.add_argument('--file', help='Configuration file to validate')
    
    return parser.parse_args()


def execute_command(args, app) -> Dict[str, Any]:
    """Execute the appropriate command handler."""
    handler_key = (args.resource, args.action)
    
    # Import command handlers here to avoid circular imports
    from src.interface.command_handlers import (
        GetAvailableTemplatesCLIHandler,
        GetRequestStatusCLIHandler,
        RequestMachinesCLIHandler,
        GetReturnRequestsCLIHandler,
        RequestReturnMachinesCLIHandler,
        MigrateRepositoryCLIHandler,
        GetProviderHealthCLIHandler,
        ListAvailableProvidersCLIHandler,
        GetProviderConfigCLIHandler,
        ValidateProviderConfigCLIHandler,
        ReloadProviderConfigCLIHandler,
        MigrateProviderConfigCLIHandler,
        SelectProviderStrategyCLIHandler,
        ExecuteProviderOperationCLIHandler,
        GetProviderMetricsCLIHandler
    )
    from src.interface.serve_command_handler import ServeCommandHandler
    
    # Command handler mapping
    COMMAND_HANDLERS = {
        # Templates
        ('templates', 'list'): GetAvailableTemplatesCLIHandler,
        ('templates', 'show'): GetAvailableTemplatesCLIHandler,
        ('templates', 'validate'): GetAvailableTemplatesCLIHandler,
        ('templates', 'reload'): GetAvailableTemplatesCLIHandler,
        
        # Machines
        ('machines', 'request'): RequestMachinesCLIHandler,
        ('machines', 'return'): RequestReturnMachinesCLIHandler,
        ('machines', 'list'): RequestMachinesCLIHandler,
        ('machines', 'show'): RequestMachinesCLIHandler,
        ('machines', 'terminate'): RequestReturnMachinesCLIHandler,
        
        # Requests
        ('requests', 'status'): GetRequestStatusCLIHandler,
        ('requests', 'list'): GetReturnRequestsCLIHandler,
        ('requests', 'show'): GetRequestStatusCLIHandler,
        ('requests', 'cancel'): GetRequestStatusCLIHandler,
        ('requests', 'retry'): GetRequestStatusCLIHandler,
        
        # Providers
        ('providers', 'health'): GetProviderHealthCLIHandler,
        ('providers', 'list'): ListAvailableProvidersCLIHandler,
        ('providers', 'show'): ListAvailableProvidersCLIHandler,
        ('providers', 'select'): SelectProviderStrategyCLIHandler,
        ('providers', 'exec'): ExecuteProviderOperationCLIHandler,
        ('providers', 'metrics'): GetProviderMetricsCLIHandler,
        
        # Storage commands
        ('storage', 'list'): None,  # TODO: Implement
        ('storage', 'show'): None,  # TODO: Implement
        ('storage', 'validate'): None,  # TODO: Implement
        ('storage', 'test'): None,  # TODO: Implement
        ('storage', 'migrate'): MigrateRepositoryCLIHandler,  # Reuse existing
        ('storage', 'health'): None,  # TODO: Implement
        ('storage', 'metrics'): None,  # TODO: Implement
        
        # System (TODO: Implement)
        ('system', 'status'): None,  # TODO: Implement
        ('system', 'info'): None,  # TODO: Implement
        ('system', 'health'): None,  # TODO: Implement
        ('system', 'serve'): ServeCommandHandler,  # REST API server
        
        # Config (TODO: Implement)
        ('config', 'show'): GetProviderConfigCLIHandler,  # Reuse existing
        ('config', 'validate'): ValidateProviderConfigCLIHandler,  # Reuse existing
        ('config', 'reload'): ReloadProviderConfigCLIHandler,  # Reuse existing
    }
    
    if handler_key not in COMMAND_HANDLERS:
        raise ValueError(f"Unknown command: {args.resource} {args.action}")
    
    handler_class = COMMAND_HANDLERS[handler_key]
    
    if handler_class is None:
        raise NotImplementedError(f"Command not yet implemented: {args.resource} {args.action}")
    
    # Instantiate handler - check if it accepts bus parameters
    import inspect

    from src.infrastructure.logging.logger import get_logger
    
    handler_signature = inspect.signature(handler_class.__init__)
    handler_params = list(handler_signature.parameters.keys())
    
    # Check if handler has complex dependencies (more than just buses)
    if 'format_service' in handler_params:
        # Handler with complex dependencies - use DI container
        from src.infrastructure.di.container import get_container
        container = get_container()
        handler = container.get(handler_class)
    elif 'query_bus' in handler_params and 'command_bus' in handler_params:
        # Modern handler that accepts bus parameters
        handler = handler_class(
            query_bus=app.get_query_bus(),
            command_bus=app.get_command_bus(),
            logger=get_logger(__name__)
        )
    else:
        # Legacy handler that uses container internally
        handler = handler_class()
    
    # Convert modern args to legacy format for existing handlers
    legacy_args = convert_to_legacy_args(args)
    
    # Handle legacy flag for template handlers
    if hasattr(args, 'legacy') and args.legacy and hasattr(handler, 'handle_with_legacy_format'):
        return handler.handle_with_legacy_format(legacy_args)
    else:
        return handler.handle(legacy_args)


def convert_to_legacy_args(args) -> argparse.Namespace:
    """
    Convert new CLI args to legacy format for backward compatibility.
    
    This function maps the new resource-action structure to the legacy
    flat argument structure that existing handlers expect.
    """
    # Create a new namespace with legacy structure
    legacy_args = argparse.Namespace()
    
    # Copy all existing attributes
    for attr, value in vars(args).items():
        setattr(legacy_args, attr, value)
    
    # Map resource-action to legacy command structure
    if args.resource == 'templates':
        if args.action == 'list':
            legacy_args.command = 'listTemplates'
        elif args.action == 'show':
            legacy_args.command = 'getTemplate'
            legacy_args.template_id = getattr(args, 'template_id', None)
        elif args.action == 'create':
            legacy_args.command = 'createTemplate'
        elif args.action == 'update':
            legacy_args.command = 'updateTemplate'
        elif args.action == 'delete':
            legacy_args.command = 'deleteTemplate'
        elif args.action == 'validate':
            legacy_args.command = 'validateTemplate'
    
    elif args.resource == 'machines':
        if args.action == 'list':
            legacy_args.command = 'listMachines'
        elif args.action == 'show':
            legacy_args.command = 'getMachine'
        elif args.action == 'create':
            legacy_args.command = 'requestMachines'
        elif args.action == 'terminate':
            legacy_args.command = 'terminateMachines'
        elif args.action == 'status':
            legacy_args.command = 'getMachineStatus'
    
    elif args.resource == 'requests':
        if args.action == 'list':
            legacy_args.command = 'listRequests'
        elif args.action == 'show':
            legacy_args.command = 'getRequest'
        elif args.action == 'create':
            legacy_args.command = 'createRequest'
        elif args.action == 'cancel':
            legacy_args.command = 'cancelRequest'
        elif args.action == 'status':
            legacy_args.command = 'getRequestStatus'
    
    return legacy_args


def main() -> None:
    """Main CLI entry point."""
    try:
        args = parse_args()
        
        # Handle completion generation
        if args.completion:
            if args.completion == 'bash':
                print(generate_bash_completion())
            elif args.completion == 'zsh':
                print(generate_zsh_completion())
            return
        
        # Configure logging - let the application's proper logging system handle everything
        log_level = getattr(logging, args.log_level.upper())
        
        logger = get_logger(__name__)
        
        # Validate required arguments
        if not args.resource:
            print("Error: No resource specified. Use --help for usage information.")
            sys.exit(1)
        
        if not args.action:
            print(f"Error: No action specified for {args.resource}. Use --help for usage information.")
            sys.exit(1)
        
        # Initialize application
        try:
            from src.bootstrap import create_application
            app = create_application(args.config)
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
        
        # Execute command
        try:
            result = execute_command(args, app)
            
            # Format and output result
            output_format = getattr(args, 'format', None) or args.format
            formatted_output = format_output(result, output_format)
            
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(formatted_output)
                if not args.quiet:
                    print(f"Output written to {args.output}")
            else:
                print(formatted_output)
                
        except DomainException as e:
            logger.error(f"Domain error: {e}")
            if not args.quiet:
                print(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            if not args.quiet:
                print(f"Unexpected error: {e}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
