#!/bin/bash

# Get the full path of the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set environment variables
export HF_PROVIDER_NAME="awscpinst"
export HF_PROVIDER_CONFDIR="${SCRIPT_DIR}/${HF_PROVIDER_NAME}/config"
export HF_PROVIDER_LOGDIR="${SCRIPT_DIR}/${HF_PROVIDER_NAME}/logs"
export HF_PROVIDER_WORKDIR="${SCRIPT_DIR}/${HF_PROVIDER_NAME}/workdir"

echo "Environment variables set:"
echo "HF_PROVIDER_NAME=${HF_PROVIDER_NAME}"
echo "HF_PROVIDER_CONFDIR=${HF_PROVIDER_CONFDIR}"
echo "HF_PROVIDER_LOGDIR=${HF_PROVIDER_LOGDIR}"
echo "HF_PROVIDER_WORKDIR=${HF_PROVIDER_WORKDIR}"
