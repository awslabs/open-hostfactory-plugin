"""
CLI-specific formatting functions for human-readable output.

This module handles presentation formatting for the CLI, including:
- Rich Unicode tables with colors and borders
- ASCII table fallbacks
- List formatting for detailed views
- Field mapping for CLI display
"""
from typing import Any, Dict, List
from src.domain.request.value_objects import RequestStatus


def format_output(data: Any, format_type: str) -> str:
    """Format data according to the specified format type."""
    if format_type == "json":
        import json
        return json.dumps(data, indent=2, default=str)
    elif format_type == "yaml":
        import yaml
        return yaml.dump(data, default_flow_style=False, default_style=None)
    elif format_type == "table":
        return format_table_output(data)
    elif format_type == "list":
        return format_list_output(data)
    else:
        # Default to JSON
        import json
        return json.dumps(data, indent=2, default=str)


def format_table_output(data: Any) -> str:
    """Format data as a table."""
    if isinstance(data, dict) and "templates" in data:
        return format_templates_table(data["templates"])
    elif isinstance(data, dict) and "requests" in data:
        return format_requests_table(data["requests"])
    elif isinstance(data, dict) and "machines" in data:
        return format_machines_table(data["machines"])
    else:
        # Fallback to JSON for unknown data structures
        import json
        return json.dumps(data, indent=2, default=str)


def format_list_output(data: Any) -> str:
    """Format data as a detailed list."""
    if isinstance(data, dict) and "templates" in data:
        return format_templates_list(data["templates"])
    elif isinstance(data, dict) and "requests" in data:
        return format_requests_list(data["requests"])
    elif isinstance(data, dict) and "machines" in data:
        return format_machines_list(data["machines"])
    else:
        # Fallback to JSON for unknown data structures
        import json
        return json.dumps(data, indent=2, default=str)


def get_field_value(data_dict: Dict[str, Any], field_mapping: Dict[str, List[str]], field_key: str, default: str = 'N/A') -> str:
    """
    Get field value from data dictionary using field mapping.
    
    Args:
        data_dict: Dictionary containing the data
        field_mapping: Mapping of logical field names to possible actual field names
        field_key: Logical field name to look up
        default: Default value if field not found
        
    Returns:
        Field value as string, or default if not found
    """
    possible_names = field_mapping.get(field_key, [field_key])
    
    for name in possible_names:
        if name in data_dict:
            value = data_dict[name]
            return str(value) if value is not None else default
    
    return default


def get_template_field_mapping() -> Dict[str, List[str]]:
    """
    Get mapping of logical template field names to possible actual field names.
    Uses Template model as source of truth for field names.
    
    Returns:
        Dictionary mapping logical names to [snake_case, camelCase] variants
    """
    return {
        'id': ['template_id', 'templateId'],
        'name': ['name'],
        'description': ['description'],
        'provider_api': ['provider_api', 'providerApi'],
        'instance_type': ['instance_type', 'vmType'],
        'image_id': ['image_id', 'imageId'],
        'max_instances': ['max_instances', 'maxNumber'],
        'subnet_ids': ['subnet_ids', 'subnetIds'],
        'security_group_ids': ['security_group_ids', 'securityGroupIds'],
        'key_name': ['key_name', 'keyName'],
        'user_data': ['user_data', 'userData'],
        'instance_tags': ['instance_tags', 'instanceTags'],
        'price_type': ['price_type', 'priceType'],
        'max_spot_price': ['max_spot_price', 'maxSpotPrice'],
        'allocation_strategy': ['allocation_strategy', 'allocationStrategy'],
        'fleet_type': ['fleet_type', 'fleetType'],
        'fleet_role': ['fleet_role', 'fleetRole'],
        'created_at': ['created_at', 'createdAt'],
        'updated_at': ['updated_at', 'updatedAt']
    }


