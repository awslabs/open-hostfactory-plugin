#!/bin/bash
set -e

VERSION=$1
PYTHON_VERSIONS=$2
DEFAULT_PYTHON=$3
CONTAINER_REGISTRY=$4
CONTAINER_IMAGE=$5

if [ $# -ne 5 ]; then
    echo "Usage: $0 <version> <python_versions> <default_python> <container_registry> <container_image>"
    echo "Example: $0 0.1.0 '3.9 3.10 3.11 3.12 3.13' 3.13 ghcr.io/awslabs open-hostfactory-plugin"
    exit 1
fi

echo "Building container images for all Python versions..."
echo "Package: $CONTAINER_IMAGE"
echo "Registry: $CONTAINER_REGISTRY"
echo "Version: $VERSION"
echo "Python versions: $PYTHON_VERSIONS"
echo "Default Python: $DEFAULT_PYTHON"

for py_ver in $PYTHON_VERSIONS; do
    echo "Building for Python $py_ver..."
    docker build \
        --build-arg PYTHON_VERSION=$py_ver \
        --build-arg APP_VERSION=$VERSION \
        -t $CONTAINER_IMAGE:$VERSION-python$py_ver \
        -t $CONTAINER_REGISTRY/$CONTAINER_IMAGE:$VERSION-python$py_ver \
        .
done

# Tag the default Python version as latest
echo "Tagging default Python $DEFAULT_PYTHON as latest..."
docker tag $CONTAINER_IMAGE:$VERSION-python$DEFAULT_PYTHON $CONTAINER_IMAGE:$VERSION
docker tag $CONTAINER_REGISTRY/$CONTAINER_IMAGE:$VERSION-python$DEFAULT_PYTHON $CONTAINER_REGISTRY/$CONTAINER_IMAGE:$VERSION

echo "Container build completed successfully"
echo "Images created:"
for py_ver in $PYTHON_VERSIONS; do
    echo "  - $CONTAINER_REGISTRY/$CONTAINER_IMAGE:$VERSION-python$py_ver"
done
echo "  - $CONTAINER_REGISTRY/$CONTAINER_IMAGE:$VERSION (default: Python $DEFAULT_PYTHON)"
