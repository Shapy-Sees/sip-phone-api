# src/Dockerfile
# Single-stage Dockerfile for SIP Phone API using Ubuntu 22.04 with PJSIP

FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    python3-dev \
    python3-lxml \
    build-essential \
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
    git \
    libsrtp2-dev \
    libsrtp2-1 \
    libv4l-dev \
    libx264-dev \
    libopus-dev \
    libvpx-dev \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    libsndfile1 \
    libasound2-dev \
    libpq-dev \
    zlib1g-dev \
    libpcre3-dev \
    libssl-dev \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    libgnutls28-dev \
    libyaml-dev \
    libsqlite3-dev \
    libspeex-dev \
    # Additional dependencies for PJSIP
    libgsm1-dev \
    libspeexdsp-dev \
    libpulse-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install wheel
RUN pip install --upgrade pip setuptools wheel

# Clone and build PJSIP from source for better control and debugging
RUN git clone https://github.com/pjsip/pjproject.git /tmp/pjproject && \
    cd /tmp/pjproject && \
    ./configure --prefix=/usr --enable-shared --disable-sound \
    --disable-video --disable-opencore-amr --disable-resample \
    --disable-g711-codec --disable-l16-codec --disable-g722-codec \
    --disable-g7221-codec --disable-gsm-codec --disable-ilbc-codec \
    --disable-ipp --disable-ssl --disable-sdl \
    --disable-ffmpeg --disable-v4l2 --disable-openh264 \
    --disable-libyuv --disable-libwebrtc --enable-extra-warnings \
    CFLAGS="-fPIC -O2 -DNDEBUG" && \
    make dep && \
    make && \
    make install && \
    ldconfig && \
    cd /tmp/pjproject/pjsip-apps/src/python && \
    python setup.py install && \
    rm -rf /tmp/pjproject

# Install requirements
COPY src/requirements.txt .
RUN pip install -r requirements.txt

# Set working directory
WORKDIR /app

# Copy application code and config
COPY sip_phone/ /app/sip_phone/
COPY config/ /app/config/

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data && \
    chmod 777 /app/logs /app/data

# Create non-root user
RUN useradd -m -u 1000 sipphone && \
    chown -R sipphone:sipphone /app

# Switch to non-root user
USER sipphone

# Expose ports (REST API and SIP)
EXPOSE 8000 5060/udp

# Set entrypoint
ENTRYPOINT ["python3", "-m"]
CMD ["sip_phone"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/status/health || exit 1

# Volumes for persistent data
VOLUME ["/app/data", "/app/logs"]
