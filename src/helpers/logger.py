import os
import logging
import structlog
from logging.handlers import RotatingFileHandler
from typing import Dict, Any
from src.config.defaults import ConfigurationManager

def setup_logging(config: Dict[str, Any] = None) -> structlog.BoundLogger:
    """
    Set up structured logging for the application using structlog.
    
    Args:
        config: Configuration dictionary from ConfigurationManager.
               If None, uses environment variables and defaults.
    Returns:
        Configured structlog logger instance.
    """
    if config is None:
        # Use ConfigurationManager if no config provided
        config_manager = ConfigurationManager()
        config = config_manager.get_config()

    logging_config = config["LOGGING_CONFIG"]
    
    # Get configuration values with fallbacks
    provider_name = os.environ.get("HF_PROVIDER_NAME", "default")
    log_dir = os.path.expandvars(logging_config["file"]["path"])
    
    # Ensure the log directory exists
    os.makedirs(os.path.dirname(log_dir), exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, logging_config["level"].upper()))

    # Create custom formatter that includes caller information
    class DetailedFormatter(logging.Formatter):
        def format(self, record):
            # Add method name and line number to the record
            record.caller_info = f"{record.module}.{record.funcName}:{record.lineno}"
            return super().format(record)

    # Configure format strings
    log_format = "%(asctime)s - %(levelname)s - %(name)s [%(caller_info)s] - %(message)s"

    # Configure handlers
    handlers = []
    
    if logging_config["destination"] in ("file", "both"):
        file_handler = RotatingFileHandler(
            log_dir,
            maxBytes=logging_config["file"]["max_size_mb"] * 1024 * 1024,
            backupCount=logging_config["file"]["backup_count"]
        )
        file_handler.setFormatter(DetailedFormatter(log_format))
        handlers.append(file_handler)

    if logging_config["destination"] in ("stdout", "both"):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(DetailedFormatter(log_format))
        handlers.append(console_handler)

    # Remove any existing handlers and add new ones
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    for handler in handlers:
        root_logger.addHandler(handler)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger(provider_name)
    
    # Log configuration info
    logger.debug(
        "Logging configured",
        log_level=logging_config["level"],
        log_destination=logging_config["destination"],
        log_dir=log_dir
    )

    return logger

# Initialize a global logger instance with default configuration
logger = setup_logging()