# CrownDesk V2 - AI Agent Management System
## Comprehensive Specification & Implementation Plan

**Created:** January 21, 2026  
**Status:** 🚀 Ready for Implementation  
**Priority:** P0 - Critical Feature

---

## 📋 Executive Summary

This document outlines the complete specification for CrownDesk's **Practice Automation Hub** - a unified management interface for AI-powered phone agents, call handling, and phone number management. This system positions CrownDesk as the intelligent automation layer for dental practices.

### Key Components:
1. **Phone Number Management** - Buy, deploy, configure numbers (Twilio/Telnyx/SIP)
2. **Agent Management** - Create, activate, monitor AI agents per organization
3. **Call Monitoring** - Real-time call status, live transcription
4. **Call History** - Complete call logs with intents, outcomes, approvals
5. **Analytics Dashboard** - Call volume, success rates, escalations

---

## 🎯 Product Vision

**Page Name:** `Practice Automation Hub` or `Call Management` or `Automation Center`  
**Marketing Angle:** Not "AI" upfront - position as "Intelligent Call Handling" or "Practice Automation"

### User Journey:
```
1. Clinic signs up → No phone system configured
2. Navigate to "Automation Hub" → See empty state with setup wizard
3. Add phone number (buy new or port existing)
4. Activate AI agent → Agent starts in "standby" mode
5. Incoming call → Agent handles, creates approval/task
6. Staff reviews call log → Approves/rejects AI actions
7. Analytics → See call volume, success rate, time saved
```

---

## 🏗️ System Architecture

### Tech Stack Integration

```
┌─────────────────────────────────────────────────────────────┐
│                  CROWNDESK AUTOMATION HUB                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Frontend (Next.js)                                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  /dashboard/automation                               │   │
│  │  - Phone Number Management                           │   │
│  │  - Agent Configuration                               │   │
│  │  - Live Call Monitor                                 │   │
│  │  - Call History & Analytics                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  Backend (NestJS) - Port 3001                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  /api/phone-numbers                                  │   │
│  │  /api/agents                                         │   │
│  │  /api/calls                                          │   │
│  │  /api/call-analytics                                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  AI Service (FastAPI) - Port 8001                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  WebSocket: /ws/retell (existing)                    │   │
│  │  POST /retell/agents                                 │   │
│  │  GET /retell/agents                                  │   │
│  │  POST /retell/phone-call                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│  ┌─────────────┬──────────┴────────┬─────────────────────┐  │
│  │             │                   │                     │  │
│  ▼             ▼                   ▼                     ▼  │
│ Retell AI   Twilio/Telnyx      Database            Approvals│
│ - Agent     - Phone Numbers    - CallRecord         Module  │
│   Creation  - SIP Trunking     - CallToolInvocation         │
│ - WebSocket - SMS (future)     - PhoneNumber                │
│                                - AgentConfig                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Database Schema Extensions

### New Tables Needed

```prisma
// Phone Number Management
model PhoneNumber {
  id            String   @id @default(uuid()) @db.Uuid
  tenantId      String   @map("tenant_id") @db.Uuid
  
  // Phone Details
  phoneNumber   String   @map("phone_number") // E.164 format: +15551234567
  friendlyName  String?  @map("friendly_name")
  provider      PhoneProvider
  providerSid   String?  @map("provider_sid") // Twilio/Telnyx ID
  
  // Configuration
  status        PhoneStatus  @default(INACTIVE)
  assignedAgentId String?   @map("assigned_agent_id") @db.Uuid
  
  // Capabilities
  voiceEnabled  Boolean  @default(true) @map("voice_enabled")
  smsEnabled    Boolean  @default(false) @map("sms_enabled")
  
  // Metadata
  purchasedAt   DateTime? @map("purchased_at")
  activatedAt   DateTime? @map("activated_at")
  createdAt     DateTime  @default(now()) @map("created_at")
  updatedAt     DateTime  @updatedAt @map("updated_at")
  
  // Relations
  tenant        Tenant   @relation(fields: [tenantId], references: [id], onDelete: Cascade)
  agent         AgentConfig? @relation(fields: [assignedAgentId], references: [id])
  calls         CallRecord[]
  
  @@map("phone_numbers")
}

enum PhoneProvider {
  TWILIO
  TELNYX
  VONAGE
  SIP_TRUNK
  OTHER
}

enum PhoneStatus {
  INACTIVE      // Purchased but not configured
  ACTIVE        // Live and receiving calls
  SUSPENDED     // Temporarily disabled
  PORTING       // Number port in progress
  RELEASED      // Released back to provider
}

// Agent Configuration
model AgentConfig {
  id              String   @id @default(uuid()) @db.Uuid
  tenantId        String   @map("tenant_id") @db.Uuid
  
  // Agent Identity
  agentName       String   @map("agent_name")
  agentType       AgentType @default(RECEPTIONIST)
  
  // Retell Integration
  retellAgentId   String?  @map("retell_agent_id") // From Retell API
  voiceId         String?  @map("voice_id")
  language        String   @default("en-US")
  
  // Status
  status          AgentStatus @default(INACTIVE)
  isActive        Boolean  @default(false) @map("is_active")
  
  // Configuration
  workingHours    Json?    @map("working_hours") // {monday: {start: "09:00", end: "17:00"}}
  transferNumber  String?  @map("transfer_number") // Human fallback
  customPrompt    String?  @map("custom_prompt") @db.Text
  
  // Guardrails
  requireApproval Boolean  @default(true) @map("require_approval")
  maxCallDuration Int      @default(1800) @map("max_call_duration") // seconds
  
  // Metadata
  activatedAt     DateTime? @map("activated_at")
  lastActiveAt    DateTime? @map("last_active_at")
  createdAt       DateTime  @default(now()) @map("created_at")
  updatedAt       DateTime  @updatedAt @map("updated_at")
  createdBy       String?   @map("created_by") @db.Uuid
  
  // Relations
  tenant          Tenant   @relation(fields: [tenantId], references: [id], onDelete: Cascade)
  phoneNumbers    PhoneNumber[]
  calls           CallRecord[]
  
  @@map("agent_configs")
}

