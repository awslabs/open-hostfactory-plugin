---------------------------------------------------------------------------------------------------------------------

getAvailableTemplates

https://www.ibm.com/docs/en/spectrum-symphony/7.3.2?topic=specification-getavailabletemplates

Input

In the documentation there appear to be a possibility of input, however, 

```
getAvailableTemplates.sh -f /tmp/hf_in_tvXQSo
{
}
```


```{
  "templates":
  [
    {
      "templateId": "(mandatory)(string) unique name for the template",
      "maxNumber": "(mandatory)(numeric) max hosts that can be provisioned",
      "attributes":  
      {
          "type": "(mandatory) ["String", "type of VM. Supported values are any EGO_MACHINE_TYPE including X86_64, NTX64, etc"]",
          "ncpus": "(mandatory) ["Numeric", "number of CPUs per host "]",
          "nram": "(mandatory) ["Numeric", "minimum RAM required per host"]"      
      },
      "attr_1": (optional) additional host provider specific attributes in JSON format,  
      ...       
      "attr_n": "(optional) additional host provider specific attributes in JSON format" 
     },
   ...
   ]
}
```

Output
```
[egoadmin@ip-10-0-59-217 ~]$ cat getAvailableTemplates.log
{
  "templates" : [ {
    "templateId" : "OnDemand-Minimal-Template-VM",
    "maxNumber" : 10,
    "attributes" : {
      "nram" : [ "Numeric", "1024" ],
      "ncpus" : [ "Numeric", "1" ],
      "ncores" : [ "Numeric", "1" ],
      "type" : [ "String", "X86_64" ]
    },
    "pgrpName" : null,
    "onDemandCapacity" : 0
  }, {
    "templateId" : "Spot-Template-VM",
    "maxNumber" : 10,
    "attributes" : {
      "nram" : [ "Numeric", "1024" ],
      "ncpus" : [ "Numeric", "1" ],
      "ncores" : [ "Numeric", "1" ],
      "type" : [ "String", "X86_64" ]
    },
    "vmTypes" : {
      "m3.medium" : 1
    },
    "instanceTags" : "company=abc;project=awscloud;team=xyz",
    "pgrpName" : null,
    "onDemandCapacity" : 0
  } ],
  "message" : "Get available templates success."
}
```


```
{
 "message": "(optional)(string) Any additional message the caller should know",
 "templates": [
    {
    "templateId": "(mandatory)(string) Unique ID to identify this template in the host provider",
    "maxNumber": "(mandatory)(numeric) Maximum number of machines that can be provisioned with this template configuration. Use -1to indicate an unlimited number of machines of this template",
    "availableNumber": "(optional)(numeric) Number of machines that can be currently provisioned with this template",  
    "requestedMachines": "(optional)(list of strings)["Names of machines provisioned from this template"],
      "attributes":  
      {
          "type": "(mandatory) ["String", "type of VM. Supported values are any EGO_MACHINE_TYPE including X86_64, NTX64, etc"]",
          "ncpus": "(mandatory) ["Numeric", "number of CPUs per host "]",
          "nram": "(mandatory) ["Numeric", "minimum RAM required per host"]"      
      },
      "attr_1": "(optional) additional host provider specific attributes in JSON format",  
      ...       
      "attr_n": "(optional) additional host provider specific attributes in JSON format" 
     },
   ...
   ]
} 
```
---------------------------------------------------------------------------------------------------------------------

requestMachines

input
```
{
  "template":
    {
      "templateId": "(mandatory)(string) Unique ID that can identify this template in the cloud provider",
      "machineCount": (mandatory)(numeric) Number of hosts of this template to be provisioned.
    }
}
```
```
requestMachines.sh -f /tmp/hf_in_mENZcL
{
        "template":     {
                "templateId":   "Spot-Template-VM",
                "machineCount": 10
        }
}
```

output

```
{
  "message": "(optional)(string) Any additional message the caller should know",  
  "requestId": "(mandatory)(string) Unique ID to identify this request in the cloud provider"
}
```

Example:
```
{
  "message" : "Request VM success from AWS.",
  "requestId" : "r-010d8f03b13097efd"
}
```
OR
```
{
  "message" : "Request Spot Instance on awsinst EC2 failed."
} 
```
---------------------------------------------------------------------------------------------------------------------

requestReturnMachines

Input

```
{
  "machines":
      {"name": "(mandatory)(string) Host name of the machine that must be returned"}
}
```

