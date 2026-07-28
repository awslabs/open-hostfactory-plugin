"""Provider-connectivity failures must surface as 'degraded', not 'unhealthy'.

An unreachable provider API (exception on the connectivity probe) is a
degraded signal, not a hard failure of the process.  Since ``/health``
maps degraded -> 200, this keeps a single unreachable provider from
forcing the whole endpoint to 503.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
class TestAWSHealthDegraded:
    def _register_and_capture(self, aws_client):
        from orb.providers.aws.health import register_aws_health_checks

        captured: dict[str, object] = {}

        health_check = MagicMock()

        def _capture(name, fn, **kwargs):
            captured[name] = fn

        health_check.register_check.side_effect = _capture
        register_aws_health_checks(health_check, aws_client, storage_strategy="json")
        return captured

    def test_aws_connectivity_failure_is_degraded(self) -> None:
        aws_client = MagicMock()
        aws_client.sts_client.get_caller_identity.side_effect = Exception("unreachable")
        captured = self._register_and_capture(aws_client)

        result = captured["aws"]()
        assert result.status == "degraded"
        assert "error" in result.details

    def test_ec2_connectivity_failure_is_degraded(self) -> None:
        from botocore.exceptions import ClientError

        aws_client = MagicMock()
        aws_client.ec2_client.describe_instances.side_effect = ClientError(
            {"Error": {"Code": "AuthFailure", "Message": "no creds"}},
            "DescribeInstances",
        )
        captured = self._register_and_capture(aws_client)

        result = captured["ec2"]()
        assert result.status == "degraded"
        assert "error" in result.details

    def test_aws_success_still_healthy(self) -> None:
        aws_client = MagicMock()
        aws_client.sts_client.get_caller_identity.return_value = {
            "Account": "123456789012",
            "UserId": "AID",
            "Arn": "arn:aws:iam::123456789012:user/x",
        }
        captured = self._register_and_capture(aws_client)

        result = captured["aws"]()
        assert result.status == "healthy"


@pytest.mark.unit
class TestK8sHealthDegraded:
    def _register_and_capture(self, kubernetes_client):
        from orb.providers.k8s.health import register_k8s_health_checks

        captured: dict[str, object] = {}

        health_check = MagicMock()

        def _capture(name, fn, **kwargs):
            captured[name] = fn

        health_check.register_check.side_effect = _capture
        register_k8s_health_checks(health_check, kubernetes_client)
        return captured

    def test_k8s_api_connectivity_failure_is_degraded(self) -> None:
        kubernetes_client = MagicMock()
        kubernetes_client.core_v1.get_api_resources.side_effect = Exception("unreachable")
        captured = self._register_and_capture(kubernetes_client)

        result = captured["kubernetes_api"]()
        assert result.status == "degraded"
        assert "error" in result.details

    def test_k8s_api_success_still_healthy(self) -> None:
        kubernetes_client = MagicMock()
        resources = MagicMock()
        resources.resources = [MagicMock(), MagicMock()]
        resources.group_version = "v1"
        kubernetes_client.core_v1.get_api_resources.return_value = resources
        captured = self._register_and_capture(kubernetes_client)

        result = captured["kubernetes_api"]()
        assert result.status == "healthy"
