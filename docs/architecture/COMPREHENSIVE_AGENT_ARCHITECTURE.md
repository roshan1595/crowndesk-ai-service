# CrownDesk V2 - Comprehensive Agent Architecture

**Date:** January 21, 2026  
**Purpose:** Define complete agent system supporting both voice agents and automation agents

---

## Agent Type Classification

### 1. Voice/Phone Agents (Retell AI Integration)
**Purpose:** Handle phone calls with patients  
**Technology:** Retell AI WebSocket + OpenAI  
**Requirements:** Phone number assignment, voice configuration

| Agent Type | Primary Function | Use Cases |
|------------|------------------|-----------|
| **VOICE_RECEPTIONIST** | Main phone line | Appointment booking, patient inquiries, call routing |
| **VOICE_SCHEDULER** | Appointment management | Rescheduling, cancellations, confirmations |
| **VOICE_EMERGENCY** | After-hours triage | Emergency assessment, on-call routing |
| **VOICE_FOLLOWUP** | Patient outreach | Post-treatment calls, reminder calls |

**Key Features:**
- Phone number assignment
- Voice ID selection (ElevenLabs)
- Working hours configuration
- Transfer number capability
- Call recording & transcription
- Real-time call status

---

### 2. Automation/Backend Agents (Internal Processing)
**Purpose:** Automate staff workflows and data processing  
**Technology:** FastAPI + OpenAI/Claude + LangChain  
**Requirements:** No phone number, API access only

| Agent Type | Primary Function | Use Cases |
|------------|------------------|-----------|
| **INSURANCE_VERIFIER** | Real-time eligibility checks | Auto-verify insurance before appointments, batch verification |
| **CLAIMS_PROCESSOR** | 837D submission & tracking | Pre-submit validation, claim scrubbing, denial analysis |
| **CODING_ASSISTANT** | CDT code suggestions | Parse clinical notes, suggest codes with evidence, billing optimization |
| **BILLING_AUTOMATOR** | Invoice generation & follow-up | Auto-create invoices from completed procedures, payment posting |
| **TREATMENT_PLANNER** | Treatment plan optimization | Suggest treatment sequences, estimate insurance coverage |
| **DENIAL_ANALYZER** | Claim denial resolution | Analyze denial reasons, suggest corrections, auto-appeal drafts |
| **PAYMENT_COLLECTOR** | AR follow-up | Identify overdue accounts, generate patient statements, payment plan suggestions |
| **APPOINTMENT_OPTIMIZER** | Schedule optimization | Fill cancellations, suggest recall appointments, provider utilization |

**Key Features:**
- Scheduled execution (cron)
- Event-driven triggers
- Batch processing capabilities
- Approval workflow integration
- Confidence scoring
- Evidence tracking

---

## Database Schema Updates

### AgentConfig Model Enhancement