enum AgentType {
  RECEPTIONIST    // Main voice assistant
  SCHEDULER       // Appointment-only agent
  BILLING         // Billing inquiries
  EMERGENCY       // After-hours emergency triage
  CUSTOM          // Custom configured agent
}

enum AgentStatus {
  INACTIVE        // Not started
  ACTIVE          // Running and ready
  ON_CALL         // Currently in a call
  PAUSED          // Temporarily paused
  ERROR           // Configuration error
}

// Enhanced CallRecord (already exists, add fields)
model CallRecord {
  // ... existing fields ...
  
  // Add these fields:
  agentConfigId   String?  @map("agent_config_id") @db.Uuid
  phoneNumberId   String?  @map("phone_number_id") @db.Uuid
  
  // Call Quality Metrics
  qualityScore    Float?   @map("quality_score") // 0-10
  userSatisfaction Int?    @map("user_satisfaction") // 1-5 stars
  wasEscalated    Boolean  @default(false) @map("was_escalated")
  escalationReason String? @map("escalation_reason")
  
  // Relations
  agentConfig     AgentConfig? @relation(fields: [agentConfigId], references: [id])
  phoneNumber     PhoneNumber? @relation(fields: [phoneNumberId], references: [id])
}
```

---

## 🎨 Frontend Pages & Components

### Route Structure

```
/dashboard/automation
├── page.tsx (Main dashboard)
├── phone-numbers/
│   ├── page.tsx (Phone number list)
│   ├── new/page.tsx (Buy/add number wizard)
│   └── [id]/page.tsx (Number configuration)
├── agents/
│   ├── page.tsx (Agent list)
│   ├── new/page.tsx (Create agent)
│   └── [id]/
│       ├── page.tsx (Agent detail)
│       └── configure/page.tsx (Agent settings)
├── calls/
│   ├── page.tsx (Call history)
│   └── [id]/page.tsx (Call detail)
└── analytics/page.tsx (Call analytics)
```

### Main Dashboard (`/dashboard/automation`)

**Layout:**
```
┌──────────────────────────────────────────────────────────────┐
│  Practice Automation Hub                    [+ Add Number]   │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  📊 Overview Stats                                            │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │ Active      │ Total Calls │ Success     │ Avg Handle  │  │
│  │ Agents: 2   │ Today: 47   │ Rate: 89%   │ Time: 3.2m  │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
│                                                               │
│  🤖 Active Agents                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🟢 Main Receptionist                      [Configure] │   │
│  │    +1 (555) 123-4567                                  │   │
│  │    Status: Active • Last call: 12 min ago            │   │
│  │    Today: 34 calls • 92% success                     │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ 🔴 After-Hours Agent                      [Configure] │   │
│  │    +1 (555) 987-6543                                  │   │
│  │    Status: Inactive (Outside working hours)          │   │
│  │    Today: 0 calls                                     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  📞 Recent Calls                         [View All →]        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 2:34 PM • John Smith • Appointment Request  ✅       │   │
│  │ 2:12 PM • Jane Doe • Insurance Question  ⚠️ Escalate │   │
│  │ 1:55 PM • Bob Johnson • Reschedule  ✅                │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**Key Features:**
- Real-time agent status (using WebSocket or polling)
- Quick stats (calls today, success rate, average handle time)
- Active agent cards with live status indicators
- Recent calls stream with outcomes
- Quick actions (add number, configure agent, view analytics)

---

### Phone Numbers Page (`/dashboard/automation/phone-numbers`)

