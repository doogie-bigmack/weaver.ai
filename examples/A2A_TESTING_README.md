# A2A (Agent-to-Agent) Testing Guide

This guide shows how to test A2A communication between Weaver AI agents over the internet.

## What Was Built

We've implemented a complete A2A bridge that allows your Redis-based agents to communicate with external agents over HTTP:

### Components:
1. **A2A Client** (`weaver_ai/a2a_client.py`) - Send signed A2A messages to remote agents
2. **A2A Router** (`weaver_ai/a2a_router.py`) - Bridge HTTP A2A messages to Redis events
3. **Gateway Endpoints** (`weaver_ai/gateway.py`) - `/a2a/message` and `/a2a/card` endpoints
4. **Test Agent** (`examples/a2a_translator_agent.py`) - Simple translator for testing
5. **Test Client** (`examples/a2a_test_client.py`) - Send test A2A requests

## Quick Start (Local Testing)

### Step 1: Generate Keys (Optional for local testing)

```bash
python scripts/generate_a2a_keys.py
```

This creates:
- `keys/instance_a_private.pem` (keep secret!)
- `keys/instance_a_public.pem` (share with others)
- `keys/instance_b_private.pem`
- `keys/instance_b_public.pem`

### Step 2: Start Redis

```bash
# Terminal 1: Redis server
redis-server --port 6379
```

### Step 3: Start Translator Agent

```bash
# Terminal 2: Translator agent
python examples/a2a_translator_agent.py --port 8001

# Output:
# ============================================================
# Translator Agent (A2A Test)
# ============================================================
# Redis URL: redis://localhost:6379
# Port: 8001
# Capabilities: translation:en-es, translation
# ============================================================
#
# ✓ Translator agent is running!
```

### Step 4: Start Gateway (with A2A endpoint)

```bash
# Terminal 3: Gateway
uvicorn weaver_ai.gateway:app --port 8001 --reload

# Gateway exposes:
# - POST /a2a/message (receive A2A messages)
# - GET /a2a/card (publish capabilities)
```

### Step 5: Test A2A Communication

```bash
# Terminal 4: Test client
python examples/a2a_test_client.py --endpoint http://localhost:8001

# Output:
# ============================================================
# A2A Translation Test
# ============================================================
# Endpoint: http://localhost:8001
# Sender ID: test-client
# ============================================================
#
# Test 1: Simple translation
# ------------------------------------------------------------
# ✓ Success! (took 245ms)
#   Original: Hello, world!
#   Translated: [ES] Hello, world!
```

## Testing Over the Internet (ngrok)

### Step 1: Install ngrok

```bash
brew install ngrok
# or download from https://ngrok.com/download
```

### Step 2: Start Agent and Gateway

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Translator Agent
python examples/a2a_translator_agent.py --port 8001

# Terminal 3: Gateway
uvicorn weaver_ai.gateway:app --port 8001
```

### Step 3: Expose with ngrok

```bash
# Terminal 4: ngrok tunnel
ngrok http 8001

# Output:
# Forwarding https://abc123.ngrok.io -> http://localhost:8001
```

### Step 4: Test from another machine

```bash
# From any machine with internet access:
python examples/a2a_test_client.py --endpoint https://abc123.ngrok.io