```
requestReturnMachines.sh -f /tmp/hf_in_yeQeSL
{
        "machines":     [{
                        "name": "ip-10-0-57-7.ec2.internal",
                        "machineId":    "i-0e90ecb3228822f6f"
                }, {
                        "name": "ip-10-0-57-154.ec2.internal",
                        "machineId":    "i-0c8755260b9aa6ebe"
                }, {
                        "name": "ip-10-0-62-139.ec2.internal",
                        "machineId":    "i-0e219a7b5a927368a"
                }, {
                        "name": "ip-10-0-58-203.ec2.internal",
                        "machineId":    "i-0cd2be94721fe4c6f"
                }, {
                        "name": "ip-10-0-57-22.ec2.internal",
                        "machineId":    "i-0721bb06651cad7f1"
                }, {
                        "name": "ip-10-0-55-65.ec2.internal",
                        "machineId":    "i-0af73d1e849ff1be7"
                }, {
                        "name": "ip-10-0-57-187.ec2.internal",
                        "machineId":    "i-0f7862c0e491a3699"
                }, {
                        "name": "ip-10-0-51-28.ec2.internal",
                        "machineId":    "i-0f1dfc111f6d14851"
                }]
}
```

Output

```
{
    "message": "(optional)(string) Any additional message the caller should know", 
    "requestId": "(mandatory)(string) Unique ID to identify this request in the cloud provider"
}
```

```
[egoadmin@ip-10-0-59-217 ~]$ cat requestReturnMachines.log
{
"message" : "Delete VM success.",
"requestId" : "ret-ce0680f0-01aa-4220-b10f-b658bb7b219e"
}

OR

{
"message" : "No Active VM.",
"requestId" : "ret-270e5a85-a7c8-4a76-9dd5-e1cdb9c47861"
}
```

---------------------------------------------------------------------------------------------------------------------

getRequestStatus

Input 

```
{
  "requests":
    {
      "requestId": "Required. Valid value type is string. Unique ID to identify this request in the cloud provider"
    }
}
```

```
getRequestStatus.sh -f /tmp/hf_in_Q2kSeS
{
        "requests":     [{
                        "requestId":    "ret-84ffbee9-8c84-4afe-8e8e-ac052a7ff8d3"
                }]
}
```

Output

```
{
    "requests": {
       "requestId":  "(mandatory)(string) Unique ID to identify this request in the cloud provider",
       "message": "(optional)(string) Any additional message the caller should know",
       "status": "(mandatory)(string) Status of request. Possible values: 'running', 'complete', 'complete_with_error'. You should check the machine information, if any, when the value is 'complete' or 'complete_with_error'",
       "machines": {
            "machineId" : "(mandatory)(string) ID of the machine being retrieved from provider",
            "name": "(mandatory)(string) Host name of the machine",
            "result": "(mandatory)(string) "Status of this request related to this machine. Possible values:  'executing', 'fail', 'succeed'. For example,
 call requestMachines with templateId and machineCount 3, and then call getRequestStatus to check the status of this request. We should get 3 machines with
 result 'succeed'. If any machine is missing or the status is not correct, that machine is not usable.",
            "status" : "(optional)(string) Status of machine. Expected values: running, stopped, terminated, shutting-down, stopping."
            "privateIpAddress" : "(mandatory)(string) private IP address of the machine",
            "publicIpAddress" :  "(optional)(string) public IP address of the machine",
            "launchtime": (mandatory)(numeric) Launch time of the machine in seconds (UTC format)",
            "message": "(mandatory if the value of 'result' parameter is 'fail')(string). Additional message for the request status of this machine"
           }
     }
 }
```

