# AWS Lambda MicroVM Provider

The MicroVM handler provisions isolated [AWS Lambda MicroVMs](https://docs.aws.amazon.com/lambda/latest/dg/lambda-microvms-guide.html) — lightweight Firecracker-based sandboxes with full lifecycle control.

## Quick start

```bash
pip install "orb-py[aws]"
orb init
```

### 1. Create a MicroVM image

Package your application as a Dockerfile and build a MicroVM image:

```bash
aws lambda-microvms create-microvm-image \
  --name my-worker \
  --code-artifact uri=s3://my-bucket/worker.zip \
  --base-image-arn arn:aws:lambda:us-east-1:aws:microvm-image:al2023-1 \
  --build-role-arn arn:aws:iam::123456789012:role/MicroVMBuildRole \
  --execution-role-arn arn:aws:iam::123456789012:role/MicroVMExecutionRole
```

The build produces an image ARN like `arn:aws:lambda:us-east-1:123456789012:microvm-image:my-worker`.

### 2. Create a template

```json
{
  "templateId": "my-worker-template",
  "name": "My Worker MicroVM",
  "description": "Isolated sandbox for running worker tasks",
  "provider_api": "MicroVM",
  "image_id": "arn:aws:lambda:us-east-1:123456789012:microvm-image:my-worker",
  "maxNumber": 20,
  "metadata": {
    "image_version": "1",
    "execution_role_arn": "arn:aws:iam::123456789012:role/MicroVMExecutionRole",
    "idle_policy": {
      "maxIdleDurationSeconds": 3600,
      "suspendedDurationSeconds": 3600,
      "autoResumeEnabled": true
    },
    "maximum_duration_in_seconds": 3600
  }
}
```

### 3. Request MicroVMs

```bash
orb machines request my-worker-template 5
```

### 4. Check status

```bash
orb requests status <request-id>
```

### 5. Return MicroVMs

```bash
orb machines return <microvm-id-1> <microvm-id-2> ...
```

## Template configuration

The MicroVM handler uses `provider_api: "MicroVM"` and configures the MicroVM through a combination of the top-level `image_id` field and the `metadata` dict.

### Top-level fields

| Field | Required | Description |
|-------|----------|-------------|
| `provider_api` | Yes | Must be `"MicroVM"` |
| `image_id` | Yes | The MicroVM image ARN or identifier. This is the image your MicroVMs will boot from. |
| `max_instances` | No | Maximum number of MicroVMs this template can provision (default: unlimited) |

### Metadata fields

All MicroVM-specific configuration lives in the `metadata` dict:

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `image_version` | No | `string` | Version of the MicroVM image to use. Omit for the latest version. |
| `execution_role_arn` | No | `string` | IAM role ARN assumed by the MicroVM at runtime. This is separate from the `buildRoleArn` used during image creation — see [IAM permissions](#iam-permissions). Grant only the permissions your application needs at runtime (e.g. SQS, DynamoDB, CloudWatch Logs). If omitted, the MicroVM has no AWS service access and runtime logs are not emitted to CloudWatch. |
| `idle_policy` | No | `object` | Controls auto-suspend and auto-resume behavior. See [Idle policy](#idle-policy). |
| `maximum_duration_in_seconds` | No | `integer` | Maximum lifetime of the MicroVM before platform termination. Range: 1–28800 (8 hours). |
| `run_hook_payload` | No | `string` | Per-MicroVM initialization data delivered as the request body of the `/run` lifecycle hook. Max 16,384 bytes. Use to pass tenant-specific config (queue URLs, secrets references, session IDs). |
| `ingress_network_connectors` | No | `list[string]` | Ingress network connector ARNs. Controls inbound connectivity — Lambda forwards HTTPS/HTTP2/gRPC/WebSocket traffic from the MicroVM's dedicated endpoint to ports inside the MicroVM. Connectors are AWS-managed; reference them by ARN. See [Network connectors](#network-connectors). |
| `egress_network_connectors` | No | `list[string]` | Egress network connector ARNs. Controls outbound connectivity — by default MicroVMs have public internet access. To route egress through a VPC (e.g. to reach RDS, ElastiCache, or on-premises systems), create a Lambda Network Connector and reference its ARN here. See [Network connectors](#network-connectors). |
| `logging` | No | `object` | Logging configuration. Either `{"disabled": {}}` or `{"cloudWatch": {"logGroup": "...", "logStream": "..."}}`. |

### Idle policy

The idle policy controls when the platform auto-suspends a MicroVM and whether it auto-resumes on incoming traffic. However, **ORB's current implementation assumes MicroVMs operate in pull mode** (e.g. polling an HPC scheduler or SQS for tasks). The platform's suspend/resume mechanism is based on inbound HTTP traffic, which pull-based workers never receive. ORB does not implement suspend/resume — it manages the full lifecycle via explicit provisioning and termination.

**Recommendation:** Set `maxIdleDurationSeconds` to match `maximumDurationInSeconds` to effectively disable suspend:

```json
{
  "idle_policy": {
    "maxIdleDurationSeconds": 3600,
    "suspendedDurationSeconds": 3600,
    "autoResumeEnabled": true
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `maxIdleDurationSeconds` | `integer` | Time (seconds) of no inbound traffic before the platform suspends the MicroVM. Set equal to `maximumDurationInSeconds` for pull-based workloads. |
| `suspendedDurationSeconds` | `integer` | Time (seconds) the MicroVM can remain suspended before auto-termination. |
| `autoResumeEnabled` | `boolean` | If `true`, the MicroVM resumes on inbound traffic while suspended. Not applicable for pull-based workloads. |

All three fields are required if `idle_policy` is provided.

### Choosing a MicroVM image

The `image_id` field accepts either:

- **Full ARN**: `arn:aws:lambda:us-east-1:123456789012:microvm-image:my-image`
- **Image name**: `my-image` (resolved in the configured region)

To list available images:

```bash
aws lambda-microvms list-microvm-images
```

To use a specific version of an image, set `image_version` in metadata:

```json
{
  "image_id": "arn:aws:lambda:us-east-1:123456789012:microvm-image:my-image",
  "metadata": {
    "image_version": "3"
  }
}
```

Omit `image_version` to always use the latest published version.

### MicroVM sizing

MicroVM compute resources are configured **at image build time** via the `resources` parameter on `create_microvm_image` — not at run time. ORB does not expose sizing configuration because it is baked into the image. See [MicroVM images](https://docs.aws.amazon.com/lambda/latest/dg/microvms-images.html) for full details.

Lambda MicroVMs use a baseline-peak model. You set the baseline memory; vCPU scales proportionally (2 GB = 1 vCPU). During peak activity, MicroVMs can burst up to 4x the baseline. You pay the baseline rate while running and only for active use above the baseline.

| Baseline | Peak (4x burst) | Max Disk | Max Bandwidth |
|----------|-----------------|----------|---------------|
| 0.5 GB / 0.25 vCPU | 2 GB / 1 vCPU | 8 GB | 1 MB/s |
| 1 GB / 0.5 vCPU | 4 GB / 2 vCPU | 8 GB | 2 MB/s |
| 2 GB / 1 vCPU (default) | 8 GB / 4 vCPU | 8 GB | 4 MB/s |
| 4 GB / 2 vCPU | 16 GB / 8 vCPU | 16 GB | 8 MB/s |
| 8 GB / 4 vCPU | 32 GB / 16 vCPU | 32 GB | 16 MB/s |

To configure sizing, set `resources` when building the image:

```bash
aws lambda-microvms create-microvm-image \
  --name my-worker \
  --code-artifact uri=s3://my-bucket/worker.zip \
  --base-image-arn arn:aws:lambda:us-east-1:aws:microvm-image:al2023-1 \
  --build-role-arn arn:aws:iam::123456789012:role/MicroVMBuildRole \
  --resources '[{"minimumMemoryInMiB": 4096}]'
```

Disk space and network bandwidth are tied to the memory tier and cannot be configured independently.

### Network connectors

MicroVMs use **network connectors** to control inbound and outbound traffic. Unlike EC2 instances, MicroVMs do not use VPC subnets or security groups directly. See [Networking](https://docs.aws.amazon.com/lambda/latest/dg/microvms-networking.html) for full protocol, port routing, and bandwidth details.

#### Ingress (inbound)

Each MicroVM gets a dedicated HTTPS endpoint. Ingress connectors are AWS-managed resources that define what protocols and ports the endpoint supports:

- HTTP/1.1, HTTP/2, gRPC, WebSockets, and Server-Sent Events (SSE)
- All ports except system-reserved ports (0–1024), except 80 and 443 which are supported
- Traffic is authenticated via JWE tokens (`X-aws-proxy-auth` header)
- Target port inside the MicroVM is selected via `X-aws-proxy-port` header (default: 8080)

Reference an AWS-managed ingress connector ARN (e.g. `arn:aws:lambda:us-east-1:aws:network-connector:aws-network-connector:ALL_INGRESS`) in `ingress_network_connectors`.

#### Egress (outbound)

By default, MicroVMs have public internet access. To route outbound traffic through your VPC instead (e.g. to reach RDS, ElastiCache, or on-premises systems via Direct Connect), create a Lambda Network Connector:

```bash
aws lambda-core create-network-connector \
  --name my-vpc-connector \
  --configuration '{
    "VpcEgressConfiguration": {
      "SubnetIds": ["subnet-xxx"],
      "SecurityGroupIds": ["sg-xxx"],
      "NetworkProtocol": "IPv4",
      "AssociatedComputeResourceTypes": ["MicroVm"]
    }
  }' \
  --operator-role arn:aws:iam::123456789012:role/ConnectorOperatorRole
```

Then reference the connector ARN in `egress_network_connectors`. A single connector can be reused across many MicroVMs. When using VPC egress, outbound traffic is subject to security group rules and network ACLs in your VPC.

## Machine data

When you query machine status, MicroVM machines have a different shape than EC2 instances:

```json
{
  "instance_id": "microvm-abc123def456",
  "status": "running",
  "private_ip": null,
  "public_ip": null,
  "launch_time": "2026-07-13T10:00:00+00:00",
  "image_id": "arn:aws:lambda:us-east-1:123456789012:microvm-image:my-worker",
  "provider_api": "MicroVM",
  "provider_data": {
    "endpoint": "https://xyz.lambda-microvms.us-east-1.on.aws",
    "image_version": "1",
    "execution_role_arn": "arn:aws:iam::123456789012:role/MicroVMExecutionRole",
    "maximum_duration_in_seconds": 28800
  }
}
```

Key differences from EC2:

- **No IP addresses** — MicroVMs expose an HTTPS endpoint instead.
- **`provider_data.endpoint`** — The URL to send requests to this MicroVM.
- **No instance type** — MicroVMs are sized by the platform (up to 16 vCPU, 32 GB RAM, 32 GB disk).

## Connecting to a MicroVM

To send traffic to a running MicroVM, generate a short-lived auth token and include it in the `X-aws-proxy-auth` header. See [Running and using MicroVMs](https://docs.aws.amazon.com/lambda/latest/dg/microvms-launching.html) for full auth token and connection details.

```bash
# Generate token
TOKEN=$(aws lambda-microvms create-microvm-auth-token \
  --microvm-identifier microvm-abc123def456 \
  --query 'authToken' --output text)

# Send request
curl -H "X-aws-proxy-auth: $TOKEN" \
  https://xyz.lambda-microvms.us-east-1.on.aws/my-endpoint
```

Auth token management is an out-of-band concern — ORB provisions and terminates MicroVMs but does not manage auth tokens.

## Lifecycle states

ORB maps MicroVM states to standard ORB machine statuses:

| MicroVM State | ORB Status | Description |
|---------------|------------|-------------|
| `PENDING` | `pending` | MicroVM is being provisioned |
| `RUNNING` | `running` | MicroVM is active |
| `SUSPENDING` | `running` | Transitioning to suspended (still alive) |
| `SUSPENDED` | `running` | Idle, state preserved |
| `TERMINATING` | `shutting-down` | Being terminated |
| `TERMINATED` | `terminated` | Terminated |

`SUSPENDING` and `SUSPENDED` map to `running` because ORB assumes MicroVMs operate in **pull mode** — polling work from queues (SQS, Kafka, etc.) rather than receiving inbound HTTP traffic.

### Suspend/resume and pull-based workloads

The MicroVM platform's suspend/resume mechanism is designed for inbound-traffic workloads: a MicroVM suspends after a period of no inbound requests and resumes when new traffic arrives. **This does not apply to pull-based workloads** managed by ORB, where the MicroVM actively polls an external source for work.

In pull mode:
- The MicroVM never receives inbound traffic, so the platform's idle detection (based on inbound requests) may trigger a suspend even while the worker is actively polling.
- A suspended MicroVM cannot poll — it loses its running process state.
- `autoResumeEnabled: true` only resumes on *inbound* traffic, which pull-based workers never receive.

**Recommendation:** For pull-based MicroVMs managed by ORB, set `maxIdleDurationSeconds` to match `maximumDurationInSeconds` (the max lifetime). This effectively disables suspend and lets ORB manage the full lifecycle via explicit termination when work is done.

```json
{
  "idle_policy": {
    "maxIdleDurationSeconds": 3600,
    "suspendedDurationSeconds": 3600,
    "autoResumeEnabled": true
  },
  "maximum_duration_in_seconds": 3600
}
```

This keeps MicroVMs running for up to 1 hour — ORB terminates them earlier via `return_machines` when no longer needed.

## IAM permissions

### ORB caller permissions

The IAM principal running ORB needs these permissions (see [RunMicrovm API reference](https://docs.aws.amazon.com/lambda/latest/microvm-api/API_RunMicrovm.html)):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda-microvms:RunMicrovm",
        "lambda-microvms:GetMicrovm",
        "lambda-microvms:TerminateMicrovm"
      ],
      "Resource": "*"
    }
  ]
}
```

### MicroVM roles

Lambda MicroVMs use two separate IAM roles, following the principle of least privilege. See [Security and permissions](https://docs.aws.amazon.com/lambda/latest/dg/microvms-security.html) for the full AWS reference.

#### Build role (`buildRoleArn`)

Passed to `create_microvm_image`. Used only during image creation to pull source artifacts and write build logs. This role is not available at runtime.

Trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Required permissions:
- `s3:GetObject` on the code artifact bucket (to pull the source archive)
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` (for build logs)
- `ecr:GetAuthorizationToken` (only if your Dockerfile references private ECR images)

#### Execution role (`execution_role_arn`)

Passed in the ORB template metadata. Assumed by the MicroVM at runtime — this is the identity your application code runs under.

Trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Required permissions:
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` (for runtime logs)
- Any permissions your application needs (e.g. `sqs:SendMessage`, `sqs:ReceiveMessage`, `dynamodb:GetItem`)

#### Why separate roles?

Separating build and execution roles means the runtime environment has no access to your source artifact bucket, and the build process has no access to your application's runtime resources (queues, databases, etc.). This limits the blast radius if either role is compromised.

## Status syncing

`orb machines list` reads from ORB's local state store — it does not poll AWS. To sync machine statuses with the live MicroVM state, query the request:

```bash
orb requests status <request-id>
```

This triggers a read-through sync: ORB calls `get_microvm` for each machine, updates the stored status, and returns the current state. After this, `orb machines list` reflects the live state.

## Provisioning behavior

- **Parallelism**: MicroVMs are provisioned in parallel with a concurrency of 25. Throttled requests automatically retry with exponential backoff and jitter.
- **Idempotency**: Each `run_microvm` call uses a unique `clientToken` for safe retries.
- **Partial success**: If some launches fail but others succeed, ORB reports partial fulfilment. The request enters `partial` state with the successfully launched MicroVMs available.

## Availability

Lambda MicroVMs are available in:
- US East (N. Virginia, Ohio)
- US West (Oregon)
- Europe (Ireland)
- Asia Pacific (Tokyo)

## Limitations

- **Maximum lifetime**: 8 hours (28,800 seconds) per MicroVM.
- **No VPC networking**: MicroVMs use platform-managed networking with dedicated HTTPS endpoints. No subnet or security group configuration.
- **ARM64 only**: MicroVMs run on ARM64 architecture.
- **No fleet API**: Each MicroVM is provisioned individually (no batch/fleet creation API).