# This sends A2A message over the internet!
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│               Your Weaver AI Instance                    │
│                                                          │
│  [External Agent]                                        │
│         │                                                │
│         │ HTTP POST /a2a/message                        │
│         ↓                                                │
│  ┌────────────────────────────────────────────┐        │
│  │  Gateway (gateway.py)                      │        │
│  │  - Verify signature                        │        │
│  │  - Check timestamp                         │        │
│  └────────────┬───────────────────────────────┘        │
│               │                                          │
│               ↓                                          │
│  ┌────────────────────────────────────────────┐        │
│  │  A2A Router (a2a_router.py)                │        │
│  │  - Convert A2A → Redis Event               │        │
│  │  - Publish to Redis                        │        │
│  │  - Wait for result                         │        │
│  │  - Convert result → A2A response           │        │
│  └────────────┬───────────────────────────────┘        │
│               │                                          │
│               ↓                                          │
│  ┌────────────────────────────────────────────┐        │
│  │  Redis Event Mesh                          │        │
│  │  Channel: tasks:translation                │        │
│  └────────────┬───────────────────────────────┘        │
│               │                                          │
│               ↓                                          │
│  ┌────────────────────────────────────────────┐        │
│  │  Translator Agent (BaseAgent)              │        │
│  │  - Subscribes to Redis                     │        │
│  │  - Processes translation                   │        │
│  │  - Publishes result                        │        │
│  └────────────────────────────────────────────┘        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Testing Checklist

- [ ] Redis is running
- [ ] Translator agent is running and subscribed
- [ ] Gateway is running with `/a2a/message` endpoint
- [ ] Can send A2A message locally (localhost)
- [ ] Can expose with ngrok
- [ ] Can send A2A message over internet
- [ ] Signature verification works
- [ ] Timestamp validation works
- [ ] Results are returned correctly

## Troubleshooting

### "Connection refused" error
- Make sure Redis is running: `redis-cli ping` should return "PONG"
- Check that agent and gateway are on the same Redis instance

### "No agent subscribed to capability"
- Verify translator agent is running: look for "Translator agent is running!"
- Check Redis channels: `redis-cli PUBSUB CHANNELS tasks:*`

### "Invalid signature" error
- Make sure you're using the correct public keys
- Check that keys are in PEM format
- Verify keys were generated correctly

### Timeout errors
- Increase budget time_ms in test client
- Check that agent is processing events
- Look for errors in agent output

## Next Steps

1. **Add More Agents**: Create additional agents with different capabilities
2. **Real LLM Integration**: Replace mock translation with actual LLM calls
3. **Production Keys**: Generate and use real RSA keys (not test keys)
4. **Cloud Deployment**: Deploy to Railway, Fly.io, or AWS
5. **External Integration**: Connect to other A2A-compliant agents

## Files Created

```
scripts/
  └── generate_a2a_keys.py          # Generate RSA key pairs

weaver_ai/
  ├── a2a_client.py                 # Client for sending A2A messages
  ├── a2a_router.py                 # Bridge HTTP → Redis
  └── gateway.py                    # Added /a2a/message, /a2a/card endpoints

examples/
  ├── a2a_translator_agent.py       # Test translator agent
  ├── a2a_test_client.py            # Test client script
  └── A2A_TESTING_README.md         # This file
```

## Security Notes

⚠️ **Important**: The test scripts use default keys for simplicity. For production:

1. **Generate real keys**: `python scripts/generate_a2a_keys.py`
2. **Keep private keys secret**: Never commit to git
3. **Use environment variables**: Store keys in env vars, not code
4. **Verify all signatures**: Always verify incoming message signatures
5. **Use HTTPS**: ngrok provides HTTPS, but for production use proper SSL

## Example A2A Message

```json
{
  "request_id": "abc123",
  "sender_id": "test-client",
  "receiver_id": "translator-agent",
  "created_at": "2025-01-15T10:30:00Z",
  "nonce": "unique-nonce-12345",
  "capabilities": [
    {
      "name": "translation:en-es",
      "version": "1.0.0",
      "scopes": ["execute"]
    }
  ],
  "budget": {
    "tokens": 1000,
    "time_ms": 5000,
    "tool_calls": 1
  },
  "payload": {
    "text": "Hello, world!"
  },
  "signature": "<signed-jwt-token>"
}
```

## Success Criteria

✅ You know it's working when:

1. Test client shows "✓ Success!"
2. Translator agent prints "Translation complete"
3. Response contains translated text
4. Works over ngrok (internet)
5. No signature errors
6. No timeout errors

Happy testing! 🎉
