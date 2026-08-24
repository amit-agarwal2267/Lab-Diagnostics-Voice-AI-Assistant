# Lab Diagnostic Voice AI Agent
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-316192?logo=postgresql)
![LiveKit](https://img.shields.io/badge/LiveKit-WebRTC-success)
![Gemini Flash Lite](https://img.shields.io/badge/LLM-Gemini_Flash_Lite-FF9D00?logo=google)

A production-ready voice AI assistant for lab diagnostic vendors that handles telephonic conversations for appointment booking, report status queries, and general support — easing the process for both vendors and patients at low cost.

## 🏗️ Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Caller Phone  │────▶│   LiveKit SIP    │────▶│  Voice AI Agent │
│   (WebRTC/SIP)  │     │   Media Server   │     │  (Python Worker)│
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                           │
                          ┌────────────────────────────────┼────────────────────────────────┐
                          ▼                                ▼                                ▼
                   ┌─────────────┐                 ┌─────────────┐                 ┌─────────────┐
                   │   STT       │                 │   LLM       │                 │   TTS       │
                   │  (Groq)     │                 │  (Gemini)   │                 │ (Piper)     │
                   │ Whisper v3  │                 │ 3.5 Flash   │                 │ Ryan High   │
                   └─────────────┘                 └─────────────┘                 └─────────────┘
                          │                                │                                │
                          └────────────────────────────────┼────────────────────────────────┘
                                                           ▼
                                                ┌─────────────────────┐
                                                │  PostgreSQL DB      │
                                                │  (Appointments,     │
                                                │   Patients, Reports,│
                                                │   Tickets, Slots)   │
                                                └─────────────────────┘
```

## ✨ Key Features

### 🎯 Core Capabilities

| Feature | Description |
|---------|-------------|
| **Appointment Booking** | Multi-step guided flow: test selection → prescription check → slot selection → patient details → confirmation |
| **Report Status** | Identity-verified report lookup with automatic email/WhatsApp resend |
| **Support Tickets** | Escalation for email corrections, complaints, and general inquiries |
| **Prescription Handling** | Automated upload link generation for tests requiring prescriptions |
| **Payment Integration** | Configurable payment link generation (UPI/Cash on Visit) |
| **Sample Collection Modes** | Visit Center & Home Visit support |

### 🤖 Multi-Agent Architecture

The system uses a **Supervisor-Router Pattern** with specialized sub-agents:

```
Supervisor Agent (Router)
├── Appointment Agent     → Booking, slots, pricing, prescriptions
├── Report Status Agent  → Identity verification, report lookup
└── Ticket Agent         → Email corrections, complaints, general inquiries
```

**Key Design Decisions:**
- **Stateless handoffs** — Context preserved via `UserData` dataclass across agent transfers
- **Sequential tool workflows** — Each agent follows a strict instruction sequence
- **Graceful fallbacks** — Failed verification → automatic ticket creation for human follow-up
- **Conversation continuity** — No re-greeting on handoff; agents resume from chat history

### 🗣️ Voice Pipeline (LiveKit)

| Component | Technology | Why |
|-----------|------------|-----|
| **STT** | Groq Whisper Large v3 Turbo | Sub-second latency, high accuracy for medical terms |
| **LLM** | Google Gemini 3.5 Flash Lite | Fast inference, strong function-calling, cost-effective |
| **TTS** | Piper (HuggingFace) — `en_US-ryan-high.onnx` | Offline, natural voice, no API costs |
| **Noise Cancellation** | LiveKit BVC (Browser Voice Cancellation) | Real-time denoising for telephony audio |
| **Turn Detection** | LiveKit Inference TurnDetector | Natural conversation flow without manual VAD tuning |

### 🗄️ Database Schema (PostgreSQL 16 + Alembic Migrations)

```sql
-- Core Tables
centre              -- Lab centers with geo-location & capabilities
lab_test            -- Test catalog (price, prescription req, instructions)
patient             -- Patient registry (name, age, phone, email)
slot_inventory      -- Time-slot management per center/date
appointment         -- Bookings with status lifecycle
appointment_test    -- Many-to-many appointment ↔ test
report              -- Report generation & delivery tracking
report_test         -- Many-to-many report ↔ test
ticket              -- Support escalation (open/resolved/escalated)
```

**Migration Strategy:**
- Version-controlled schema via Alembic (10 migrations)
- `pgcrypto` extension for UUID generation
- Partial indexes for performance (e.g., `WHERE is_booked = FALSE`)
- Foreign key constraints with cascade deletes

### 🔐 Security & Privacy

- **Identity Verification** — Multi-factor: name + age + phone (last 4 digits spoken digit-by-digit)
- **Attempt Limiting** — Configurable `MAX_VERIFICATION_ATTEMPTS` (default: 2)
- **No PII in Logs** — Structured logging with sensitive data redaction
- **Environment-based Config** — All secrets via `.env` (never committed)
- **SQL Injection Prevention** — Parameterized queries via psycopg2

### 🚀 Production-Ready Infrastructure

#### Docker Compose Stack
```yaml
services:
  livekit-server:   # Media server (WebRTC/SIP)
  postgres:         # PostgreSQL 16 with persistent volume
  # Add: voice-agent worker, streamlit dashboard, nginx reverse proxy
```

#### Configuration Management (Pydantic Settings)
```python
# All settings validated at startup
LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
GOOGLE_API_KEY, GROQ_API_KEY
LLM_MODEL, STT_MODEL, TTS_MODEL_PATH
DB_URL (SecretStr)
LAB_NAME, PRESCRIPTION_UPLOAD_BASE_URL, PAYMENT_BASE_URL
MAX_VERIFICATION_ATTEMPTS, REPORT_TTL_DAYS
LOG_LEVEL, ENVIRONMENT (development/staging/production)
```

#### Health & Observability
- **Structured Logging** — Configurable levels (DEBUG/INFO/WARNING/ERROR)
- **Graceful Shutdown** — LiveKit agent lifecycle hooks
- **Connection Pooling** — psycopg2 per-request connections (stateless workers)
- **Error Boundaries** — Tool-level try/catch with user-friendly messages

## 📁 Project Structure

```
voice-ai-agent/
├── main.py                    # LiveKit agent worker entrypoint
├── streamlit_app.py           # Web demo / testing UI
├── docker-compose.yml         # Local dev stack (LiveKit + Postgres)
├── pyproject.toml             # Dependencies (uv-managed)
├── .env.example               # Template for environment variables
├── alembic.ini                # Migration config
├── app/
│   ├── config/
│   │   └── config.py          # Pydantic Settings (validated)
│   ├── core/
│   │   ├── state.py           # UserData dataclass (session state)
│   │   ├── prompts.py         # Agent instructions (system prompts)
│   │   ├── tools.py           # Function tools (DB operations)
│   │   └── agents/
│   │       ├── supervisor.py  # Router agent
│   │       ├── appointment.py # Booking specialist
│   │       ├── report_status.py
│   │       └── ticket.py
│   └── db/
│       ├── client.py          # Raw SQL helpers (psycopg2)
│       └── migrations/        # Alembic versions (10 migrations)
├── tests/
│   └── db/                    # Pytest suite with fixtures
├── models/
│   └── piper/                 # TTS model artifacts (gitignored)
└── livekit_client_script/     # Browser client bundle
```

## 🛠️ Getting Started

### Prerequisites
- Python 3.12+
- Docker & Docker Compose
- PostgreSQL 16 (or use compose)
- LiveKit Cloud account or self-hosted server
- Google AI API key (Gemini)
- Groq API key (Whisper STT)

### Quick Start

```bash
# 1. Clone & enter
cd voice-ai-agent

# 2. Configure environment
cp .env.example .env
# Edit .env with your keys

# 3. Start infrastructure
docker-compose up -d

# 4. Run migrations
cd app/db
alembic upgrade head

# 5. Seed test data (optional)
psql $DB_URL -f tests/db/scripts/mock_data.sql

# 6. Start voice agent worker
cd ../..
python main.py

# 7. (Optional) Launch Streamlit demo
streamlit run streamlit_app.py
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LIVEKIT_URL` | ✅ | — | WebSocket URL (e.g., `wss://your-project.livekit.cloud`) |
| `LIVEKIT_API_KEY` | ✅ | — | LiveKit API key |
| `LIVEKIT_API_SECRET` | ✅ | — | LiveKit API secret |
| `GOOGLE_API_KEY` | ✅ | — | Google AI Studio key for Gemini |
| `GROQ_API_KEY` | ✅ | — | Groq key for Whisper STT |
| `DB_URL` | ✅ | — | PostgreSQL connection string |
| `LLM_MODEL` | ❌ | `gemini-3.5-flash-lite` | LLM model identifier |
| `STT_MODEL` | ❌ | `whisper-large-v3-turbo` | STT model identifier |
| `TTS_MODEL_PATH` | ❌ | `models/piper/en_US-ryan-high.onnx` | Piper ONNX model path |
| `LAB_NAME` | ❌ | `Dino Labs` | Brand name spoken by agent |
| `MAX_VERIFICATION_ATTEMPTS` | ❌ | `2` | Failed verification limit |
| `REPORT_TTL_DAYS` | ❌ | `14` | Report retention before cleanup |

## 🧪 Testing

```bash
# Run all tests (requires running Postgres)
cd tests
pytest -v

# Run specific test module
pytest tests/db/test_client.py -v
```

**Test Coverage:**
- Database connection & CRUD operations
- Slot reservation & conflict handling
- Identity verification (partial phone matching)
- Appointment creation (prescription vs payment flows)
- Report status & resend logic
- Ticket creation (with/without patient)
- Report expiration cleanup

## 📈 Production Checklist

### ✅ Completed
- [x] Multi-agent architecture with clean handoffs
- [x] Database schema with migrations & indexes
- [x] Comprehensive test suite
- [x] Environment-based configuration
- [x] Docker Compose for local dev
- [x] Noise cancellation & turn detection
- [x] Offline TTS (no external API dependency)
- [x] Identity verification with attempt limiting
- [x] Prescription & payment link generation
- [x] Report TTL & storage cleanup utilities
- [x] Structured logging
- [x] Streamlit demo for manual testing

### 🚧 Recommended for v1 Release
- [ ] **Load Testing** — Concurrent call simulation (k6/Locust)
- [ ] **Monitoring** — Prometheus metrics + Grafana dashboards
- [ ] **Alerting** — PagerDuty/Slack for failed calls, DB errors
- [ ] **CI/CD** — GitHub Actions: lint → test → build → deploy
- [ ] **Secrets Management** — HashiCorp Vault / AWS Secrets Manager
- [ ] **TLS Termination** — Nginx/Traefik reverse proxy for LiveKit
- [ ] **Rate Limiting** — Per-caller API quotas
- [ ] **Call Recording** — Optional compliance recording to S3/GCS
- [ ] **Analytics** — Call volume, intent classification, drop-off points
- [ ] **Multi-language** — i18n for agent prompts (Hindi, regional)

## 💰 Cost Optimization

| Component | Cost Model | Optimization |
|-----------|------------|--------------|
| **STT (Groq)** | Per-minute | Whisper Turbo = ~$0.006/min |
| **LLM (Gemini)** | Per-token | Flash Lite = ~$0.075/1M tokens |
| **TTS (Piper)** | Free (local) | Zero marginal cost |
| **LiveKit** | Per-minute | Self-hosted = infrastructure only |
| **PostgreSQL** | Instance | Right-size; read replicas for analytics |

**Estimated per-call cost: < $0.02** (vs $0.50–2.00 for fully managed voice AI)

## 🔧 Extending the System

### Adding a New Agent
1. Create `app/core/agents/new_agent.py` extending `Agent`
2. Define instructions in `app/core/prompts.py`
3. Add tools in `app/core/tools.py`
4. Register handoff in `supervisor.py`

### Adding a New Tool
```python
@function_tool
async def my_new_tool(param: str, context: RunContext[UserData]) -> str:
    # Access DB via client.py helpers
    # Read/write context.userdata for session state
    return "Result message to caller"
```

### Customizing Verification
Modify `verify_patient_identity` in `tools.py` to add:
- OTP via SMS/WhatsApp
- Date of birth check
- Last appointment date confirmation

## 📄 License

Proprietary — All rights reserved. Not open source at this stage.

## 🤝 Contributing

Internal project — see internal wiki for contribution guidelines.

---

**Built with:** Python 3.12 · LiveKit Agents · Groq · Google Gemini · HuggingFace Piper · PostgreSQL · Alembic · Streamlit · Docker