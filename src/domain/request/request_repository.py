# src/domain/request/request_repository.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from src.domain.request.request_aggregate import Request
from src.domain.request.value_objects import RequestId, RequestStatus
from src.domain.request.exceptions import RequestNotFoundError

class RequestRepository(ABC):
    """Repository interface for request persistence."""
    
    @abstractmethod
    def save(self, request: Request) -> None:
        """Save a new request or update an existing one."""
        pass

    @abstractmethod
    def find_by_id(self, request_id: RequestId) -> Optional[Request]:
        """Find a request by its ID."""
        pass

    @abstractmethod
    def find_by_status(self, status: RequestStatus) -> List[Request]:
        """Find all requests with a specific status."""
        pass

    def find_by_template_id(self, template_id: str) -> List[Request]:
        """
        Find all requests for a specific template.
        
        Args:
            template_id: ID of the template to find requests for
            
        Returns:
            List of requests using the specified template
        """
        pass

    @abstractmethod
    def find_active_requests(self) -> List[Request]:
        """Find all active (non-completed) requests."""
        pass

    def find_pending_timeouts(self) -> List[Request]:
        """
        Find requests that may have timed out.
        
        Returns:
            List of requests that have exceeded their timeout period
        """
        pass

    @abstractmethod
    def find_return_requests(self) -> List[Request]:
        """Find all return requests."""
        pass

    @abstractmethod
    def delete(self, request_id: RequestId) -> None:
        """Delete a request."""
        pass

    @abstractmethod
    def exists(self, request_id: RequestId) -> bool:
        """Check if a request exists."""
        pass

class JSONRequestRepository(RequestRepository):
    """JSON file implementation of request repository."""
    
    def __init__(self, db_handler):
        """Initialize with database handler."""
        self._db = db_handler

    def save(self, request: Request) -> None:
        """Save or update a request."""
        self._db.add_or_update_request(request)

    def find_by_id(self, request_id: RequestId) -> Optional[Request]:
        """Find a request by its ID."""
        request_data = self._db.get_request(str(request_id))
        return Request.from_dict(request_data) if request_data else None

    def find_by_status(self, status: RequestStatus) -> List[Request]:
        """Find all requests with a specific status."""
        requests_data = self._db.get_requests_by_status(status.value)
        return [Request.from_dict(data) for data in requests_data]

    def find_by_template_id(self, template_id: str) -> List[Request]:
        """Find all requests for a specific template."""
        return self.find_by_criteria({"template_id": str(template_id)})

    def find_active_requests(self) -> List[Request]:
        """Find all active (non-completed) requests."""
        active_statuses = [
            RequestStatus.PENDING.value,
            RequestStatus.RUNNING.value
        ]
        requests = []
        for status in active_statuses:
            requests.extend(self.find_by_status(RequestStatus(status)))
        return requests

    def find_pending_timeouts(self) -> List[Request]:
        """Find requests that may have timed out."""
        active_requests = self.find_active_requests()
        return [
            request for request in active_requests
            if request.has_timed_out
        ]

    def find_return_requests(self) -> List[Request]:
        """Find all return requests."""
        all_requests = self._db.get_all_requests()
        return [
            Request.from_dict(data) for data in all_requests 
            if RequestId(data["requestId"]).is_return_request
        ]

    def delete(self, request_id: RequestId) -> None:
        """Delete a request."""
        self._db.delete_request(str(request_id))

    def exists(self, request_id: RequestId) -> bool:
        """Check if a request exists."""
        return self._db.get_request(str(request_id)) is not None

    def clean_old_requests(self, max_age_hours: int = 24) -> None:
        """Clean up old completed requests."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        all_requests = self._db.get_all_requests()
        
        for request_data in all_requests:
            request = Request.from_dict(request_data)
            if (request.is_complete and 
                request.last_status_check and 
                request.last_status_check < cutoff_time):
                self.delete(request.request_id)