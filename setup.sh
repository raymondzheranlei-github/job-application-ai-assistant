#!/bin/bash
# Setup script to install Python dependencies

set -e

if [ -f requirement.txt ]; then
    pip install -r requirement.txt
else
    echo "requirement.txt not found" >&2
    exit 1
fi
