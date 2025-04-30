import pytest
from src.domain.template.template_aggregate import Template
from src.domain.template.exceptions import TemplateValidationError

@pytest.fixture
def valid_template_data():
    return {
        "templateId": "test-template",
        "awsHandler": "EC2Fleet",
        "maxNumber": 10,
        "attributes": {
            "type": ["String", "X86_64"],
            "ncores": ["Numeric", "2"],
            "ncpus": ["Numeric", "1"],
            "nram": ["Numeric", "4096"]
        },
        "imageId": "ami-12345678",
        "subnetId": "subnet-12345",
        "vmType": "t2.micro",
        "securityGroupIds": ["sg-12345"]
    }

def test_template_validation_missing_required_fields(valid_template_data):
    # Remove required fields
    invalid_data = valid_template_data.copy()
    del invalid_data["awsHandler"]
    
    with pytest.raises(TemplateValidationError) as exc:
        Template.from_dict(invalid_data)
    assert "awsHandler" in str(exc.value)

def test_template_validation_invalid_max_number(valid_template_data):
    invalid_data = valid_template_data.copy()
    invalid_data["maxNumber"] = 0
    
    with pytest.raises(TemplateValidationError) as exc:
        Template.from_dict(invalid_data)
    assert "maxNumber" in str(exc.value)

def test_template_attributes_validation(valid_template_data):
    invalid_data = valid_template_data.copy()
    invalid_data["attributes"]["ncores"] = ["Numeric", "-1"]
    
    with pytest.raises(TemplateValidationError) as exc:
        Template.from_dict(invalid_data)
    assert "attributes" in str(exc.value)

def test_template_subnet_validation(valid_template_data):
    invalid_data = valid_template_data.copy()
    del invalid_data["subnetId"]
    
    with pytest.raises(TemplateValidationError) as exc:
        Template.from_dict(invalid_data)
    assert "subnet" in str(exc.value)

def test_template_security_groups_validation(valid_template_data):
    invalid_data = valid_template_data.copy()
    invalid_data["securityGroupIds"] = []
    
    with pytest.raises(TemplateValidationError) as exc:
        Template.from_dict(invalid_data)
    assert "security group" in str(exc.value)

def test_template_vm_type_validation(valid_template_data):
    invalid_data = valid_template_data.copy()
    del invalid_data["vmType"]
    
    with pytest.raises(TemplateValidationError) as exc:
        Template.from_dict(invalid_data)
    assert "vm type" in str(exc.value)
