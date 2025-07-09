"""API routers package."""

from .templates import router as templates_router
from .machines import router as machines_router
from .requests import router as requests_router

__all__ = [
    'templates_router',
    'machines_router', 
    'requests_router'
]