EXAMPLE:
```
{
    "requests" : [ {
      "status" : "complete",
      "machines" : [ {
        "machineId" : "i-0721bb06651cad7f1",
        "name" : "ip-10-0-57-22.ec2.internal",
        "priceType" : "ondemand",
        "instanceType" : "r5n.2xlarge",
        "result" : "succeed",
        "status" : "terminated",
        "privateIpAddress" : "10.0.57.22",
        "instanceTags" : "",
        "cloudHostId" : null,
        "launchtime" : 1734619942,
        "message" : ""
      }, {
        "machineId" : "i-0af73d1e849ff1be7",
        "name" : "ip-10-0-55-65.ec2.internal",
        "priceType" : "ondemand",
        "instanceType" : "r5n.2xlarge",
        "result" : "succeed",
        "status" : "terminated",
        "privateIpAddress" : "10.0.55.65",
        "instanceTags" : "",
        "cloudHostId" : null,
        "launchtime" : 1734619942,
        "message" : ""
      }, {
        "machineId" : "i-0f7862c0e491a3699",
        "name" : "ip-10-0-57-187.ec2.internal",
        "priceType" : "ondemand",
        "instanceType" : "r5n.2xlarge",
        "result" : "succeed",
        "status" : "terminated",
        "privateIpAddress" : "10.0.57.187",
        "instanceTags" : "",
        "cloudHostId" : null,
        "launchtime" : 1734619942,
        "message" : ""
      }, {
        "machineId" : "i-0f1dfc111f6d14851",
        "name" : "ip-10-0-51-28.ec2.internal",
        "priceType" : "ondemand",
        "instanceType" : "r5n.2xlarge",
        "result" : "succeed",
        "status" : "terminated",
        "privateIpAddress" : "10.0.51.28",
        "instanceTags" : "",
        "cloudHostId" : null,
        "launchtime" : 1734619942,
        "message" : ""
      }, {
        "machineId" : "i-0e90ecb3228822f6f",
        "name" : "ip-10-0-57-7.ec2.internal",
        "priceType" : "ondemand",
        "instanceType" : "r5n.2xlarge",
        "result" : "succeed",
        "status" : "terminated",
        "privateIpAddress" : "10.0.57.7",
        "instanceTags" : "",
        "cloudHostId" : null,
        "launchtime" : 1734619988,
        "message" : ""
      }, {
        "machineId" : "i-0c8755260b9aa6ebe",
        "name" : "ip-10-0-57-154.ec2.internal",
        "priceType" : "ondemand",
        "instanceType" : "r5n.2xlarge",
        "result" : "succeed",
        "status" : "terminated",
        "privateIpAddress" : "10.0.57.154",
        "instanceTags" : "",
        "cloudHostId" : null,
        "launchtime" : 1734619988,
        "message" : ""
      }, {
        "machineId" : "i-0e219a7b5a927368a",
        "name" : "ip-10-0-62-139.ec2.internal",
        "priceType" : "ondemand",
        "instanceType" : "r5n.2xlarge",
        "result" : "succeed",
        "status" : "terminated",
        "privateIpAddress" : "10.0.62.139",
        "instanceTags" : "",
        "cloudHostId" : null,
        "launchtime" : 1734619988,
        "message" : ""
      }, {
        "machineId" : "i-0cd2be94721fe4c6f",
        "name" : "ip-10-0-58-203.ec2.internal",
        "priceType" : "ondemand",
        "instanceType" : "r5n.2xlarge",
        "result" : "succeed",
        "status" : "terminated",
        "privateIpAddress" : "10.0.58.203",
        "instanceTags" : "",
        "cloudHostId" : null,
        "launchtime" : 1734619988,
        "message" : ""
      } ],
      "requestId" : "ret-84ffbee9-8c84-4afe-8e8e-ac052a7ff8d3",
      "message" : ""
    } ]
}
```

---------------------------------------------------------------------------------------------------------------------

getReturnRequests

Input

```
{
  "machines":[(optional)All hosts provisioned from the provider and known to HostFactory
      {"name": "(mandatory)(string) Host name of the machine"}
    ]
}
```

EXAMPLE:
```
getReturnRequests.sh -f /tmp/hf_in_hJ0r8z
{
        "machines":     [{
                        "name": "ip-10-0-58-4.ec2.internal",
                        "machineId":    "i-022161abf93cc2af9"
                }, {
                        "name": "ip-10-0-50-105.ec2.internal",
                        "machineId":    "i-03fb8d8d5a6b2d681"
                }]
}
```

Output

```
{
    "message": "Any additional message the caller should know" 
    "requests": [Note: Includes Spot instances and On-Demand instances returned from the management console.
     {
       "machine": "(mandatory)(string) Host name of the machine that must be returned",
       "gracePeriod": "(mandatory)(numeric). Time remaining (in seconds) before this host will be reclaimed by the provider"
     }]
  }
```

  EXAMPLE:
```
  {
    "status" : "complete",
    "message" : "Instances marked for termination retrieved successfully.",
    "requests" : [ ]
  }
```
```
  {
    "status" : "complete",
    "message" : "Instances marked for termination retrieved successfully.",
    "requests" : [ {
      "gracePeriod" : 0,
      "machine" : "ip-10-0-57-7.ec2.internal"
    }, {
      "gracePeriod" : 0,
      "machine" : "ip-10-0-57-154.ec2.internal"
    }, {
      "gracePeriod" : 0,
      "machine" : "ip-10-0-62-139.ec2.internal"
    }, {
      "gracePeriod" : 0,
      "machine" : "ip-10-0-58-203.ec2.internal"
    }, {
      "gracePeriod" : 0,
      "machine" : "ip-10-0-57-22.ec2.internal"
    }, {
      "gracePeriod" : 0,
      "machine" : "ip-10-0-55-65.ec2.internal"
    }, {
      "gracePeriod" : 0,
      "machine" : "ip-10-0-57-187.ec2.internal"
    }, {
      "gracePeriod" : 0,
      "machine" : "ip-10-0-51-28.ec2.internal"
    } ]
  }
```