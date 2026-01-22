# Complete PMS Sync Architecture - CrownDesk V2

## Date: January 20, 2026

## Executive Summary
This document outlines ALL entities that must be synced between Open Dental (PMS) and CrownDesk for a complete, cohesive dental practice workflow.

---

## Workflow Context

### The Complete Dental Practice Workflow:
1. **Patient arrives** → Front desk checks them in
2. **Doctor examines** → Creates/updates treatment plan
3. **Treatment delivered** → Doctor completes procedures in Open Dental
4. **Billing happens** → Procedures → Claims → Insurance/Patient payments
5. **Follow-up** → Next appointment scheduled

### CrownDesk's Role:
- **Read** everything from Open Dental (system of record)
- **Augment** with AI insights, automation, and intelligence
- **Write back** only with human approval (Phase 2)

---

## Entity Sync Status Matrix

| # | Entity | Priority | Status | Fetch Method | Sync Method | Database Model | Notes |
|---|--------|----------|--------|--------------|-------------|----------------|-------|
| 1 | **Patients** | P0 | ✅ DONE | fetchPatients() | syncPatientsFromPms() | Patient | Core entity |
| 2 | **Families** | P0 | ❌ TODO | ❌ Not implemented | ❌ Missing | Family | Family billing/accounts |
| 3 | **Providers** | P0 | ✅ DONE | fetchProviders() | syncProvidersFromPms() | Provider | Just implemented |
| 4 | **Operatories** | P0 | ✅ DONE | fetchOperatories() | syncOperatoriesFromPms() | Operatory | Just implemented |
| 5 | **Appointments** | P0 | ✅ DONE | fetchAppointments() | syncAppointmentsFromPms() | Appointment | Core scheduling |
| 6 | **Procedure Codes** | P0 | ⚠️ PARTIAL | fetchProcedureCodes() | ❌ Missing | ProcedureCode | CDT codes, fees |
| 7 | **Completed Procedures** | P0 | ✅ DONE | fetchProcedures() | syncProceduresFromPms() | CompletedProcedure | Critical for billing |
| 8 | **Treatment Plans** | P1 | ⚠️ PARTIAL | fetchTreatmentPlans() | ❌ Missing | TreatmentPlan | Future treatments |
| 9 | **Insurance Plans** | P0 | ⚠️ PARTIAL | fetchInsurancePlans() | syncInsuranceFromPms() | InsurancePolicy | Partial implementation |
| 10 | **Insurance Subscribers** | P0 | ⚠️ PARTIAL | fetchInsuranceSubscriptions() | ❌ Partial | InsurancePolicy | Link patients to plans |
| 11 | **Benefits** | P1 | ⚠️ PARTIAL | fetchBenefits() | ❌ Missing | InsurancePolicy.coverageDetails | Coverage %s, limits |
| 12 | **Payments** | P1 | ❌ TODO | ❌ Not implemented | ❌ Missing | Payment | Payment history |
| 13 | **Adjustments** | P2 | ❌ TODO | ❌ Not implemented | ❌ Missing | Payment? | Write-offs, discounts |
| 14 | **Referral Sources** | P2 | ❌ TODO | ❌ Not implemented | ❌ Missing | N/A | Marketing tracking |
| 15 | **Fee Schedules** | P1 | ❌ TODO | ❌ Not implemented | ❌ Missing | ProcedureCode | Practice-specific fees |

---

## Critical Missing Entities (Must Implement)

### 1. Family Accounts (P0 - CRITICAL)
**Why**: Family billing is core to dental practices. Grandparent pays for grandkids, parents pay for kids, etc.

**Open Dental Structure:**
- `patient.Guarantor` field → Points to family billing account holder
- `patient.FamNum` → Family number grouping

**What We Need:**
```typescript
// Prisma model already exists!
model Family {
  id           String   @id @default(uuid)
  tenantId     String
  guarantorId  String   // Primary account holder (bill payer)
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt
  
  // Relations
  tenant       Tenant   @relation(...)
  guarantor    Patient  @relation("FamilyGuarantor", ...)
  members      Patient[] @relation("FamilyMembers")
  // ...
}

// Patient model needs:
model Patient {
  // ...
  familyId      String?  
  guarantorId   String?  // Who pays this patient's bills
  // ...
}
```