```
┌──────────────────────────────────────────────────────────────┐
│  Phone Numbers                    [+ Buy Number] [+ Port In] │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  📱 Active Numbers (2)                                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ +1 (555) 123-4567                          [Settings] │   │
│  │ Provider: Twilio • Assigned: Main Receptionist        │   │
│  │ Status: 🟢 Active • 34 calls today                   │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ +1 (555) 987-6543                          [Settings] │   │
│  │ Provider: Twilio • Assigned: After-Hours Agent        │   │
│  │ Status: 🔴 Inactive • 0 calls today                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ⏳ Porting In Progress (1)                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ +1 (555) 444-8888                          [Details]  │   │
│  │ From: Existing Provider • ETA: 2-3 business days      │   │
│  │ Status: 🟡 Pending                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**Wizards:**

1. **Buy New Number**
   - Step 1: Select provider (Twilio, Telnyx, Vonage)
   - Step 2: Search area code/location
   - Step 3: Choose number from available list
   - Step 4: Configure (name, assign agent)
   - Step 5: Review and purchase

2. **Port Existing Number**
   - Step 1: Enter current number
   - Step 2: Current provider details
   - Step 3: Authorization form
   - Step 4: LOA (Letter of Authorization) upload
   - Step 5: Submit port request

3. **Configure SIP Trunk**
   - Step 1: SIP provider details
   - Step 2: Trunk credentials
   - Step 3: Inbound routing
   - Step 4: Test connection

---

### Agent Management Page (`/dashboard/automation/agents`)

```
┌──────────────────────────────────────────────────────────────┐
│  AI Agents                                  [+ Create Agent]  │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Filters: [All] [Active] [Inactive] [On Call]                │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🟢 Main Receptionist                   [⚙️] [▶️/⏸️]  │   │
│  │ ───────────────────────────────────────────────────  │   │
│  │ Type: Receptionist • Voice: Rachel (Friendly)        │   │
│  │ Phone: +1 (555) 123-4567                             │   │
│  │ Active: 24/7 • Last active: 12 minutes ago           │   │
│  │                                                       │   │
│  │ Today's Performance:                                  │   │
│  │ 📞 34 calls • ✅ 31 handled • ⚠️ 3 escalated         │   │
│  │ ⏱️ Avg. 3.2 min • 😊 4.5 stars                       │   │
│  │                                                       │   │
│  │ [View Call History] [Configure] [Analytics]          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🔴 After-Hours Emergency                [⚙️] [▶️/⏸️]  │   │
│  │ ───────────────────────────────────────────────────  │   │
│  │ Type: Emergency Triage • Voice: David (Professional) │   │
│  │ Phone: +1 (555) 987-6543                             │   │
│  │ Active: Weekdays 6PM-8AM, Weekends 24/7              │   │
│  │                                                       │   │
│  │ Status: Currently inactive (within working hours)     │   │
│  │ Last active: Yesterday at 11:45 PM                    │   │
│  │                                                       │   │
│  │ [View Call History] [Configure] [Analytics]          │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**Agent Configuration Modal:**
```
┌──────────────────────────────────────────────┐
│  Configure Agent                        [✕]  │
├──────────────────────────────────────────────┤
│                                               │
│  Basic Settings                               │
│  ├─ Agent Name: [Main Receptionist      ]   │
│  ├─ Agent Type: [Receptionist ▼]            │
│  └─ Voice: [Rachel - Friendly ▼]            │
│                                               │
│  Phone Number                                 │
│  └─ Assigned: [+1 (555) 123-4567 ▼]         │
│                                               │
│  Working Hours                                │
│  ├─ Monday-Friday: [09:00] to [17:00]       │
│  ├─ Saturday: [09:00] to [13:00]            │
│  └─ Sunday: [Closed]                         │
│                                               │
│  Behavior                                     │
│  ├─ ☑ Require approval for bookings          │
│  ├─ ☑ Escalate complex questions            │
│  ├─ Transfer Number: [+1555-STAFF-01 ]      │
│  └─ Max Call Duration: [30] minutes          │
│                                               │
│  Custom Instructions (Optional)               │
│  ┌───────────────────────────────────────┐  │
│  │ Always mention our new patient        │  │
│  │ special: $99 cleaning + exam          │  │
│  └───────────────────────────────────────┘  │
│                                               │
│  [Test Agent] [Cancel] [Save & Activate]     │
└──────────────────────────────────────────────┘
```

---

### Call History Page (`/dashboard/automation/calls`)

```
┌──────────────────────────────────────────────────────────────┐
│  Call History                      [Date Range ▼] [Export]   │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Filters: [All] [Successful] [Escalated] [Failed]            │
│  Agent: [All Agents ▼] | Search: [              🔍]         │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 2:34 PM • 3m 21s                        [View Detail] │   │
│  │ ───────────────────────────────────────────────────  │   │
│  │ Caller: John Smith                                    │   │
│  │ Number: +1 (555) 111-2222                            │   │
│  │ Agent: Main Receptionist                              │   │
│  │                                                       │   │
│  │ Intent: 📅 Appointment Request                        │   │
│  │ Outcome: ✅ Successfully Booked                       │   │
│  │ Approval: Pending staff review                        │   │
│  │                                                       │   │
│  │ Key Details:                                          │   │
│  │ • Patient: John Smith (DOB: 03/15/1985)             │   │
│  │ • Requested: Next Tuesday, Morning                   │   │
│  │ • Type: Cleaning                                     │   │
│  │                                                       │   │
│  │ [▶️ Listen] [📄 Transcript] [✅ Approve] [❌ Reject]  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 2:12 PM • 5m 47s                        [View Detail] │   │
│  │ ───────────────────────────────────────────────────  │   │
│  │ Caller: Jane Doe                                      │   │
│  │ Number: +1 (555) 333-4444                            │   │
│  │ Agent: Main Receptionist                              │   │
│  │                                                       │   │
│  │ Intent: ❓ Insurance Question                         │   │
│  │ Outcome: ⚠️ Escalated to Staff                        │   │
│  │ Reason: Complex coverage question beyond scope       │   │
│  │                                                       │   │
│  │ Question: "Does my plan cover veneers?"              │   │
│  │ Action: Transferred to billing specialist            │   │
│  │                                                       │   │
│  │ [▶️ Listen] [📄 Transcript]                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  [Load More Calls...]                                         │
└──────────────────────────────────────────────────────────────┘
```

---

### Call Detail Page (`/dashboard/automation/calls/[id]`)

