# SIP Phone API

A Python-based SIP server and API that provides a clean interface to analog telephones connected through a Grandstream HT802 ATA (Analog Telephone Adapter). This service enables high-level control and monitoring of analog phone lines for smart home integration, including real-time audio streaming.

## Core Features

- Simple SIP server implementation for HT802 connection
- Real-time phone state monitoring
- Bidirectional audio streaming
- Audio format conversion and processing
- DTMF tone detection
- Ring control
- WebSocket-based event system
- Comprehensive error handling and diagnostics
- Docker containerized deployment

## Overview

This API acts as a bridge between an analog telephone (connected via Grandstream HT802) and a smart home system. It:
- Detects when the phone is picked up or put down
- Captures DTMF tones (button presses)
- Streams audio from the phone to clients
- Streams audio from clients to the phone
- Can trigger the phone to ring
- Streams all events to connected clients via WebSocket

The API is designed to be a component in a larger smart home system where other services can:
- Monitor phone state
- React to button presses
- Process voice commands in real-time
- Provide audio responses to the phone
- Trigger rings for notifications

## Hardware Requirements

### Required Hardware
- Grandstream HT802 ATA (Analog Telephone Adapter)
- Standard analog telephone
- Network connectivity between server and HT802
- Audio processing capabilities on server

### System Requirements
- Linux/Windows/MacOS
- Python 3.9+
- Docker Engine 20.10+ (optional)
- 2GB RAM minimum (for audio processing)
- 10GB available disk space
- Low-latency network connection

### Network Requirements
- Static IP for HT802
- SIP port access (default: 5060)
- RTP ports for audio streaming (default: 10000-20000)
- WebSocket port access (default: 8001)
- REST API port access (default: 8000)

## Audio Specifications

### Input Audio
- Sample Rate: 8kHz (standard telephony)
- Bit Depth: 16-bit
- Channels: Mono
- Codec: G.711 (μ-law or A-law)

### Output Audio
- Sample Rate: 8kHz
- Bit Depth: 16-bit
- Channels: Mono
- Codec: G.711 (μ-law or A-law)

### Audio Streaming
- Protocol: RTP over UDP
- Buffer Size: 20ms frames
- Latency Target: <100ms
- Format: Raw PCM or encoded G.711

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
   - Set audio codec preferences to G.711

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

## API Usage

### REST Endpoints

#### Get Status
```
GET /status
```
Returns current phone status including off-hook state, last DTMF digit, and audio streaming status.

#### Ring Control
```
POST /ring
```
Triggers phone to ring with specified pattern.

#### Audio Stream Control
```
POST /audio/start
```
Start audio streaming session.

```
POST /audio/stop
```
Stop audio streaming session.

### WebSocket Events

Connect to `ws://server:8001/ws` to receive real-time events:

```javascript
{
  "type": "off_hook",
  "timestamp": "2025-01-29T12:00:00Z"
}
```

```javascript
{
  "type": "dtmf",
  "digit": "3",
  "timestamp": "2025-01-29T12:00:00Z"
}
```

```javascript
{
  "type": "on_hook",
  "timestamp": "2025-01-29T12:00:00Z"
}
```

```javascript
{
  "type": "audio_start",
  "stream_id": "abc123",
  "timestamp": "2025-01-29T12:00:00Z"
}
```

### Audio Streaming

Audio streaming is handled through RTP:
- Input stream: Phone audio is streamed to connected clients
- Output stream: Client audio is streamed to phone
- Each stream has unique identifiers
- Clients can subscribe to streams via WebSocket
- Audio data is streamed in configurable chunks
- Support for both raw PCM and G.711 encoded audio

## Configuration

### Environment Variables
- `SIP_SERVER_HOST`: SIP server listen address
- `SIP_SERVER_PORT`: SIP server port (default: 5060)
- `API_HOST`: REST API host address
- `API_PORT`: REST API port (default: 8000)
- `WS_PORT`: WebSocket port (default: 8001)
- `RTP_PORT_MIN`: Minimum RTP port (default: 10000)
- `RTP_PORT_MAX`: Maximum RTP port (default: 20000)
- `LOG_LEVEL`: Logging level

### Configuration File
Location: `/etc/sip_phone/config.yml`

Example configuration:
```yaml
server:
  host: "0.0.0.0"
  rest_port: 8000
  websocket_port: 8001
  sip_port: 5060

ht802:
  host: "192.168.1.100"  # HT802 IP address
  auth_enabled: false
  credentials:
    username: "phone1"
    password: "secret"

audio:
  sample_rate: 8000
  bit_depth: 16
  channels: 1
  codec: "PCMU"  # or "PCMA"
  buffer_size: 320  # 20ms @ 8kHz/16-bit
  rtp_ports:
    min: 10000
    max: 20000

logging:
  level: "INFO"
  format: "json"
  output: "/var/log/sip_phone/api.log"
  rotation: "1 day"
  retention: "30 days"
```

## Development Notes

### Debugging

#### Logging System
- Comprehensive logging throughout all components
- Configurable log levels via config.yml
- Structured logging with JSON format support
- Rotated log files with retention policies

#### Diagnostics
- SIP message logging
- Audio stream monitoring
- Real-time state monitoring
- DTMF detection verification
- RTP statistics
- WebSocket connection status

#### Audio Testing Tools
- Audio loopback testing
- Stream latency measurement
- Codec verification
- Audio level monitoring

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add or update tests
5. Submit a pull request


## Support

For support:
- Open an issue on GitHub
- Check the documentation
- Contact the development team

## Acknowledgments

- Grandstream for HT802 specifications
- FastAPI framework developers
- Python SIP library developers
- WebSocket protocol developers
- RTP protocol developers