**Implementation:**
- `fetchFamilies()` - Group patients by FamNum from Open Dental
- `syncFamiliesFromPms()` - Create Family records, link patients
- UI: Show family members in patient detail
- UI: Combined family billing ledger

---

### 2. Procedure Codes Sync (P0 - CRITICAL)
**Why**: Without CDT codes in database, we can't:
- Validate procedure entries
- Show procedure descriptions
- Calculate insurance coverage
- Generate claims with proper codes

**Current Status**: 
- ✅ `fetchProcedureCodes()` exists in adapter
- ✅ `ProcedureCode` model exists in database
- ❌ No sync service method
- ❌ Codes not being populated

**What We Need:**
```typescript
async syncProcedureCodesFromPms(tenantId: string): Promise<SyncResult> {
  const codes = await this.openDental.fetchProcedureCodes();
  
  for (const code of codes) {
    await this.prisma.procedureCode.upsert({
      where: { tenantId_code: { tenantId, code: code.code } },
      create: {
        tenantId,
        code: code.code,          // D0120, D1110, etc.
        category: mapCategory(code.category),
        description: code.description,
        abbreviation: code.abbreviation,
        defaultFee: code.defaultFee,
        typicalDuration: parseTime(code.procTime),
        isActive: true,
      },
      update: { /* update fields */ }
    });
  }
}
```

**Add to fullSync():**
```typescript
const results = {
  procedureCodes: await this.syncProcedureCodesFromPms(tenantId), // NEW
  providers: await this.syncProvidersFromPms(tenantId),
  operatories: await this.syncOperatoriesFromPms(tenantId),
  // ...
}
```

---

### 3. Treatment Plans Sync (P1 - HIGH)
**Why**: Treatment plans are the bridge between diagnosis and treatment
- Shows what needs to be done
- Estimates costs
- Tracks which treatments are completed
- Critical for case acceptance

**Current Status:**
- ✅ `fetchTreatmentPlans()` exists
- ✅ `TreatmentPlan`, `TreatmentPhase`, `PlannedProcedure` models exist
- ❌ No sync service method

**What We Need:**
```typescript
async syncTreatmentPlansFromPms(tenantId: string): Promise<SyncResult> {
  const plans = await this.openDental.fetchTreatmentPlans();
  
  for (const plan of plans) {
    // Find patient mapping
    const patientMapping = await this.findPatientMapping(plan.patientPmsId);
    
    // Upsert treatment plan
    const treatmentPlan = await this.prisma.treatmentPlan.upsert({
      where: { /* composite key */ },
      create: {
        tenantId,
        patientId: patientMapping.crownDeskId,
        pmsTreatmentPlanId: plan.pmsId,
        name: plan.heading || 'Treatment Plan',
        status: mapStatus(plan.status),
        // ...
      },
      update: { /* ... */ }
    });
    
    // Sync procedures in the plan
    for (const proc of plan.procedures) {
      await this.prisma.plannedProcedure.upsert({
        // Link to treatment plan
        // Include CDT code, fee, tooth numbers
      });
    }
  }
}
```

---

### 4. Enhanced Insurance Sync (P0 - CRITICAL)
**Current Issue**: Insurance sync is partial - not linking subscribers properly

**What's Missing:**
```typescript
// After syncing plans, sync subscribers (patient-to-plan links)
async syncInsuranceSubscribersFromPms(tenantId: string) {
  const subscriptions = await this.openDental.fetchInsuranceSubscriptions();
  
  for (const sub of subscriptions) {
    // Link patient → insurance plan
    // Store subscriber relationship (self, spouse, child)
    // Track effective/termination dates
  }
}

// Sync benefit details (coverage percentages, limits)
async syncBenefitsFromPms(tenantId: string) {
  const plans = await this.prisma.insurancePolicy.findMany({ where: { tenantId }});
  
  for (const plan of plans) {
    const benefits = await this.openDental.fetchBenefits(plan.pmsInsurancePlanId);
    
    // Update plan with:
    // - Preventive coverage % (usually 100%)
    // - Basic coverage % (usually 80%)
    // - Major coverage % (usually 50%)
    // - Annual maximum
    // - Deductibles
    // - Frequency limitations
  }
}
```

