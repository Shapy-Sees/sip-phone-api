# SIP Phone API - Complete Architecture Design

## Overview

The SIP Phone API is a network service that provides a clean interface to analog telephones connected through a Grandstream HT802 ATA (Analog Telephone Adapter). It provides bidirectional communication, handling both incoming phone control commands and outgoing phone events through a combination of webhooks, WebSocket streaming, and REST APIs.

## System Context

### Network Components
- **SIP Server** (this API)
  - Handles SIP signaling with HT802
  - Manages phone state
  - Processes events
  - Streams audio
- **Grandstream HT802 ATA**
  - Converts analog phone signals to SIP
  - Must be on same network as API
  - Pre-configured with SIP settings
- **Analog telephone** (connected to HT802)
- **Local network connection**

### External Systems
- **Operator Server**
  - Receives phone events via webhooks
  - Controls phone via REST API
  - Handles voice-to-text processing
  - Manages business logic
  - Processes DTMF commands
  - Streams audio bidirectionally

## Core Design Decisions

### 0. Pure Network Interface
**Decision**: Implement as network service only, communicating with HT802 via SIP protocol.

**Rationale**:
- Eliminates hardware dependencies
- Simplifies deployment
- Works with any HT802-compatible phone
- Allows for future hardware flexibility



### 1. Event-Driven Architecture
**Decision**: Implement a centralized event system for all phone-related events.

**Rationale**:
- Decouples event generation from handling
- Allows multiple event handlers (webhooks, WebSocket)
- Easy to add new event types
- Consistent event processing

**Implementation**:
```
Event Sources → Event Dispatcher → Event Handlers
   (Phone)                         (Webhooks)
   (DTMF)                         (WebSocket)
   (State)                        (Logging)
```

### 2. Bidirectional Communication
**Decision**: Separate concerns between incoming control and outgoing events.

**Implementation**:
1. **Incoming Control**
   - REST API endpoints
   - Incoming webhooks
   - WebSocket commands
   
2. **Outgoing Events**
   - Event-driven webhooks
   - WebSocket state updates
   - Real-time audio streaming

### 3. Direct Audio Streaming
**Decision**: Implement direct RTP-to-WebSocket audio forwarding.

**Rationale**:
- Minimizes latency
- Reduces resource usage
- Simplifies processing
- Suitable for Raspberry Pi

## System Architecture

### 1. Core Components

#### Phone Control System
```
REST API → Phone Controller → SIP Server → HT802
   ↓              ↓             ↓
   └──────→ State Manager ←─────┘
```

#### Event System
```
Event Sources → Event Dispatcher → Event Handlers
     ↓               ↓                ↓
  (Phone)     (Validation/Routing)  Webhooks
  (DTMF)                           WebSocket
  (State)                          Logging
```

#### Audio System
```
Phone ←→ HT802 ←→ SIP Server ←→ WebSocket Manager ←→ Operator
```

### 2. Communication Protocols

#### REST API Endpoints
```
POST /api/v1/phone/ring     # Trigger ring
POST /api/v1/phone/hangup   # End call
GET  /api/v1/phone/status   # Get state
POST /api/v1/phone/audio    # Send audio
```

#### Outgoing Webhooks
1. **State Changes**
```json
{
    "type": "state_change",
    "old_state": "on_hook",
    "new_state": "off_hook",
    "timestamp": "2025-02-08T14:30:00Z",
    "call_id": "abc123"
}
```

2. **DTMF Events**
```json
{
    "type": "dtmf",
    "digit": "5",
    "timestamp": "2025-02-08T14:30:00Z",
    "call_id": "abc123",
    "sequence": 1,
    "duration_ms": 250
}
```

#### WebSocket Communication
1. **Audio Streaming**
   - Binary messages for audio data
   - G.711 codec pass-through
   - Direct RTP forwarding

2. **State Updates**
   - JSON messages for state changes
   - Call events
   - Connection status

### 3. Configuration Management

#### Environment-Based Configuration
```yaml
server:
  host: "0.0.0.0"
  rest_port: 8000
  sip_port: 5060

webhooks:
  outgoing:
    state:
      url: "https://operator/state-webhook"
      events: ["off_hook", "on_hook", "ringing"]
    dtmf:
      url: "https://operator/dtmf-webhook"
  
  retry:
    count: 3
    delay_ms: 500
    max_delay_ms: 5000

operator:
  websocket_url: "wss://operator/audio"
  auth_token: "secret"
```

### 4. Error Handling Strategy

#### Layers of Resilience
1. **Network Issues**
   - Automatic reconnection
   - Event queuing
   - Webhook retries

2. **Hardware Problems**
   - State recovery
   - Error reporting
   - Fallback modes

3. **Resource Management**
   - Memory monitoring
   - Connection limits
   - Queue management

### 5. Monitoring System

#### Health Metrics
1. **System Health**
   - Resource usage
   - Connection status
   - Event queues

2. **Call Metrics**
   - Call duration
   - Audio quality
   - DTMF reliability

3. **Integration Health**
   - Webhook success rates
   - WebSocket stability
   - Operator connection

## Implementation Guidelines

### Phase 1: Core Infrastructure
1. Event system
2. Configuration
3. Logging

### Phase 2: Communication
1. SIP server
2. WebSocket handler
3. Webhook system

### Phase 3: Integration
1. Phone controller
2. State management
3. Audio streaming

### Phase 4: Monitoring
1. Health checks
2. Metrics collection
3. Debugging tools

## Security Considerations

### Network Security
1. **Local Network**
   - HT802 isolation
   - SIP security
   - Access control

2. **External Communication**
   - TLS for webhooks
   - WebSocket security
   - API authentication

### Configuration Security
1. **Credentials**
   - Secure storage
   - Token management
   - Key rotation

## Debug Support

### Logging Levels
- ERROR: Failures, hardware issues
- WARN: Retries, anomalies
- INFO: State changes, events
- DEBUG: Detailed operations

### Monitoring Points
1. **Call Flow**
   - SIP signaling
   - Audio quality
   - DTMF detection

2. **Integration**
   - Webhook delivery
   - WebSocket status
   - Event processing

## Future Considerations

### Potential Enhancements
1. Multiple phone lines
2. Local audio recording
3. Emergency mode
4. Backup operator support

### Known Limitations
1. Single phone line initial support
2. Raspberry Pi resource constraints
3. Local network deployment
4. Basic audio capabilities