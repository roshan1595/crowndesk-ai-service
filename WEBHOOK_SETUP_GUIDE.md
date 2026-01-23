# CrownDesk AI Service - Webhook Configuration Guide

This document explains all webhooks needed for the CrownDesk AI receptionist system.

## Overview

The CrownDesk AI system uses multiple service integrations that communicate via webhooks:
- **Retell AI**: Voice call handling and phone number management
- **ElevenLabs**: Text-to-Speech (TTS) for natural voice generation
- **Twilio**: Alternative voice infrastructure (optional)
- **CrownDesk Backend**: Business logic and database operations

---

## 1. Retell AI Webhooks

### A. Custom LLM WebSocket (Primary Integration)

**WebSocket URL**: `wss://ai-service-sparkling-brook-7912.fly.dev/retell-llm`

**Purpose**: Real-time bidirectional communication between Retell AI and your AI service for handling phone conversations.

**Setup in Retell Dashboard**:
1. Go to https://dashboard.retell.ai
2. Navigate to **Agents** → **Create New Agent**
3. Select **Custom LLM** as the language model
4. Enter WebSocket URL: `wss://ai-service-sparkling-brook-7912.fly.dev/retell-llm`
5. Configure voice settings (see ElevenLabs section below)

**Protocol**: WebSocket with JSON messages
- **Inbound events**: `response_required`, `update_only`, `reminder_required`, `ping_pong`, `call_details`
- **Outbound events**: `response`, `config`, `tool_call_invocation`, `tool_call_result`

**Authentication**: None required (WebSocket connection authenticated by Retell)

---

### B. Post-Call Webhook (Optional)

**Webhook URL**: `https://ai-service-sparkling-brook-7912.fly.dev/api/retell/webhook`

**Purpose**: Receive call completion notifications, transcripts, and analytics after each call ends.

**Method**: `POST`

**Payload Example**:
```json
{
  "event_type": "call_ended",
  "call_id": "abc123",
  "agent_id": "agent_xyz",
  "call_status": "completed",
  "call_duration": 120,
  "transcript": [
    {"role": "agent", "content": "Hello! How can I help you?"},
    {"role": "user", "content": "I need to book an appointment"}
  ],
  "recording_url": "https://...",
  "ended_at": "2026-01-22T10:30:00Z"
}
```

**Setup in Retell Dashboard**:
1. Go to **Settings** → **Webhooks**
2. Add webhook URL
3. Select events: `call_started`, `call_ended`, `call_analyzed`
4. Save configuration

---

## 2. ElevenLabs Webhooks

### A. Voice Selection in Retell

**Purpose**: Use ElevenLabs voices for natural-sounding speech in phone conversations.

