# awsprov_config.json reference

The Amazon Web Services (AWS) provider configuration file, which contains administrative and authentication information for provisioning from AWS.

## Location

The awsprov_config.json file is located at:
- %HF_TOP%\%HF_VERSION%\providerplugins\aws\sampleconf\ on Windows.
- $HF_TOP/$HF_VERSION/providerplugins/aws/sampleconf/ on Linux®.

Tip: The awsprov_config.json sample file is renamed to awsinstprov_config.json when copied into the configuration directory location, for example: %HF_CONFDIR%\providers\awsinst\ on Windows or $HF_CONFDIR/providers/awsinst/ on Linux.

---

## Parameters

### ACCEPT_PROPAGATED_LOG_SETTING

- Optional. Whether to use the HostFactory service log setting or not.
- Valid value is `true` or `false`.
- If omitted, defaults to `false`.
- When set to `true`, the HostFactory service log settings are used. See `HF_LOGLEVEL`, `HF_LOG_MAX_FILE_SIZE`, and `HF_LOG_MAX_ROTATE` in the hostfactoryconf.json reference topic.
- When set to `false`, log settings from `log4j.xml` are used. See `MaxFileSize` and `MaxBackupIndex` in the LoggerAppenderRollingFile and Loggers references in Apache log4php documentation.
- **Warning:** If `MaxBackupIndex` is set to 0 or negative, log rotation is disabled and old messages may be lost.

### AWS_CREDENTIAL_FILE

- Required. Full path to the AWS credential file on your primary host that contains the long-term credentials of the designated IAM user.
- Long-term credentials consist of an access key ID and secret access key, in the format:
  ``
  [default]
  aws_access_key_id=ABCDEFGHIJ1K
  aws_secret_access_key=/aBccdeGhIjkL12mNMOp34Qrst
  ``
- If HostFactory runs on an EC2 host with an IAM role that has permissions for provisioning and releasing EC2 hosts, you are not required to configure this parameter. If specified, HostFactory authenticates via those long-term credentials; if not, it uses the instance-profile credentials.

### AWS_ENDPOINT_URL

- Optional.
- Typically, the AWS provider can determine the endpoint from the region name, but if the provider is running in an environment without public internet access, you can specify a private endpoint.
- If using AWS_ENDPOINT_URL, also specify the AWS_REGION configuration (which indicates the signing region).
- Example:
  ``
  {
    "AWS_CREDENTIAL_FILE": "/root/.aws/credentials",
    "AWS_ENDPOINT_URL": "https://ec2.us-east-1.amazonaws.com:443",
    "AWS_REGION": "us-east-1",
    "AWS_KEY_FILE": "/root/.aws/data",
    "AWS_PROXY_HOST": "",
    "AWS_PROXY_PORT": 80
  }
  ``
  or
  ``
  "AWS_ENDPOINT_URL": "https://vpce-0fe79612078a1ab7c-idd8hzys.ec2.eu-west-1.vpce.amazonaws.com:443"
  ``

### AWS_REGION

- Required. The region code for your Amazon EC2 region.
- All EC2 instances are provisioned from this region.
- When using AWS_ENDPOINT_URL, AWS_REGION is also used for signing.
- Example:
  ``
  {
    "AWS_CREDENTIAL_FILE": "/root/.aws/credentials",
    "AWS_ENDPOINT_URL": "https://ec2.us-east-1.amazonaws.com:443",
    "AWS_REGION": "us-east-1",
    ...
  }
  ``

### AWS_KEY_FILE

- Optional. Full path to the directory containing the key pair file (`keyfile.pem`) on your primary host.
- During provisioning, the system looks for the .pem file that contains the key pair defined by the keyName parameter of each template in the awsprov_templates.json file.

### AWS_PROXY_HOST

- Optional. Host name of a proxy server, enabling AWS connections through the proxy server.
- Configure the proxy server to listen on the port specified by the AWS_PROXY_PORT parameter and forward to the actual AWS endpoint.
- If AWS_PROXY_HOST is not defined or is empty, the proxy connection is not enabled.

