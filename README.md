# GuardScreen — AML Sanctions Screening System

Real-time AML screening platform with Track A (deterministic sanctions gate) and Track B (probabilistic risk scoring), peer-challenge review powered by a local LLM, and a full-screen network graph explorer.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Docker Desktop | 4.x+ |
| Docker Compose | v2 (bundled with Docker Desktop) |
| Python 3 | 3.10+ (for seed scripts only) |
| Ollama | latest (for LLM challenge review) |

---

## First-time setup

### 1. Clone the repo

```bash
git clone https://github.com/DejanM053/screening_sys.git
cd screening_sys
```

### 2. Build and start all services

```bash
make build
make up
```

This starts:

| Service | Port | Description |
|---------|------|-------------|
| Frontend (Vite/React) | 3000 | Main UI |
| Screening API (FastAPI) | 8001 | Track A/B scoring, explanation tree |
| Entity Resolution | 8002 | RapidFuzz name matching |
| Regulatory Engine | 8003 | OFAC, FCA, EU rulesets |
| Graph Engine | 8005 | Network noisy-OR risk |
| Review Queue | 8009 | Redis-backed case queue |
| PostgreSQL | 5432 | Audit trail + challenge case DB |
| Redis | 6379 | Queue + KYB wallet registry |

### 3. Run database migrations

```bash
make migrate
```

### 4. Seed test data

```bash
pip3 install httpx
make seed-all
```

This populates:
- **Redis queue** — 19 realistic AML cases (MATCH / REVIEW / NO_MATCH, various countries and tracks)
- **PostgreSQL** — 20 historical precedent cases with mixed verdicts for the challenge review system

### 5. Pull the LLM model (for Challenge Review)

Requires [Ollama](https://ollama.com) running locally:

```bash
ollama pull llama3.2
```

---

## Open the app

```bash
open http://localhost:3000
```

---

## Key workflows

### Review Queue
Browse pending cases sorted by priority. Filter by Transfer Type or Verdict (MATCH / REVIEW / NO_MATCH). Click a row to open Case Detail.

### Case Detail
- **Left panel** — payment instruction, entity profile, UBO resolution status
- **Center panel** — risk score waterfall (6 weighted factors, click to expand each)
- **Right panel** — network cluster mini-graph (noisy-OR, ownership chain, or cluster view)
- **Action bar** — CLEAR / BLOCK / ESCALATE; buttons lock after a decision is recorded

### Network Explorer
Click **"Network Explorer"** in the nav (or **"Full Graph →"** inside Case Detail) to open the interactive D3 force-directed network graph. Drag nodes, scroll to zoom, click a node for its risk detail panel.

### Challenge Review
On any case, click **"Challenge Review"** to open the peer-review panel:
1. Form auto-fills from case data — adjust typology tags and draft verdict
2. Submit → system finds similar historical precedents from PostgreSQL
3. If a contradicting precedent is found, Ollama generates a structured challenge (tension / precedent / distinguishing argument / one question)
4. Answer the challenge questions → case is re-enqueued for final decision

---

## Day-to-day commands

```bash
make up          # Start all services
make down        # Stop all services
make logs        # Stream logs from all services

make seed-queue     # Re-seed Redis queue (19 cases)
make seed-postgres  # Re-seed PostgreSQL precedents (20 cases)
make seed-all       # Both

make migrate     # Run DB migrations (safe to re-run)
```

---

## Service ports at a glance

```
http://localhost:3000   Frontend
http://localhost:8001   Screening API  →  /screen/fiat  /screen/wallet  /explanation/{id}
http://localhost:8002   Entity Resolution
http://localhost:8003   Regulatory Engine
http://localhost:8005   Graph Engine
http://localhost:8009   Review Queue   →  /queue  /enqueue  /decide/{id}
```

---

## Architecture

```
Frontend (React + Vite)
    │
    ├── Review Queue API  (FastAPI + Redis)
    │       └── /queue  /enqueue  /decide/{id}
    │
    └── Screening API  (FastAPI)
            ├── Track A — RapidFuzz name matching vs OpenSanctions / OFAC
            ├── Track B — 6-factor weighted risk score
            │       ├── Factor 1: Identity match signal
            │       ├── Factor 2: Behavioral anomaly
            │       ├── Factor 3: Network noisy-OR (networkx graph)
            │       ├── Factor 4: Entity risk profile
            │       ├── Factor 5: Document integrity
            │       └── Factor 6: Historical flag rate (Beta-Binomial)
            ├── Regulatory Engine — OFAC + FCA rulesets
            ├── Challenge System  — PostgreSQL + BOW embeddings + Ollama LLM
            └── Explanation tree  — serialised ScoreNode DAG
```

---

## Troubleshooting

**Queue is empty after restart**
Redis is ephemeral. Re-seed with:
```bash
make seed-queue
```

**Challenge Review finds no similar cases**
PostgreSQL was reset. Re-seed with:
```bash
make seed-postgres
```

**Challenge Review times out**
Ollama must be running locally with `llama3.2` pulled:
```bash
ollama serve          # if not already running
ollama pull llama3.2
```

**Frontend not updating after code change**
SSH tunnels block HMR. Do a hard refresh: `Cmd+Shift+R`
