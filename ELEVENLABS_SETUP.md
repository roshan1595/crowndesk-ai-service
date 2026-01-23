# ElevenLabs Conversational AI Setup Guide

Complete guide to configure CrownDesk AI Receptionist using ElevenLabs Conversational AI with webhooks.

---

## Overview

Instead of Retell AI, we're using **ElevenLabs Conversational AI** which provides:
- Natural voice conversations
- Built-in webhook/tool calling
- Phone number integration
- Web embed widget
- Better voice quality with ElevenLabs voices

---

## Prerequisites

1. **ElevenLabs Account**: https://elevenlabs.io (sign up for free)
2. **Backend API Key**: From your Vercel backend environment
3. **Tenant ID**: Your practice's tenant UUID from the database

---

## Quick Setup (15 Minutes)

### Step 1: Create ElevenLabs Agent

1. Go to https://elevenlabs.io/app/conversational-ai
2. Click **"Create Agent"**
3. Fill in basic info:
   - **Name**: `CrownDesk AI Receptionist`
   - **Description**: `AI receptionist for dental practice - books appointments, answers questions, verifies insurance`

### Step 2: Configure Agent Settings

#### System Prompt
Copy this into the "System Prompt" field:

```
You are a friendly and professional AI receptionist for a dental practice. Your name is CrownDesk Assistant.

## Your Capabilities:
- Schedule, reschedule, and cancel appointments
- Answer questions about office hours, location, and services
- Look up patient information (after identity verification)
- Check insurance information
- Provide general information about dental procedures
- Transfer to a human receptionist when needed

## Important Rules:
1. NEVER provide medical diagnoses or treatment recommendations
2. NEVER guarantee insurance coverage amounts
3. ALWAYS verify patient identity before disclosing personal information (ask for name and date of birth)
4. If unsure or the patient requests, offer to transfer to a human receptionist
5. Be concise - aim for responses under 2-3 sentences when possible
6. Speak naturally and conversationally
7. If there's an emergency, advise them to call 911 or go to the nearest emergency room

## Conversation Flow:
1. Greet warmly and ask how you can help
2. Use webhooks to search patients, check availability, book appointments
3. Always confirm all details before finalizing actions
4. Provide confirmation and next steps

## Booking Appointment Flow:
1. Ask patient name → use 'search_patients' webhook
2. Verify DOB for security
3. Ask preferred date/time
4. Use 'get_available_slots' to check availability
5. Offer available times
6. Use 'create_appointment' to book
7. Confirm details and offer to send confirmation
```

#### First Message
```
Hello! Thank you for calling. This is the CrownDesk dental practice assistant. How can I help you today?
```

#### Voice Selection
- **Recommended**: Rachel (professional female voice)
- **Alternatives**: Adam (male), Bella (warm female), Antoni (calm male)
- **Settings**:
  - Stability: 0.5
  - Similarity Boost: 0.75
  - Style Exaggeration: 0.0

### Step 3: Add Webhooks (Tools)

In the agent configuration, go to the **"Tools"** or **"Webhooks"** section. Add each webhook below:

---

## Webhook Configurations

### 1. Search Patients

**Purpose**: Find patient by name, phone, or email

```json
{
  "type": "webhook",
  "name": "search_patients",
  "description": "Search for patients by name, phone, or email. Use this when caller mentions their name or you need to find a patient.",
  "api_schema": {
    "url": "https://cdapi.xaltrax.com/api/patients/search",
    "method": "GET",
    "path_params_schema": [],
    "query_params_schema": [
      {
        "name": "q",
        "type": "string",
        "required": true,
        "description": "Search query - patient name, email, or phone number"
      }
    ],
    "request_body_schema": null,
    "request_headers": [
      {
        "name": "Authorization",
        "value": "Bearer YOUR_BACKEND_API_KEY_HERE"
      },
      {
        "name": "x-tenant-id",
        "value": "YOUR_TENANT_ID_HERE"
      }
    ]
  },
  "response_timeout_secs": 10
}
```

---

### 2. Get Available Appointment Slots

**Purpose**: Check available times for appointment booking

