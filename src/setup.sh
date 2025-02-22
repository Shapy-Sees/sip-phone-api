#!/bin/bash
# File: src/setup.sh
# This script sets up the required environment for the SIP Phone API

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    log_error "Please do not run as root"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if (( $(echo "$PYTHON_VERSION < 3.9" | bc -l) )); then
    log_error "Python 3.9 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

# Install system dependencies if not in Docker
if [ ! -f /.dockerenv ]; then
    log_info "Installing system dependencies..."
    
    # Check package manager
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y \
            build-essential \
            python3-dev \
            libssl-dev \
            libxml2-dev \
            libxslt1-dev \
            libffi-dev \
            libsrtp2-dev \
            libportaudio2 \
            portaudio19-dev \
            libsndfile1 \
            libasound2-dev \
            libgnutls28-dev \
            libyaml-dev \
            python3-lxml \
            libpcre3-dev \
            libopenblas-dev \
            liblapack-dev \
            libatlas-base-dev
    else
        log_warn "Unsupported package manager. Please install dependencies manually."
        log_warn "See requirements.prod.txt for the list of required system packages."
    fi
fi

# Create and activate virtual environment
log_info "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# Upgrade pip and install dependencies
log_info "Installing Python dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.prod.txt

# Create required directories
log_info "Creating required directories..."
mkdir -p logs data config
chmod 755 logs data config

# Set up configuration
log_info "Setting up configuration..."

# Handle config.yml
if [ ! -f config/config.yml ]; then
    if [ -f config/config.yml.example ]; then
        cp config/config.yml.example config/config.yml
        log_info "Created config.yml from example"
    else
        log_warn "config.yml.example not found"
    fi
fi

# Handle .env file
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        log_info "Created .env from example"
    else
        log_warn ".env.example not found"
    fi
fi

# Verify installation
log_info "Verifying installation..."

# Check if key Python packages are installed
python3 -c "import fastapi" || { log_error "FastAPI not installed correctly"; exit 1; }
python3 -c "import sipsimple" || { log_warn "python-sipsimple not installed - you may need to install it manually"; }
python3 -c "import numpy" || { log_error "NumPy not installed correctly"; exit 1; }
python3 -c "import scipy" || { log_error "SciPy not installed correctly"; exit 1; }

# Print success message
log_info "Setup completed successfully!"
log_info "Next steps:"
echo "1. Edit config/config.yml with your settings"
echo "2. Edit .env with your environment variables"
echo "3. Run 'python -m sip_phone' to start the service"

# Cleanup
deactivate
