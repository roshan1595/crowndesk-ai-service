# AI Agent Authentication for CrownDesk

## The Problem

Your AI receptionist needs to call backend APIs (search patients, book appointments, etc.), but:
- **Anyone can call the AI** (public phone line)
- **Backend requires authentication** (Clerk JWT)
- **AI agent is not a user** - it's a service acting on behalf of the practice

## The Solution: Service API Keys

We've implemented a **service authentication system** that allows AI agents to authenticate without user credentials.

---

## How It Works

```
┌─────────────────┐
│   Patient       │
│   Calls AI      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ElevenLabs     │
│  AI Agent       │
└────────┬────────┘
         │ Webhook Call
         │ Authorization: Bearer sk_live_abc123...
         │ x-tenant-id: tenant-uuid
         ▼
┌─────────────────┐
│  CrownDesk      │
│  Backend API    │
└────────┬────────┘
         │
         │ 1. ServiceAuthGuard validates API key
         │ 2. Looks up key in database
         │ 3. Verifies tenant ID matches
         │ 4. Attaches service context to request
         │ 5. Processes request as tenant service
         │
         ▼
┌─────────────────┐
│  Database       │
│  (Patient Data) │
└─────────────────┘
```

---

## Architecture

### Service API Keys Table

```typescript
ServiceApiKey {
  id: string             // UUID
  tenantId: string       // Which practice this key belongs to
  name: string           // "ElevenLabs AI Receptionist"
  keyHash: string        // SHA-256 hash of API key (never plain text)
  serviceType: string    // "ai_agent" | "webhook" | "integration"
  description: string    // Optional notes
  isActive: boolean      // Can be disabled without deleting
  expiresAt: Date        // Optional expiration
  lastUsedAt: Date       // Track usage
  usageCount: number     // Count API calls
  createdByUserId: string // Who created this key
}
```

### Authentication Flow

1. **Admin creates API key** via CrownDesk dashboard
2. **System generates key**: `sk_live_abc123...` (shown **once**)
3. **Admin configures ElevenLabs** with API key in webhook headers
4. **AI agent calls backend**:
   ```http
   POST /api/appointments
   Authorization: Bearer sk_live_abc123...
   x-tenant-id: tenant-uuid-here
   Content-Type: application/json
   
   {
     "patientId": "patient-123",
     "startTime": "2026-01-25T09:00:00Z",
     ...
   }
   ```
5. **ServiceAuthGuard validates**:
   - Extracts API key from `Authorization` header
   - Extracts tenant ID from `x-tenant-id` header
   - Hashes key and looks up in database
   - Verifies key belongs to tenant
   - Checks if key is active and not expired
   - Updates `lastUsedAt` and increments `usageCount`
6. **Request proceeds** with service context attached

---

## Security Features

### 1. **Keys are Hashed**
- Plain text key: `sk_live_abc123def456...`
- Stored as SHA-256 hash: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- If database is compromised, keys cannot be recovered

### 2. **Tenant Isolation**
- Each API key is scoped to a single tenant
- AI agent can only access data for that tenant
- Multi-tenant security enforced at key level

### 3. **Expiration & Revocation**
- Keys can have expiration dates
- Keys can be revoked instantly (soft delete)
- Admin dashboard shows all active keys

### 4. **Audit Logging**
- Every API key usage is logged
- Track which service made which request
- Monitor for suspicious activity

### 5. **Rate Limiting**
- Service requests go through same rate limiting as user requests
- Prevents abuse even if key is leaked

---

## Implementation

### Step 1: Add Prisma Model

```prisma
model ServiceApiKey {
  id              String   @id @default(uuid())
  tenantId        String   @map("tenant_id")
  name            String
  keyHash         String   @map("key_hash")
  serviceType     String   @map("service_type")
  description     String?
  isActive        Boolean  @default(true) @map("is_active")
  createdAt       DateTime @default(now()) @map("created_at")
  updatedAt       DateTime @updatedAt @map("updated_at")
  expiresAt       DateTime? @map("expires_at")
  lastUsedAt      DateTime? @map("last_used_at")
  usageCount      Int      @default(0) @map("usage_count")
  createdByUserId String   @map("created_by_user_id")

  tenant Tenant @relation(fields: [tenantId], references: [id])

  @@map("service_api_keys")
}
```

### Step 2: Run Migration

```powershell
cd crowndesk-backend
npx prisma migrate dev --name add_service_api_keys
```

### Step 3: Update Auth Module

Already created:
- ✅ `service-auth.decorator.ts` - Marks routes as service-accessible
- ✅ `service-auth.guard.ts` - Validates API keys
- ✅ `service-api-keys.controller.ts` - API key management
- ✅ `service-api-keys.service.ts` - Business logic

### Step 4: Register Guards in App Module

```typescript
// app.module.ts
import { ServiceAuthGuard } from './common/auth/guards/service-auth.guard';

@Module({
  providers: [
    {
      provide: APP_GUARD,
      useClass: ClerkAuthGuard, // Runs first
    },
    {
      provide: APP_GUARD,
      useClass: ServiceAuthGuard, // Runs second
    },
  ],
})
export class AppModule {}
```

### Step 5: Mark Routes as Service-Accessible

```typescript
// appointments.controller.ts
@Controller('appointments')
@ApiBearerAuth('clerk-jwt')
@ServiceAuth() // ✅ Allow service API key auth
export class AppointmentsController {
  @Post()
  async create(@Body() data: CreateAppointmentDto) {
    // Works with both:
    // - User JWT (Authorization: Bearer <clerk-jwt>)
    // - Service API key (Authorization: Bearer sk_live_...)
  }
}
```

