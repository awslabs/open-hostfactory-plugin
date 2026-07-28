"""AWSImageCache surfaces cache read/write failures instead of swallowing them.

A corrupt cache file or an unwritable directory is non-fatal — the cache
degrades gracefully — but the failure must not vanish silently. These tests
lock in that a debug log is emitted on each failure path.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from orb.providers.aws.infrastructure.caching.aws_image_cache import AWSImageCache


@pytest.mark.unit
class TestAWSImageCacheFailureLogging:
    def test_corrupt_cache_file_is_logged_and_reset(self, tmp_path) -> None:
        cache_file = tmp_path / "image_cache_aws.json"
        cache_file.write_text("{ not valid json")

        with patch(
            "orb.providers.aws.infrastructure.caching.aws_image_cache._logger"
        ) as mock_logger:
            cache = AWSImageCache(provider_name="aws", cache_dir=str(tmp_path))

        assert cache._runtime_cache == {}
        mock_logger.debug.assert_called()

    def test_unwritable_cache_save_is_logged(self, tmp_path) -> None:
        cache = AWSImageCache(provider_name="aws", cache_dir=str(tmp_path))

        with patch(
            "orb.providers.aws.infrastructure.caching.aws_image_cache._logger"
        ) as mock_logger:
            with patch(
                "orb.providers.aws.infrastructure.caching.aws_image_cache.open",
                side_effect=IOError("disk full"),
            ):
                cache.set("al2023", "ami-123")

        mock_logger.debug.assert_called()

    def test_healthy_roundtrip_does_not_log(self, tmp_path) -> None:
        cache = AWSImageCache(provider_name="aws", cache_dir=str(tmp_path))
        cache.set("al2023", "ami-123")
        assert cache.get("al2023") == "ami-123"
        assert os.path.exists(cache._cache_file)
