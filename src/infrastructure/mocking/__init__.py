"""Infrastructure mocking utilities for dry-run support."""

from .dry_run_context import dry_run_context, is_dry_run_active

__all__ = ['dry_run_context', 'is_dry_run_active']