```json
{
  "type": "webhook",
  "name": "get_available_slots",
  "description": "Check available appointment time slots for a specific provider and date. Use when scheduling appointments.",
  "api_schema": {
    "url": "https://cdapi.xaltrax.com/api/appointments/slots/{provider}/{date}",
    "method": "GET",
    "path_params_schema": [
      {
        "name": "provider",
        "type": "string",
        "required": true,
        "description": "Provider name or 'any' for any provider"
      },
      {
        "name": "date",
        "type": "string",
        "required": true,
        "description": "Date in YYYY-MM-DD format"
      }
    ],
    "query_params_schema": [
      {
        "name": "duration",
        "type": "number",
        "required": false,
        "description": "Duration in minutes (default 30)"
      }
    ],
    "request_body_schema": null,
    "request_headers": [
      {
        "name": "Authorization",
        "value": "Bearer YOUR_BACKEND_API_KEY_HERE"
      },
      {
        "name": "x-tenant-id",
        "value": "YOUR_TENANT_ID_HERE"
      }
    ]
  },
  "response_timeout_secs": 10,
  "force_pre_tool_speech": "Let me check available times for you."
}
```

---

### 3. Create Appointment

**Purpose**: Book a new appointment

```json
{
  "type": "webhook",
  "name": "create_appointment",
  "description": "Book a new appointment for a patient. Use after confirming patient details, date, time, and appointment type.",
  "api_schema": {
    "url": "https://cdapi.xaltrax.com/api/appointments",
    "method": "POST",
    "path_params_schema": [],
    "query_params_schema": [],
    "request_body_schema": {
      "type": "object",
      "properties": {
        "patientId": {
          "type": "string",
          "description": "Patient UUID from search results"
        },
        "startTime": {
          "type": "string",
          "description": "ISO datetime (e.g., 2026-01-25T09:00:00Z)"
        },
        "endTime": {
          "type": "string",
          "description": "ISO datetime (e.g., 2026-01-25T09:30:00Z)"
        },
        "appointmentType": {
          "type": "string",
          "enum": ["cleaning", "exam", "treatment", "emergency", "consultation"],
          "description": "Type of appointment"
        },
        "status": {
          "type": "string",
          "description": "Use 'scheduled'"
        },
        "notes": {
          "type": "string",
          "description": "Additional notes"
        }
      },
      "required": ["patientId", "startTime", "endTime", "appointmentType"]
    },
    "request_headers": [
      {
        "name": "Authorization",
        "value": "Bearer YOUR_BACKEND_API_KEY_HERE"
      },
      {
        "name": "x-tenant-id",
        "value": "YOUR_TENANT_ID_HERE"
      },
      {
        "name": "Content-Type",
        "value": "application/json"
      }
    ]
  },
  "response_timeout_secs": 15,
  "disable_interruptions": true,
  "force_pre_tool_speech": "Perfect! I'm booking that appointment for you now."
}
```

---

### 4. Get Patient Appointments

**Purpose**: Check patient's existing appointments

```json
{
  "type": "webhook",
  "name": "get_patient_appointments",
  "description": "Get all appointments for a specific patient. Use to check existing appointments.",
  "api_schema": {
    "url": "https://cdapi.xaltrax.com/api/patients/{patient_id}/appointments",
    "method": "GET",
    "path_params_schema": [
      {
        "name": "patient_id",
        "type": "string",
        "required": true,
        "description": "Patient UUID"
      }
    ],
    "query_params_schema": [
      {
        "name": "limit",
        "type": "number",
        "required": false,
        "description": "Max results (default 10)"
      }
    ],
    "request_body_schema": null,
    "request_headers": [
      {
        "name": "Authorization",
        "value": "Bearer YOUR_BACKEND_API_KEY_HERE"
      },
      {
        "name": "x-tenant-id",
        "value": "YOUR_TENANT_ID_HERE"
      }
    ]
  },
  "response_timeout_secs": 10,
  "force_pre_tool_speech": "Let me check your appointments."
}
```

---

### 5. Update Appointment Status

**Purpose**: Cancel or reschedule appointments

