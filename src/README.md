# SIP Phone API

A Python-based SIP server designed for Raspberry Pi that provides a clean interface to analog telephones connected through a Grandstream HT802 ATA (Analog Telephone Adapter). This service enables integration with smart home systems by providing real-time audio streaming via WebSocket and DTMF event delivery via webhooks.

## Core Features

- SIP server implementation for HT802 connection using PJSIP/PJSUA2
- Real-time phone state monitoring
- DTMF webhook dispatch with retry mechanism
- Direct audio streaming via WebSocket
- Simple REST API for phone control
- Docker containerized deployment
- Comprehensive logging and diagnostics

## Project Structure

The project has been consolidated to use only the PJSIP implementation, which offers better compatibility, reliability, and maintenance compared to the original SIPSimple implementation.

### Key Components

- **SIP Server**: Core implementation using PJSIP/PJSUA2 for SIP signaling and audio handling
- **API Server**: FastAPI-based REST API for phone control and status
- **WebSocket Manager**: Handles real-time audio streaming and state updates
- **Event System**: Centralized event dispatching for phone events
- **Webhook System**: Delivers DTMF and state events to external systems

## Getting Started

### Prerequisites

- Raspberry Pi (3 or newer recommended)
- Grandstream HT802 ATA (Analog Telephone Adapter)
- Standard analog telephone
- Docker and Docker Compose

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sip-phone-api.git
cd sip-phone-api
```

2. Configure the environment:
```bash
cp src/.env.example src/.env
cp src/config/config.yml.example src/config/config.yml
```

3. Edit the configuration files to match your environment:
```bash
nano src/.env
nano src/config/config.yml
```

4. Build and start the container:
```bash
cd src
docker-compose build
docker-compose up -d
```

5. View logs:
```bash
docker-compose logs -f
```

## Configuration

### Environment Variables
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `PJSIP_LOG_LEVEL`: PJSIP logging level (0-6, where 6 is most verbose)

### Configuration File
Location: `src/config/config.yml`

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

## Development

### Debug Mode
Enable debug logging by setting:
```bash
export LOG_LEVEL=DEBUG
export PJSIP_LOG_LEVEL=5
```

### Monitoring
- Check logs: `docker-compose logs -f`
- API status: `GET /health`
- View metrics: `GET /metrics`

## License

This project is licensed under the MIT License - see the LICENSE file for details.
