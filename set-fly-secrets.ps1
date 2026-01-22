# Set all environment variables for Fly.io AI Service
# Run from apps/ai-service directory

Write-Host "Setting secrets for AI Service on Fly.io..." -ForegroundColor Cyan

flyctl secrets set `
  DATABASE_URL="postgresql://user:password@host/db?sslmode=require" `
  LLM_PROVIDER="openai" `
  OPENAI_API_KEY="sk-proj-xxxxx..." `
  OPENAI_MODEL="gpt-4-turbo-preview" `
  OPENAI_EMBEDDING_MODEL="text-embedding-3-large" `
  ANTHROPIC_API_KEY="sk-ant-api03-xxxxx..." `
  ANTHROPIC_MODEL="claude-3-5-sonnet-20241022" `
  PINECONE_API_KEY="pcsk_xxxxx..." `
  PINECONE_HOST="https://crowndesk-xxxxx.svc.xxxxx.pinecone.io" `
  PINECONE_INDEX_NAME="crowndesk" `
  PINECONE_DIMENSION="1024" `
  PINECONE_METRIC="cosine" `
  BACKEND_URL="https://crowndesk-backend-aaal.vercel.app" `
  REDIS_URL="redis://default:xxxxx@xxxxx"

Write-Host "All secrets set successfully!" -ForegroundColor Green
Write-Host "You can now deploy with: flyctl deploy" -ForegroundColor Yellow
