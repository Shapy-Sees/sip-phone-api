# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    libsndfile1 \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy configuration files
COPY config/default.yml /app/config/default.yml
COPY config/config.yml /app/config/config.yml

# Copy source code
COPY sip_phone /app/sip_phone

# Create necessary directories
RUN mkdir -p /app/logs /app/data

# Create non-root user
RUN useradd -m -u 1000 sipphone && \
    chown -R sipphone:sipphone /app

# Switch to non-root user
USER sipphone

# Expose ports
EXPOSE 8000

# Set entrypoint and default command
ENTRYPOINT ["python", "-m"]
CMD ["sip_phone"]

# Health check
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

# Volume for persistent data
VOLUME ["/app/data", "/app/logs"]
