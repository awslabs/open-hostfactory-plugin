"""AMI Resolution interface for template domain."""
from abc import ABC, abstractmethod


class AMIResolver(ABC):
    """
    Interface for resolving AMI IDs from various formats.
    
    This interface allows the domain layer to resolve AMI IDs without
    depending on specific cloud provider implementations.
    """
    
    @abstractmethod
    def resolve_ami_id(self, ami_id_or_alias: str) -> str:
        """
        Resolve AMI ID from alias, SSM parameter path, or direct ID.
        
        Args:
            ami_id_or_alias: AMI ID, alias, or SSM parameter path
            
        Returns:
            Resolved AMI ID
            
        Raises:
            ValueError: If AMI cannot be resolved
        """