```prisma
enum AgentCategory {
  VOICE        // Phone-based agents (Retell AI)
  AUTOMATION   // Backend automation agents
}

enum AgentType {
  // Voice Agents
  VOICE_RECEPTIONIST
  VOICE_SCHEDULER
  VOICE_EMERGENCY
  VOICE_FOLLOWUP
  
  // Automation Agents
  INSURANCE_VERIFIER
  CLAIMS_PROCESSOR
  CODING_ASSISTANT
  BILLING_AUTOMATOR
  TREATMENT_PLANNER
  DENIAL_ANALYZER
  PAYMENT_COLLECTOR
  APPOINTMENT_OPTIMIZER
  
  // Custom
  CUSTOM
}

model AgentConfig {
  id String @id @default(dbgenerated("uuid_generate_v4()")) @db.Uuid
  tenantId String @map("tenant_id") @db.Uuid
  
  // Basic Info
  agentName String @map("agent_name")
  agentCategory AgentCategory @map("agent_category") // NEW
  agentType AgentType @map("agent_type")
  status AgentStatus
  
  // Voice-specific (nullable for automation agents)
  retellAgentId String? @map("retell_agent_id")
  voiceId String? @map("voice_id")
  language String? @default("en-US")
  workingHours Json? @map("working_hours")
  transferNumber String? @map("transfer_number")
  
  // Automation-specific (nullable for voice agents)
  executionSchedule String? @map("execution_schedule") // Cron expression
  batchSize Int? @map("batch_size") // For batch processing
  priority Int? @default(5) // 1-10 priority level
  
  // Common fields
  customPrompt String? @map("custom_prompt") @db.Text
  beginMessage String? @map("begin_message") @db.Text
  requireApproval Boolean @default(true) @map("require_approval")
  maxCallDuration Int? @map("max_call_duration")
  
  // Relations
  phoneNumbers PhoneNumber[]
  callRecords CallRecord[]
  automationRuns AutomationRun[] // NEW
  
  @@index([tenantId])
  @@index([agentCategory, status])
  @@map("agent_configs")
}

// New model for tracking automation agent executions
model AutomationRun {
  id String @id @default(dbgenerated("uuid_generate_v4()")) @db.Uuid
  tenantId String @map("tenant_id") @db.Uuid
  agentConfigId String @map("agent_config_id") @db.Uuid
  
  status AutomationRunStatus
  startedAt DateTime @map("started_at")
  completedAt DateTime? @map("completed_at")
  
  itemsProcessed Int @default(0) @map("items_processed")
  itemsSucceeded Int @default(0) @map("items_succeeded")
  itemsFailed Int @default(0) @map("items_failed")
  
  error String? @db.Text
  logs Json? // Detailed execution logs
  
  // Relations
  tenant Tenant @relation(fields: [tenantId], references: [id], onDelete: Cascade)
  agentConfig AgentConfig @relation(fields: [agentConfigId], references: [id], onDelete: Cascade)
  
  @@index([tenantId, agentConfigId])
  @@index([status, startedAt])
  @@map("automation_runs")
}

enum AutomationRunStatus {
  running
  completed
  failed
  cancelled
}
```

---

## API Endpoints

### Voice Agent Operations (Existing)
- `POST /api/agents` - Create voice agent
- `PUT /api/agents/:id` - Update voice agent
- `POST /api/agents/:id/activate` - Activate voice agent
- `POST /api/agents/:id/deactivate` - Deactivate voice agent

### Automation Agent Operations (NEW)
- `POST /api/automation-agents` - Create automation agent
- `PUT /api/automation-agents/:id` - Update automation agent
- `POST /api/automation-agents/:id/trigger` - Manually trigger execution
- `GET /api/automation-agents/:id/runs` - Get execution history
- `GET /api/automation-agents/:id/runs/:runId` - Get run details
- `POST /api/automation-agents/:id/pause` - Pause scheduled runs
- `POST /api/automation-agents/:id/resume` - Resume scheduled runs

### Common Agent Operations
- `GET /api/agents` - List all agents (filter by category)
- `GET /api/agents/:id` - Get agent details
- `DELETE /api/agents/:id` - Delete agent
- `GET /api/agents/stats` - Get statistics

---

## Frontend Integration Plan

### 1. Update Sidebar Navigation

```typescript
// Current: "Agent Management"
// New structure:

Automation Hub
├── Overview (dashboard)
├── Voice Agents (phone/call handling)
│   ├── Phone Numbers
│   ├── Call History
│   └── Analytics
└── Automation Agents (backend tasks)
    ├── Insurance Verification
    ├── Claims Processing
    ├── Coding & Billing
    └── Execution History
```

### 2. Main Automation Hub Page

