# SIP Phone API - Architecture Overview

## System Overview

The SIP Phone API provides a modern network interface to analog telephones by bridging between standard telephony protocols (SIP/RTP) and web protocols (WebSocket/HTTP). The system uses a Grandstream HT802 Analog Telephone Adapter (ATA) to convert analog phone signals to SIP, then provides additional integration capabilities through a REST API, webhooks, and WebSocket streaming.

## Key Components

### Hardware Setup
- **Analog Telephone**: Standard analog telephone
- **Grandstream HT802**: Analog Telephone Adapter that converts analog signals to SIP
- **Raspberry Pi**: Hosts the SIP Phone API service
- **Network**: Local network connecting all components

### Software Components
1. **SIP Server**
   - Handles all SIP protocol communication with HT802
   - Manages call signaling (REGISTER, INVITE, BYE)
   - Processes RTP audio streams
   - No direct configuration of HT802 needed - all communication via SIP

2. **REST API**
   - Provides control interface for phone operations
   - Exposes status and monitoring endpoints
   - Handles webhook registration

3. **WebSocket Server**
   - Streams real-time audio data
   - Provides state change notifications
   - Enables bidirectional communication

4. **Event System**
   - Processes phone events (state changes, DTMF)
   - Manages webhook delivery
   - Handles event routing

## Communication Flow

### Initial Setup
```
1. Manual HT802 Configuration (one-time setup)
   Web Browser → HT802 Web Interface (192.168.1.x)
   - Set static IP
   - Configure SIP server address
   - Set audio codec to G.711
   - No authentication required for local network

2. SIP Registration
   HT802 → SIP Server (port 5060)
   - Standard SIP REGISTER messages
   - Local network only, no external SIP traffic
```

### Normal Operation
```
1. Incoming Calls:
   Analog Phone → HT802 → SIP Server → WebSocket → Operator
                     (SIP)    (RTP)      (WS/HTTP)

2. Outgoing Control:
   Operator → REST API → SIP Server → HT802 → Analog Phone
             (HTTP)     (SIP)      (Analog)

3. Audio Streaming:
   Phone ↔ HT802 ↔ SIP Server ↔ WebSocket ↔ Operator
         (Analog) (RTP)     (Streaming)
```

## Protocol Details

### SIP Communication
- Uses standard SIP protocol (RFC 3261)
- Local network communication only
- No SIP authentication required (closed network)
- Supports basic call operations:
  - REGISTER: HT802 registration
  - INVITE: Call setup
  - BYE: Call termination
  - INFO: DTMF relay

### RTP Audio
- G.711 μ-law codec (PCMU)
- 20ms packet size
- Direct streaming to WebSocket
- No transcoding required

### WebSocket Interface
- Audio streaming
- State notifications
- Command channel
- Supports binary (audio) and text (JSON) messages

## Security Considerations

### Network Security
- SIP traffic contained to local network
- HT802 isolated from internet
- API endpoints require authentication
- WebSocket connections authenticated

### Configuration Security
- HT802 web interface password protected
- API keys for REST endpoints
- Webhook HMAC validation
- TLS for external communication

## Monitoring and Debugging

### Logging Levels
```python
DEBUG: SIP message details, audio metrics
INFO: Call events, state changes
WARNING: Retry events, audio issues
ERROR: Call failures, connection issues
```

### Health Metrics
1. SIP Connection Status
2. Audio Stream Quality
3. WebSocket Connection Health
4. Event Processing Stats

## Configuration

### HT802 Settings (Manual)
```yaml
Network:
  IP: Static (192.168.1.x)
  Subnet: 255.255.255.0
  Gateway: 192.168.1.1

SIP:
  Server: 192.168.1.y:5060
  Registration: Yes
  Codec: PCMU (G.711μ)
```

### API Settings
```yaml
server:
  host: "0.0.0.0"
  rest_port: 8000
  sip_port: 5060

audio:
  codec: "PCMU"
  ptime: 20
  buffer_size: 320

security:
  api_tokens: ["token1", "token2"]
  allowed_origins: ["https://operator.example.com"]
```

## Limitations

1. Single Phone Line
   - One analog phone per HT802 port
   - Multiple HT802s possible but not implemented

2. Audio Capabilities
   - G.711 only
   - No transcoding
   - Basic DTMF detection

3. Network Requirements
   - Local network deployment
   - Static IP for HT802
   - No NAT traversal

4. Hardware Dependencies
   - Specific to HT802 model
   - Raspberry Pi resource constraints

## Future Enhancements

1. Multiple Phone Lines
   - Support for both HT802 ports
   - Multiple device support

2. Advanced Audio
   - Additional codecs
   - Audio recording
   - Quality metrics

3. Network Features
   - NAT traversal
   - SIP authentication
   - External SIP trunking

4. Redundancy
   - Backup operator support
   - Failover modes
   - State persistence