# Native AWS Specification Support

## Overview

Native AWS specification support allows you to use raw AWS API specifications alongside or instead of simplified template fields. This provides full access to AWS API capabilities while maintaining backward compatibility.

## How It Works

### Merge Modes

Configure merge behavior in your configuration:

```json
{
  "native_spec": {
    "merge_mode": "merge"
  }
}
```

**Available modes:**
- `merge`: Combine default template with native spec (recommended)
- `replace`: Use only native spec, ignore template defaults

### Specification Types

You can specify native AWS configurations in four ways:

#### 1. Provider API Spec (Inline)
Direct AWS API specification in template:

```json
{
  "template_id": "my-template",
  "provider_api_spec": {
    "LaunchTemplateConfigs": [{
      "LaunchTemplateSpecification": {
        "LaunchTemplateName": "my-custom-lt",
        "Version": "$Latest"
      },
      "Overrides": [{
        "InstanceType": "c5.xlarge",
        "SubnetId": "subnet-12345"
      }]
    }],
    "TargetCapacitySpecification": {
      "TotalTargetCapacity": 10,
      "DefaultTargetCapacityType": "spot"
    }
  }
}
```

#### 2. Provider API Spec File
Reference external file:

```json
{
  "template_id": "my-template", 
  "provider_api_spec_file": "specs/ec2fleet-config.json"
}
```

#### 3. Launch Template Spec (Inline)
Launch template specification in template:

```json
{
  "template_id": "my-template",
  "launch_template_spec": {
    "LaunchTemplateName": "custom-lt-{{ request_id }}",
    "LaunchTemplateData": {
      "ImageId": "ami-12345",
      "InstanceType": "m5.large",
      "SecurityGroupIds": ["sg-12345"],
      "UserData": "{{ user_data | b64encode }}"
    }
  }
}
```

#### 4. Launch Template Spec File
Reference external launch template file:

```json
{
  "template_id": "my-template",
  "launch_template_spec_file": "specs/launch-template.json"
}
```

## Merge Behavior

### Merge Mode (Default)
Combines template defaults with native specifications:

**Template:**
```json
{
  "instance_type": "t3.medium",
  "provider_api_spec": {
    "TargetCapacitySpecification": {
      "TotalTargetCapacity": 5
    }
  }
}
```

**Result:** Default EC2Fleet config + your target capacity override

### Replace Mode
Uses only native specification, ignores template defaults:

**Template:**
```json
{
  "instance_type": "t3.medium",
  "provider_api_spec": {
    "LaunchTemplateConfigs": [...],
    "TargetCapacitySpecification": {...}
  }
}
```

**Result:** Only your native specification is used

## Precedence Order

When multiple specifications are provided, precedence is:

1. **provider_api_spec** (highest)
2. **provider_api_spec_file**
3. **launch_template_spec** 
4. **launch_template_spec_file**
5. **Template defaults** (lowest)

## Jinja2 Templating

All specifications support Jinja2 variables:

```json
{
  "provider_api_spec": {
    "LaunchTemplateConfigs": [{
      "LaunchTemplateSpecification": {
        "LaunchTemplateName": "lt-{{ request_id }}",
        "Version": "{{ template_version | default('$Latest') }}"
      }
    }],
    "TargetCapacitySpecification": {
      "TotalTargetCapacity": "{{ requested_count }}"
    }
  }
}
```

**Available variables:**
- `{{ request_id }}` - Unique request identifier
- `{{ template_id }}` - Template identifier  
- `{{ requested_count }}` - Number of instances requested
- `{{ timestamp }}` - Current timestamp
- `{{ package_name }}` - Package name for tagging

## Examples

### EC2Fleet with Custom Configuration

```json
{
  "template_id": "custom-fleet",
  "provider_api_spec": {
    "Type": "instant",
    "LaunchTemplateConfigs": [{
      "LaunchTemplateSpecification": {
        "LaunchTemplateName": "my-template",
        "Version": "$Latest"
      },
      "Overrides": [
        {"InstanceType": "c5.large", "SubnetId": "subnet-1"},
        {"InstanceType": "c5.xlarge", "SubnetId": "subnet-2"}
      ]
    }],
    "TargetCapacitySpecification": {
      "TotalTargetCapacity": "{{ requested_count }}",
      "DefaultTargetCapacityType": "spot",
      "OnDemandTargetCapacity": 1
    }
  }
}
```

### SpotFleet with Launch Template

```json
{
  "template_id": "spot-fleet",
  "launch_template_spec": {
    "LaunchTemplateName": "spot-lt-{{ request_id }}",
    "LaunchTemplateData": {
      "ImageId": "ami-12345",
      "InstanceType": "m5.large",
      "SecurityGroupIds": ["sg-12345"],
      "IamInstanceProfile": {"Name": "my-role"}
    }
  },
  "provider_api_spec": {
    "LaunchSpecifications": [{
      "LaunchTemplate": {
        "LaunchTemplateName": "spot-lt-{{ request_id }}",
        "Version": "$Latest"
      }
    }],
    "TargetCapacity": "{{ requested_count }}",
    "AllocationStrategy": "diversified"
  }
}
```

### External File References

**Template:**
```json
{
  "template_id": "file-based",
  "provider_api_spec_file": "specs/production-fleet.json",
  "launch_template_spec_file": "specs/production-lt.json"
}
```

**specs/production-fleet.json:**
```json
{
  "Type": "maintain",
  "TargetCapacitySpecification": {
    "TotalTargetCapacity": "{{ requested_count }}",
    "DefaultTargetCapacityType": "on-demand"
  }
}
```

## Configuration

### Enable Native Specs

```json
{
  "native_spec": {
    "merge_mode": "merge"
  }
}
```

### Template File Locations

Place specification files in your template directory:
```
config/
├── awsprov_templates.json
└── specs/
    ├── ec2fleet-configs/
    ├── launch-templates/
    └── common/
```

## Backward Compatibility

- **Existing templates continue to work unchanged**
- **No migration required** - add native specs when needed
- **Gradual adoption** - use native specs for specific templates
- **Fallback behavior** - system falls back to template defaults if native spec fails

## Best Practices

1. **Start with merge mode** for gradual adoption
2. **Use Jinja2 variables** for dynamic values
3. **External files** for complex specifications
4. **Test thoroughly** before production use
5. **Keep templates simple** - use native specs for complexity

## Troubleshooting

### Common Issues

**Template rendering fails:**
- Check Jinja2 syntax in specifications
- Verify file paths for external references
- Ensure required variables are available

**Merge not working as expected:**
- Verify `merge_mode` configuration
- Check precedence order
- Review merge logic for your provider API

**AWS API errors:**
- Validate native specification against AWS API docs
- Check IAM permissions for specified resources
- Verify resource names and IDs exist
