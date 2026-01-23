# AI Service Fly.io Deployment Guide

## Current Status

✅ **Deployed and Working**: `https://ai-service-sparkling-brook-7912.fly.dev`
- App: `ai-service-sparkling-brook-7912`
- Region: `iad` (Ashburn, Virginia)
- Health endpoint: `GET /health` returns 200 OK

## Recent Fixes Applied

1. **Added health checks** to `fly.toml`:
   - Grace period: 30s (allows app startup time)
   - Interval: 15s between checks
   - Timeout: 5s per check
   - Path: `/health`

2. **Auto-stop configured**:
   - Machines stop after 6 minutes of inactivity (saves costs)
   - Auto-restart on incoming requests
   - Min machines running: 0

## Deploy Updates

### Prerequisites

```powershell
# Install Fly CLI (if not installed)
irm https://fly.io/install.ps1 | iex

# Login
fly auth login
```

### Deploy

```powershell
cd crowndesk-ai-service

# Deploy with updated fly.toml
fly deploy

# Or force rebuild
fly deploy --build-only
fly deploy
```

### Update Secrets

If you need to update environment variables:

```powershell
# Edit set-fly-secrets.ps1 with real values, then:
.\set-fly-secrets.ps1

# Or set individual secrets:
fly secrets set OPENAI_API_KEY="sk-proj-..."
fly secrets set DATABASE_URL="postgresql://..."
```

### Verify Deployment

```powershell
# Check status
fly status

# View logs
fly logs

# Open dashboard
fly dashboard

# Test health endpoint
curl https://ai-service-sparkling-brook-7912.fly.dev/health
```

## Troubleshooting

### If health checks fail

1. Check logs: `fly logs`
2. Verify app starts: Look for "Uvicorn running on http://0.0.0.0:8000"
3. Test health endpoint locally before deploying
4. Increase grace_period in fly.toml if startup is slow

### If machines keep timing out

- Increase `grace_period` to 60s in fly.toml
- Check if DATABASE_URL and API keys are set correctly
- Verify the app doesn't crash on startup

## Architecture

- **Platform**: Fly.io (Firecracker VMs)
- **Docker**: Python 3.11-slim with FastAPI/Uvicorn
- **Resources**: 1GB RAM, shared CPU
- **Port**: Internal 8000, external HTTPS
- **Auto-scaling**: Min 0, auto-start/stop enabled