```
┌──────────────────────────────────────────────────────────────┐
│  ← Back to Calls                                              │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Call Details                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Time: Today at 2:34 PM                                │   │
│  │ Duration: 3 minutes 21 seconds                        │   │
│  │ Agent: Main Receptionist                              │   │
│  │ Phone: +1 (555) 123-4567                             │   │
│  │ Caller: +1 (555) 111-2222                            │   │
│  │ Quality Score: ★★★★★ 4.8/5.0                         │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  Tabs: [Transcript] [Summary] [Actions] [Recording]          │
│                                                               │
│  📄 Transcript                                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 00:03 Agent: "Hello! Thank you for calling Smith     │   │
│  │              Dental. How can I help you today?"       │   │
│  │                                                       │   │
│  │ 00:07 Caller: "Hi, I'd like to schedule a cleaning." │   │
│  │                                                       │   │
│  │ 00:09 Agent: "Of course! May I have your name and    │   │
│  │              date of birth to look up your record?"  │   │
│  │                                                       │   │
│  │ 00:12 Caller: "John Smith, March 15th, 1985."        │   │
│  │                                                       │   │
│  │ 00:14 Agent: "Thank you, John! I found your record.  │   │
│  │              When would you like to come in?"         │   │
│  │                                                       │   │
│  │ 00:18 Caller: "Do you have anything next Tuesday     │   │
│  │              morning?"                                │   │
│  │                                                       │   │
│  │ 00:20 Agent: [🔧 Checking availability...]            │   │
│  │                                                       │   │
│  │ 00:23 Agent: "Yes! We have 10:00 AM available with   │   │
│  │              Dr. Johnson. Would that work?"           │   │
│  │                                                       │   │
│  │ 00:25 Caller: "Perfect!"                              │   │
│  │                                                       │   │
│  │ 00:26 Agent: [🔧 Booking appointment...]              │   │
│  │                                                       │   │
│  │ 00:30 Agent: "Great! I've scheduled your cleaning    │   │
│  │              for Tuesday, January 28th at 10:00 AM.  │   │
│  │              This requires staff approval, but you'll │   │
│  │              receive a confirmation soon."            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  🎯 Intent Analysis                                           │
│  ├─ Primary: Appointment Booking                              │
│  ├─ Confidence: 98%                                           │
│  └─ Keywords: "schedule", "cleaning", "Tuesday morning"       │
│                                                               │
│  ⚡ Actions Taken                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. ✅ Patient Lookup                                   │   │
│  │    Found: John Smith (ID: PAT-1234)                   │   │
│  │                                                       │   │
│  │ 2. 🔧 Check Availability                               │   │
│  │    Date: 01/28/2026, Time: Morning                    │   │
│  │    Available slots found: 3                           │   │
│  │                                                       │   │
│  │ 3. 📅 Book Appointment                                 │   │
│  │    Status: ⏳ Pending Approval                         │   │
│  │    Details: Dr. Johnson, 10:00 AM, Cleaning          │   │
│  │                                                       │   │
│  │    [✅ Approve Booking] [❌ Reject] [✏️ Edit]          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  📊 Call Metrics                                              │
│  ├─ Wait Time: 0s (immediate answer)                          │
│  ├─ Hold Time: 0s                                             │
│  ├─ Agent Talk Time: 1m 45s                                   │
│  ├─ Caller Talk Time: 1m 36s                                  │
│  └─ Total Duration: 3m 21s                                    │
└──────────────────────────────────────────────────────────────┘
```

---

### Analytics Page (`/dashboard/automation/analytics`)

```
┌──────────────────────────────────────────────────────────────┐
│  Automation Analytics                     [Last 30 Days ▼]   │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  📊 Overview                                                  │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │ Total       │ Success     │ Escalated   │ Time        │  │
│  │ Calls       │ Rate        │ Rate        │ Saved       │  │
│  │             │             │             │             │  │
│  │   1,247     │   89.3%     │   10.7%     │  62.4 hrs   │  │
│  │  (+23%)     │  (+5.2%)    │  (-2.1%)    │  ($1,560)   │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
│                                                               │
│  📈 Call Volume Trend                                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         [Chart: Line graph showing daily calls]       │   │
│  │  60 ┤                           ╭──╮                  │   │
│  │  50 ┤               ╭──╮       ╭╯  ╰╮                │   │
│  │  40 ┤         ╭────╯  ╰╮     ╭╯    ╰╮               │   │
│  │  30 ┤    ╭───╯         ╰─────╯      ╰──╮            │   │
│  │  20 ┤╭───╯                            ╰───╮         │   │
│  │     └──────────────────────────────────────────     │   │
│  │      Jan 1  Jan 8  Jan 15  Jan 22  Jan 29           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  🎯 Intent Distribution                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Appointment Booking      ████████████░░░░░ 62%      │   │
│  │ Rescheduling            ██████░░░░░░░░░░░ 18%      │   │
│  │ Insurance Questions      ████░░░░░░░░░░░░ 12%      │   │
│  │ General Inquiry          ██░░░░░░░░░░░░░░ 5%       │   │
│  │ Other                    █░░░░░░░░░░░░░░░ 3%       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ⏰ Busiest Hours                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 9-10 AM   ███████████████░░░ 45 calls               │   │
│  │ 2-3 PM    ████████████░░░░░░ 38 calls               │   │
│  │ 12-1 PM   ██████████░░░░░░░ 31 calls                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  🤖 Agent Performance                                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Agent              Calls  Success  Avg Time  Rating  │   │
│  │ Main Receptionist  1,124   91.2%   3.2 min   4.7★   │   │
│  │ After-Hours        123     78.5%   5.1 min   4.3★   │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔌 Backend API Specifications

### Phone Numbers API

#### `POST /api/phone-numbers/buy`
```typescript
// Request
{
  provider: "TWILIO" | "TELNYX" | "VONAGE",
  areaCode?: string,
  searchPattern?: string, // e.g., "*SMILE*"
  capabilities: {
    voice: boolean,
    sms: boolean
  }
}