**Setup in Retell Dashboard**:
1. In your agent configuration, go to **Voice Settings**
2. Select **ElevenLabs** as the TTS provider
3. Enter your **ElevenLabs API Key** (from https://elevenlabs.io/app/settings)
4. Choose a voice:
   - **Rachel**: Professional female (recommended for dental receptionist)
   - **Adam**: Professional male
   - **Bella**: Warm and friendly female
   - **Antoni**: Calm and reassuring male
5. Adjust voice stability and similarity boost settings

**No webhook needed** - Retell calls ElevenLabs API directly for TTS

---

### B. ElevenLabs Webhook (Optional - for advanced features)

**Webhook Format** (as provided by user):
```json
{
  "type": "webhook",
  "name": "",
  "description": "",
  "api_schema": {
    "url": "",
    "method": "GET",
    "path_params_schema": [],
    "query_params_schema": [],
    "request_body_schema": null,
    "request_headers": [],
    "auth_connection": null
  },
  "response_timeout_secs": 20,
  "dynamic_variables": {
    "dynamic_variable_placeholders": {}
  },
  "assignments": [],
  "disable_interruptions": false,
  "force_pre_tool_speech": "auto",
  "tool_call_sound": null,
  "tool_call_sound_behavior": "auto",
  "execution_mode": "immediate"
}
```

**When to use**: 
- Custom voice generation callbacks
- Speech analytics events
- Voice cloning completion notifications

**Typical Setup**:
```json
{
  "type": "webhook",
  "name": "voice_generation_complete",
  "description": "Notify when voice synthesis completes",
  "api_schema": {
    "url": "https://ai-service-sparkling-brook-7912.fly.dev/api/elevenlabs/callback",
    "method": "POST",
    "request_headers": [
      {
        "name": "X-API-Key",
        "value": "${ELEVENLABS_API_KEY}"
      }
    ]
  },
  "response_timeout_secs": 20
}
```

---

## 3. Twilio Webhooks (Alternative Voice Integration)

### A. Voice Call Webhook

**Webhook URL**: `https://ai-service-sparkling-brook-7912.fly.dev/api/voice-agent/incoming`

**Purpose**: Handle incoming voice calls via Twilio instead of Retell AI.

**Method**: `POST`

**Setup in Twilio Console**:
1. Go to https://console.twilio.com
2. Navigate to **Phone Numbers** → Select your number
3. Under **Voice & Fax**, configure:
   - **A Call Comes In**: Webhook
   - URL: `https://ai-service-sparkling-brook-7912.fly.dev/api/voice-agent/incoming`
   - Method: `POST`
4. Save configuration

**TwiML Response**: Returns XML instructions for call handling

---

### B. Media Stream Webhook

**WebSocket URL**: `wss://ai-service-sparkling-brook-7912.fly.dev/voice-agent/media-stream`

**Purpose**: Real-time audio streaming for speech recognition and synthesis.

**Setup**: Configured in TwiML response from incoming call webhook:
```xml
<Response>
  <Connect>
    <Stream url="wss://ai-service-sparkling-brook-7912.fly.dev/voice-agent/media-stream" />
  </Connect>
</Response>
```

---

## 4. CrownDesk Backend Webhooks

### A. Appointment Confirmation

**Webhook URL**: `https://cdapi.xaltrax.com/api/appointments/confirm`

**Purpose**: Called by AI service after booking an appointment to update status.

**Method**: `POST`

**Headers**:
```
Authorization: Bearer ${BACKEND_API_KEY}
Content-Type: application/json
```

**Payload**:
```json
{
  "appointment_id": "123",
  "tenant_id": "tenant_abc",
  "patient_id": "patient_xyz",
  "confirmed": true,
  "confirmed_at": "2026-01-22T10:30:00Z"
}
```

---

### B. Call Record Webhook

**Webhook URL**: `https://cdapi.xaltrax.com/api/calls/record`

**Purpose**: Log all AI receptionist calls to the backend database.

**Method**: `POST`

**Payload**:
```json
{
  "call_id": "call_123",
  "tenant_id": "tenant_abc",
  "phone_number": "+1234567890",
  "duration": 120,
  "call_type": "appointment_booking",
  "transcript": "...",
  "outcome": "appointment_booked",
  "created_at": "2026-01-22T10:30:00Z"
}
```

---

## 5. Complete Setup Checklist

### Step 1: Retell AI Configuration
- [ ] Sign up at https://dashboard.retell.ai
- [ ] Create a new agent
- [ ] Set Custom LLM WebSocket URL: `wss://ai-service-sparkling-brook-7912.fly.dev/retell-llm`
- [ ] Configure post-call webhook (optional): `https://ai-service-sparkling-brook-7912.fly.dev/api/retell/webhook`
- [ ] Get a phone number from Retell
- [ ] Test by calling the number

### Step 2: ElevenLabs Voice Configuration
- [ ] Sign up at https://elevenlabs.io
- [ ] Get API key from settings
- [ ] In Retell dashboard, add ElevenLabs API key
- [ ] Select voice (recommended: Rachel)
- [ ] Adjust voice settings (stability: 0.5, similarity: 0.75)

### Step 3: Environment Variables
Add to `.env` or Fly.io secrets:
```bash
# Retell AI
RETELL_API_KEY=your_retell_api_key_here
RETELL_LLM_WEBSOCKET_URL=wss://ai-service-sparkling-brook-7912.fly.dev/retell-llm

# ElevenLabs
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel voice

# Backend
BACKEND_URL=https://cdapi.xaltrax.com
BACKEND_API_KEY=your_backend_api_key_here
```

### Step 4: Deploy Secrets to Fly.io
```powershell
fly secrets set RETELL_API_KEY="your_retell_api_key_here" -a crowndesk-ai-service
fly secrets set ELEVENLABS_API_KEY="your_elevenlabs_api_key_here" -a crowndesk-ai-service
fly secrets set BACKEND_API_KEY="your_backend_api_key_here" -a crowndesk-ai-service
```

### Step 5: Test the Integration
1. Call the Retell phone number
2. Test appointment booking flow
3. Check backend database for created appointments
4. Review call transcript in Retell dashboard

---

## 6. Webhook Security Best Practices

### Verify Webhook Signatures
```python
import hmac
import hashlib

def verify_retell_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### Rate Limiting
Configure in `fly.toml`:
```toml
[[http_service]]
  rate_limit = { requests = 1000, per = "1m" }
```

### IP Whitelisting
For production, whitelist Retell AI IPs:
- Retell AI IP ranges: (check Retell docs)
- ElevenLabs IP ranges: (check ElevenLabs docs)

---

## 7. Monitoring & Debugging

### View Real-Time Logs
```powershell
fly logs -a crowndesk-ai-service
```

### Test WebSocket Connection
```powershell
# Install wscat: npm install -g wscat
wscat -c "wss://ai-service-sparkling-brook-7912.fly.dev/retell-llm"
```

### Check Webhook Delivery
- Retell Dashboard → **Webhooks** → View delivery logs
- ElevenLabs Dashboard → **Webhooks** → Check event history

---

## 8. Troubleshooting

### Issue: WebSocket connection fails
**Solution**: Check health endpoint first:
```powershell
Invoke-RestMethod -Uri "https://ai-service-sparkling-brook-7912.fly.dev/health"
```

### Issue: Voice quality is poor
**Solution**: Adjust ElevenLabs settings in Retell dashboard:
- Increase voice stability (0.5 → 0.7)
- Use premium voices
- Check network latency

### Issue: Appointments not saving
**Solution**: Check backend API key and endpoint:
```powershell
$headers = @{"Authorization" = "Bearer $BACKEND_API_KEY"}
Invoke-RestMethod -Uri "https://cdapi.xaltrax.com/api/health" -Headers $headers
```

---

## Need Help?

- Retell AI: https://docs.retellai.com
- ElevenLabs: https://docs.elevenlabs.io
- Twilio: https://www.twilio.com/docs
- CrownDesk Support: support@crowndesk.app
