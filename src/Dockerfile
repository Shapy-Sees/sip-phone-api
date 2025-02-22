# Use Python 3.8 slim image as base
FROM python:3.8-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies required for python-sipsimple and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    pkg-config \
    libtool \
    automake \
    gcc \
    g++ \
    make \
    # SIP dependencies
    libsrtp2-dev \
    libsrtp2-1 \
    # Audio dependencies
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    libsndfile1 \
    libasound2-dev \
    # Additional dependencies
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python-sipsimple with proper dependencies and flags
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        python3-dev \
        libssl-dev \
        libv4l-dev \
        libx264-dev \
        libopus-dev \
        libvpx-dev && \
    # Clone and build python-sipsimple from source
    git clone https://github.com/AGProjects/python-sipsimple.git /tmp/python-sipsimple && \
    cd /tmp/python-sipsimple && \
    # Set architecture-specific flags
    if [ "$(uname -m)" = "aarch64" ]; then \
        export CFLAGS="-DHAVE_OPENSSL_SSL_H=1 -I/usr/include/openssl -I/usr/include/aarch64-linux-gnu" && \
        export LDFLAGS="-L/usr/lib/aarch64-linux-gnu"; \
    else \
        export CFLAGS="-DHAVE_OPENSSL_SSL_H=1 -I/usr/include/openssl -I/usr/include/x86_64-linux-gnu" && \
        export LDFLAGS="-L/usr/lib/x86_64-linux-gnu"; \
    fi && \
    # Build and install
    python setup.py build_ext --pjsip-clean-compile && \
    python setup.py install && \
    # Cleanup
    cd / && \
    rm -rf /tmp/python-sipsimple && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy and install other requirements
COPY requirements.prod.txt .
RUN pip install --no-cache-dir -r requirements.prod.txt

# Copy source code and config
COPY sip_phone/ /app/sip_phone/
COPY config/ /app/config/

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data && \
    chmod 755 /app/logs /app/data

# Create non-root user
RUN useradd -m -u 1000 sipphone && \
    chown -R sipphone:sipphone /app

# Switch to non-root user
USER sipphone

# Expose ports (both REST API and SIP)
EXPOSE 8000 5060/udp

# Set entrypoint and default command
ENTRYPOINT ["python", "-m"]
CMD ["sip_phone"]

# Health check with proper timeout
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/status/health || exit 1

# Labels
LABEL maintainer="Your Name <your.email@example.com>" \
      version="1.0.0" \
      description="SIP Phone API service" \
      org.opencontainers.image.source="https://github.com/yourusername/sip-phone-api"

# Build arguments (can be overridden at build time)
ARG BUILD_DATE
ARG VCS_REF

# Additional labels using build arguments
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.schema-version="1.0"

# Volume for persistent data and logs
VOLUME ["/app/data", "/app/logs"]