def format_templates_table(templates: List[Dict]) -> str:
    """Format templates as a proper table using Rich library."""
    if not templates:
        return "No templates found."
    
    try:
        from rich.table import Table
        from rich.console import Console
        
        # Create Rich table
        table = Table(show_header=True, header_style="bold magenta", show_lines=True)
        table.add_column("ID", style="cyan", width=15)
        table.add_column("Name", style="green", width=15) 
        table.add_column("Provider", style="blue", width=10)
        table.add_column("CPUs", style="yellow", justify="right", width=6)
        table.add_column("RAM (MB)", style="yellow", justify="right", width=10)
        table.add_column("Max Inst", style="red", justify="right", width=8)
        
        field_mapping = get_template_field_mapping()
        
        # Add rows
        for template in templates:
            template_id = get_field_value(template, field_mapping, 'id')
            name = get_field_value(template, field_mapping, 'name')
            provider_api = get_field_value(template, field_mapping, 'provider_api')
            max_instances = get_field_value(template, field_mapping, 'max_instances')
            
            # Handle different formats
            attributes = template.get('attributes')
            if attributes and isinstance(attributes, dict):
                # HF format - extract from attributes
                cpus = attributes.get('ncpus', ['Numeric', 'N/A'])[1] if attributes.get('ncpus') else 'N/A'
                ram = attributes.get('nram', ['Numeric', 'N/A'])[1] if attributes.get('nram') else 'N/A'
            else:
                # Standard format - derive from instance_type
                instance_type = get_field_value(template, field_mapping, 'instance_type')
                cpus, ram = _derive_cpu_ram_from_instance_type(instance_type)
            
            # Truncate long values for table display
            table.add_row(
                template_id[:15],
                name[:15] if name != 'N/A' else name,
                provider_api[:10] if provider_api != 'N/A' else provider_api,
                cpus,
                ram,
                max_instances
            )
        
        # Capture Rich output as string
        console = Console(width=120, legacy_windows=False, force_terminal=False)
        with console.capture() as capture:
            console.print(table)
        
        return capture.get()
        
    except ImportError:
        # Fallback to ASCII table if Rich is not available
        return _format_ascii_table(templates)


def _format_ascii_table(templates: List[Dict]) -> str:
    """Fallback ASCII table formatter when Rich is not available."""
    field_mapping = get_template_field_mapping()
    
    # Define table headers
    headers = ['ID', 'Name', 'Provider', 'CPUs', 'RAM (MB)', 'Max Inst']
    
    # Extract data for each template
    rows = []
    for template in templates:
        template_id = get_field_value(template, field_mapping, 'id')
        name = get_field_value(template, field_mapping, 'name')
        provider_api = get_field_value(template, field_mapping, 'provider_api')
        max_instances = get_field_value(template, field_mapping, 'max_instances')
        
        # Handle different formats
        attributes = template.get('attributes')
        if attributes and isinstance(attributes, dict):
            # HF format - extract from attributes
            cpus = attributes.get('ncpus', ['Numeric', 'N/A'])[1] if attributes.get('ncpus') else 'N/A'
            ram = attributes.get('nram', ['Numeric', 'N/A'])[1] if attributes.get('nram') else 'N/A'
        else:
            # Standard format - derive from instance_type
            instance_type = get_field_value(template, field_mapping, 'instance_type')
            cpus, ram = _derive_cpu_ram_from_instance_type(instance_type)
        
        # Truncate long values for table display
        row = [
            template_id[:15],
            name[:15] if name != 'N/A' else name,
            provider_api[:10] if provider_api != 'N/A' else provider_api,
            cpus,
            ram,
            max_instances
        ]
        rows.append(row)
    
    return _format_table_with_headers(headers, rows)


def _derive_cpu_ram_from_instance_type(instance_type: str) -> tuple[str, str]:
    """Derive CPU and RAM from instance type for table display."""
    if instance_type == 'N/A':
        return 'N/A', 'N/A'
    
    # Simple mapping for common instance types
    cpu_ram_mapping = {
        "t2.micro": ("1", "1024"),
        "t2.small": ("1", "2048"),
        "t2.medium": ("2", "4096"),
        "t2.large": ("2", "8192"),
        "t2.xlarge": ("4", "16384"),
        "t3.micro": ("2", "1024"),
        "t3.small": ("2", "2048"),
        "t3.medium": ("2", "4096"),
        "t3.large": ("2", "8192"),
        "t3.xlarge": ("4", "16384"),
        "m5.large": ("2", "8192"),
        "m5.xlarge": ("4", "16384"),
        "m5.2xlarge": ("8", "32768"),
        "c5.large": ("2", "4096"),
        "c5.xlarge": ("4", "8192"),
        "r5.large": ("2", "16384"),
        "r5.xlarge": ("4", "32768"),
    }
    
    return cpu_ram_mapping.get(instance_type, ("1", "1024"))