---

## Usage

### Create API Key (Admin)

```powershell
# Via API
$headers = @{
    "Authorization" = "Bearer <clerk-jwt>"
}

$body = @{
    name = "ElevenLabs AI Receptionist"
    serviceType = "ai_agent"
    description = "AI receptionist for phone calls"
    expiresInDays = 365
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://cdapi.xaltrax.com/api/service-api-keys" `
    -Method POST `
    -Headers $headers `
    -Body $body `
    -ContentType "application/json"
```

**Response:**
```json
{
  "id": "key-uuid",
  "name": "ElevenLabs AI Receptionist",
  "serviceType": "ai_agent",
  "apiKey": "sk_live_abc123def456...",
  "expiresAt": "2027-01-22T00:00:00Z",
  "warning": "Save this API key securely. It will not be shown again."
}
```

### Configure ElevenLabs Webhook

In `ELEVENLABS_WEBHOOKS.json`, replace:

```json
{
  "request_headers": [
    {
      "name": "Authorization",
      "value": "Bearer sk_live_abc123def456..."
    },
    {
      "name": "x-tenant-id",
      "value": "your-tenant-uuid"
    }
  ]
}
```

### List API Keys

```powershell
Invoke-RestMethod -Uri "https://cdapi.xaltrax.com/api/service-api-keys" `
    -Headers @{ "Authorization" = "Bearer <clerk-jwt>" }
```

### Revoke API Key

```powershell
Invoke-RestMethod -Uri "https://cdapi.xaltrax.com/api/service-api-keys/key-uuid" `
    -Method DELETE `
    -Headers @{ "Authorization" = "Bearer <clerk-jwt>" }
```

---

## Monitoring

### Track API Key Usage

```sql
-- View API key usage stats
SELECT 
  name,
  service_type,
  usage_count,
  last_used_at,
  created_at
FROM service_api_keys
WHERE tenant_id = 'your-tenant-id'
ORDER BY last_used_at DESC;
```

### Audit Logs

Every service API call is logged:

```sql
SELECT 
  action_type,
  details,
  created_at
FROM audit_logs
WHERE 
  tenant_id = 'your-tenant-id'
  AND user_id LIKE 'service_%'
ORDER BY created_at DESC
LIMIT 100;
```

---

## Best Practices

### 1. **One Key Per Service**
- ✅ Create separate keys for each agent/integration
- ✅ Name them clearly: "ElevenLabs Receptionist", "Twilio Voice Agent"
- ❌ Don't share one key across multiple services

### 2. **Rotate Keys Regularly**
- Set expiration dates (e.g., 1 year)
- Create new key before old one expires
- Update service configuration
- Revoke old key

### 3. **Monitor Usage**
- Check `usage_count` for anomalies
- Alert on unusual spikes
- Review `last_used_at` for inactive keys

### 4. **Least Privilege**
- Future: Scope keys to specific endpoints
- Example: "appointments_read_write", "patients_read_only"

### 5. **Secure Storage**
- Store in environment variables (not code)
- Use secrets manager (Vercel secrets, AWS Secrets Manager)
- Never commit to git

---

## Comparison: User Auth vs Service Auth

| Feature | User Auth (Clerk JWT) | Service Auth (API Key) |
|---------|----------------------|------------------------|
| **Authentication** | Clerk JWT token | API key (sk_live_...) |
| **Identity** | Individual user | Service/integration |
| **Permissions** | User role | Service type |
| **Session** | 15 min inactivity timeout | No timeout |
| **MFA** | Required | N/A |
| **Audit** | User actions logged | Service actions logged |
| **Use Case** | Human users via UI | AI agents, webhooks, bots |

---

## Troubleshooting

### Issue: "Missing API key"
**Fix**: Ensure `Authorization: Bearer sk_...` header is present

### Issue: "Missing x-tenant-id header"
**Fix**: Add `x-tenant-id: your-tenant-uuid` header

### Issue: "Invalid API key"
**Fix**: 
1. Check key hasn't been revoked
2. Check key hasn't expired
3. Verify key belongs to tenant in `x-tenant-id`
4. Check for typos in key

### Issue: "Authentication required"
**Fix**: Add `@ServiceAuth()` decorator to controller

---

## Next Steps

1. ✅ Run database migration
2. ✅ Update `app.module.ts` with guards
3. ✅ Add `@ServiceAuth()` to all controllers used by AI
4. ✅ Create API key via admin panel
5. ✅ Update `ELEVENLABS_WEBHOOKS.json` with real API key
6. ✅ Test webhook calls
7. ✅ Monitor usage in audit logs

---

## Security Considerations

### ⚠️ API Key = Full Access

Service API keys have **admin-level access** to tenant data. Protect them like passwords:

- ✅ Store in secrets manager
- ✅ Rotate regularly
- ✅ Revoke immediately if compromised
- ✅ Monitor usage for anomalies
- ❌ Never commit to git
- ❌ Never share in plain text
- ❌ Never log the full key

### HIPAA Compliance

Service API keys are HIPAA-compliant:
- ✅ All access is logged (audit trail)
- ✅ Keys can be revoked instantly
- ✅ Tenant isolation enforced
- ✅ Keys are hashed in database
- ✅ Usage tracking for accountability

---

## Summary

**Problem**: AI agent needs backend access, but anyone can call it  
**Solution**: Service API keys with tenant-scoped authentication  
**Security**: Hashed storage, tenant isolation, audit logging, expiration  
**Usage**: Create key → Configure ElevenLabs → AI authenticates automatically  

Your AI receptionist is now **securely authenticated** and can safely access patient data! 🔐