// Response
{
  availableNumbers: [
    {
      phoneNumber: "+15551234567",
      friendlyName: "Chicago - (555) 123-4567",
      monthly Cost: 1.00,
      setupFee: 0
    }
  ]
}
```

#### `POST /api/phone-numbers/purchase`
```typescript
// Request
{
  provider: "TWILIO",
  phoneNumber: "+15551234567",
  friendlyName: "Main Line"
}

// Response
{
  id: "phn_abc123",
  phoneNumber: "+15551234567",
  provider: "TWILIO",
  status: "ACTIVE",
  monthlyCost: 1.00
}
```

#### `GET /api/phone-numbers`
```typescript
// Response
{
  phoneNumbers: [
    {
      id: "phn_abc123",
      phoneNumber: "+15551234567",
      friendlyName: "Main Line",
      provider: "TWILIO",
      status: "ACTIVE",
      assignedAgent: {
        id: "agt_xyz789",
        name: "Main Receptionist"
      },
      stats: {
        callsToday: 34,
        callsTotal: 1247
      }
    }
  ]
}
```

#### `POST /api/phone-numbers/:id/configure`
```typescript
// Request
{
  friendlyName: "Main Line",
  assignedAgentId: "agt_xyz789",
  forwardingNumber?: "+15559998888",
  voicemailEnabled: boolean
}
```

#### `POST /api/phone-numbers/:id/port`
```typescript
// Request
{
  currentProvider: string,
  accountNumber: string,
  pin?: string,
  authorizedName: string,
  loaDocument: File // Letter of Authorization
}

// Response
{
  portRequestId: "port_123",
  status: "PENDING",
  estimatedCompletion: "2026-02-05"
}
```

---

### Agents API

#### `POST /api/agents`
```typescript
// Request
{
  agentName: "Main Receptionist",
  agentType: "RECEPTIONIST",
  voiceId: "eleven_labs_rachel",
  language: "en-US",
  phoneNumberId?: "phn_abc123",
  workingHours: {
    monday: { start: "09:00", end: "17:00", enabled: true },
    tuesday: { start: "09:00", end: "17:00", enabled: true },
    // ...
  },
  transferNumber: "+15559998888",
  requireApproval: true,
  customPrompt?: string
}

// Response
{
  id: "agt_xyz789",
  agentName: "Main Receptionist",
  retellAgentId: "retell_agent_abc123",
  status: "INACTIVE", // Needs activation
  createdAt: "2026-01-21T10:00:00Z"
}
```

#### `POST /api/agents/:id/activate`
```typescript
// Request
{}

// Response
{
  id: "agt_xyz789",
  status: "ACTIVE",
  activatedAt: "2026-01-21T10:05:00Z",
  webhookUrl: "https://api.crowndesk.app/webhooks/retell/agt_xyz789"
}
```

#### `POST /api/agents/:id/deactivate`
```typescript
// Request
{
  reason?: string
}

// Response
{
  id: "agt_xyz789",
  status: "INACTIVE",
  deactivatedAt: "2026-01-21T11:00:00Z"
}
```

#### `GET /api/agents/:id/status`
```typescript
// Response (Real-time via polling or WebSocket)
{
  id: "agt_xyz789",
  status: "ON_CALL", // ACTIVE, ON_CALL, INACTIVE, ERROR
  currentCall: {
    callId: "call_123",
    startedAt: "2026-01-21T10:30:00Z",
    callerNumber: "+15551112222",
    duration: 123 // seconds
  },
  lastActive: "2026-01-21T10:30:00Z",
  stats: {
    callsToday: 34,
    successRate: 0.91
  }
}
```

#### `GET /api/agents`
```typescript
// Response
{
  agents: [
    {
      id: "agt_xyz789",
      agentName: "Main Receptionist",
      agentType: "RECEPTIONIST",
      status: "ACTIVE",
      phoneNumber: "+15551234567",
      stats: {
        callsToday: 34,
        callsTotal: 1247,
        successRate: 0.91,
        avgHandleTime: 192, // seconds
        lastActive: "2026-01-21T10:45:00Z"
      }
    }
  ]
}
```

---

### Calls API

#### `GET /api/calls`
```typescript
// Query Params
?startDate=2026-01-01
&endDate=2026-01-31
&agentId=agt_xyz789
&status=successful|escalated|failed
&intent=appointment_booking|insurance_query
&limit=20
&offset=0

