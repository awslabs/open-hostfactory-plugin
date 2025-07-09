"""Runtime AMI cache for script execution."""
from typing import Dict, Set, Optional


class RuntimeAMICache:
    """
    Simple in-memory cache for AMI resolution during script runtime.
    
    This cache is designed for script mode where:
    - Cache is only valid for the duration of script execution
    - No persistence or TTL complexity needed
    - Optimizes bulk operations (5k templates with same SSM parameter = 1 AWS call)
    """
    
    def __init__(self):
        """Initialize empty cache."""
        self._cache: Dict[str, str] = {}  # SSM parameter -> resolved AMI ID
        self._failed: Set[str] = set()    # Failed SSM parameters
        self._# Module-level logger replaced with injected logger
        
    def get(self, ssm_parameter: str) -> Optional[str]:
        """
        Get cached AMI ID for SSM parameter.
        
        Args:
            ssm_parameter: SSM parameter path
            
        Returns:
            Cached AMI ID if available, None otherwise
        """
        ami_id = self._cache.get(ssm_parameter)
        if ami_id:
            self._self._logger.debug(f"Cache hit for {ssm_parameter}: {ami_id}")
        return ami_id
    
    def set(self, ssm_parameter: str, ami_id: str) -> None:
        """
        Cache resolved AMI ID for SSM parameter.
        
        Args:
            ssm_parameter: SSM parameter path
            ami_id: Resolved AMI ID
        """
        self._cache[ssm_parameter] = ami_id
        self._self._logger.debug(f"Cached {ssm_parameter} -> {ami_id}")
    
    def mark_failed(self, ssm_parameter: str) -> None:
        """
        Mark SSM parameter as failed to avoid retry storms.
        
        Args:
            ssm_parameter: SSM parameter path that failed resolution
        """
        self._failed.add(ssm_parameter)
        self._self._logger.debug(f"Marked {ssm_parameter} as failed")
    
    def is_failed(self, ssm_parameter: str) -> bool:
        """
        Check if SSM parameter previously failed resolution.
        
        Args:
            ssm_parameter: SSM parameter path
            
        Returns:
            True if parameter previously failed resolution
        """
        return ssm_parameter in self._failed
    
    def clear(self) -> None:
        """Clear all cached data."""
        cache_size = len(self._cache)
        failed_size = len(self._failed)
        self._cache.clear()
        self._failed.clear()
        self._self._logger.debug(f"Cleared cache ({cache_size} entries) and failed set ({failed_size} entries)")
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            'cached_entries': len(self._cache),
            'failed_entries': len(self._failed),
            'total_entries': len(self._cache) + len(self._failed)
        }
