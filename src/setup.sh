#!/bin/bash
# File: src/setup.sh
# This script sets up the required directories and permissions for the SIP Phone API

# Create required directories if they don't exist
mkdir -p logs data config

# Set proper permissions
chmod 755 logs data config

# Create default config if it doesn't exist
if [ ! -f config/config.yml ]; then
    if [ -f config/config.yml.example ]; then
        cp config/config.yml.example config/config.yml
        echo "Created config.yml from example"
    else
        echo "Warning: config.yml.example not found"
    fi
fi

echo "Setup complete. Directories created and permissions set."
