# CrownDesk AI Service - Quick Start: Setting Up Webhooks

This guide gets you from zero to a working AI receptionist in **15 minutes**.

---

## What You Need

1. **Retell AI Account** (for phone calls) - https://dashboard.retell.ai
2. **ElevenLabs Account** (for voice) - https://elevenlabs.io
3. **Your AI Service URL**: `https://ai-service-sparkling-brook-7912.fly.dev`

---

## Step 1: Set Up Retell AI (5 minutes)

### 1.1 Create Account & Get API Key
```
1. Go to https://dashboard.retell.ai
2. Sign up (free trial available)
3. Go to Settings → API Keys
4. Copy your API key
```

### 1.2 Create AI Agent
```
1. Click "Agents" → "Create New Agent"
2. Fill in:
   - Name: "CrownDesk Receptionist"
   - Language: English (US)
   - Language Model: Select "Custom LLM"
3. In Custom LLM Settings:
   - WebSocket URL: wss://ai-service-sparkling-brook-7912.fly.dev/retell-llm
4. Save agent (you'll get an Agent ID)
```

### 1.3 Get a Phone Number
```
1. Click "Phone Numbers" → "Get a Number"
2. Choose country and area code
3. Select your "CrownDesk Receptionist" agent
4. Complete purchase
```

**✅ You now have a working phone number connected to your AI!**

---

## Step 2: Set Up ElevenLabs Voice (3 minutes)

### 2.1 Get API Key
```
1. Go to https://elevenlabs.io
2. Sign up (free tier available)
3. Go to Profile → API Keys
4. Copy your API key
```

### 2.2 Configure Voice in Retell
```
1. Back in Retell Dashboard
2. Go to your "CrownDesk Receptionist" agent
3. Click "Voice Settings"
4. Select "ElevenLabs" as TTS provider
5. Paste your ElevenLabs API key
6. Choose a voice:
   - Rachel (recommended): Professional female
   - Adam: Professional male  
   - Bella: Warm and friendly
7. Adjust settings:
   - Stability: 0.5
   - Similarity Boost: 0.75
   - Style Exaggeration: 0.0
8. Save
```

**✅ Your AI now has a natural-sounding voice!**

---

## Step 3: Configure Your AI Service (5 minutes)

### 3.1 Add Secrets to Fly.io

Open PowerShell and run:

```powershell
cd "c:\Users\Sai Tejaswi B\Desktop\CrownDesk\crowndesk-ai-service"

# Add Retell AI API Key
fly secrets set RETELL_API_KEY="your_retell_api_key_here"

# Add ElevenLabs API Key
fly secrets set ELEVENLABS_API_KEY="your_elevenlabs_api_key_here"

# Add backend API key (if you have one, otherwise skip)
fly secrets set BACKEND_API_KEY="your_backend_api_key_here"

# Verify secrets
fly secrets list
```

### 3.2 Update Environment Files

Edit `c:\Users\Sai Tejaswi B\Desktop\CrownDesk\env\.env.local.ai-service`:

```dotenv
# -------------------------
# RetellAI (Voice Agent)
# -------------------------
RETELL_API_KEY=your_retell_api_key_here
RETELL_LLM_WEBSOCKET_URL=wss://ai-service-sparkling-brook-7912.fly.dev/retell-llm

# -------------------------
# ElevenLabs (TTS)
# -------------------------
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel voice
# Other voice IDs:
# Adam: pNInz6obpgDQGcFmaJgB
# Bella: EXAVITQu4vr4xnSDxMaL
# Antoni: ErXwobaYiN019PkySvjV

# -------------------------
# Backend Integration
# -------------------------
BACKEND_URL=https://cdapi.xaltrax.com
BACKEND_API_KEY=your_backend_api_key_here
```

### 3.3 Restart AI Service (if running locally)

```powershell
# If running locally
cd "c:\Users\Sai Tejaswi B\Desktop\CrownDesk"
.\start-all-servers.ps1
```

**Fly.io automatically restarts** when you set secrets, so no manual restart needed for production!

---

## Step 4: Test Your AI Receptionist (2 minutes)

### 4.1 Make a Test Call

```
1. Call the phone number from Retell (Step 1.3)
2. You should hear: "Hello! Thank you for calling. This is the CrownDesk dental practice assistant. How can I help you today?"
3. Try saying: "I want to schedule a cleaning appointment"
4. Follow the conversation!
```

### 4.2 Test Appointment Booking

**Example conversation:**
```
AI: "Hello! How can I help you today?"
You: "I need to book a cleaning appointment"
AI: "I'd be happy to help schedule a cleaning for you. May I have your name?"
You: "John Smith"
AI: "Thank you, John. And your date of birth for verification?"
You: "January 15, 1980"
AI: "Great! What day works best for you?"
You: "Next Tuesday morning"
AI: "Perfect! I have 9 AM or 10:30 AM available. Which would you prefer?"
You: "9 AM works"
AI: "Excellent! I've scheduled your cleaning for Tuesday at 9 AM. You'll receive a confirmation. Is there anything else?"
```

