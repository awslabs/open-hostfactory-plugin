"""
File utility functions for the AWS Host Factory Plugin - Performance optimized.

This module provides a unified interface to file operations with lazy loading
and performance optimizations.
"""
from typing import Any, Dict, List, Callable, Optional, TYPE_CHECKING

# Use TYPE_CHECKING for imports that are only needed for type hints
if TYPE_CHECKING:
    from src.domain.base.ports import LoggingPort

# Lazy import core operations
def _get_logger():
    """Lazy import logger."""
    from src.infrastructure.logging.logger import get_logger
    return get_logger(__name__)

from .file_operations import (
    ensure_directory_exists,
    ensure_parent_directory_exists,
    read_text_file,
    write_text_file,
    read_json_file,
    write_json_file,
    file_exists,
    directory_exists,
    get_file_size,
    create_temp_file,
    create_temp_directory
)

# Lazy loading for complex operations
def read_yaml_file(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """
    Read a YAML file with lazy import.
    
    Args:
        file_path: File path
        encoding: File encoding
        
    Returns:
        Parsed YAML data
    """
    import yaml
    with open(file_path, 'r', encoding=encoding) as f:
        return yaml.safe_load(f)

def write_yaml_file(file_path: str, data: Dict[str, Any], encoding: str = "utf-8") -> None:
    """
    Write data to a YAML file with lazy import.
    
    Args:
        file_path: File path
        data: Data to write
        encoding: File encoding
    """
    import yaml
    ensure_parent_directory_exists(file_path)
    with open(file_path, 'w', encoding=encoding) as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

def copy_file(source_path: str, destination_path: str) -> None:
    """
    Copy a file with lazy import.
    
    Args:
        source_path: Source file path
        destination_path: Destination file path
    """
    import shutil
    ensure_parent_directory_exists(destination_path)
    shutil.copy2(source_path, destination_path)

def move_file(source_path: str, destination_path: str) -> None:
    """
    Move a file with lazy import.
    
    Args:
        source_path: Source file path
        destination_path: Destination file path
    """
    import shutil
    ensure_parent_directory_exists(destination_path)
    shutil.move(source_path, destination_path)

def delete_file(file_path: str) -> None:
    """
    Delete a file.
    
    Args:
        file_path: File path to delete
    """
    import os
    if file_exists(file_path):
        os.remove(file_path)

def delete_directory(directory_path: str, recursive: bool = False) -> None:
    """
    Delete a directory with lazy import.
    
    Args:
        directory_path: Directory path to delete
        recursive: Whether to delete recursively
    """
    import shutil
    import os
    
    if directory_exists(directory_path):
        if recursive:
            shutil.rmtree(directory_path)
        else:
            os.rmdir(directory_path)

def list_files(directory_path: str, pattern: Optional[str] = None, recursive: bool = False) -> List[str]:
    """
    List files in a directory with lazy import.
    
    Args:
        directory_path: Directory path
        pattern: File pattern to match (glob style)
        recursive: Whether to search recursively
        
    Returns:
        List of file paths
    """
    import glob
    from pathlib import Path
    
    if pattern:
        if recursive:
            search_pattern = str(Path(directory_path) / "**" / pattern)
            return glob.glob(search_pattern, recursive=True)
        else:
            search_pattern = str(Path(directory_path) / pattern)
            return glob.glob(search_pattern)
    else:
        path = Path(directory_path)
        if recursive:
            return [str(p) for p in path.rglob("*") if p.is_file()]
        else:
            return [str(p) for p in path.iterdir() if p.is_file()]

# Logger instance
logger = None

def get_file_utils_logger():
    """Get logger instance with lazy loading."""
    global logger
    if logger is None:
        logger = _get_logger()
    return logger

# Export all functions
__all__ = [
    'ensure_directory_exists',
    'ensure_parent_directory_exists',
    'read_text_file',
    'write_text_file',
    'read_json_file',
    'write_json_file',
    'read_yaml_file',
    'write_yaml_file',
    'file_exists',
    'directory_exists',
    'get_file_size',
    'create_temp_file',
    'create_temp_directory',
    'copy_file',
    'move_file',
    'delete_file',
    'delete_directory',
    'list_files',
    'get_file_utils_logger'
]

def write_text_file(file_path: str, content: str, encoding: str = "utf-8") -> None:
    """
    Write a text file.
    
    Args:
        file_path: File path
        content: File contents
        encoding: File encoding
        
    Raises:
        IOError: If file cannot be written
    """
    ensure_parent_directory_exists(file_path)
    with open(file_path, "w", encoding=encoding) as f:
        f.write(content)

def append_text_file(file_path: str, content: str, encoding: str = "utf-8") -> None:
    """
    Append to a text file.
    
    Args:
        file_path: File path
        content: Content to append
        encoding: File encoding
        
    Raises:
        IOError: If file cannot be written
    """
    ensure_parent_directory_exists(file_path)
    with open(file_path, "a", encoding=encoding) as f:
        f.write(content)

def read_binary_file(file_path: str) -> bytes:
    """
    Read a binary file.
    
    Args:
        file_path: File path
        
    Returns:
        File contents
        
    Raises:
        FileNotFoundError: If file does not exist
        IOError: If file cannot be read
    """
    with open(file_path, "rb") as f:
        return f.read()

def write_binary_file(file_path: str, content: bytes) -> None:
    """
    Write a binary file.
    
    Args:
        file_path: File path
        content: File contents
        
    Raises:
        IOError: If file cannot be written
    """
    ensure_parent_directory_exists(file_path)
    with open(file_path, "wb") as f:
        f.write(content)

def read_json_file(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """
    Read a JSON file.
    
    Args:
        file_path: File path
        encoding: File encoding
        
    Returns:
        JSON data
        
    Raises:
        FileNotFoundError: If file does not exist
        IOError: If file cannot be read
        json.JSONDecodeError: If file is not valid JSON
    """
    with open(file_path, "r", encoding=encoding) as f:
        return json.load(f)

def write_json_file(
    file_path: str,
    data: Dict[str, Any],
    indent: int = 2,
    sort_keys: bool = False,
    encoding: str = "utf-8"
) -> None:
    """
    Write a JSON file.
    
    Args:
        file_path: File path
        data: JSON data
        indent: Indentation level
        sort_keys: Whether to sort keys
        encoding: File encoding
        
    Raises:
        IOError: If file cannot be written
        TypeError: If data is not JSON serializable
    """
    ensure_parent_directory_exists(file_path)
    with open(file_path, "w", encoding=encoding) as f:
        json.dump(data, f, indent=indent, sort_keys=sort_keys)

def read_yaml_file(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """
    Read a YAML file.
    
    Args:
        file_path: File path
        encoding: File encoding
        
    Returns:
        YAML data
        
    Raises:
        FileNotFoundError: If file does not exist
        IOError: If file cannot be read
        yaml.YAMLError: If file is not valid YAML
    """
    with open(file_path, "r", encoding=encoding) as f:
        return yaml.safe_load(f)

def write_yaml_file(
    file_path: str,
    data: Dict[str, Any],
    default_flow_style: bool = False,
    encoding: str = "utf-8"
) -> None:
    """
    Write a YAML file.
    
    Args:
        file_path: File path
        data: YAML data
        default_flow_style: Whether to use flow style
        encoding: File encoding
        
    Raises:
        IOError: If file cannot be written
        yaml.YAMLError: If data is not YAML serializable
    """
    ensure_parent_directory_exists(file_path)
    with open(file_path, "w", encoding=encoding) as f:
        yaml.dump(data, f, default_flow_style=default_flow_style)

def file_exists(file_path: str) -> bool:
    """
    Check if a file exists.
    
    Args:
        file_path: File path
        
    Returns:
        True if file exists, False otherwise
    """
    return os.path.isfile(file_path)

def directory_exists(directory_path: str) -> bool:
    """
    Check if a directory exists.
    
    Args:
        directory_path: Directory path
        
    Returns:
        True if directory exists, False otherwise
    """
    return os.path.isdir(directory_path)

def get_file_size(file_path: str) -> int:
    """
    Get the size of a file in bytes.
    
    Args:
        file_path: File path
        
    Returns:
        File size in bytes
        
    Raises:
        FileNotFoundError: If file does not exist
        OSError: If file size cannot be determined
    """
    return os.path.getsize(file_path)

def get_file_modification_time(file_path: str) -> float:
    """
    Get the modification time of a file.
    
    Args:
        file_path: File path
        
    Returns:
        Modification time as a timestamp
        
    Raises:
        FileNotFoundError: If file does not exist
        OSError: If modification time cannot be determined
    """
    return os.path.getmtime(file_path)

def get_file_creation_time(file_path: str) -> float:
    """
    Get the creation time of a file.
    
    Args:
        file_path: File path
        
    Returns:
        Creation time as a timestamp
        
    Raises:
        FileNotFoundError: If file does not exist
        OSError: If creation time cannot be determined
    """
    return os.path.getctime(file_path)

def get_file_access_time(file_path: str) -> float:
    """
    Get the last access time of a file.
    
    Args:
        file_path: File path
        
    Returns:
        Last access time as a timestamp
        
    Raises:
        FileNotFoundError: If file does not exist
        OSError: If access time cannot be determined
    """
    return os.path.getatime(file_path)

def delete_file(file_path: str) -> None:
    """
    Delete a file.
    
    Args:
        file_path: File path
        
    Raises:
        FileNotFoundError: If file does not exist
        OSError: If file cannot be deleted
    """
    os.remove(file_path)

def delete_directory(directory_path: str, recursive: bool = False) -> None:
    """
    Delete a directory.
    
    Args:
        directory_path: Directory path
        recursive: Whether to delete recursively
        
    Raises:
        FileNotFoundError: If directory does not exist
        OSError: If directory cannot be deleted
    """
    if recursive:
        shutil.rmtree(directory_path)
    else:
        os.rmdir(directory_path)

def copy_file(source_path: str, destination_path: str) -> None:
    """
    Copy a file.
    
    Args:
        source_path: Source file path
        destination_path: Destination file path
        
    Raises:
        FileNotFoundError: If source file does not exist
        IOError: If file cannot be copied
    """
    ensure_parent_directory_exists(destination_path)
    shutil.copy2(source_path, destination_path)

def move_file(source_path: str, destination_path: str) -> None:
    """
    Move a file.
    
    Args:
        source_path: Source file path
        destination_path: Destination file path
        
    Raises:
        FileNotFoundError: If source file does not exist
        IOError: If file cannot be moved
    """
    ensure_parent_directory_exists(destination_path)
    shutil.move(source_path, destination_path)

def rename_file(file_path: str, new_name: str) -> str:
    """
    Rename a file.
    
    Args:
        file_path: File path
        new_name: New file name (not path)
        
    Returns:
        New file path
        
    Raises:
        FileNotFoundError: If file does not exist
        IOError: If file cannot be renamed
    """
    directory = os.path.dirname(file_path)
    new_path = os.path.join(directory, new_name)
    os.rename(file_path, new_path)
    return new_path

def list_files(directory_path: str, recursive: bool = False) -> List[str]:
    """
    List files in a directory.
    
    Args:
        directory_path: Directory path
        recursive: Whether to list files recursively
        
    Returns:
        List of file paths
        
    Raises:
        FileNotFoundError: If directory does not exist
        OSError: If directory cannot be read
    """
    if recursive:
        result = []
        for root, _, files in os.walk(directory_path):
            for file in files:
                result.append(os.path.join(root, file))
        return result
    else:
        return [
            os.path.join(directory_path, f)
            for f in os.listdir(directory_path)
            if os.path.isfile(os.path.join(directory_path, f))
        ]

def list_directories(directory_path: str, recursive: bool = False) -> List[str]:
    """
    List subdirectories in a directory.
    
    Args:
        directory_path: Directory path
        recursive: Whether to list directories recursively
        
    Returns:
        List of directory paths
        
    Raises:
        FileNotFoundError: If directory does not exist
        OSError: If directory cannot be read
    """
    if recursive:
        result = []
        for root, dirs, _ in os.walk(directory_path):
            for dir_name in dirs:
                result.append(os.path.join(root, dir_name))
        return result
    else:
        return [
            os.path.join(directory_path, d)
            for d in os.listdir(directory_path)
            if os.path.isdir(os.path.join(directory_path, d))
        ]

def get_file_extension(file_path: str) -> str:
    """
    Get the extension of a file.
    
    Args:
        file_path: File path
        
    Returns:
        File extension (including the dot)
    """
    return os.path.splitext(file_path)[1]

def get_file_name(file_path: str) -> str:
    """
    Get the name of a file without the directory.
    
    Args:
        file_path: File path
        
    Returns:
        File name
    """
    return os.path.basename(file_path)

def get_file_name_without_extension(file_path: str) -> str:
    """
    Get the name of a file without the directory and extension.
    
    Args:
        file_path: File path
        
    Returns:
        File name without extension
    """
    return os.path.splitext(os.path.basename(file_path))[0]

def get_directory_name(file_path: str) -> str:
    """
    Get the directory name of a file.
    
    Args:
        file_path: File path
        
    Returns:
        Directory name
    """
    return os.path.dirname(file_path)

def get_absolute_path(file_path: str) -> str:
    """
    Get the absolute path of a file.
    
    Args:
        file_path: File path
        
    Returns:
        Absolute path
    """
    return os.path.abspath(file_path)

def get_relative_path(file_path: str, start: str = None) -> str:
    """
    Get the relative path of a file.
    
    Args:
        file_path: File path
        start: Start directory
        
    Returns:
        Relative path
    """
    return os.path.relpath(file_path, start)

def join_paths(*paths: str) -> str:
    """
    Join paths.
    
    Args:
        *paths: Paths to join
        
    Returns:
        Joined path
    """
    return os.path.join(*paths)

def normalize_path(file_path: str) -> str:
    """
    Normalize a path.
    
    Args:
        file_path: File path
        
    Returns:
        Normalized path
    """
    return os.path.normpath(file_path)

def create_temp_file(suffix: str = "", prefix: str = "", dir: str = None) -> str:
    """
    Create a temporary file.
    
    Args:
        suffix: File suffix
        prefix: File prefix
        dir: Directory
        
    Returns:
        Temporary file path
        
    Raises:
        IOError: If file cannot be created
    """
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
    os.close(fd)
    return path

def create_temp_directory(suffix: str = "", prefix: str = "", dir: str = None) -> str:
    """
    Create a temporary directory.
    
    Args:
        suffix: Directory suffix
        prefix: Directory prefix
        dir: Parent directory
        
    Returns:
        Temporary directory path
        
    Raises:
        IOError: If directory cannot be created
    """
    return tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)

def with_temp_file(
    func: Callable[[str], Any],
    suffix: str = "",
    prefix: str = "",
    dir: str = None
) -> Any:
    """
    Execute a function with a temporary file.
    
    Args:
        func: Function to execute
        suffix: File suffix
        prefix: File prefix
        dir: Directory
        
    Returns:
        Function result
        
    Raises:
        IOError: If file cannot be created
    """
    path = create_temp_file(suffix=suffix, prefix=prefix, dir=dir)
    try:
        return func(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

def with_temp_directory(
    func: Callable[[str], Any],
    suffix: str = "",
    prefix: str = "",
    dir: str = None
) -> Any:
    """
    Execute a function with a temporary directory.
    
    Args:
        func: Function to execute
        suffix: Directory suffix
        prefix: Directory prefix
        dir: Parent directory
        
    Returns:
        Function result
        
    Raises:
        IOError: If directory cannot be created
    """
    path = create_temp_directory(suffix=suffix, prefix=prefix, dir=dir)
    try:
        return func(path)
    finally:
        try:
            shutil.rmtree(path)
        except OSError:
            pass

def get_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """
    Get the hash of a file.
    
    Args:
        file_path: File path
        algorithm: Hash algorithm
        
    Returns:
        File hash
        
    Raises:
        FileNotFoundError: If file does not exist
        IOError: If file cannot be read
        ValueError: If algorithm is not supported
    """
    import hashlib
    
    hash_func = getattr(hashlib, algorithm, None)
    if hash_func is None:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    h = hash_func()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    
    return h.hexdigest()

def find_files(
    directory_path: str,
    pattern: str = "*",
    recursive: bool = True
) -> List[str]:
    """
    Find files matching a pattern.
    
    Args:
        directory_path: Directory path
        pattern: Glob pattern
        recursive: Whether to search recursively
        
    Returns:
        List of matching file paths
        
    Raises:
        FileNotFoundError: If directory does not exist
    """
    import glob
    
    if recursive:
        return glob.glob(os.path.join(directory_path, "**", pattern), recursive=True)
    else:
        return glob.glob(os.path.join(directory_path, pattern), recursive=False)

def touch_file(file_path: str) -> None:
    """
    Touch a file (create if it does not exist, update modification time if it does).
    
    Args:
        file_path: File path
        
    Raises:
        IOError: If file cannot be touched
    """
    from pathlib import Path
    ensure_parent_directory_exists(file_path)
    Path(file_path).touch()

def is_file_empty(file_path: str) -> bool:
    """
    Check if a file is empty.
    
    Args:
        file_path: File path
        
    Returns:
        True if file is empty, False otherwise
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    return os.path.getsize(file_path) == 0

def get_file_mime_type(file_path: str) -> str:
    """
    Get the MIME type of a file.
    
    Args:
        file_path: File path
        
    Returns:
        MIME type
        
    Raises:
        FileNotFoundError: If file does not exist
        ImportError: If mimetypes module is not available
    """
    import mimetypes

    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"

def is_text_file(file_path: str) -> bool:
    """
    Check if a file is a text file.
    
    Args:
        file_path: File path
        
    Returns:
        True if file is a text file, False otherwise
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    mime_type = get_file_mime_type(file_path)
    return mime_type.startswith("text/") or mime_type in [
        "application/json",
        "application/xml",
        "application/javascript",
        "application/x-javascript",
        "application/yaml",
        "application/x-yaml"
    ]

def is_binary_file(file_path: str) -> bool:
    """
    Check if a file is a binary file.
    
    Args:
        file_path: File path
        
    Returns:
        True if file is a binary file, False otherwise
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    return not is_text_file(file_path)

def get_home_directory() -> str:
    """
    Get the home directory.
    
    Returns:
        Home directory path
    """
    return os.path.expanduser("~")

def get_current_directory() -> str:
    """
    Get the current working directory.
    
    Returns:
        Current working directory path
    """
    return os.getcwd()

def change_directory(directory_path: str) -> None:
    """
    Change the current working directory.
    
    Args:
        directory_path: Directory path
        
    Raises:
        FileNotFoundError: If directory does not exist
        NotADirectoryError: If path is not a directory
    """
    os.chdir(directory_path)

def get_file_permissions(file_path: str) -> int:
    """
    Get the permissions of a file.
    
    Args:
        file_path: File path
        
    Returns:
        File permissions as an integer
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    return os.stat(file_path).st_mode & 0o777

def set_file_permissions(file_path: str, permissions: int) -> None:
    """
    Set the permissions of a file.
    
    Args:
        file_path: File path
        permissions: File permissions as an integer
        
    Raises:
        FileNotFoundError: If file does not exist
        OSError: If permissions cannot be set
    """
    os.chmod(file_path, permissions)

def get_file_owner(file_path: str) -> int:
    """
    Get the owner of a file.
    
    Args:
        file_path: File path
        
    Returns:
        File owner as an integer
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    return os.stat(file_path).st_uid

def get_file_group(file_path: str) -> int:
    """
    Get the group of a file.
    
    Args:
        file_path: File path
        
    Returns:
        File group as an integer
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    return os.stat(file_path).st_gid

def set_file_owner_and_group(file_path: str, owner: int, group: int) -> None:
    """
    Set the owner and group of a file.
    
    Args:
        file_path: File path
        owner: File owner as an integer
        group: File group as an integer
        
    Raises:
        FileNotFoundError: If file does not exist
        OSError: If owner and group cannot be set
    """
    os.chown(file_path, owner, group)