### AWS_PROXY_PORT

- Required when AWS_PROXY_HOST is defined. Port used by the proxy server.

### AWS_CONNECTION_TIMEOUT_MS

- Optional. Maximum duration (in milliseconds) to wait for the proxy connection to be established, after which time the connection times out.
- Valid values are positive integers, up to a maximum of 2147483647.
- Default is 10000 (ms).

### AWS_REQUEST_RETRY_ATTEMPTS

- Optional. Number of times to retry a failed AWS request (such as intermittent timeout errors).
- Valid value is 0 - 10. Default is 0 (no retry).
- Example error:
  ``
  [2020-07-16 15:28:06.502]-[ERROR]-[com.ibm.spectrum.util.AwsUtil.requestSpotInstance(AwsUtil.java:809)] Create instances error. com.amazonaws.SdkClientException: Unable to execute HTTP request: Read timed out
  ``
- If all retry attempts fail, you may need to manually remove any provisioned hosts from AWS.

- The log file will contain messages with the request retry counter:
  ``
  Retrying request for Spot Fleet with client token xxxxxxx-xxxx [retry count=1]
  ``
- To avoid the request from reaching timeout while retrying, you can increase the value of the HF_PROVIDER_ACTION_TIMEOUT parameter in hostfactoryconf.json.

### AWS_INSTANCE_PENDING_TIMEOUT_SEC

- Optional. The timeout in seconds after which an instance in pending state is terminated.
- Valid value is an integer in the range 180 - 10000 inclusive. Default is 180.

### AWS_DESCRIBE_REQUEST_RETRY_ATTEMPTS

- Optional. The number of retries to get instance status from the provider.
- Valid value is 0 - 10 inclusive. Default is 0 (no retry).
- If all retry attempts fail, the request is completed with errors and returned with the list of already provisioned instances.

### AWS_DESCRIBE_REQUEST_INTERVAL

- Optional. The time duration (in milliseconds) to define delay between retries to get status of instances from the provider.
- Valid value is 0 - 10000. Default is 0.
- Each delay between retries equals AWS_DESCRIBE_REQUEST_INTERVAL multiplied by AWS_DESCRIBE_REQUEST_RETRY_ATTEMPTS.

---

## Example awsprov_config.json file

### Windows

``
{
  "ACCEPT_PROPAGATED_LOG_SETTING": "false",
  "AWS_CREDENTIAL_FILE": "C:\\AmazonKey\\credentials",
  "AWS_KEY_FILE": "C:\\AmazonKey\\",
  "AWS_REGION": "us-east-1",
  "AWS_PROXY_HOST": "proxyhost",
  "AWS_PROXY_PORT": 80,
  "AWS_CONNECTION_TIMEOUT_MS": 10000,
  "AWS_REQUEST_RETRY_ATTEMPTS": 0
}
``

### Linux

``
{
  "ACCEPT_PROPAGATED_LOG_SETTING": "false",
  "AWS_CREDENTIAL_FILE": "/home/aws/credentials",
  "AWS_KEY_FILE": "/home/aws/",
  "AWS_REGION": "us-east-1",
  "AWS_PROXY_HOST": "proxyhost",
  "AWS_PROXY_PORT": 80,
  "AWS_CONNECTION_TIMEOUT_MS": 10000,
  "AWS_REQUEST_RETRY_ATTEMPTS": 0
}
``

---

## References

- [IBM Spectrum Symphony 7.3.2 awsprov_config.json Documentation](https://www.ibm.com/docs/en/spectrum-symphony/7.3.2?topic=factory-awsprov-configjson)
- [IBM Spectrum Symphony 7.3.1 awsprov_config.json Reference](https://www.ibm.com/docs/en/spectrum-symphony/7.3.1?topic=reference-awsprov-configjson)