### 4.3 Check Logs

```powershell
# View real-time logs
fly logs -a crowndesk-ai-service

# Should see:
# WebSocket connection established
# Function calls: book_appointment, check_availability
# Conversation transcript
```

---

## Step 5: Optional Webhooks (Advanced)

### 5.1 Post-Call Webhook in Retell

Receive notifications when calls end:

```
1. In Retell Dashboard → Settings → Webhooks
2. Add webhook URL: https://ai-service-sparkling-brook-7912.fly.dev/api/retell/webhook
3. Select events:
   - call_started
   - call_ended
   - call_analyzed
4. Save
```

**Payload you'll receive:**
```json
{
  "event_type": "call_ended",
  "call_id": "abc123",
  "duration": 120,
  "transcript": [...],
  "recording_url": "https://..."
}
```

### 5.2 ElevenLabs Webhook (Optional)

Only needed for advanced voice features:

```json
{
  "type": "webhook",
  "name": "voice_synthesis_complete",
  "api_schema": {
    "url": "https://ai-service-sparkling-brook-7912.fly.dev/api/elevenlabs/callback",
    "method": "POST"
  }
}
```

---

## Complete Webhook Summary

| Service | Type | URL | Purpose |
|---------|------|-----|---------|
| **Retell AI** | WebSocket | `wss://ai-service-sparkling-brook-7912.fly.dev/retell-llm` | **Primary**: Real-time AI conversation |
| Retell AI | Webhook | `https://ai-service-sparkling-brook-7912.fly.dev/api/retell/webhook` | Optional: Post-call notifications |
| **ElevenLabs** | API | Configured in Retell | **Primary**: Text-to-Speech |
| ElevenLabs | Webhook | Custom endpoint | Optional: Voice generation events |
| Backend | API | `https://cdapi.xaltrax.com/api/*` | Save appointments to database |

---

## Troubleshooting

### Issue: "WebSocket connection failed"
**Fix:**
```powershell
# Check if AI service is running
Invoke-RestMethod -Uri "https://ai-service-sparkling-brook-7912.fly.dev/health"
# Should return: {"status":"ok"}
```

### Issue: "AI doesn't respond"
**Fix:**
1. Check Fly.io logs: `fly logs -a crowndesk-ai-service`
2. Verify WebSocket URL in Retell dashboard matches exactly
3. Ensure RETELL_API_KEY is set in Fly.io secrets

### Issue: "Voice sounds robotic"
**Fix:**
1. In Retell agent → Voice Settings
2. Increase Stability to 0.7
3. Try different voice (Rachel, Bella)
4. Use ElevenLabs premium voices

### Issue: "Appointments not saving"
**Fix:**
```powershell
# Verify backend API key
fly secrets list
# Should show BACKEND_API_KEY

# Test backend connection
$headers = @{"Authorization" = "Bearer YOUR_KEY"}
Invoke-RestMethod -Uri "https://cdapi.xaltrax.com/api/health" -Headers $headers
```

---

## Testing Checklist

- [ ] Call the phone number and hear greeting
- [ ] AI responds to "book appointment"
- [ ] AI asks for name and date of birth
- [ ] AI suggests available times
- [ ] Appointment is confirmed
- [ ] Check backend database for new appointment
- [ ] Review transcript in Retell dashboard
- [ ] Test "reschedule appointment" flow
- [ ] Test "office hours" question
- [ ] Test transfer to human ("talk to a person")

---

## What's Configured

After completing this guide, you have:

✅ **Retell AI Agent** with custom LLM integration  
✅ **Phone Number** connected to your AI  
✅ **ElevenLabs Voice** for natural conversations  
✅ **WebSocket Connection** handling real-time calls  
✅ **Function Calling** for appointments, patient lookup, insurance  
✅ **Backend Integration** to save appointments  
✅ **HIPAA Guardrails** protecting patient privacy  

---

## Next Steps

1. **Customize Prompts**: Edit system prompt in `retell.py` (lines 76-100)
2. **Add More Functions**: Add patient lookup, insurance verification
3. **Configure Business Hours**: Set office hours in agent configuration
4. **Enable Call Recording**: Turn on in Retell dashboard for compliance
5. **Set Up Analytics**: Track call metrics and conversion rates

---

## Need Help?

- **View API Docs**: https://ai-service-sparkling-brook-7912.fly.dev/docs
- **Check Logs**: `fly logs -a crowndesk-ai-service`
- **Test Health**: `Invoke-RestMethod -Uri "https://ai-service-sparkling-brook-7912.fly.dev/health"`
- **Retell Support**: https://docs.retellai.com
- **ElevenLabs Docs**: https://docs.elevenlabs.io

---

**You're done! Your AI receptionist is ready to take calls 24/7! 🎉**