// Response
{
  calls: [
    {
      id: "call_123",
      startTime: "2026-01-21T14:34:00Z",
      endTime: "2026-01-21T14:37:21Z",
      duration: 201, // seconds
      callerNumber: "+15551112222",
      agent: {
        id: "agt_xyz789",
        name: "Main Receptionist"
      },
      intent: {
        primary: "appointment_booking",
        confidence: 0.98
      },
      outcome: "successful",
      requiresApproval: true,
      approvalStatus: "pending",
      transcriptAvailable: true,
      recordingUrl: "https://...",
      qualityScore: 4.8
    }
  ],
  pagination: {
    total: 1247,
    limit: 20,
    offset: 0
  }
}
```

#### `GET /api/calls/:id`
```typescript
// Response
{
  id: "call_123",
  startTime: "2026-01-21T14:34:00Z",
  endTime: "2026-01-21T14:37:21Z",
  duration: 201,
  
  // Participants
  callerNumber: "+15551112222",
  callerName: "John Smith", // If identified
  agent: {
    id: "agt_xyz789",
    name: "Main Receptionist",
    voiceId: "eleven_labs_rachel"
  },
  
  // Call Details
  phoneNumber: "+15551234567",
  direction: "inbound",
  
  // Analysis
  intent: {
    primary: "appointment_booking",
    secondary: null,
    confidence: 0.98,
    keywords: ["schedule", "cleaning", "Tuesday morning"]
  },
  
  // Outcome
  outcome: "successful",
  wasEscalated: false,
  escalationReason: null,
  
  // Actions
  toolInvocations: [
    {
      id: "inv_1",
      toolName: "find_patient",
      arguments: {
        name: "John Smith",
        dob: "1985-03-15"
      },
      result: {
        patientId: "pat_abc123",
        found: true
      },
      timestamp: "2026-01-21T14:34:14Z"
    },
    {
      id: "inv_2",
      toolName: "check_availability",
      arguments: {
        date: "2026-01-28",
        timePreference: "morning"
      },
      result: {
        availableSlots: [
          { time: "09:00", provider: "Dr. Johnson" },
          { time: "10:00", provider: "Dr. Johnson" },
          { time: "11:00", provider: "Dr. Smith" }
        ]
      },
      timestamp: "2026-01-21T14:34:20Z"
    },
    {
      id: "inv_3",
      toolName: "book_appointment",
      arguments: {
        patientId: "pat_abc123",
        appointmentType: "cleaning",
        date: "2026-01-28",
        time: "10:00",
        providerId: "prov_456"
      },
      result: {
        approvalId: "appr_789",
        status: "pending_approval"
      },
      timestamp: "2026-01-21T14:34:26Z"
    }
  ],
  
  // Approval
  requiresApproval: true,
  approval: {
    id: "appr_789",
    status: "pending",
    entityType: "appointment",
    entityId: "apt_new_123"
  },
  
  // Transcript
  transcript: [
    {
      timestamp: "2026-01-21T14:34:03Z",
      speaker: "agent",
      text: "Hello! Thank you for calling Smith Dental. How can I help you today?"
    },
    {
      timestamp: "2026-01-21T14:34:07Z",
      speaker: "user",
      text: "Hi, I'd like to schedule a cleaning."
    },
    // ...
  ],
  
  // Quality
  qualityScore: 4.8,
  userSatisfaction: 5,
  
  // Media
  recordingUrl: "https://recordings.crowndesk.app/call_123.mp3",
  recordingDuration: 201
}
```

#### `POST /api/calls/:id/approve`
```typescript
// Request
{
  approvalId: "appr_789",
  notes?: string
}

// Response
{
  success: true,
  entityCreated: {
    type: "appointment",
    id: "apt_123",
    details: { /* appointment object */ }
  }
}
```

#### `POST /api/calls/:id/reject`
```typescript
// Request
{
  approvalId: "appr_789",
  reason: string
}

// Response
{
  success: true,
  notificationSent: true
}
```

---

### Analytics API

#### `GET /api/calls/analytics/overview`
```typescript
// Query Params
?startDate=2026-01-01&endDate=2026-01-31&agentId=agt_xyz789

