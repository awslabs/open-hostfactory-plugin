"""Package metadata and naming constants."""

import os
from pathlib import Path


def _get_repo_name():
    """Get repository name from git remote or directory name."""
    try:
        import subprocess

        result = subprocess.run(
            ["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True
        )
        # Extract repo name from URL
        url = result.stdout.strip()
        if url.endswith(".git"):
            url = url[:-4]

        # Handle SSH URLs (git@github.com:org/repo)
        if url.startswith("git@"):
            return url.split("/")[-1]
        # Handle HTTPS URLs (https://github.com/org/repo)
        else:
            return url.split("/")[-1]
    except (subprocess.CalledProcessError, OSError, AttributeError):
        # Fallback to directory name
        return Path.cwd().name


def _get_repo_org():
    """Get repository organization from git remote."""
    try:
        import subprocess

        result = subprocess.run(
            ["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True
        )
        url = result.stdout.strip()

        # Handle SSH URLs (git@github.com:org/repo)
        if url.startswith("git@github.com:"):
            # Remove git@github.com: prefix and .git suffix
            path = url.replace("git@github.com:", "")
            if path.endswith(".git"):
                path = path[:-4]
            return path.split("/")[0]
        # Handle HTTPS URLs (https://github.com/org/repo)
        elif "github.com" in url:
            if url.endswith(".git"):
                url = url[:-4]
            parts = url.split("/")
            return parts[-2]  # Organization name
    except (subprocess.CalledProcessError, OSError, AttributeError, IndexError):
        pass
    return "awslabs"  # Default fallback


# Package metadata
PACKAGE_NAME = _get_repo_name()
PACKAGE_NAME_PYTHON = PACKAGE_NAME.replace("-", "_")
PACKAGE_NAME_SHORT = "ohfp"  # CLI command name

# Repository metadata
REPO_ORG = _get_repo_org()
REPO_NAME = PACKAGE_NAME
REPO_URL = f"https://github.com/{REPO_ORG}/{REPO_NAME}"
REPO_ISSUES_URL = f"{REPO_URL}/issues"
DOCS_URL = f"https://{REPO_ORG}.github.io/{REPO_NAME}"

# Container registry
CONTAINER_REGISTRY = f"ghcr.io/{REPO_ORG}"
CONTAINER_IMAGE = PACKAGE_NAME
