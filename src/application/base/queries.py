"""Base query handlers - foundation for query processing."""
from typing import Protocol
from src.application.dto.base import BaseQuery, BaseResponse


class QueryBus(Protocol):
    """Protocol for query bus."""
    
    async def send(self, query: BaseQuery) -> BaseResponse:
        """Send a query for processing."""
        ...
    
    def register_handler(self, query_type: type, handler) -> None:
        """Register a query handler."""
        ...