---

### 5. Payment History Sync (P1 - HIGH)
**Why**: Knowing payment history is critical for:
- Patient ledger accuracy
- AR aging calculations
- Collections workflows
- Financial reporting

**What We Need:**
```typescript
interface PmsPayment {
  pmsId: string;
  patientPmsId: string;
  amount: number;
  paymentDate: Date;
  paymentType: string;  // cash, check, card, insurance
  checkNumber?: string;
  appliedToProcedures: Array<{
    procPmsId: string;
    amount: number;
  }>;
}

async fetchPayments(since?: Date): Promise<PmsPayment[]> {
  // Query Open Dental payment table
}

async syncPaymentsFromPms(tenantId: string): Promise<SyncResult> {
  // Create Payment records
  // Link to patients
  // Link to completed procedures
  // Update procedure.billingStatus
}
```

---

### 6. Fee Schedules (P1 - HIGH)
**Why**: Different patients have different fee schedules
- Cash patients: Standard fees
- PPO patients: Negotiated fees
- Medicaid: Government fees

**What We Need:**
```typescript
model FeeSchedule {
  id           String   @id @default(uuid)
  tenantId     String
  name         String   // "Standard", "PPO - Delta", "Medicaid"
  isDefault    Boolean  @default(false)
  
  fees         FeeScheduleEntry[]
}

model FeeScheduleEntry {
  id             String   @id @default(uuid)
  feeScheduleId  String
  procedureCodeId String
  fee            Float
  
  feeSchedule    FeeSchedule @relation(...)
  procedureCode  ProcedureCode @relation(...)
}
```

---

## Sync Priority Order (What to Build Next)

### Phase 1: Critical Gaps (This Week)
1. ✅ **Stop backend server, regenerate Prisma client** (fixes TypeScript errors)
2. 🔄 **Procedure Codes Sync** - `syncProcedureCodesFromPms()`
   - Without this, completed procedures have no descriptions
   - Critical for claims and billing
3. 🔄 **Family Accounts Sync** - `syncFamiliesFromPms()`
   - Core to dental billing workflow
   - Many practices bill by family

### Phase 2: Treatment Workflow (Next Week)
4. **Treatment Plans Sync** - `syncTreatmentPlansFromPms()`
   - Shows what's planned vs. completed
   - Important for case tracking
5. **Enhanced Insurance Sync** - `syncBenefitsFromPms()`
   - Proper coverage percentages
   - Limits and deductibles

### Phase 3: Financial Workflow (Week 3)
6. **Payment History Sync** - `syncPaymentsFromPms()`
   - Complete financial picture
   - AR aging accuracy
7. **Fee Schedules** - `syncFeeSchedulesFromPms()`
   - Accurate fee calculations
   - Insurance estimate accuracy

---

## Implementation Checklist

### Immediate Actions (Today):
- [ ] Stop backend dev server
- [ ] Run `npx prisma generate` in apps/backend
- [ ] Restart dev server
- [ ] Test current sync works (providers, operatories, procedures show up)

### This Week:
- [ ] Implement `syncProcedureCodesFromPms()`
  - [ ] Add method to pms-sync.service.ts
  - [ ] Add to fullSync() call
  - [ ] Add to triggerSync() switch
  - [ ] Test: POST /pms-sync/full-sync
  - [ ] Verify: Procedure codes appear in database
  
- [ ] Implement `syncFamiliesFromPms()`
  - [ ] Add `fetchFamilies()` to adapter
  - [ ] Add family sync method
  - [ ] Update patient records with familyId
  - [ ] Test family grouping in UI

### Next Week:
- [ ] Implement `syncTreatmentPlansFromPms()`
- [ ] Enhance `syncInsuranceFromPms()` with benefits
- [ ] Create UI for treatment plans
- [ ] Create UI for family billing

---

## Data Dependencies Graph