```json
{
  "type": "webhook",
  "name": "update_appointment_status",
  "description": "Update appointment status (cancel, reschedule, etc.)",
  "api_schema": {
    "url": "https://cdapi.xaltrax.com/api/appointments/{appointment_id}/status",
    "method": "PATCH",
    "path_params_schema": [
      {
        "name": "appointment_id",
        "type": "string",
        "required": true,
        "description": "Appointment UUID"
      }
    ],
    "query_params_schema": [],
    "request_body_schema": {
      "type": "object",
      "properties": {
        "status": {
          "type": "string",
          "enum": ["scheduled", "confirmed", "cancelled", "no_show"],
          "description": "New status"
        }
      },
      "required": ["status"]
    },
    "request_headers": [
      {
        "name": "Authorization",
        "value": "Bearer YOUR_BACKEND_API_KEY_HERE"
      },
      {
        "name": "x-tenant-id",
        "value": "YOUR_TENANT_ID_HERE"
      },
      {
        "name": "Content-Type",
        "value": "application/json"
      }
    ]
  },
  "response_timeout_secs": 10
}
```

---

### 6. Get Patient Insurance

**Purpose**: Check insurance information

```json
{
  "type": "webhook",
  "name": "get_patient_insurance",
  "description": "Get patient's insurance information and coverage details.",
  "api_schema": {
    "url": "https://cdapi.xaltrax.com/api/patients/{patient_id}/insurance",
    "method": "GET",
    "path_params_schema": [
      {
        "name": "patient_id",
        "type": "string",
        "required": true,
        "description": "Patient UUID"
      }
    ],
    "query_params_schema": [],
    "request_body_schema": null,
    "request_headers": [
      {
        "name": "Authorization",
        "value": "Bearer YOUR_BACKEND_API_KEY_HERE"
      },
      {
        "name": "x-tenant-id",
        "value": "YOUR_TENANT_ID_HERE"
      }
    ]
  },
  "response_timeout_secs": 10,
  "force_pre_tool_speech": "Let me look up your insurance information."
}
```

---

### 7. Query Knowledge Base

**Purpose**: Answer questions about office hours, services, policies

```json
{
  "type": "webhook",
  "name": "query_knowledge_base",
  "description": "Search practice knowledge base for answers to questions (office hours, services, pricing, policies).",
  "api_schema": {
    "url": "https://ai-service-sparkling-brook-7912.fly.dev/rag/query",
    "method": "POST",
    "path_params_schema": [],
    "query_params_schema": [],
    "request_body_schema": {
      "type": "object",
      "properties": {
        "tenant_id": {
          "type": "string",
          "description": "Tenant UUID"
        },
        "query": {
          "type": "string",
          "description": "Patient's question"
        },
        "top_k": {
          "type": "number",
          "description": "Number of results (default 5)"
        }
      },
      "required": ["tenant_id", "query"]
    },
    "request_headers": [
      {
        "name": "Content-Type",
        "value": "application/json"
      }
    ]
  },
  "response_timeout_secs": 15,
  "force_pre_tool_speech": "Let me check that information for you."
}
```

---

## Step 4: Get Your Environment Variables

### Backend API Key

**Option A: From Vercel**
```powershell
cd crowndesk-backend
vercel env pull .env.production
# Look for BACKEND_API_KEY or JWT_SECRET
```

**Option B: Generate New Key**
```powershell
# Generate random API key
$apiKey = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
Write-Host "New API Key: $apiKey"
```

### Tenant ID

**Get from database:**
```sql
SELECT id, name FROM tenants LIMIT 1;
```

Or create a new tenant via API.

---

## Step 5: Replace Placeholders

In **each webhook**, replace:
- `YOUR_BACKEND_API_KEY_HERE` → Your actual backend API key
- `YOUR_TENANT_ID_HERE` → Your tenant UUID

---

## Step 6: Test Your Agent

### Test in ElevenLabs Dashboard

1. Click **"Test Agent"** button
2. Try these scenarios:

**Scenario 1: Book Appointment**
```
You: "Hi, I need to schedule a cleaning"
AI: "I'd be happy to help! May I have your name please?"
You: "John Smith"
AI: [searches using webhook] "Thank you John. For verification, what's your date of birth?"
You: "January 15, 1980"
AI: "Great! What day works best for you?"
You: "Next Tuesday morning"
AI: [checks slots] "I have 9 AM and 10:30 AM available. Which would you prefer?"
You: "9 AM"
AI: [creates appointment] "Perfect! I've booked your cleaning for Tuesday at 9 AM."
```

**Scenario 2: Office Hours**
```
You: "What are your office hours?"
AI: [queries knowledge base] "We're open Monday through Friday, 8 AM to 5 PM..."
```

