"""Unit tests for OrchestratorBase._dispatch error-handling seam."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from orb.application.services.orchestration.base import OrchestratorBase


class _StubOrchestrator(OrchestratorBase[str, str]):
    """Minimal concrete orchestrator exposing _dispatch for testing."""

    def __init__(self, logger: MagicMock) -> None:
        self._logger = logger

    async def execute(self, input: str) -> str:
        return input


@pytest.fixture
def logger() -> MagicMock:
    return MagicMock()


@pytest.fixture
def orchestrator(logger: MagicMock) -> _StubOrchestrator:
    return _StubOrchestrator(logger)


@pytest.mark.unit
@pytest.mark.application
class TestOrchestratorBaseDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_returns_result_on_success(self, orchestrator, logger):
        async def _ok() -> int:
            return 42

        result = await orchestrator._dispatch("Op", _ok())

        assert result == 42
        logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_logs_and_reraises_original_exception(self, orchestrator, logger):
        boom = ValueError("boom")

        async def _fail() -> int:
            raise boom

        with pytest.raises(ValueError) as exc_info:
            await orchestrator._dispatch("MyOp", _fail())

        # The original exception instance/type is preserved (not wrapped).
        assert exc_info.value is boom
        logger.error.assert_called_once()
        # Operation label is included in the log so failures are attributable.
        assert "MyOp" in str(logger.error.call_args)

    @pytest.mark.asyncio
    async def test_dispatch_preserves_exception_subtype(self, orchestrator, logger):
        class CustomError(RuntimeError):
            pass

        async def _fail() -> int:
            raise CustomError("specific")

        with pytest.raises(CustomError):
            await orchestrator._dispatch("Op", _fail())
