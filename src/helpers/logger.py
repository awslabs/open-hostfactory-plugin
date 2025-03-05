import logging
import os

def setup_logging(
    log_dir: str = None,
    log_filename: str = None,
    log_level: str = "INFO",
    log_destination: str = "both"
) -> logging.Logger:
    """
    Set up logging for the application.

    :param log_dir: Directory where the log file will be stored.
    :param log_filename: Name of the log file.
    :param log_level: Logging level (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL).
    :param log_destination: Where to send logs ("file", "stdout", or "both").
    :return: Configured logger instance.
    """
    # Default values for log directory and file name
    provider_name = os.environ.get("HF_PROVIDER_NAME", "default")
    default_log_dir = os.environ.get("HF_PROVIDER_LOGDIR", f"./{provider_name}/logs")
    default_log_filename = f"{provider_name}_log.log"

    log_dir = log_dir or default_log_dir
    log_filename = log_filename or default_log_filename

    # Ensure the log directory exists
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Configure logging handlers
    handlers = []
    if log_destination in ("file", "both"):
        file_handler = logging.FileHandler(os.path.join(log_dir, log_filename))
        handlers.append(file_handler)
    
    if log_destination in ("stdout", "both"):
        stream_handler = logging.StreamHandler()
        handlers.append(stream_handler)

    # Configure logging format
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(name)s.%(module)s.%(funcName)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )

    logger = logging.getLogger(provider_name)
    # logger.info(f"Logging initialized. Level: {log_level}, Destination: {log_destination}")
    
    return logger

# Initialize a global logger instance
logger = setup_logging()