**Scenario 3: Insurance**
```
You: "Do you accept my insurance?"
AI: "I'd be happy to check. May I have your name and date of birth?"
[After verification]
AI: [gets insurance] "Yes, I see you have Delta Dental PPO..."
```

---

## Step 7: Deploy

### Get a Phone Number

1. In ElevenLabs dashboard, go to **"Phone Numbers"**
2. Click **"Get a Number"**
3. Choose your region and area code
4. Assign to your "CrownDesk AI Receptionist" agent
5. **You now have a working AI receptionist phone line!**

### Embed on Website

1. Go to agent settings → **"Embed"**
2. Copy the embed code
3. Add to your practice website
4. Patients can now chat with AI on your site

---

## Monitoring & Analytics

### View Call Logs
- Go to ElevenLabs Dashboard → **"Conversations"**
- See all calls, transcripts, and webhook calls
- Monitor success rates and common issues

### Webhook Success Rate
- Check which webhooks are being called
- Identify failed requests
- Optimize based on usage patterns

---

## Troubleshooting

### Issue: Webhook returns 401 Unauthorized
**Fix**: Check that `Authorization: Bearer YOUR_API_KEY` header is correct

### Issue: Agent can't find patients
**Fix**: 
1. Verify `x-tenant-id` header matches your tenant
2. Check that patients exist in database
3. Test search endpoint manually:
```powershell
$headers = @{
    "Authorization" = "Bearer YOUR_API_KEY"
    "x-tenant-id" = "YOUR_TENANT_ID"
}
Invoke-RestMethod -Uri "https://cdapi.xaltrax.com/api/patients/search?q=Smith" -Headers $headers
```

### Issue: Appointments not creating
**Fix**:
1. Check startTime/endTime format (must be ISO 8601)
2. Verify patientId exists
3. Test manually:
```powershell
$body = @{
    patientId = "patient-uuid"
    startTime = "2026-01-25T09:00:00Z"
    endTime = "2026-01-25T09:30:00Z"
    appointmentType = "cleaning"
    status = "scheduled"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://cdapi.xaltrax.com/api/appointments" -Method POST -Body $body -ContentType "application/json" -Headers $headers
```

### Issue: Voice sounds unnatural
**Fix**:
1. Try different voice (Rachel, Bella, Adam)
2. Adjust stability slider (lower = more expressive)
3. Use shorter sentences in responses

---

## Advanced Configuration

### Add More Webhooks

See `ELEVENLABS_WEBHOOKS.json` for complete list including:
- `classify_intent` - AI intent classification
- `extract_entities` - Extract names, dates, times
- `suggest_procedure_codes` - CDT code suggestions
- `check_insurance_eligibility` - Real-time eligibility verification

### Custom Knowledge Base

1. Prepare documents (office hours, services, policies)
2. Use RAG ingest endpoint:
```powershell
$docs = @{
    tenant_id = "YOUR_TENANT_ID"
    content = "Our office hours are Monday-Friday 8 AM to 5 PM..."
    metadata = @{ type = "office_info" }
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://ai-service-sparkling-brook-7912.fly.dev/rag/ingest" -Method POST -Body $docs -ContentType "application/json"
```

3. Agent will automatically query this when asked

---

## Cost Estimation

**ElevenLabs Pricing** (as of Jan 2026):
- **Free Tier**: 10,000 characters/month (~20-30 calls)
- **Starter**: $5/month - 30,000 characters
- **Creator**: $22/month - 100,000 characters
- **Pro**: $99/month - 500,000 characters
- **Scale**: $330/month - 2,000,000 characters

**Typical call**: 500-1000 characters

---

## Next Steps

1. ✅ Configure agent in ElevenLabs
2. ✅ Add all webhooks with your API keys
3. ✅ Test thoroughly with various scenarios
4. ✅ Get phone number
5. ✅ Update practice website/marketing materials
6. 📊 Monitor call analytics
7. 🔄 Iterate based on real conversations
8. 📈 Scale up as needed

---

## Support Resources

- **ElevenLabs Docs**: https://docs.elevenlabs.io/conversational-ai
- **CrownDesk API Docs**: https://cdapi.xaltrax.com/api/docs
- **AI Service Docs**: https://ai-service-sparkling-brook-7912.fly.dev/docs
- **All Webhooks**: See `ELEVENLABS_WEBHOOKS.json` for complete configuration

---

**You're ready to launch your AI receptionist! 🎉**