// Response
{
  period: {
    start: "2026-01-01",
    end: "2026-01-31"
  },
  totals: {
    calls: 1247,
    successful: 1114,
    escalated: 133,
    failed: 0,
    successRate: 0.893,
    escalationRate: 0.107
  },
  timeSaved: {
    totalMinutes: 3744,
    totalHours: 62.4,
    costSavings: 1560 // $25/hr * 62.4
  },
  comparison: {
    vs PreviousPeriod: {
      callsChange: 0.23, // +23%
      successRateChange: 0.052 // +5.2%
    }
  }
}
```

#### `GET /api/calls/analytics/trends`
```typescript
// Response
{
  dailyVolume: [
    { date: "2026-01-01", calls: 38, successful: 34, escalated: 4 },
    { date: "2026-01-02", calls: 42, successful: 39, escalated: 3 },
    // ...
  ],
  hourlyDistribution: [
    { hour: 9, averageCalls: 45 },
    { hour: 10, averageCalls: 38 },
    // ...
  ]
}
```

#### `GET /api/calls/analytics/intents`
```typescript
// Response
{
  intents: [
    {
      intent: "appointment_booking",
      count: 773,
      percentage: 0.62,
      avgDuration: 185, // seconds
      successRate: 0.94
    },
    {
      intent: "rescheduling",
      count: 224,
      percentage: 0.18,
      avgDuration: 142,
      successRate: 0.91
    },
    // ...
  ]
}
```

#### `GET /api/calls/analytics/performance`
```typescript
// Response
{
  agents: [
    {
      agentId: "agt_xyz789",
      agentName: "Main Receptionist",
      stats: {
        calls: 1124,
        successRate: 0.912,
        avgHandleTime: 192,
        avgQualityScore: 4.7,
        avgSatisfaction: 4.8
      }
    },
    // ...
  ],
  metrics: {
    avgWaitTime: 0, // seconds
    avgHandleTime: 192,
    firstCallResolution: 0.89
  }
}
```

---

## 🎬 Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
**Goal:** Basic infrastructure and data models

**Backend:**
- [ ] Create new Prisma models (PhoneNumber, AgentConfig, enhance CallRecord)
- [ ] Run migration
- [ ] Create `phone-numbers` module in NestJS
- [ ] Create `agents` module in NestJS
- [ ] Create `calls` module in NestJS

**Frontend:**
- [ ] Create `/dashboard/automation` route structure
- [ ] Build empty state page with "Get Started" wizard
- [ ] Create reusable components (StatusBadge, AgentCard, CallCard)

**Testing:**
- [ ] Verify database migrations
- [ ] Test API endpoints with Postman
- [ ] Smoke test frontend routes

---

### Phase 2: Phone Number Management (Week 3-4)
**Goal:** Phone number purchasing and configuration

**Backend:**
- [ ] Implement Twilio integration
  - [ ] Search available numbers
  - [ ] Purchase number
  - [ ] Configure webhooks
- [ ] Implement number porting workflow
- [ ] Create SIP trunk configuration
- [ ] Phone number CRUD APIs

**Frontend:**
- [ ] Phone numbers list page
- [ ] "Buy Number" wizard (3 steps)
- [ ] "Port Number" wizard (5 steps)
- [ ] Number configuration modal
- [ ] Number status dashboard

**Testing:**
- [ ] Test number purchase flow (Twilio sandbox)
- [ ] Verify webhook configuration
- [ ] Test number activation/deactivation

---

### Phase 3: Agent Management (Week 5-6)
**Goal:** Agent creation, configuration, and activation

**Backend:**
- [ ] Enhance existing Retell service
- [ ] Agent creation API
- [ ] Agent configuration API
- [ ] Agent activation/deactivation
- [ ] Agent status polling

**AI Service (FastAPI):**
- [ ] Enhance existing `/ws/retell` endpoint
- [ ] Add agent ID to WebSocket context
- [ ] Store agent configuration in DB
- [ ] Implement working hours logic

**Frontend:**
- [ ] Agents list page
- [ ] "Create Agent" wizard
- [ ] Agent configuration modal
  - Working hours editor
  - Voice selection
  - Custom instructions
- [ ] Agent status indicators (real-time)
- [ ] Test agent dialog

**Testing:**
- [ ] Create test agent
- [ ] Activate agent
- [ ] Simulate call (Retell test mode)
- [ ] Verify agent responds correctly

---

### Phase 4: Call Monitoring & History (Week 7-8)
**Goal:** Real-time call monitoring and historical logs

**Backend:**
- [ ] Enhance CallRecord storage
- [ ] Store transcript and tool invocations
- [ ] Store call analysis (intent, outcome)
- [ ] Call query APIs (filtering, pagination)
- [ ] Call detail API

**Frontend:**
- [ ] Main dashboard with live call stream
- [ ] Call history page with filters
- [ ] Call detail page
  - Full transcript view
  - Tool invocations timeline
  - Approval actions
  - Recording player
- [ ] Real-time status updates (WebSocket or polling)

**Testing:**
- [ ] Make test calls
- [ ] Verify transcript storage
- [ ] Test approval workflow
- [ ] Verify recording playback

---

### Phase 5: Analytics & Reporting (Week 9-10)
**Goal:** Insights and performance metrics

**Backend:**
- [ ] Analytics aggregation queries
- [ ] Time-series data for trends
- [ ] Agent performance metrics
- [ ] Cost savings calculations

**Frontend:**
- [ ] Analytics dashboard page
  - Overview stats
  - Call volume charts
  - Intent distribution
  - Agent performance
- [ ] Date range selector
- [ ] Export functionality (CSV)

**Testing:**
- [ ] Generate sample data
- [ ] Verify chart accuracy
- [ ] Test date filtering
- [ ] Validate calculations

---

### Phase 6: Approvals Integration (Week 11-12)
**Goal:** Connect AI actions to approval workflow

**Backend:**
- [ ] Enhance approval creation from AI calls
- [ ] Link approvals to call records
- [ ] Notification system (email/SMS)
- [ ] Bulk approval actions

**Frontend:**
- [ ] Approval panel in call detail
- [ ] Approve/reject from call history
- [ ] Approval notifications
- [ ] Approval history view

**Testing:**
- [ ] Test appointment booking approval
- [ ] Test rescheduling approval
- [ ] Test rejection flow
- [ ] Verify notifications

---

### Phase 7: Advanced Features (Week 13-14)
**Goal:** Polish and advanced capabilities

**Features:**
- [ ] **SMS Integration** (send appointment confirmations)
- [ ] **After-Hours Mode** (automatic agent switching)
- [ ] **Call Recording Playback** (embedded player)
- [ ] **Call Quality Scoring** (AI-powered analysis)
- [ ] **Transfer to Human** (live transfer capability)
- [ ] **Custom Agent Training** (fine-tune prompts)
- [ ] **Multi-language Support** (Spanish, etc.)
- [ ] **Voice Cloning** (custom practice voice)

---

### Phase 8: Production Readiness (Week 15-16)
**Goal:** Security, compliance, performance

**Tasks:**
- [ ] Security audit (API authentication, rate limiting)
- [ ] HIPAA compliance review (audit logging, encryption)
- [ ] Performance optimization (query optimization, caching)
- [ ] Error handling and logging
- [ ] Documentation (user guide, API docs)
- [ ] Load testing (simulate high call volume)
- [ ] Monitoring and alerts (call failures, agent errors)

---

## 📝 Implementation Checklist

### Database (Prisma)
- [ ] Create `PhoneNumber` model
- [ ] Create `AgentConfig` model
- [ ] Enhance `CallRecord` model with new fields
- [ ] Create migration
- [ ] Seed sample data for development

### Backend (NestJS)
#### PhoneNumbers Module
- [ ] `phone-numbers.controller.ts`
- [ ] `phone-numbers.service.ts`
- [ ] `twilio.service.ts` (integration)
- [ ] DTOs (CreatePhoneNumberDto, UpdatePhoneNumberDto)

#### Agents Module
- [ ] `agents.controller.ts`
- [ ] `agents.service.ts`
- [ ] `agent-orchestrator.service.ts` (manages agent lifecycle)
- [ ] DTOs (CreateAgentDto, UpdateAgentDto, ActivateAgentDto)

#### Calls Module
- [ ] `calls.controller.ts`
- [ ] `calls.service.ts`
- [ ] `call-analytics.service.ts`
- [ ] DTOs (CallQueryDto, ApproveCallActionDto)

### AI Service (FastAPI)
- [ ] Enhance `retell_service.py` with agent config
- [ ] Add working hours logic
- [ ] Implement agent-specific prompts
- [ ] Store call analysis in CallRecord

### Frontend (Next.js)
#### Pages
- [ ] `/dashboard/automation/page.tsx`
- [ ] `/dashboard/automation/phone-numbers/page.tsx`
- [ ] `/dashboard/automation/phone-numbers/new/page.tsx`
- [ ] `/dashboard/automation/agents/page.tsx`
- [ ] `/dashboard/automation/agents/new/page.tsx`
- [ ] `/dashboard/automation/agents/[id]/page.tsx`
- [ ] `/dashboard/automation/calls/page.tsx`
- [ ] `/dashboard/automation/calls/[id]/page.tsx`
- [ ] `/dashboard/automation/analytics/page.tsx`

#### Components
- [ ] `PhoneNumberCard.tsx`
- [ ] `BuyNumberWizard.tsx`
- [ ] `PortNumberWizard.tsx`
- [ ] `AgentCard.tsx`
- [ ] `AgentConfigModal.tsx`
- [ ] `AgentStatusBadge.tsx`
- [ ] `CallCard.tsx`
- [ ] `CallTranscript.tsx`
- [ ] `CallTimeline.tsx`
- [ ] `AnalyticsChart.tsx`

#### API Hooks (React Query)
- [ ] `usePhoneNumbers()`
- [ ] `usePurchaseNumber()`
- [ ] `useAgents()`
- [ ] `useCreateAgent()`
- [ ] `useActivateAgent()`
- [ ] `useCalls()`
- [ ] `useCallDetail()`
- [ ] `useCallAnalytics()`

---

## 🚀 Quick Start Commands

### 1. Create New Branch
```bash
git checkout -b feature/automation-hub
```

### 2. Generate Prisma Migration
```bash
cd apps/backend
npx prisma migrate dev --name add_automation_hub_tables
```

### 3. Generate Backend Modules
```bash
cd apps/backend
nest g module phone-numbers
nest g controller phone-numbers
nest g service phone-numbers

