# SIP Phone API

A Python-based SIP server designed for Raspberry Pi that provides a clean interface to analog telephones connected through a Grandstream HT802 ATA (Analog Telephone Adapter). This service enables integration with smart home systems by providing real-time audio streaming via WebSocket and DTMF event delivery via webhooks.

## Core Features

- SIP server implementation for HT802 connection
- Real-time phone state monitoring
- DTMF webhook dispatch with retry mechanism
- Direct audio streaming via WebSocket
- Simple REST API for phone control
- Docker containerized deployment
- Comprehensive logging and diagnostics

## Overview

This API acts as a bridge between an analog telephone and your smart home system. It:
- Detects when the phone is picked up or put down
- Sends DTMF tones (button presses) via webhooks
- Streams audio to your operator server via WebSocket
- Can trigger the phone to ring
- Provides real-time state updates

## Hardware Requirements

### Required Hardware
- Raspberry Pi (3 or newer recommended)
- Grandstream HT802 ATA (Analog Telephone Adapter)
- Standard analog telephone
- Network connectivity between all components

### System Requirements
- Raspbian OS / Debian
- Python 3.9+
- Docker Engine 20.10+ (optional)
- 512MB RAM minimum
- 5GB available disk space
- Stable network connection

### Network Requirements
- Static IP for HT802
- Static IP for Raspberry Pi
- SIP port access (default: 5060)
- Webhook endpoint accessibility
- WebSocket connectivity to operator server

## Getting Started

### HT802 Setup

1. Factory reset the HT802:
   - Hold reset button for 7 seconds
   - Release when LEDs start flashing

2. Configure network settings:
   - Connect to HT802 web interface (default: 192.168.2.1)
   - Set static IP address
   - Note the IP address for API configuration

3. Configure SIP settings:
   - Disable external SIP registration
   - Set local SIP server (this API) as primary server
   - Configure authentication if needed
   - Set audio codec to G.711

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sip-phone-api.git
cd sip-phone-api
```

2. Build and start the container:
```bash
docker-compose build
docker-compose up -d
```

3. View logs:
```bash
docker-compose logs -f
```

4. Verify the installation:
```bash
curl http://localhost:8000/status  # Should return phone line status
```

## Configuration

### Environment Variables
- `SIP_SERVER_HOST`: SIP server listen address
- `SIP_SERVER_PORT`: SIP server port (default: 5060)
- `API_HOST`: REST API host address
- `API_PORT`: REST API port (default: 8000)
- `WS_PORT`: WebSocket port (default: 8001)
- `WEBHOOK_URL`: DTMF webhook endpoint
- `OPERATOR_WS_URL`: Operator WebSocket endpoint
- `LOG_LEVEL`: Logging level

### Configuration File
Location: `/etc/sip_phone/config.yml`

Example configuration:
```yaml
server:
  host: "0.0.0.0"
  rest_port: 8000
  sip_port: 5060

ht802:
  host: "192.168.1.100"  # HT802 IP address
  auth_enabled: false
  credentials:
    username: "phone1"
    password: "secret"

webhooks:
  dtmf:
    url: "https://your-operator-server/dtmf-webhook"
    timeout_ms: 1000
    retry_count: 3
    retry_delay_ms: 500
    auth_token: "secret"

operator:
  websocket_url: "wss://your-operator-server/audio"
  auth_token: "secret"

logging:
  level: "INFO"
  format: "json"
  output: "/var/log/sip_phone/api.log"
```

## API Usage

### REST Endpoints

#### Get Status
```
GET /status
```
Returns current phone status including off-hook state and connection status.

#### Ring Control
```
POST /ring
```
Triggers phone to ring with specified pattern.

For detailed architecture, design decisions, and technical specifications, please refer to the [Architecture Document](./docs/ARCHITECTURE.md).

## Development

### Debug Mode
Enable debug logging by setting:
```bash
export LOG_LEVEL=DEBUG
```

### Monitoring
- Check logs: `docker-compose logs -f`
- API status: `GET /health`
- View metrics: `GET /metrics`

## Support

For support:
- Open an issue on GitHub
- Check the documentation
- Contact the development team

## Acknowledgments

- Grandstream for HT802 specifications
- FastAPI framework developers
- Python SIP library developers