Shows unified view:
- Voice agents stats (active calls, today's calls)
- Automation agents stats (running tasks, completed today)
- Quick actions (trigger verification, process claims)
- Recent activity timeline

### 3. Voice Agents Section (Existing Pages)

Keep current implementation:
- `/dashboard/automation/voice/phone-numbers`
- `/dashboard/automation/voice/agents`
- `/dashboard/automation/voice/calls`
- `/dashboard/automation/voice/analytics`

### 4. Automation Agents Section (NEW Pages)

Create new pages:
- `/dashboard/automation/backend/agents` - List automation agents
- `/dashboard/automation/backend/runs` - Execution history
- `/dashboard/automation/backend/analytics` - Performance metrics

---

## Component Updates Needed

### 1. AgentCard Component
**Update to support both types:**

```typescript
interface AgentCardProps {
  agent: {
    id: string;
    agentName: string;
    agentCategory: 'VOICE' | 'AUTOMATION';
    agentType: string;
    status: string;
    
    // Voice-specific
    phoneNumbers?: PhoneNumber[];
    totalCalls?: number;
    
    // Automation-specific
    executionSchedule?: string;
    lastRunAt?: Date;
    successRate?: number;
  };
}

// Show different metrics based on category
```

### 2. AgentConfigModal Component
**Update to support agent category selection:**

```typescript
// Step 1: Choose category (Voice or Automation)
// Step 2: Choose type (based on category)
// Step 3-5: Configure (different fields based on category)

// Voice agents: show voice, phone, working hours
// Automation agents: show schedule, batch size, priority
```

### 3. New: AutomationRunCard Component
Display execution history:
- Run status (running/completed/failed)
- Items processed/succeeded/failed
- Duration
- Error details (if failed)

---

## Example Use Cases

### Voice Agent: Receptionist
```
Agent: VOICE_RECEPTIONIST
Phone: +1 (555) 123-4567
Working Hours: Mon-Fri 8am-6pm

Capabilities:
- Answer incoming calls
- Book appointments via approval workflow
- Transfer to staff when needed
- Capture patient information
- Provide general practice info
```

### Automation Agent: Insurance Verifier
```
Agent: INSURANCE_VERIFIER
Schedule: Every day at 6am (0 6 * * *)
Batch Size: 50 patients

Capabilities:
- Query today's appointments
- Check insurance eligibility (270/271)
- Flag missing/invalid insurance
- Create approval requests for new policies
- Email staff with verification report
```

### Automation Agent: Claims Processor
```
Agent: CLAIMS_PROCESSOR
Schedule: Every weekday at 8pm (0 20 * * 1-5)

Capabilities:
- Find completed procedures without claims
- Build 837D claim drafts
- Run claim scrubbing rules
- Create approval requests for submission
- Track submission success rate
```

### Automation Agent: Coding Assistant
```
Agent: CODING_ASSISTANT
Trigger: Event-driven (appointment.completed)

Capabilities:
- Parse clinical notes from PMS
- Extract treatment details
- Suggest CDT codes with confidence
- Attach evidence from knowledge base
- Create approval for code assignment
```

---

## Implementation Priority

### Phase 1: Voice Agents (CURRENT - 95% Complete)
- ✅ Database models
- ✅ Backend APIs (23 endpoints)
- ✅ Frontend components (10 components)
- 🔄 Page integration (needed)

### Phase 2: Automation Infrastructure (NEXT)
1. Add `agentCategory` field to schema
2. Create AutomationRun model
3. Build automation agent APIs
4. Create execution scheduler service
5. Build automation run tracking

### Phase 3: Specific Automation Agents
1. **Insurance Verifier** (easiest)
   - Uses existing Stedi integration
   - Query patients, call eligibility API
   - Store results, create alerts

2. **Coding Assistant** (medium)
   - Uses existing AI service
   - Parse notes, suggest codes
   - Create approvals for review

3. **Claims Processor** (complex)
   - Uses existing claims module
   - Find unbilled procedures
   - Generate 837D drafts
   - Submit with approval

4. **Billing Automator** (medium)
   - Uses existing billing module
   - Create invoices from completed procedures
   - Post insurance payments from 835
   - Generate patient statements

---

## Next Immediate Steps

1. **Add `agentCategory` enum to schema** (2 min)
2. **Update AgentType enum with automation types** (5 min)
3. **Generate and apply migration** (5 min)
4. **Update AgentConfigModal to support category selection** (30 min)
5. **Update pages to filter by category** (20 min)
6. **Create automation agents section** (later)

Would you like me to proceed with these updates?
