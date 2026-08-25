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
| **STT** | Groq Whisper Large v3 Turbo | Sub-second latency, low cost — see [known limitation](#-known-limitations--tradeoffs) on Indian name accuracy |
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
- `fuzzystrmatch` + `pg_trgm` extensions for phonetic/similarity name & city matching
- Partial indexes for performance (e.g., `WHERE is_booked = FALSE`)
- Foreign key constraints with cascade deletes

### 🔤 Fuzzy Name & City Matching

Real callers' names and cities are frequently mis-transcribed by STT. Identity/record lookups use a two-tier strategy:
1. **Exact/ILIKE match** first, pinned on hard filters (age + last-4 phone digits — never fuzzy).
2. **Phonetic fallback** (`dmetaphone`) for names, and **trigram similarity** (`pg_trgm`) for city, when the exact tier misses.

This closes most of the gap for *matching against existing DB records*; it does **not** fix what gets transcribed or stored in the first place — see tradeoffs below.

### 🔐 Security & Privacy

- **Identity Verification** — Multi-factor: name + age + phone (last 4 digits spoken digit-by-digit)
- **Attempt Limiting** — Configurable `MAX_VERIFICATION_ATTEMPTS` (default: 2)
- **No PII in Logs** — Structured logging with sensitive data redaction
- **Environment-based Config** — All secrets via `.env` (never committed)
- **SQL Injection Prevention** — Parameterized queries via psycopg2
- **⚠️ Medical-advice guardrail** — not yet implemented (see [Recommended for v1](#-recommended-for-v1-release))

### 🚀 Infrastructure

#### Docker Compose Stack (current)
```yaml
services:
  livekit-server:   # Media server (WebRTC/SIP)
  postgres:         # PostgreSQL 16 with persistent volume
```
> The application worker and Streamlit dashboard are **not yet containerized** — no `Dockerfile` exists for either at this stage; both are run directly via `python main.py` / `streamlit run`. Containerizing them is on the v1 checklist.

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
- **Health/readiness endpoints** — `/healthz`, `/readyz` (DB connectivity check)
- **Structured Logging** — JSON logs, configurable levels (DEBUG/INFO/WARNING/ERROR)
- **LiveKit session metrics** — collected and logged (`metrics_collected`, `session_usage_updated`), but **not yet exported to any monitoring/alerting tool** (no Prometheus/Grafana/PagerDuty wiring — logs only, for now)
- **Connection Pooling** — psycopg2 per-request connections (stateless workers)
- **Error Boundaries** — Tool-level try/catch with user-friendly messages

## 📁 Project Structure

```
voice-ai-agent/
├── main.py                    # LiveKit agent worker entrypoint
├── streamlit_app.py           # Web demo / testing UI
├── docker-compose.yml         # Local dev stack (LiveKit + Postgres only)
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
│       ├── client.py          # Raw SQL helpers (psycopg2), incl. fuzzy match
│       └── migrations/        # Alembic versions (10+ migrations)
├── tests/
│   └── db/                    # Pytest suite with fixtures
├── models/
│   └── piper/                 # TTS model artifacts (gitignored)
└── livekit_client_script/     # Browser client bundle
```

## 🛠️ Getting Started

### Prerequisites
- Python 3.12+
- Docker & Docker Compose (for Postgres + LiveKit media server)
- LiveKit Cloud account or self-hosted server
- Google AI API key(s) (Gemini) — see LLM fallback note below
- Groq API key (Whisper STT)

### Quick Start

```bash
# 1. Clone & enter
cd voice-ai-agent

# 2. Configure environment
cp .env.example .env
# Edit .env with your keys

# 3. Start infrastructure (Postgres + LiveKit only — app is not containerized yet)
docker-compose up -d

# 4. Run migrations
alembic -c app/db/alembic.ini upgrade head

# 5. Seed test data (optional)
docker compose exec -T postgres psql -U lab_admin -d lab_diagnostics < db/scripts/mock_data.sql

# 6. Start voice agent worker (runs on host, not in a container)
python main.py

# 7. (Optional) Launch Streamlit demo (also runs on host)
streamlit run streamlit_app.py
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LIVEKIT_URL` | ✅ | — | WebSocket URL (e.g., `wss://your-project.livekit.cloud`) |
| `LIVEKIT_API_KEY` | ✅ | — | LiveKit API key |
| `LIVEKIT_API_SECRET` | ✅ | — | LiveKit API secret |
| `GOOGLE_API_KEY` | ✅ | — | Google AI Studio key for Gemini (primary) |
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
- Fuzzy name/city matching (dmetaphone / trigram)
- Appointment creation (prescription vs payment flows)
- Report status & resend logic
- Ticket creation (with/without patient)
- Report expiration cleanup

> No CI/CD pipeline runs these yet — currently local/manual only. A golden-dataset eval suite (agent tool-call correctness + STT word-error-rate on Indian names) is planned but not built.

## ⚖️ Known Limitations & Tradeoffs

Documented deliberately — these are conscious, budget/timeline-driven decisions, not oversights.

### 1. STT: Whisper (via Groq) instead of Sarvam AI
Groq Whisper Large v3 Turbo was chosen for latency and cost, but it is **not** tuned for Indian names/accents — mis-transcriptions like "Agarwal" → "Akarwal" are common and directly affect patient-record accuracy. **Sarvam AI** (India-specific STT, e.g. Saarika) is the intended production replacement and is expected to perform meaningfully better on this exact failure mode.

**Interim mitigations (planned, not yet implemented):**
- **Prompt-biasing** — feeding Whisper a curated list of common Indian names/cities/test names via its `prompt` parameter to bias decoding.
- **Spell-back confirmation** — having the agent read back a captured name letter-by-letter for explicit caller confirmation before it's used downstream, closing the loop with the one person who actually knows the correct spelling.

These reduce the *visible* impact of the underlying STT weakness for a demo/prototype; they are not a substitute for migrating to a better-suited STT provider, which is the planned production fix.

### 2. LLM fallback: same-provider key rotation, not multi-provider
The LLM fallback is currently `llm.FallbackAdapter([gemini_1, gemini_2, gemini_3])` — three Gemini instances on **different API keys**, not different providers. This protects against hitting a single key's rate limit (e.g. Google's free-tier 15 req/min) but does **not** protect against a Gemini-wide outage or systemic issue, since all three fallbacks share the same upstream provider.

This is a deliberate budget tradeoff: a true multi-provider fallback (e.g. adding Groq/Llama or another vendor as a second provider) would improve resilience further but adds cost and a need to validate function-calling parity on a different model family — deferred until budget allows.

## 📈 Production Checklist

### ✅ Completed
- [x] Multi-agent architecture with clean handoffs
- [x] Database schema with migrations & indexes
- [x] Fuzzy name/city matching (fuzzystrmatch, pg_trgm)
- [x] Health/readiness endpoints
- [x] Structured (JSON) logging
- [x] Unit test suite
- [x] Environment-based configuration
- [x] Docker Compose for Postgres + LiveKit media server
- [x] Noise cancellation & turn detection
- [x] Offline TTS (no external API dependency)
- [x] Identity verification with attempt limiting
- [x] Prescription & payment link generation
- [x] Report TTL & storage cleanup utilities
- [x] LLM fallback across multiple Gemini API keys (same-provider only — see tradeoffs)
- [x] LiveKit session metrics collection (logged, not yet exported)
- [x] Streamlit demo for manual testing

### 🚧 Recommended for v1 Release
- [ ] **Medical-advice guardrail** — deterministic (regex-based) interception before any medically-sensitive query reaches the LLM; agent should defer to a doctor rather than answer
- [ ] **Spell-back name confirmation** in booking flow
- [ ] **Whisper prompt-biasing** with common Indian name/city vocabulary (interim STT mitigation)
- [ ] **Migrate STT to Sarvam AI** (production fix for Indian-name accuracy)
- [ ] **True multi-provider LLM fallback** (e.g. add a non-Gemini provider), budget permitting
- [ ] **CI/CD** — GitHub Actions: lint → test → build → deploy
- [ ] **Golden-dataset eval suite** — tool-call correctness (text-level) + STT word-error-rate benchmark on Indian names
- [ ] **Containerize application worker & Streamlit app** (Dockerfiles)
- [ ] **Monitoring** — export existing LiveKit metrics to Prometheus/Grafana (metrics are already collected, just not connected to a dashboard)
- [ ] **Alerting** — PagerDuty/Slack for failed calls, DB errors
- [ ] **Load Testing** — Concurrent call simulation (k6/Locust)
- [ ] **Secrets Management** — HashiCorp Vault / AWS Secrets Manager
- [ ] **TLS Termination** — Nginx/Traefik reverse proxy for LiveKit
- [ ] **Rate Limiting** — Per-caller API quotas
- [ ] **Call Recording** — Optional compliance recording to S3/GCS
- [ ] **Analytics** — Call volume, intent classification, drop-off points
- [ ] **Multi-language** — i18n for agent prompts (Hindi, regional)

## 💰 Cost Optimization

| Component | Cost Model | Optimization |
|-----------|------------|--------------|
| **STT (Groq)** | Per-minute | Whisper Turbo = ~$0.006/min (accuracy tradeoff noted above) |
| **LLM (Gemini)** | Per-token | Flash Lite = ~$0.075/1M tokens; multi-key fallback for rate-limit resilience at $0 extra cost |
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