```
┌─────────────────┐
│ Procedure Codes │ ← Must sync FIRST (referenced by everything)
└────────┬────────┘
         │
         ├──────────────┬──────────────┬──────────────┐
         ▼              ▼              ▼              ▼
    ┌────────┐    ┌──────────┐   ┌─────────────┐  ┌────────────┐
    │Patients│    │Providers │   │Operatories  │  │ Insurance  │
    └───┬────┘    └────┬─────┘   └─────┬───────┘  │   Plans    │
        │              │               │           └──────┬─────┘
        │              │               │                  │
        ├──────────────┼───────────────┼──────────────────┤
        ▼              ▼               ▼                  ▼
    ┌──────────────────────────────────────────────────────┐
    │              Appointments                            │
    └──────────────────────────────────────────────────────┘
        │
        ├──────────────────────┬────────────────────┐
        ▼                      ▼                    ▼
    ┌──────────────┐   ┌──────────────────┐  ┌─────────────┐
    │  Treatment   │   │   Completed      │  │   Families  │
    │    Plans     │   │   Procedures     │  │             │
    └──────────────┘   └────────┬─────────┘  └─────────────┘
                                │
                                ├──────────────┬──────────────┐
                                ▼              ▼              ▼
                            ┌────────┐    ┌────────┐    ┌──────────┐
                            │ Claims │    │Invoices│    │ Payments │
                            └────────┘    └────────┘    └──────────┘
```

---

## Testing Strategy

### Unit Tests:
- Mock Open Dental API responses
- Test each sync method independently
- Verify data transformation logic

### Integration Tests:
1. **Fresh Database Test**:
   - Empty database
   - Run full sync
   - Verify all entities created
   - Check relationships intact

2. **Update Test**:
   - Run sync twice
   - Verify updates work
   - Check no duplicates created

3. **Workflow Test**:
   - Patient synced → Appointment synced → Procedure synced → Claim created
   - End-to-end data flow

### Manual Testing Checklist:
```bash
# 1. Trigger full sync
POST /api/pms-sync/full-sync

# 2. Check each entity count
GET /api/patients        # Should show patients
GET /api/appointments    # Should show appointments
GET /api/completed-procedures  # Should show procedures
GET /api/procedure-codes # Should show CDT codes

# 3. Check UI pages
/dashboard/patients
/dashboard/appointments
/dashboard/completed-procedures
/dashboard/insurance

# 4. Verify relationships
- Click patient → see their appointments
- Click appointment → see linked procedures
- Click procedure → see CDT code description
```

---

## Success Metrics

### Week 1 Goals:
- ✅ Procedure codes: 500+ CDT codes in database
- ✅ Families: All patients linked to families
- ✅ Completed procedures: Show proper descriptions from CDT codes

### Week 2 Goals:
- ✅ Treatment plans: Planned procedures viewable
- ✅ Insurance: Coverage percentages accurate
- ✅ UI: Treatment plan page functional

### Week 3 Goals:
- ✅ Payments: Full financial history
- ✅ AR Aging: Accurate calculations
- ✅ Fee schedules: Multiple schedules supported

---

## Open Questions

1. **Frequency**: How often should each entity sync?
   - Procedure codes: Daily (rarely change)
   - Patients: Every 5 minutes (active changes)
   - Appointments: Every 2 minutes (real-time critical)
   - Completed procedures: Every 5 minutes (billing critical)
   - Treatment plans: Every 15 minutes (less urgent)

2. **Conflict Resolution**: What if data changes in both systems?
   - Rule: PMS always wins (it's the system of record)
   - Log conflicts in Approval table for review

3. **Performance**: With large practices (10,000+ patients)?
   - Use watermarks (already implemented)
   - Batch inserts (consider bulk operations)
   - Index optimization (already in Prisma schema)

---

## Next Steps

1. **Immediate**: Fix Prisma client generation
2. **Today**: Implement procedure code sync
3. **Tomorrow**: Implement family sync
4. **This Week**: Test complete workflow end-to-end
5. **Next Week**: Treatment plans + enhanced insurance
6. **Week 3**: Payment history + fee schedules

---

**Document Owner**: Development Team  
**Last Updated**: January 20, 2026  
**Status**: Active Development