def format_templates_list(templates: List[Dict]) -> str:
    """Format templates as a detailed list."""
    if not templates:
        return "No templates found."
    
    field_mapping = get_template_field_mapping()
    lines = []
    
    for i, template in enumerate(templates):
        if i > 0:
            lines.append("")  # Blank line between templates
        
        template_id = get_field_value(template, field_mapping, 'id')
        name = get_field_value(template, field_mapping, 'name')
        provider_api = get_field_value(template, field_mapping, 'provider_api')
        instance_type = get_field_value(template, field_mapping, 'instance_type')
        max_instances = get_field_value(template, field_mapping, 'max_instances')
        
        lines.append(f"Template: {template_id}")
        lines.append(f"  Name: {name}")
        lines.append(f"  Provider: {provider_api}")
        lines.append(f"  Instance Type: {instance_type}")
        lines.append(f"  Max Instances: {max_instances}")
        
        # Handle HF format attributes
        attributes = template.get('attributes')
        if attributes and isinstance(attributes, dict):
            # Extract info from HF attributes format
            cpus = attributes.get('ncpus', ['Numeric', 'N/A'])[1] if attributes.get('ncpus') else 'N/A'
            ram = attributes.get('nram', ['Numeric', 'N/A'])[1] if attributes.get('nram') else 'N/A'
            lines.append(f"  CPUs: {cpus}")
            lines.append(f"  RAM (MB): {ram}")
        
        # Add other fields if available
        description = get_field_value(template, field_mapping, 'description')
        if description != 'N/A':
            lines.append(f"  Description: {description}")
        
        image_id = get_field_value(template, field_mapping, 'image_id')
        if image_id != 'N/A':
            lines.append(f"  Image ID: {image_id}")
        
        subnet_ids = get_field_value(template, field_mapping, 'subnet_ids')
        if subnet_ids != 'N/A':
            lines.append(f"  Subnet IDs: {subnet_ids}")
    
    return "\n".join(lines)


def get_request_field_mapping() -> Dict[str, List[str]]:
    """Get mapping of logical request field names to possible actual field names."""
    return {
        'id': ['request_id', 'requestId'],
        'status': ['status'],
        'template_id': ['template_id', 'templateId'],
        'num_requested': ['num_requested', 'numRequested'],
        'num_allocated': ['num_allocated', 'numAllocated'],
        'created_at': ['created_at', 'createdAt'],
        'updated_at': ['updated_at', 'updatedAt']
    }


def format_requests_list(requests: List[Dict]) -> str:
    """Format requests as a detailed list."""
    if not requests:
        return "No requests found."
    
    field_mapping = get_request_field_mapping()
    lines = []
    
    for i, request in enumerate(requests):
        if i > 0:
            lines.append("")  # Blank line between requests
        
        request_id = get_field_value(request, field_mapping, 'id')
        status = get_field_value(request, field_mapping, 'status')
        template_id = get_field_value(request, field_mapping, 'template_id')
        num_requested = get_field_value(request, field_mapping, 'num_requested')
        created_at = get_field_value(request, field_mapping, 'created_at')
        
        lines.append(f"Request: {request_id}")
        lines.append(f"  Status: {status}")
        lines.append(f"  Template: {template_id}")
        lines.append(f"  Requested: {num_requested}")
        lines.append(f"  Created: {created_at}")
    
    return "\n".join(lines)


