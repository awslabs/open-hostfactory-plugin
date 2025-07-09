"""CLI command handler for REST API server."""
import asyncio
import signal
import sys
from typing import Optional, Dict, Any

from src.interface.command_handlers import CLICommandHandler
from src.config.manager import ConfigurationManager
from src.config.schemas.server_schema import ServerConfig
from src.infrastructure.di.services import register_all_services
from src.infrastructure.logging.logger import get_logger
from src.infrastructure.error.decorators import handle_interface_exceptions


class ServeCommandHandler(CLICommandHandler):
    """Handler for the serve command - starts REST API server."""
    
    def __init__(self, query_bus=None, command_bus=None):
        """Initialize serve command handler."""
        # ServeCommandHandler doesn't actually use query_bus/command_bus, but CLICommandHandler requires them
        # We'll pass them through to satisfy the interface, but won't use them
        super().__init__(query_bus=query_bus, command_bus=command_bus)
        self.logger = get_logger(__name__)
        self.server_process = None
        
    def handle(self, command) -> Dict[str, Any]:
        """
        Handle the serve command - start REST API server.
        
        Args:
            command: Legacy command arguments with serve parameters
            
        Returns:
            Command result
        """
        # Extract parameters from legacy args
        host = getattr(command, 'host', None)
        port = getattr(command, 'port', None)
        workers = getattr(command, 'workers', None)
        reload = getattr(command, 'reload', False)
        log_level = getattr(command, 'server_log_level', None)  # Use server_log_level to avoid conflict
        
        # Call the async handler synchronously
        return self.handle_sync(
            host=host,
            port=port,
            workers=workers,
            reload=reload,
            log_level=log_level
        )
    
    @handle_interface_exceptions(context="serve_command", interface_type="cli")
    async def handle_async(self, 
                          host: Optional[str] = None,
                          port: Optional[int] = None,
                          workers: Optional[int] = None,
                          reload: bool = False,
                          log_level: Optional[str] = None,
                          **kwargs) -> Dict[str, Any]:
        """
        Handle the serve command asynchronously - start REST API server.
        
        Args:
            host: Server host (overrides config)
            port: Server port (overrides config)
            workers: Number of worker processes
            reload: Enable auto-reload for development
            log_level: Server log level
            **kwargs: Additional arguments
            
        Returns:
            Command result
        """
        try:
            # Load configuration
            config_manager = ConfigurationManager()
            server_config = config_manager.get_typed(ServerConfig)
            
            # Check if server is enabled
            if not server_config.enabled:
                return {
                    "success": False,
                    "message": "REST API server is disabled in configuration. Set server.enabled=true to enable.",
                    "data": {
                        "server_enabled": False,
                        "config_file": "config/default_config.json"
                    }
                }
            
            # Apply command line overrides
            effective_config = self._apply_overrides(server_config, host, port, workers, reload, log_level)
            
            self.logger.info(f"Starting REST API server on {effective_config.host}:{effective_config.port}")
            
            # Register all services (including server services)
            container = register_all_services()
            
            # Start the server
            await self._start_server(effective_config)
            
            return {
                "success": True,
                "message": "REST API server started successfully",
                "data": {
                    "host": effective_config.host,
                    "port": effective_config.port,
                    "workers": effective_config.workers,
                    "docs_url": f"http://{effective_config.host}:{effective_config.port}{effective_config.docs_url}" if effective_config.docs_enabled else None
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to start REST API server: {e}")
            return {
                "success": False,
                "message": f"Failed to start REST API server: {str(e)}",
                "error": str(e)
            }
    
    def _apply_overrides(self, 
                        server_config: ServerConfig,
                        host: Optional[str],
                        port: Optional[int],
                        workers: Optional[int],
                        reload: bool,
                        log_level: Optional[str]) -> ServerConfig:
        """Apply command line overrides to server configuration."""
        # Create a copy of the config with overrides
        config_dict = server_config.model_dump()
        
        if host is not None:
            config_dict['host'] = host
        if port is not None:
            config_dict['port'] = port
        if workers is not None:
            config_dict['workers'] = workers
        if reload:
            config_dict['reload'] = reload
        if log_level is not None:
            config_dict['log_level'] = log_level
            
        return ServerConfig(**config_dict)
    
    async def _start_server(self, server_config: ServerConfig) -> None:
        """Start the FastAPI server with uvicorn."""
        try:
            import uvicorn
            from src.api.server import create_fastapi_app
            
            # Create FastAPI app
            app = create_fastapi_app(server_config)
            
            # Configure uvicorn
            uvicorn_config = uvicorn.Config(
                app=app,
                host=server_config.host,
                port=server_config.port,
                workers=server_config.workers if not server_config.reload else 1,  # Workers=1 for reload mode
                reload=server_config.reload,
                log_level=server_config.log_level,
                access_log=server_config.access_log,
            )
            
            # Create and start server
            server = uvicorn.Server(uvicorn_config)
            
            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers(server)
            
            self.logger.info(f"REST API server starting on http://{server_config.host}:{server_config.port}")
            if server_config.docs_enabled:
                self.logger.info(f"API documentation available at http://{server_config.host}:{server_config.port}{server_config.docs_url}")
            
            # Start the server (this blocks until shutdown)
            await server.serve()
            
        except ImportError:
            raise RuntimeError("uvicorn is required to run the REST API server. Install with: pip install uvicorn[standard]")
        except Exception as e:
            self.logger.error(f"Server startup failed: {e}")
            raise
    
    def _setup_signal_handlers(self, server) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            """Handle shutdown signals gracefully.
            
            Args:
                signum: Signal number received
                frame: Current stack frame
            """
            self.logger.info(f"Received signal {signum}, shutting down gracefully...")
            server.should_exit = True
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # On Windows, also handle CTRL_BREAK_EVENT
        if sys.platform == "win32":
            signal.signal(signal.SIGBREAK, signal_handler)
    
    def handle_sync(self, **kwargs) -> Dict[str, Any]:
        """Synchronous wrapper for the serve command."""
        try:
            return asyncio.run(self.handle_async(**kwargs))
        except KeyboardInterrupt:
            self.logger.info("Server shutdown requested by user")
            return {
                "success": True,
                "message": "Server shutdown completed",
                "data": {"shutdown_reason": "user_request"}
            }
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            return {
                "success": False,
                "message": f"Server error: {str(e)}",
                "error": str(e)
            }