nest g module agents
nest g controller agents
nest g service agents

nest g module calls
nest g controller calls
nest g service calls
```

### 4. Create Frontend Routes
```bash
cd apps/web/src/app/dashboard
mkdir -p automation/{phone-numbers,agents,calls,analytics}
```

### 5. Install Dependencies (if needed)
```bash
# Twilio SDK
npm install twilio --workspace apps/backend

# Chart library (for analytics)
npm install recharts --workspace apps/web
```

---

## ✅ Success Criteria

### MVP (Minimum Viable Product)
- [ ] Clinic can add at least one phone number
- [ ] Clinic can create and activate one AI agent
- [ ] Agent can handle incoming calls
- [ ] Agent can book appointments (with approval)
- [ ] Clinic can see call history with transcripts
- [ ] Staff can approve/reject AI actions from UI

### V1.0 (Full Release)
- [ ] Support multiple phone numbers per clinic
- [ ] Support multiple agents with different types
- [ ] Working hours configuration per agent
- [ ] Real-time call status monitoring
- [ ] Complete analytics dashboard
- [ ] SMS notifications for approvals
- [ ] Call recording playback
- [ ] After-hours agent auto-switching

### V2.0 (Future Enhancements)
- [ ] Multi-language support
- [ ] Voice cloning (custom practice voice)
- [ ] AI training interface
- [ ] Advanced analytics (cohort analysis)
- [ ] Outbound calling (reminders, follow-ups)
- [ ] Video call support
- [ ] Integration with EHR systems

---

## 📚 Related Documentation

- [V2_COMPREHENSIVE_FEATURE_SPEC.md](./V2_COMPREHENSIVE_FEATURE_SPEC.md) - Overall system spec
- [IMPLEMENTATION_CHECKLIST.md](./IMPLEMENTATION_CHECKLIST.md) - Main implementation tracker
- [DATA_FLOW_ARCHITECTURE.md](./DATA_FLOW_ARCHITECTURE.md) - System architecture
- [plan.txt](../plan.txt) - Original project plan

---

**Next Steps:**
1. ✅ Review this spec with the team
2. Create detailed tasks in project management tool
3. Start Phase 1: Database migrations
4. Build empty state UI
5. Implement phone number purchasing
6. Launch MVP to beta testers

---

**End of Specification**