def format_machines_list(machines: List[Dict]) -> str:
    """Format machines as a detailed list."""
    if not machines:
        return "No machines found."
    
    field_mapping = get_machine_field_mapping()
    lines = []
    
    for i, machine in enumerate(machines):
        if i > 0:
            lines.append("")  # Blank line between machines
        
        machine_id = get_field_value(machine, field_mapping, 'id')
        name = get_field_value(machine, field_mapping, 'name')
        status = get_field_value(machine, field_mapping, 'status')
        instance_type = get_field_value(machine, field_mapping, 'instance_type')
        private_ip = get_field_value(machine, field_mapping, 'private_ip')
        
        lines.append(f"Machine: {machine_id}")
        lines.append(f"  Name: {name}")
        lines.append(f"  Status: {status}")
        lines.append(f"  Instance Type: {instance_type}")
        lines.append(f"  Private IP: {private_ip}")
    
    return "\n".join(lines)


def get_machine_field_mapping() -> Dict[str, List[str]]:
    """Get mapping of logical machine field names to possible actual field names."""
    return {
        'id': ['machine_id', 'machineId', 'instance_id', 'instanceId'],
        'name': ['name', 'machine_name', 'machineName'],
        'status': ['status', 'state'],
        'instance_type': ['instance_type', 'instanceType', 'vm_type', 'vmType'],
        'private_ip': ['private_ip', 'privateIp', 'private_ip_address'],
        'public_ip': ['public_ip', 'publicIp', 'public_ip_address'],
        'created_at': ['created_at', 'createdAt', 'launch_time'],
        'template_id': ['template_id', 'templateId']
    }


def format_machines_table(machines: List[Dict]) -> str:
    """Format machines as a table."""
    if not machines:
        return "No machines found."
    
    field_mapping = get_machine_field_mapping()
    
    # Define table headers
    headers = ['ID', 'Name', 'Status', 'Type', 'Private IP']
    
    # Extract data for each machine
    rows = []
    for machine in machines:
        machine_id = get_field_value(machine, field_mapping, 'id')
        name = get_field_value(machine, field_mapping, 'name')
        status = get_field_value(machine, field_mapping, 'status')
        instance_type = get_field_value(machine, field_mapping, 'instance_type')
        private_ip = get_field_value(machine, field_mapping, 'private_ip')
        
        # Truncate long values for table display
        row = [
            machine_id[:15],
            name[:15] if name != 'N/A' else name,
            status[:10],
            instance_type[:10],
            private_ip
        ]
        rows.append(row)
    
    return _format_table_with_headers(headers, rows)


def format_requests_table(requests: List[Dict]) -> str:
    """Format requests as a table."""
    if not requests:
        return "No requests found."
    
    field_mapping = get_request_field_mapping()
    
    # Define table headers
    headers = ['ID', 'Status', 'Template', 'Requested', 'Created']
    
    # Extract data for each request
    rows = []
    for request in requests:
        request_id = get_field_value(request, field_mapping, 'id')
        status = get_field_value(request, field_mapping, 'status')
        template_id = get_field_value(request, field_mapping, 'template_id')
        num_requested = get_field_value(request, field_mapping, 'num_requested')
        created_at = get_field_value(request, field_mapping, 'created_at')
        
        # Truncate long values for table display
        row = [
            request_id[:15],
            status[:10],
            template_id[:15],
            num_requested,
            created_at[:19] if created_at != 'N/A' else created_at  # Show date/time only
        ]
        rows.append(row)
    
    return _format_table_with_headers(headers, rows)


def _format_table_with_headers(headers: List[str], rows: List[List[str]]) -> str:
    """Format data as ASCII table with headers."""
    if not rows:
        return "No data to display."
    
    # Calculate column widths
    all_rows = [headers] + rows
    widths = [max(len(str(row[i])) for row in all_rows) for i in range(len(headers))]
    
    # Format table
    def format_row(row, widths):
        return '| ' + ' | '.join(str(row[i]).ljust(widths[i]) for i in range(len(row))) + ' |'
    
    def format_separator(widths):
        return '+' + '+'.join('-' * (w + 2) for w in widths) + '+'
    
    lines = []
    lines.append(format_separator(widths))
    lines.append(format_row(headers, widths))
    lines.append(format_separator(widths))
    for row in rows:
        lines.append(format_row(row, widths))
    lines.append(format_separator(widths))
    
    return "\n".join(lines)
