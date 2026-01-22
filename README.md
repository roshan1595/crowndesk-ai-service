# CrownDesk AI Service

Modern dental practice management system - **AI/ML Service**

## 🚀 Tech Stack

- **Framework:** FastAPI (Python 3.11+)
- **LLM:** OpenAI GPT-4, Anthropic Claude
- **Vector DB:** Pinecone (embeddings)
- **Queue:** Celery + Redis
- **Deployment:** Fly.io

## 📦 Quick Start

### Prerequisites
- Python 3.11+
- pip or poetry
- Redis (for Celery)

### Installation

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Create `.env` with:

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...

# Pinecone Vector DB
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=crowndesk-embeddings

# Redis
REDIS_URL=redis://localhost:6379

# Backend API
BACKEND_URL=http://localhost:3001

# App Config
PORT=8001
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Development

```bash
# Start dev server (http://localhost:8001)
uvicorn main:app --reload --port 8001

# Run tests
pytest

# Format code
black .
isort .
```

## 🔗 Key Features

### 1. Intent Classification
- Natural language understanding
- Action extraction
- Entity recognition

### 2. RAG (Document Queries)
- Semantic search
- Context-aware answers
- Source citations

### 3. AI Insights
- Patient recommendations
- Financial optimization
- Practice analytics

### 4. Smart Scheduling
- Time slot optimization
- Provider matching
- Conflict detection

## 🚀 Deployment (Fly.io)

**Current Production:** https://ai-service-sparkling-brook-7912.fly.dev

```bash
# Deploy
flyctl deploy

# View logs
flyctl logs

# Set secrets
flyctl secrets set OPENAI_API_KEY=sk-...
```

## 📊 API Endpoints

```
GET  /health              # Health check
POST /api/intent          # Intent classification
POST /api/rag/query       # RAG query
POST /api/insights/{id}   # AI insights
```

## 📞 Related Repositories

- **Frontend:** [crowndesk-frontend](https://github.com/roshan1595/crowndesk-frontend)
- **Backend:** [crowndesk-backend](https://github.com/roshan1595/crowndesk-backend)

- **Repo linked to fly.io**

---

**Built with ❤️ for dental practices**
