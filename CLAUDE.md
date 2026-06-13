# SANCTIONS SCREENING SYSTEM — MASTER PLAN
## Deep Research & Architecture Document
### Version 1.2 | June 2026

---

# TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Sokin Intelligence Report](#2-sokin-intelligence-report)
3. [Threat Model & Problem Space](#3-threat-model--problem-space)
4. [Technical Architecture — Domain-Based, Dockerized](#4-technical-architecture--domain-based-dockerized)
5. [Open-Source LLM Strategy (No Paid API)](#5-open-source-llm-strategy-no-paid-api)
6. [Scoring Engine — Individual + Cumulative Network Risk](#6-scoring-engine--individual--cumulative-network-risk)
7. [Score Explanation Graph (Explainability Layer)](#7-score-explanation-graph-explainability-layer)
8. [Business/UBO Layer — Corporate Ownership Engine](#8-businessubo-layer--corporate-ownership-engine)
9. [Regulatory Engine — Country-Based Rule System](#9-regulatory-engine--country-based-rule-system)
10. [Stablecoin & Crypto Compliance Engine](#10-stablecoin--crypto-compliance-engine)
11. [How Stable Crypto Banks Work — Reference Architecture](#11-how-stable-crypto-banks-work--reference-architecture)
12. [UI/UX Research — Analyst Experience](#12-uiux-research--analyst-experience)
13. [Claude Code Prompts](#13-claude-code-prompts)
14. [Claude Design Prompts](#14-claude-design-prompts)

---

# 1. EXECUTIVE SUMMARY

This document delivers a complete plan for building a production-grade, open-source, sanctions screening system specifically oriented around:

- **Sokin/Plata Capital Ltd** as the primary operational context
- **KYB-first screening** — the platform currently onboards businesses only (KYB); KYC for individual onboarding is a planned future extension and the architecture must accommodate it without structural rework
- **Business-first screening** — beneficial ownership, corporate layers, shell structures; UBO resolution is the primary identity check, not a secondary one
- **Cumulative risk scoring** — detecting when multiple entities with moderate scores (0.5–0.6) collectively form a high-risk cluster
- **Regulatory engine** — pluggable, country-aware rule sets (OFAC, FCA, FATF, MiCA, etc.)
- **Stablecoin focus, TRON/USDT primary** — USDT on TRON is the dominant payment rail; USDC on Ethereum/Solana is secondary; the system is designed around pre-execution stablecoin screening with KYB-verified wallet attribution
- **No paid LLM API** — fully self-hosted via Ollama + open-source models
- **Domain-based microservices** — each domain in its own Docker container
- **Score graphs** — every verdict is visually and logically explainable

> **KYC Extension Note:** All schemas, data models, and scoring factors are designed to accommodate both legal entities (KYB) and natural persons (KYC). KYB-specific fields (UBO chain, corporate risk signals, entity age) are present from day one; KYC-specific fields (DOB, passport number, biometric reference) are included in the data model as nullable fields and will be activated when the KYC onboarding module is built. No structural migration will be required.

---

# 2. SOKIN INTELLIGENCE REPORT

## 2.1 Corporate Structure (Layered)

```
Plata Capital Ltd (England & Wales, #10958599)
│   Registered c/o Mishcon de Reya, Africa House, 70 Kingsway, London WC2B 6AH
│   Trading name: SOKIN
│
├── Sokin (UK) — FCA registered
├── Sokin Australia Pty Ltd (ABN 15 635 563 941)
│   ├── Regulated by ASIC (AFSL #536975)
│   └── Enrolled with AUSTRAC as reporting entity
├── Sokin DIFC Limited
│   └── Regulated by DFSA (Dubai International Financial Centre)
├── Sokin (Canada)
│   └── Registered with Bank of Canada / FINTRAC
├── Sokin (EEA/EU)
│   └── Operating via Modulr Finance B.V. (Netherlands, DNB, EMI #R182870)
└── Sokin (US)
    └── Registered with FinCEN
```

**Key dependency:** For European operations, Sokin relies on **Modulr Finance B.V.** as the licensed EMI. This means Sokin is a distributor/agent, not the direct license holder in Europe — a common layering pattern that itself deserves scrutiny in any compliance context.

**Investor:** Morgan Stanley Expansion Capital (strategic, c-suite seat)

## 2.2 Review Intelligence & Suspicious Signals

From Trustpilot and review aggregators (86–100 reviews, score 2–3/5):

**Observed Patterns (sourced from public Trustpilot reviews; treated as internal design motivation and hypotheses, not verified findings about the company):**
- **Jurisdictional confusion** — When UK-registered users attempt GDPR data deletion post-rejection, Sokin invokes Canadian AML law rather than UK GDPR, despite the entity being Plata Capital Ltd (England & Wales). This could reflect genuine regulatory complexity (a Canada-entity handling UK users) or a deflection strategy; the system design must handle both scenarios without assuming intent.
- **Over-intrusive KYC** — Questions that analysts describe as far exceeding normal AML requirements; potential indicator of over-zealous automated flags with poor explainability.
- **Account rejection with data retention** — Rejected applicants unable to recover passport/KYC documents. Regulatory risk: if screening over-flags legitimate businesses, the cost is real.
- **No phone/email support** — Contact-form only; makes dispute resolution of false positives extremely slow.
- **Proximity to suspicious websites** — Scam Detector flags elevated proximity score; warrants ongoing monitoring.

## 2.3 What This Means for Our System

Building for Sokin-like fintechs means solving:

1. Multi-jurisdiction regulatory stack (UK/FCA + EU/DNB + UAE/DFSA + AU/ASIC + CA/FINTRAC + US/FinCEN simultaneously)
2. False positive control — their Trustpilot failures are largely false-positive failures
3. Business-first screening (they serve SMEs, clubs, sports organizations — not individuals)
4. Corporate layer analysis — their clients send/receive via holding companies, intermediaries
5. Explainable rejections — they cannot legally explain decisions to rejected applicants without an audit trail

---

# 3. THREAT MODEL & PROBLEM SPACE

## 3.1 The Three Failure Modes

| Mode | Description | Cost |
|------|-------------|------|
| **Under-blocking** | Sanctioned entity clears screening | Regulatory fine (up to 10-figure), criminal liability, license revocation |
| **Over-blocking** | Legitimate business blocked | Revenue loss, customer churn, reputational damage, possible discrimination claim |
| **Explainability failure** | Can't justify decision to regulator | Regulatory censure even when decision was correct |

## 3.2 Why Business Screening Is Harder Than Individual Screening

Individuals have: name, DOB, nationality, passport number.

Businesses have:
- Legal name + trading name + DBA aliases
- Multiple UBOs (each may be sanctioned separately)
- Shell company chains (3–12 layers is common offshore)
- Nominee directors vs actual beneficial owners
- Cross-jurisdictional incorporation (holding co in BVI, ops in UK, bank in UAE)
- Stablecoin wallets owned by the entity's treasury function

**KYC extension note:** When KYC onboarding is activated in a future phase, individual screening will reuse the identity matching and network graph infrastructure already built for UBO resolution. The scoring weights will differ (no corporate risk signals; DOB/passport corroboration replaces entity-age/PSC checks) but the underlying service contracts are identical.

## 3.3 The Cumulative Risk Problem

Existing systems screen one entity at a time. The real criminal pattern is:

> Five companies, each with a 0.55 suspicion score, are all controlled by the same shadow UBO who is on an OFAC list under a different alias.

No single entity triggers MATCH. But the network does. This requires:
- Shared-attribute clustering (same address, same phone, same director)
- Graph traversal to shared sanctioned nodes
- Cumulative score aggregation across a connected subgraph

> **Reconciliation note — cumulative layer vs. revised guardrails:** The engine described in later sections is more conservative than the framing above implies. The cumulative/network layer's role is **REVIEW-prioritization and recall amplification**, not automatic blocking. For the "shadow UBO on OFAC under a different alias" scenario, the correct resolution is stronger alias matching feeding the Track A 50%-rule, which then blocks deterministically if ownership ≥50% is established. Without a confirmed alias match, the network layer routes to REVIEW for human examination — the right outcome. Also note: at a REVIEW threshold of 0.50, each 0.55-scoring entity already reaches REVIEW individually; the network layer's value is raising queue priority for the cluster, not changing the verdict class. **Network/cluster analysis never produces a MATCH verdict.**

---

# 4. TECHNICAL ARCHITECTURE — DOMAIN-BASED, DOCKERIZED

## 4.1 Domain Map

Each domain is an independent Docker service with its own data store, API, and deployment lifecycle:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY (Kong / Traefik)                    │
│                    Rate limiting | Auth | Request routing                │
└──────────┬──────────────┬──────────────┬──────────────┬─────────────────┘
           │              │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌───▼───────┐ ┌───▼───────────┐
    │  SCREENING  │ │   ENTITY   │ │REGULATORY │ │    CRYPTO     │
    │     API     │ │ RESOLUTION │ │  ENGINE   │ │   SCREENER    │
    │  (FastAPI)  │ │ (FastAPI)  │ │ (FastAPI) │ │  (FastAPI)    │
    │  Port 8001  │ │  Port 8002 │ │ Port 8003 │ │  Port 8004    │
    └──────┬──────┘ └─────┬──────┘ └───┬───────┘ └───┬───────────┘
           │              │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌───▼───────┐ ┌───▼───────────┐
    │  SANCTIONS  │ │  GRAPH DB  │ │  RULES DB │ │   CHAIN       │
    │  LIST SYNC  │ │  (Neo4j)   │ │(PostgreSQL)│ │   ORACLE      │
    │  (Celery)   │ │  Port 7474 │ │  Port 5432│ │  (External)   │
    └─────────────┘ └────────────┘ └───────────┘ └───────────────┘
           │
    ┌──────▼──────┐ ┌─────────────┐ ┌───────────┐ ┌───────────────┐
    │     LLM     │ │   REVIEW    │ │   AUDIT   │ │  NOTIFICATION │
    │   SERVICE   │ │    QUEUE    │ │   TRAIL   │ │   SERVICE     │
    │  (Ollama)   │ │  (FastAPI   │ │(PostgreSQL│ │  (FastAPI)    │
    │  Port 11434 │ │  + Redis)   │ │+ S3/Minio)│ │  Port 8007    │
    └─────────────┘ └─────────────┘ └───────────┘ └───────────────┘
```

## 4.2 Docker Compose Structure

```
sanctions-system/
├── docker-compose.yml              # Orchestration
├── docker-compose.dev.yml          # Dev overrides
├── docker-compose.prod.yml         # Prod overrides
│
├── domains/
│   ├── screening-api/              # Core verdict engine
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── routers/
│   │   │   │   ├── fiat.py         # Name/country screening
│   │   │   │   └── crypto.py       # Wallet screening
│   │   │   ├── services/
│   │   │   │   ├── scorer.py       # Score aggregation
│   │   │   │   ├── cumulative.py   # Network risk scoring
│   │   │   │   └── verdicts.py     # MATCH/REVIEW/NO_MATCH
│   │   │   └── models/
│   │   └── requirements.txt
│   │
│   ├── entity-resolution/          # Name matching & deduplication
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── fuzzy/              # Phonetic, transliteration, edit-distance
│   │   │   ├── transliteration/    # Arabic/Russian/Chinese → Latin
│   │   │   └── ner/                # Named Entity Recognition (SpaCy)
│   │   └── requirements.txt
│   │
│   ├── graph-engine/               # Neo4j wrapper + UBO traversal
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── traversal.py        # Cypher query builder
│   │   │   ├── ubo.py              # UBO discovery
│   │   │   ├── clustering.py       # Community detection
│   │   │   └── risk_propagation.py # Score propagation across graph
│   │   └── requirements.txt
│   │
│   ├── regulatory-engine/          # Country-based rule sets
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── rules/
│   │   │   │   ├── ofac.py
│   │   │   │   ├── fca.py
│   │   │   │   ├── eu_aml.py
│   │   │   │   ├── fatf.py
│   │   │   │   ├── austrac.py
│   │   │   │   ├── fintrac.py
│   │   │   │   ├── dfsa.py
│   │   │   │   └── mica.py
│   │   │   ├── country_mapper.py   # Country → applicable ruleset
│   │   │   └── threshold_config.py # Per-jurisdiction thresholds
│   │   └── requirements.txt
│   │
│   ├── crypto-screener/            # Stablecoin + wallet screening
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── kyb_registry.py     # KYB-verified wallet registry (NEW)
│   │   │   ├── wallet_screen.py    # OFAC SDN wallet list match
│   │   │   ├── chain_trace.py      # On-chain hop analysis
│   │   │   ├── stablecoin/
│   │   │   │   ├── usdt_tron.py    # TRON/USDT analytics (PRIMARY RAIL)
│   │   │   │   ├── usdt_eth.py     # Ethereum/USDT analytics (SECONDARY)
│   │   │   │   ├── usdc.py         # Circle/USDC analytics (SECONDARY)
│   │   │   │   └── freeze_check.py # Blacklisted address lookup
│   │   │   └── travelrule.py       # FATF Travel Rule enforcement
│   │   └── requirements.txt
│   │
│   ├── llm-service/                # Ollama wrapper + NLP tasks
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── adverse_media.py    # News classification
│   │   │   ├── entity_extract.py   # Entity extraction from docs
│   │   │   ├── explain.py          # Score explanation generation
│   │   │   └── translate.py        # Document translation
│   │   └── requirements.txt
│   │
│   ├── list-sync/                  # Sanctions list downloader/parser
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── sources/
│   │   │   │   ├── ofac_sdn.py     # OFAC SDN XML parser
│   │   │   │   ├── ofsi.py         # UK OFSI list parser
│   │   │   │   ├── eu_consolidated.py
│   │   │   │   ├── un_list.py
│   │   │   │   └── pep_list.py     # PEP databases
│   │   │   ├── scheduler.py        # Daily sync (Celery beat)
│   │   │   └── diff_engine.py      # Delta detection, alert on changes
│   │   └── requirements.txt
│   │
│   ├── review-queue/               # Analyst workflow
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── queue.py            # Priority-sorted REVIEW queue
│   │   │   ├── assignment.py       # Analyst assignment
│   │   │   ├── decisions.py        # Decision recording
│   │   │   └── escalation.py       # Auto-escalation rules
│   │   └── requirements.txt
│   │
│   ├── audit-trail/               # Immutable audit log
│   │   ├── Dockerfile
│   │   ├── app/
│   │   │   ├── logger.py           # Write-once audit records
│   │   │   ├── export.py           # Regulatory export format
│   │   │   └── retention.py        # Jurisdiction-specific retention periods
│   │   └── requirements.txt
│   │
│   └── notification-service/      # Alerts & escalation
│       ├── Dockerfile
│       ├── app/
│       │   ├── channels/
│       │   │   ├── email.py
│       │   │   ├── slack.py
│       │   │   └── webhook.py
│       │   └── rules.py
│       └── requirements.txt
│
├── infrastructure/
│   ├── postgres/
│   │   └── init.sql
│   ├── neo4j/
│   │   └── setup.cypher
│   ├── redis/
│   │   └── redis.conf
│   ├── elasticsearch/
│   │   └── mappings.json
│   └── minio/
│       └── buckets.sh
│
└── frontend/                      # Analyst UI (React)
    ├── Dockerfile
    └── src/
```

## 4.3 Data Flow

```
Payment Instruction Received
         │
         ▼
API Gateway → Screening API
         │
         ├──→ KYB Registry Check (FIRST for all crypto transactions)
         │         ├── Is sending wallet KYB-verified platform member?
         │         ├── Is receiving wallet KYB-verified platform member?
         │         ├── UBO resolution status of both parties
         │         └── Internal-to-internal flag (reduces default risk floor,
         │               allows reduced hop-trace depth of 1 instead of 3)
         │
         ├──→ Entity Resolution Domain
         │         ├── Fuzzy name match (RapidFuzz + Phonetic)
         │         ├── Transliteration (Arabic/Russian/Chinese)
         │         └── SpaCy NER (extract entities from free text)
         │
         ├──→ List Lookup (Elasticsearch + Redis cache)
         │         ├── OFAC SDN, OFSI, EU Consolidated, UN
         │         └── PEP lists, adverse media flags
         │
         ├──→ Regulatory Engine Domain
         │         ├── Map payment corridor to applicable rules
         │         ├── Apply jurisdiction thresholds
         │         └── Country risk multiplier
         │
         ├──→ Graph Engine Domain
         │         ├── UBO traversal (Neo4j Cypher)
         │         ├── Connected entity scoring
         │         └── Cumulative cluster risk
         │
         ├──→ Crypto Screener Domain (if wallet)
         │         ├── OFAC wallet list match
         │         ├── On-chain hop tracing (depth scaled by KYB status)
         │         ├── Stablecoin freeze status
         │         └── MiCA compliance tag (EU corridors + USDT)
         │
         └──→ LLM Service Domain (if REVIEW candidate)
                   ├── Adverse media classification
                   └── Score explanation generation
         │
         ▼
  Score Aggregation → Verdict Engine
         │
         ├── MATCH → Block + Audit + Notify
         ├── REVIEW → Queue + Analyst Dashboard
         └── NO_MATCH → Release + Audit
```

---

# 5. OPEN-SOURCE LLM STRATEGY (NO PAID API)

## 5.1 Stack Decision: Ollama as Inference Server

**Ollama** runs as a local Docker container exposing an OpenAI-compatible REST API at `localhost:11434`. This means code written for OpenAI SDK works without modification — just change the base URL.

```yaml
# docker-compose.yml
llm-ollama:
  image: ollama/ollama:latest
  container_name: sanctions-ollama
  ports:
    - "11434:11434"
  volumes:
    - ollama_models:/root/.ollama
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]  # Optional: GPU acceleration
```

## 5.2 Model Recommendations by Task

| Task | Recommended Model | Size | Why |
|------|-------------------|------|-----|
| Name entity extraction from docs | `mistral:7b` | 4GB | Fast, accurate NER |
| Adverse media classification | `llama3.2:3b` | 2GB | Speed > accuracy here |
| Score explanation generation | `qwen2.5:14b` | 9GB | Best instruction-following |
| Document translation (Arabic/Russian) | `aya:8b` | 5GB | Multilingual specialist |
| Complex reasoning on suspicious patterns | `deepseek-r1:8b` | 5GB | Chain-of-thought reasoning |

**Pulling models at startup:**
```bash
# init-models.sh (runs in llm-service Dockerfile)
ollama pull mistral:7b
ollama pull llama3.2:3b
ollama pull qwen2.5:14b
ollama pull aya:8b
```

## 5.3 Where LLM Is NOT Used

LLM is deliberately avoided for:
- Real-time name matching (use RapidFuzz/ElasticSearch instead — deterministic, <50ms)
- List lookups (use Redis cache + Elasticsearch)
- Audit records (deterministic only — no LLM hallucination risk)

LLM is used for:
- Adverse media summarization and classification from news articles
- Translating foreign-language documents before entity extraction
- Generating human-readable explanations of scores for analysts
- Extracting entities from unstructured corporate documents (PDFs, filings)

## 5.4 Alternative: Hugging Face Inference (No GPU Needed)

If no GPU available, use `sentence-transformers` for embedding + `transformers` for NER:

```python
# Lightweight, CPU-only NER for entity extraction
from transformers import pipeline

ner = pipeline(
    "ner",
    model="dslim/bert-base-NER",  # 420MB, CPU-friendly
    aggregation_strategy="simple"
)
```

---

# SECTION 6 (REVISED) — SCORING ENGINE
## Two-Track Architecture: Deterministic Sanctions Gate + Explainable Risk Intelligence

> **Design principle:** Sanctions decisioning and AML risk scoring are *two different jobs* and must not be blended into one number. A block must be explainable as a discrete cause ("matched OFAC SDN entry X"), not as the output of a 7-way weighted average. Risk scoring can only **add** suspicion (escalate to REVIEW), never **subtract** it from a confirmed list hit. A missed sanctioned entity is far more costly than a false positive, so the system favours recall on detection and routes all ambiguity to a human.

---

## 6.1 The Two Tracks

### Track A — Sanctions Decision Gate (deterministic, court-dispositive)
Answers the binary, legally mandated question: *is this party on, or legally equivalent to, a list?*

- **Identity match:** fuzzy name composite (Jaro-Winkler + Levenshtein + token-sort) corroborated by secondary identifiers (DOB for individuals / registration number for entities, nationality/jurisdiction, known aliases).
- **Ownership/control rule:** OFAC **50% Rule** (and UK/EU equivalents) — an entity owned >=50% in aggregate by one or more *named* SDNs is itself blocked, even if unnamed. This is a deterministic legal rule applied over an **established** ownership chain (all percentages known; see Section 8.3), **not** fuzzy network propagation.
- **Comprehensive-sanctions jurisdiction:** The payment corridor involves a counterparty jurisdiction subject to a comprehensive or near-comprehensive international sanctions program (OFAC/OFSI/EU countermeasures — e.g., Iran, North Korea, Myanmar; see Section 9.3 BLACK tier). This is a deterministic legal prohibition encoded in the regulatory engine, not a score threshold or risk inference.

Track A alone decides MATCH via three paths: identity match, 50%-rule ownership, or comprehensive-sanctions jurisdiction. The risk score never participates in a block.

### Track B — Risk Intelligence Score (probabilistic, recall amplifier)
Answers: *of everything the lists did NOT catch, what looks suspicious enough for a human to examine?* Produces a single score `R in [0,1]` that (a) prioritises the REVIEW queue and (b) escalates list-clean cases into REVIEW. It can never reach MATCH on its own and can never lower a Track A verdict.

```
                 +-----------------------------+
  payment ------>|  TRACK A: Sanctions Gate     |-- strong identity match --> MATCH (block)
                 |  (deterministic)             |-- 50% ownership to SDN ---> MATCH (block)
                 |                              |-- partial/ambiguous match -> REVIEW
                 +-------------+----------------+
                               | no / weak list hit
                               v
                 +-----------------------------+
                 |  TRACK B: Risk Score R       |-- R >= escalation threshold -> REVIEW
                 |  (6 factors + bounded ML)    |-- else --------------------> NO_MATCH (release)
                 +-----------------------------+
   Risk score sets REVIEW priority but can only ADD suspicion, never subtract.
```

---

## 6.2 Verdict Resolution Logic

```python
def resolve_verdict(payment, entity) -> Verdict:
    A = sanctions_gate(entity)          # deterministic, Track A
    R, R_explain = risk_score(entity)   # weighted 6-factor + bounded ML, Track B

    # 1) Deterministic legal blocks (Track A only — three paths)
    if A.comprehensive_sanctions_jurisdiction:  # BLACK-tier country: full legal prohibition (see 9.3)
        return Verdict(MATCH, cause=A.country_sanctions_program, track="A:country-sanctions")
    if A.identity_confirmed:        # name >= HARD_NAME and >=1 corroborating identifier
        return Verdict(MATCH, cause=A.list_evidence, track="A:identity")
    if A.owned_50pct_by_named_sdn:  # established ownership chain >= 50%, all pcts known (see 8.3)
        return Verdict(MATCH, cause=A.ownership_path, track="A:50pct-rule")

    # 2) Ambiguous identity -> always a human, prioritised by risk
    if A.identity_partial:          # name-only, or moderate fuzzy, no corroboration
        return Verdict(REVIEW, cause=A.list_evidence, priority=R, track="A:partial")

    # 3) No list hit -> Track B is the recall net
    if R >= REVIEW_RISK_THRESHOLD:
        return Verdict(REVIEW, cause=R_explain.top_factors, priority=R, track="B:risk")

    return Verdict(NO_MATCH, priority=R)
    # INVARIANT: Track B (risk score R) can only escalate to REVIEW, never to MATCH.
    #            Three deterministic Track A paths produce MATCH:
    #              A:country-sanctions (BLACK-tier jurisdiction — Section 9.3)
    #              A:identity         (list match, confirmed corroboration)
    #              A:50pct-rule       (established >=50% ownership chain)
    #            Network/cluster association ceiling = REVIEW. Lists → MATCH.
```

**Identity thresholds (Track A), tune on demo data:**
- `name_composite >= 0.92` **AND** >=1 corroborating identifier -> MATCH
- `name_composite >= 0.85` with no corroboration, **or** `0.70-0.92` with partial corroboration -> REVIEW
- below that -> falls through to Track B (R can still pull it to REVIEW)

---

## 6.3 Track B — The Six Factors (+ Bounded ML)

Weighted linear sum, deliberately chosen because it renders as an auditable waterfall (each term's contribution is visible and additive). Weights below are the starting point; they are configurable per jurisdiction by the Regulatory Engine.

| # | Factor | Weight | Buildable in hackathon? | Court-explainability |
|---|--------|--------|--------------------------|----------------------|
| 1 | Identity match *signal* (feeds Track A; mirrored here only as a feature, not a block) | 25% | YES, real (yente) | Direct: matched list + alias + score |
| 2 | Behavioral / transaction anomaly | 20% | PARTIAL, synthetic data | Transparent rules: z-score, structuring vs. CTR thresholds |
| 3 | Network / graph exposure | 20% | YES, small synthetic graph + 1 real SDN node | Noisy-OR / decayed-path (see 6.4) |
| 4 | Entity risk profile | 15% | YES, real (metadata flags) | Deterministic flags |
| 5 | Document / onboarding integrity | 10% | NO, slide/stub | Confidence flag (ideally a multiplier — see note) |
| 6 | Historical flag rate | 10% | PARTIAL, synthetic | Beta-Binomial smoothing (see 6.5) |
| 7 | ML (LightGBM) + Isolation Forest | bounded, <=0.15 cap, supplementary | NO, roadmap/stub | SHAP per-transaction |

**Composite:**
```
R = clamp01( sum( w_i * factor_i ) )       # six factors, sum(w_i) = 1.0
R = clamp01( R + min(ml_delta, 0.15) )     # ML can only nudge, bounded, never dominates
```

**Three modelling corrections vs. the original 7-layer proposal:**

1. **Factor 1 is a gate, not a 25% weight.** A confirmed identity match is decided in Track A and forces MATCH regardless of R. Inside R it appears only as a feature so the risk view is complete; it cannot be diluted by clean factors into a non-block.
2. **Factor 5 is multiplicative on identity confidence, not additive.** If the stated identity is forged/anonymous, a name match means *less* (could be a fabricated name) — or, in context, *more* (deliberate evasion). Conceptually `effective_identity_confidence = name_score * doc_integrity`. For the hackathon, keep it as a simple flag and note the interaction as future work.
3. **Factor 7 (ML) is a parallel opinion, bounded, and must NOT re-aggregate factors 1-6.** Feeding the six factor scores into LightGBM *and* weighting them separately double-counts and corrupts the SHAP attributions. Have the model see raw/velocity/centrality features and contribute a small bounded delta. **You cannot train it in a hackathon (no labels: SAR filings, confirmed hits, reviewer decisions don't exist yet)** — present it as roadmap with the SHAP-explainability story; stub to passthrough. Isolation Forest (unsupervised, no labels) can run on synthetic features to surface novel patterns to the queue.

---

## 6.4 Network / Graph Exposure — Defensible, Not PageRank

**Why not raw personalized PageRank:** it is deterministic and reproducible, but a node's score is a property of a random walk over the *whole* graph, so you cannot cleanly attribute "entity X is risky *because of neighbor Y*." For a regulator or court you need **local, per-neighbor attribution**. Use one of the two below — both reproduce PageRank's intuition (suspicious neighbours raise risk; distant ones matter less) with clean attribution.

### Option A — Bayesian noisy-OR (recommended)
```
network_risk(e) = 1 - product over f of [ 1 - p_f * lambda^d(e,f) ]
```
- `f` = flagged neighbour (confirmed sanctioned, or itself in REVIEW)
- `p_f` = taint/confidence of `f` (1.0 for a confirmed SDN node)
- `lambda = 0.5` per-hop decay; `d(e,f)` = shortest-path hops, capped at 3
- Reads as: *"the probability that at least one tainted neighbour contaminated e."* Bounded [0,1], monotonic. Per-neighbour marginal contribution = leave-one-out recompute (drives the explanation panel).

### Option B — Deterministic decayed-path taint
```
contribution_f = taint(f) * lambda^d(e,f) * volume_weight(edge)
network_risk(e) = min(1, sum over f of contribution_f)     # or max_f for single-path attribution
```
Draw the exact path and show the arithmetic. Cleanest for a courtroom slide; use `max` if you want strict single-cause attribution, `sum` to capture cumulative exposure.

**Worked example (noisy-OR):** entity `e` is 1 hop from confirmed SDN `S` (`p=1.0`) and 2 hops from a REVIEW entity `M` (`p=0.6`):
```
network_risk = 1 - (1 - 1.0*0.5^1) * (1 - 0.6*0.5^2)
             = 1 - (0.5) * (0.85) = 1 - 0.425 = 0.575
```
-> contributes to R; on its own this maps to **REVIEW** for a human, not a block.

**Two hard guardrails (defensibility):**
- **Association -> REVIEW, never autonomous MATCH.** A clean entity with dirty neighbours is *examined*, not convicted. The graph layer's ceiling for a list-clean entity is REVIEW.
- **The only graph path to MATCH is the deterministic 50% Rule** (Track A), where ownership >=50% by a *named* SDN is established — a legal rule, not a fuzzy inference. Keep it entirely separate from noisy-OR.

This replaces the original plan's Louvain-community + quadratic-amplifier escalation, which lacked per-entity attribution and allowed clusters to auto-escalate to MATCH.

---

## 6.5 Historical Flag Rate — Beta-Binomial Smoothing

```
smoothed_rate(e) = (k_true + alpha) / (n_screen + alpha + beta)
```
- `n_screen` = prior screenings of `e`; `k_true` = prior **confirmed-true** flags
- `alpha, beta` = prior pseudo-counts (e.g. `alpha=1, beta=9` -> 10% baseline prior; small counts pull toward baseline, large counts dominate)
- Confirmed **false positives** feed a separate *mild downward* behavioral-sensitivity adjustment (alert-fatigue reduction), not an upward risk term.

**Example:** 40 screenings, 1 confirmed true hit -> `(1+1)/(40+10) = 0.04`.

**Guardrails:** (1) never reduces a Track A sanctions hit; (2) "reward clean history" is gameable by a patient actor who builds a benign record before transacting illicitly — document this limitation and keep the downward adjustment small and bounded; (3) the smoothing is fully transparent and reproducible — show the fraction.

---

## 6.6 What You Show a Court (per-factor evidence map)

| Factor | The exact sentence in the audit record |
|--------|----------------------------------------|
| Identity (Track A) | "Blocked: name 'V. Putin' matched OFAC SDN alias 'Vladimir Vladimirovich Putin' at Jaro-Winkler 0.93, corroborated by DOB 1952-10-07. List version 2026-06-12." |
| 50% Rule (Track A) | "Blocked: recipient owned 60% by named SDN via chain X->Y->[SDN]; ownership established from UK PSC + OpenCorporates. All chain percentages confirmed." |
| Country-sanctions (Track A) | "Blocked: payment corridor involves Iran — subject to comprehensive OFAC/OFSI/EU countermeasures (Track A:country-sanctions, BLACK tier). Legal basis: OFAC Iran NSRP program. Score irrelevant." |
| Behavioral | "12 transfers of $9,800 over 30 days, each below the $10,000 CTR threshold — structuring pattern; amount z-score 3.1 vs. own baseline." |
| Network | "Risk 0.58: 1 hop from confirmed SDN address Z (noisy-OR). Path shown. Routed to REVIEW — not blocked on association alone." |
| Entity profile | "Flags: FATF grey-list jurisdiction; incorporated 2 months ago; registered at agent address; no PSC filed." |
| Historical | "Beta(1,9)-smoothed prior flag rate 0.04 over 40 screenings; no upward adjustment." |
| ML | "LightGBM bounded delta +0.06; top SHAP features: counterparty novelty, velocity spike. Supplementary only." |

Every decision is logged with **who / what / when / why**, the **algorithm + version**, and the **list version/date in force at decision time** (so the verdict is reconstructible years later, >=5-year retention).

---

## 6.7 Hackathon Build vs. Pitch Split (scoring only)

- **Build for real:** Track A identity gate on OpenSanctions/yente; entity-profile flags (factor 4); network noisy-OR over a **small synthetic graph containing one real OFAC-sanctioned node** (this is the visual demo centerpiece and tells the recall story); the verdict-resolution logic; the waterfall + path-attribution explanation.
- **Synthetic-data demo:** behavioral anomaly (factor 2) and historical flag rate (factor 6) on a fabricated transaction history for 2-3 demo entities.
- **Slide / roadmap only:** LightGBM + SHAP (factor 7) and document integrity (factor 5). Do not train anything.
- **Never cut:** the two-track separation, the audit record, and the "association -> REVIEW, lists -> MATCH" story. These are what make the pitch defensible.

**The pitch sentence:** *"Lists give us precision on blocks. The risk graph gives us recall on everything lists miss. The human queue absorbs the difference — and every decision is attributable to a discrete, reproducible cause we can defend two years later."*

---

# 7. SCORE EXPLANATION GRAPH (EXPLAINABILITY LAYER)

Every verdict must produce a human-readable, regulator-defensible explanation. This is built as a DAG (Directed Acyclic Graph) of contributing factors.

## 7.1 Score Tree Structure

```json
{
  "verdict": "REVIEW",
  "composite_score": 0.64,
  "entity_id": "ENT-20240613-8821",
  "entity_type": "business",
  "explanation_tree": {
    "root": {
      "label": "Composite Risk Score",
      "score": 0.64,
      "threshold_context": "REVIEW threshold: 0.50",
      "children": [
        {
          "label": "Identity Match Signal",
          "score": 0.71,
          "weight": 0.25,
          "weighted_contribution": 0.178,
          "detail": "Entity name 'Al-Qadir Trading LLC' matches alias 'Al Qadir Trade (LLC)' on EU Consolidated List — mirrored from Track A as a Track B feature signal only; the list match itself is adjudicated in Track A",
          "match_method": "phonetic + edit_distance",
          "edit_distance": 3,
          "children": [
            {
              "label": "OFAC SDN",
              "score": 0.12,
              "detail": "No match found"
            },
            {
              "label": "EU Consolidated List",
              "score": 0.71,
              "detail": "Alias match at 71% confidence",
              "list_entry_id": "EU-2023-0084-ENTITY"
            },
            {
              "label": "UN List",
              "score": 0.05,
              "detail": "No significant match"
            }
          ]
        },
        {
          "label": "Behavioral / Transaction Anomaly",
          "score": 0.60,
          "weight": 0.20,
          "weighted_contribution": 0.120,
          "detail": "Transaction velocity 2.1× above entity baseline over 30 days; 4 transfers clustered just below $10,000 CTR threshold — structuring pattern. z-score 2.8 vs. own history."
        },
        {
          "label": "Network / Graph Exposure",
          "score": 0.58,
          "weight": 0.20,
          "weighted_contribution": 0.116,
          "detail": "noisy-OR score 0.58: 1 hop from REVIEW entity ENT-8820 (p=0.6, λ^1=0.5 → contribution 0.30); 2 hops from confirmed SDN (p=1.0, λ^2=0.25 → contribution 0.25). Leave-one-out attribution in network panel. Routed to REVIEW — not blocked on association alone.",
          "score_formula": "1 - (1 - 0.6×0.5¹) × (1 - 1.0×0.5²) ≈ 0.58 after edge-weight adjustment"
        },
        {
          "label": "Entity Risk Profile",
          "score": 0.80,
          "weight": 0.15,
          "weighted_contribution": 0.120,
          "detail": "UAE jurisdiction (FATF grey-list monitoring, ×1.35 country-risk multiplier applied within this sub-score). UBO: Ahmad Khalid Mansour verified; secondary UBO unresolved at depth 3 → PARTIAL status. Registered at agent address; incorporated 8 months ago. Adverse media: 2 articles (Reuters 2024-03-12, Al Arabiya 2022-11-05), LLM relevance 0.67/0.44.",
          "ubo_resolution_status": "PARTIAL",
          "ubo_chain_depth": 2,
          "corporate_risk_flags": ["registered_agent_address", "age_under_6_months"],
          "country_risk_multiplier": 1.35
        },
        {
          "label": "Document / Onboarding Integrity",
          "score": 0.60,
          "weight": 0.10,
          "weighted_contribution": 0.060,
          "detail": "Uploaded certificate of incorporation unverifiable against UAE registry; registered address differs from stated operating address"
        },
        {
          "label": "Historical Flag Rate",
          "score": 0.46,
          "weight": 0.10,
          "weighted_contribution": 0.046,
          "detail": "Beta(1,9)-smoothed prior flag rate 0.046 over 40 screenings; 1 prior confirmed true hit. No upward adjustment to Track A verdict."
        }
      ]
    },
    "network_context": {
      "neighbourhood_id": "NET-2024-0071",
      "neighbour_count": 2,
      "network_risk_score": 0.58,
      "connected_entities": [
        {"id": "ENT-8819", "score": 0.58, "shared_attribute": "registered_address", "hop_distance": 1},
        {"id": "ENT-8820", "score": 0.61, "shared_attribute": "director_id", "hop_distance": 1}
      ],
      "network_escalation_applied": true,
      "escalation_reason": "noisy-OR network risk 0.58 from 2 connected REVIEW entities at 1 hop (λ=0.5); queue priority elevated — verdict class unchanged (REVIEW)"
    }
  }
}
```

> **Note on `ubo_resolution_status`:** This field is surfaced in the Entity Risk Profile factor node's metadata (which consolidates UBO flags, country-risk multiplier, and corporate risk signals as a combined sub-score) and as a top-level flag in the verdict output. UNRESOLVED status triggers a mandatory REVIEW override regardless of the numeric score — an entity whose beneficial ownership cannot be traced is treated equivalently to an anonymous counterparty. See Section 8.6. Country risk is applied as a multiplier within the Entity Risk Profile sub-score, not as a separate additive factor in the waterfall.

## 7.2 Visualization (Frontend)

The score tree renders as an interactive force-directed graph in the analyst UI:

- **Root node** (large circle): composite score, colored by verdict
- **Factor nodes** (medium circles): each scoring component
- **List nodes** (small circles): individual list check results
- **Network cluster panel**: adjacent panel showing connected entity subgraph
- **Hover**: shows exact score, weight, contribution, and data source
- **Drill-down**: click any node to see raw evidence

---

# 8. BUSINESS/UBO LAYER — CORPORATE OWNERSHIP ENGINE

## 8.1 The Shell Company Problem

A typical sanctioned entity structure:

```
[Actual Sanctioned Person: Ivan Petrov]
         │
         ▼
[BVI Holding: Meridian Global Ltd]
         │
         ▼
[Cyprus SPV: Aldgate Finance Services]
         │
         ▼
[UK Ltd: Thames Import Solutions]
         │
         ▼
[Sokin payment instruction sent by: Thames Import Solutions]
```

No individual hop triggers a match. The graph traversal does.

## 8.2 Data Sources for UBO Discovery

| Source | What It Provides | Access |
|--------|-----------------|--------|
| UK Companies House | Director/shareholder data for UK Ltd | Free API |
| OpenCorporates | Global company registry aggregator | Free (limited) / Paid |
| OpenOwnership Register | Beneficial ownership from PSC filings | Free download |
| EU Business Registers (EBR) | EU-wide company data | Free (varies by country) |
| GLEIF (LEI) | Legal Entity Identifier global database | Free |
| ICIJ Offshore Leaks | Panama Papers, Pandora Papers, Offshore Leaks DB | Free download |
| OCCRP Aleph | Document + entity search | Free API |

## 8.3 UBO Resolution Algorithm

```python
class UBOResolver:
    def resolve(self, entity_id: str, max_depth: int = 8) -> UBOResult:
        """
        Traverse ownership graph up to max_depth layers.
        Returns identified UBOs with confidence and path.
        """
        cypher = """
        MATCH p=(start:Entity {id: $entity_id})-[:OWNED_BY|CONTROLLED_BY*1..{max_depth}]->(ubo:Person)
        WHERE NOT (ubo)-[:OWNED_BY|CONTROLLED_BY]->()
          AND all(r in relationships(p) WHERE r.ownership_pct IS NOT NULL)
        RETURN p, ubo,
               reduce(pct = 1.0, r in relationships(p) |
                   pct * r.ownership_pct) as effective_ownership
        ORDER BY effective_ownership DESC
        """.format(max_depth=max_depth)
        # NOTE: chains where any r.ownership_pct IS NULL are intentionally excluded.
        # The 50%-rule is a deterministic legal block that requires ESTABLISHED ownership
        # percentages (Section 6.1). A chain with unknown percentages cannot satisfy
        # "owned >= 50%"; it is treated as UNESTABLISHED and routed to REVIEW instead.
        # coalesce(r.ownership_pct, 0.5) was removed — guessing 0.5 can fabricate or
        # destroy a >=50% aggregate and must not feed a deterministic block.
        
        results = self.neo4j.query(cypher, entity_id=entity_id)
        return self._build_ubo_result(results)
```

> **UBO depth parameters — reconciliation:** The resolver's `max_depth=8` is the maximum traversal depth; it does not guarantee resolution at that depth. The mandatory activation gate (Section 8.6) requires resolution within 4 hops — an entity unresolved at depth 4 is flagged UNRESOLVED regardless of whether a UBO might exist at hops 5–8 (deeper opaque chains are themselves a risk signal, not a reason to keep searching). Depth references of 3 in worked examples (Sections 7.1, CD-06) are illustrative of typical chain lengths, not system limits.

## 8.4 Circular Ownership Detection

```cypher
// Detect circular ownership (common in shell company abuse)
MATCH p=(e:Entity)-[:OWNED_BY*2..10]->(e)
RETURN e, p
```

## 8.5 Scoring Corporate Risk Factors

```python
CORPORATE_RISK_SIGNALS = {
    "age_under_6_months": +0.15,          # Brand new entity
    "nominee_director": +0.20,             # Nominee service detected
    "registered_agent_address": +0.10,     # Registered at agent (not real office)
    "multiple_jurisdictions": +0.08,       # Holds entities in 3+ countries
    "circular_ownership_detected": +0.35,  # Circular ownership loop
    "bvi_cayman_offshore": +0.15,          # Offshore jurisdiction in chain
    "ubo_depth_over_4": +0.12,             # Deep ownership chain
    "dissolved_entity_in_chain": +0.18,    # Prior dissolved entity same directors
    "psc_missing": +0.22,                  # UK: no PSC filed (legal requirement)
    "icij_mention": +0.30,                 # Appears in ICIJ Offshore Leaks database
    "ubo_unresolved": +0.40,               # UBO chain cannot be established (hard signal)
    "kyb_wallet_ubo_mismatch": +0.25,      # Wallet UBO differs from onboarding UBO
}
```

## 8.6 KYB-Specific UBO Mandatory Verification Gate

**Under a KYB-only policy, UBO resolution is not optional — it is the primary identity check.** The business entity itself is not the risk subject; the beneficial humans controlling it are. The system must enforce a hard gate at onboarding: no business account is activated until at least one UBO is identified, verified, and screened against all applicable sanctions lists. If UBO cannot be established beyond a configurable depth (default: 4 hops), the account is held in mandatory review regardless of entity-level score.

This is particularly relevant for TRON-based USDT accounts, where a shell company could otherwise establish a verified wallet with an opaque ownership chain.

**UBO Resolution Status** is a first-class field on every onboarded entity:

```python
class UBOResolutionStatus(str, Enum):
    FULL = "FULL"           # All UBOs identified, verified, screened — account activated normally
    PARTIAL = "PARTIAL"     # ≥1 UBO identified and screened; ≥1 UBO remains unclear — account activated under enhanced monitoring (see table below)
    UNRESOLVED = "UNRESOLVED"  # UBO chain cannot be traced at all — activation blocked, mandatory REVIEW until resolved
```

**Activation policy by UBO resolution status:**

| Status | Account activation | Transaction limits | Ongoing monitoring |
|---|---|---|---|
| FULL | Immediate | Standard tier | Standard periodic review |
| PARTIAL | Permitted | Reduced (configurable; default 50% of standard tier) | Enhanced — every transaction screened; quarterly re-verification of outstanding UBOs required |
| UNRESOLVED | Blocked | N/A | Held in mandatory REVIEW queue; activation only after resolution to FULL or PARTIAL |

This reconciles the two activation rules in the document: the gate in Section 8.6 ("at least one UBO identified, verified, and screened") is satisfied by PARTIAL status, and Section 11.5 ("Account activated only on FULL or PARTIAL UBO status") reflects the same policy. UNRESOLVED is the only status that blocks activation outright.

The KYB wallet registry (Section 10.3 Step 1b) tags each wallet with its UBO resolution status. UNRESOLVED wallets are treated equivalently to anonymous external wallets for screening purposes, even when they are nominally platform members.

**KYC Extension Note:** When KYC onboarding is activated in a future phase, this gate adapts as follows: instead of UBO chain resolution, the gate checks biometric verification status and identity document validation. The resolution status enum (`FULL` / `PARTIAL` / `UNRESOLVED`) is reused with the same downstream logic — no new verdict paths are required.

---

# 9. REGULATORY ENGINE — COUNTRY-BASED RULE SYSTEM

## 9.1 Architecture

The regulatory engine is a **pluggable rule system** where each jurisdiction is a Python module implementing a standard interface:

```python
class JurisdictionRule(ABC):
    @abstractmethod
    def applies_to(self, payment: Payment) -> bool:
        """Does this rule apply to this payment corridor?"""
    
    @abstractmethod
    def get_screening_requirements(self) -> ScreeningRequirements:
        """What must be screened, and to what depth?"""
    
    @abstractmethod
    def get_score_thresholds(self) -> ScoreThresholds:
        """MATCH/REVIEW/NO_MATCH thresholds for this jurisdiction."""
    
    @abstractmethod
    def get_required_lists(self) -> List[SanctionsList]:
        """Which lists must be checked (mandatory vs recommended)."""
    
    @abstractmethod
    def get_retention_period_days(self) -> int:
        """How long audit records must be kept."""
```

## 9.2 Key Jurisdiction Rules

### US (OFAC/FinCEN)
- **Lists**: OFAC SDN, OFAC Consolidated (all programs), BIS Entity List
- **Threshold**: Near-zero tolerance; even 50% ownership by SDN entity = block
- **Crypto**: OFAC publishes sanctioned wallet addresses — direct match = hard block
- **Travel Rule**: FinCEN requires VASPs to pass sender/receiver info for transfers >$3,000
- **SAR**: Mandatory Suspicious Activity Report to FinCEN within 30 days of detection
- **Retention**: 5 years

### UK (FCA/OFSI)
- **Lists**: UK Sanctions List (post-Brexit independent list), OFSI consolidated
- **Threshold**: FCA SYSC 6.3 requires "appropriate" systems — no single threshold defined
- **Reporting**: Mandatory reporting to OFSI within days of knowledge of breach
- **PEP**: Enhanced Due Diligence mandatory for all PEPs; domestic PEPs treated same as foreign
- **Retention**: 5 years (MLRO records)

### EU (EBA/AMLA/MiCA)
- **Lists**: EU Consolidated Sanctions List, EU Terrorism list, UN List
- **MiCA** (since Dec 2024): Stablecoin issuers must implement sanctions screening; 6th AMLD applies
- **MiCA Article 48 — USDT specifically:** Tether (USDT) is not MiCA-authorized as of mid-2026, as Tether Ltd has not obtained an e-money token authorization from an EU competent authority. EU-regulated entities processing USDT payments for business customers therefore operate in a grey zone. The regulatory engine flags any USDT transaction involving an EU-corridor counterparty with a dedicated `MiCA_COMPLIANCE_RISK` tag in the verdict metadata — distinct from the sanctions score — prompting legal review rather than automatic block. USDC (Circle, MiCA-authorized) does not carry this flag for EU corridors.
- **AMLA** (new 2025): Single EU AML supervisory authority; harmonized thresholds coming
- **Travel Rule**: FATF Travel Rule implemented via TFR (Transfer of Funds Regulation) — all crypto transfers require originator/beneficiary data
- **PEP**: 18-month lookback after leaving office
- **Retention**: 5 years (10 for high-risk)

### TRON Network (Protocol-Level Policy Rule)
While not a jurisdiction, TRON's dominance in USDT settlement means the regulatory engine treats TRON-settled transactions as carrying an additional due diligence flag for EU and UK corridors, given Tether's unresolved MiCA authorization status. This is a **business-policy rule**, not a sanctions rule, and lives in the regulatory engine's policy layer (`tron_corridor_policy.py`) rather than the scoring engine. The flag surfaces in the analyst dashboard as an informational tag (`TRON_EU_CORRIDOR_REVIEW`) and does not independently alter the numeric score.

### UAE (DFSA/CBUAE)
- **Lists**: UAE Local Terrorist Designation List, OFAC, UN
- **DFSA**: Requires FI to screen against all international lists; high-risk jurisdiction treatment for Iran, North Korea, Russia
- **Crypto**: VARA (Virtual Asset Regulatory Authority) requires VASP licensing and screening
- **Stablecoins**: Subject to Payment Token regulation under CBUAE

### Australia (AUSTRAC/ASIC)
- **Lists**: DFAT Consolidated List (Australian autonomous sanctions)
- **AML/CTF Act 2006**: Mandatory program, threshold transactions reporting (AUD 10,000+)
- **AUSTRAC**: Real-time reporting for suspicious matters; no de minimis exemption for sanctions
- **Crypto**: Designated Service; AUSTRAC registration mandatory for all digital currency exchanges

### Canada (FINTRAC)
- **Lists**: OSFI Consolidated List, UN List
- **PCMLTFA**: Proceeds of Crime Act — mandatory EDD for high-risk
- **FINTRAC**: Large cash transaction reports (CAD 10,000+); suspicious transaction reports
- **Data retention**: 5 years; this is the law Sokin cited when refusing UK user data deletion requests (technically correct for Canadian customers)

## 9.3 Country Risk Tiers (FATF-Based)

```python
COUNTRY_RISK_TIERS = {
    "BLACK": {  # FATF Call to Action / Comprehensive sanctions
        "countries": ["Iran", "North Korea", "Myanmar"],
        "score_multiplier": 2.0,
        "auto_block": True,  # Track A deterministic legal block (A:country-sanctions) — not a score override; see Sections 6.1 and 6.2
        "description": "Subject to comprehensive countermeasures — payment block is a Track A legal rule, score irrelevant"
    },
    "GREY": {  # FATF Enhanced Follow-up / Monitoring
        # Updated June 2026 — Bulgaria and Croatia removed (EU members, exited 2023)
        # Venezuela removed from GREY — it also appeared in HIGH_RISK (duplicate); HIGH_RISK retained
        # as the primary classification (active OFAC SDN programs, sectoral sanctions).
        "countries": [
            "Burkina Faso", "Cameroon",
            "Democratic Republic of Congo", "Haiti", "Kenya",
            "Mali", "Mozambique", "Nigeria", "Philippines",
            "Senegal", "South Africa", "Syria", "Tanzania",
            "Vietnam", "Yemen"
        ],
        "score_multiplier": 1.35,
        "auto_block": False,
        "description": "Enhanced monitoring required"
    },
    "HIGH_RISK": {  # Not FATF-listed but jurisdictionally risky
        "countries": ["Russia", "Belarus", "Cuba", "Venezuela"],
        "score_multiplier": 1.50,
        "auto_block": False,
        "description": "Sectoral/comprehensive sanctions programs active"
    },
    "OFFSHORE": {  # Tax/secrecy jurisdictions
        "countries": [
            "British Virgin Islands", "Cayman Islands", "Seychelles",
            "Panama", "Belize", "Vanuatu", "Marshall Islands"
        ],
        "score_multiplier": 1.20,
        "auto_block": False,
        "description": "Elevated anonymity risk; deeper UBO check required"
    }
}
```

> **Maintenance note:** FATF grey list is re-assessed every 4 months (February, June, October plenary). The `GREY` country list must be treated as a living configuration — store in YAML and include a migration/update script triggered by the list-sync service. The previous version of this document incorrectly included Bulgaria and Croatia; both are EU members that exited the grey list in 2023.

---

# 10. STABLECOIN & CRYPTO COMPLIANCE ENGINE

## 10.1 Primary Rail: TRON/USDT — Why Stablecoins Are Traceable

**USDT on TRON is the primary payment rail for this platform.** Ethereum and Solana are secondary. The screening priority order is: (1) TRON/USDT, (2) Ethereum/USDT and USDC, (3) Solana/USDC, (4) Base and Arbitrum/USDC. Chain-specific screener instances are weighted accordingly in the Celery task queue, with the TRON screener allocated the highest throughput budget.

TRON dominates USDT cross-border volume — approximately 70%+ of global USDT transfers settle on TRON due to near-zero fees and fast finality (~3 second block time). This makes it the preferred rail for the business payment use case the platform targets.

Stablecoins run on public blockchains with permanent, immutable transaction records:

- **USDT on TRON** — Tether's primary high-volume chain. Tether maintains freeze capability via the `addBlackList` function on the TRC-20 contract. Full on-chain history is publicly available via Tronscan API.
- **USDT on Ethereum** — Tether's original chain. Same freeze capability. Lower volume than TRON for cross-border payments due to gas costs.
- **USDC** (Circle) — primarily Ethereum, Solana, Base, Arbitrum. Circle can freeze addresses at regulator request. MiCA-authorized for EU corridors.

**Key compliance advantage of KYB-only policy:** Because every counterparty that is a registered platform member has a verified wallet address recorded at KYB onboarding, the wallet-to-entity mapping problem is largely solved for internal transfers. The hop-tracing logic starts with a known, attributed address on both sides — not an anonymous wallet. This materially raises attribution confidence and reduces false positive rates from hop analysis, which in non-KYB systems frequently penalizes wallets simply because the counterparty is unknown.

**Key traceability advantage of public blockchains:** Every transaction hop is auditable retroactively. A chain trace from a suspicious wallet can reveal connections that name-based screening misses entirely. Unlike fiat, there is no expiry on blockchain history — a transaction from 2019 is as visible today as one from yesterday.

## 10.2 Pre-Execution vs Post-Hoc Screening

| Approach | When | Risk |
|----------|------|------|
| Post-hoc logging | After settlement | Cannot reverse USDT on TRON; SAR is too late |
| **Pre-execution screening** | Before signing/broadcasting | Block before settlement — only viable approach |

**KYB advantage for pre-execution:** Since the sending wallet is registered to a KYB-verified entity, pre-execution screening can draw on the entity's full compliance profile (UBO status, historical flag rate, entity risk score) in addition to wallet-level signals. This is not possible in a consumer/KYC model where the wallet may only be linked to an individual at account level.

## 10.3 Wallet Screening Architecture

```python
class StablecoinScreener:
    
    def screen_wallet(
        self,
        address: str,
        chain: str,
        counterparty_address: str = "",
        corridor: str = "",
    ) -> WalletScreenResult:
        result = WalletScreenResult(address=address, chain=chain)
        result.is_internal = False   # default; overridden below if both parties are KYB-verified
        result.corridor = corridor   # passed in by the caller from the payment instruction
        
        # Step 1b: KYB Registry Lookup (FIRST — run before any external check)
        # Is this address a known KYB-verified platform member?
        result.kyb_verified = self.kyb_wallet_registry.lookup(address)
        if result.kyb_verified:
            # Attribution is already known; skip Step 4 (WalletAttributor)
            # Reduce hop-trace depth to 1 for internal-to-internal transfers
            # Apply internal risk floor reduction (entity profile already screened at onboarding)
            result.is_internal = self.kyb_wallet_registry.is_internal_pair(
                address, counterparty_address  # counterparty_address is a method parameter, not a result field
            )
            result.ubo_status = result.kyb_verified.ubo_resolution_status
            if result.ubo_status == UBOResolutionStatus.UNRESOLVED:
                # Even platform members with unresolved UBO get full external treatment
                result.kyb_verified = None  # downgrade to external path
                result.is_internal = False   # reset — UNRESOLVED UBO must use hop depth 3 (external)
                # This matches the CC-05 spec: is_internal_pair() returns False for UNRESOLVED UBO status.
                # Without this reset, is_internal stays True (set above) and hop_depth stays 1,
                # contradicting the "full external treatment" comment and the CC-05 KYBWalletRegistry spec.
        
        # Step 1: OFAC SDN wallet list (instant, < 10ms)
        result.ofac_match = self.ofac_wallet_db.lookup(address)
        
        # Step 2: Issuer blacklist check (Circle/Tether)
        result.issuer_frozen = self.check_issuer_blacklist(address, chain)
        
        # Step 3: On-chain hop analysis
        # Depth: 1 hop for verified internal pairs, 3 hops for all external counterparties
        hop_depth = 1 if result.is_internal else 3
        result.hop_analysis = self.trace_hops(address, chain, max_hops=hop_depth)
        
        # Step 4: Attribution (skipped for KYB-verified internal addresses)
        if not result.kyb_verified:
            result.attribution = self.wallet_attributor.lookup(address)
        
        # Step 5: Volume anomaly (sudden large inflows from unknown addresses)
        result.volume_anomaly = self.detect_volume_anomaly(address, chain)
        
        # Step 6: MiCA compliance tag (EU corridors + USDT only)
        result.mica_flag = self.check_mica_compliance(address, chain, result.corridor)
        
        return result
    
    def trace_hops(self, address: str, chain: str, max_hops: int) -> HopAnalysis:
        """
        BFS traversal of on-chain transaction graph.
        Score degrades by 0.3 per hop (linear schedule):
        - Direct connection to sanctioned address: score = 1.0
        - 1 hop away: score = 0.7
        - 2 hops away: score = 0.4
        - 3 hops away: score = 0.1

        Note: this uses a linear −0.3/hop decay, intentionally distinct from the
        geometric 0.5^d decay used in the graph-engine noisy-OR (Section 6.4).
        On-chain hops are direct confirmed fund flows (each hop is a real transaction),
        warranting a shallower, more aggressive decay than the probabilistic contamination
        model applied to ownership/shared-attribute graphs where the link type is softer.

        For TRON: use Tronscan API (primary).
        For Ethereum: use Etherscan API (secondary).
        Stop traversal when total value traced < $1,000 (de minimis).
        Cache results in Redis with 24h TTL.
        """
        ...
    
    def check_mica_compliance(self, address: str, chain: str, corridor: str) -> MiCAFlag:
        """
        Returns MiCA_COMPLIANCE_RISK tag for USDT transfers on any EU corridor.
        USDC on EU corridors returns None (MiCA-authorized).
        This is a policy flag, not a score modifier.
        """
        ...
```

## 10.4 Open-Source Blockchain Data Sources

| Tool | Data | Chain | License |
|------|------|-------|---------|
| **Tronscan API** | TRON transactions (USDT primary) | TRON | Free |
| **Etherscan API** | Ethereum transactions | Ethereum | Free tier: 5 req/sec |
| **Solscan API** | Solana (USDC-dominant) | Solana | Free |
| **OFAC SDN Crypto Addresses** | Sanctioned wallets (all chains) | Multi | Public |
| **OSINT Industries** | Wallet attribution (community) | Multi | Free/OSS |
| **Rotki** | Open-source blockchain analytics | Multi | AGPL-3.0 |
| **Breadcrumbs** | Free on-chain graph explorer | Multi | Free web tool |

## 10.5 FATF Travel Rule for Stablecoins

Travel Rule thresholds differ by jurisdiction. Both values cited elsewhere in this document are correct but jurisdiction-specific — they are not contradictory:

| Jurisdiction | Travel Rule threshold | Legal basis |
|---|---|---|
| **US** | USD 3,000 | FinCEN Bank Secrecy Act (31 CFR § 103.33) |
| **EU** | EUR 0 (all transfers) | EU Transfer of Funds Regulation (TFR 2023/1113), full originator/beneficiary data required regardless of amount |
| **UK** | GBP 0 (all transfers) | UK Wire Transfer Regulations 2017 (post-Brexit retained) |
| **Most other FATF members** | USD/EUR 1,000 | FATF Recommendation 16 (as locally transposed) |
| **Australia** | AUD 1,000 | AUSTRAC AML/CTF Rules |
| **Canada** | CAD 1,000 | FINTRAC Proceeds of Crime Act |

The `get_threshold(transfer.originator_country)` call in `TravelRuleEnforcer` must resolve to the correct per-jurisdiction value from this table (stored in `threshold_config.py`), not a single global constant.

For transfers above the applicable jurisdiction threshold:

```python
class TravelRuleEnforcer:
    def enforce(self, transfer: StablecoinTransfer) -> TravelRuleResult:
        if transfer.amount_usd < self.get_threshold(transfer.originator_country):
            return TravelRuleResult(required=False)
        
        required_data = TravelRuleData(
            originator_name=transfer.originator.full_name,
            originator_account=transfer.originator_wallet,
            originator_address=transfer.originator.address,
            beneficiary_name=transfer.beneficiary.full_name,
            beneficiary_account=transfer.beneficiary_wallet,
        )
        
        # Check if receiving VASP supports Travel Rule protocol
        # (TRUST, OpenVASP, Notabene, Sygna)
        vasp_support = self.vasp_registry.lookup(transfer.beneficiary_vasp)
        
        if not vasp_support.travel_rule_enabled:
            return TravelRuleResult(
                required=True,
                compliant=False,
                action="BLOCK_OR_REVIEW",
                reason="Beneficiary VASP does not support Travel Rule data exchange"
            )
```

**KYB advantage for Travel Rule:** Because all platform-side originators are KYB-verified businesses, the originator data fields (legal name, registered address, LEI or registration number) are always available and pre-validated. The Travel Rule data packet is generated from the KYB record, not collected ad hoc at transaction time. This eliminates a common compliance gap where Travel Rule data is incomplete or self-reported.

---

# 11. HOW STABLE CRYPTO BANKS WORK — REFERENCE ARCHITECTURE

## 11.1 How Circle (USDC Issuer) Works

Circle holds 1:1 USD reserves in US Treasuries and cash equivalents. They:
- Issue USDC to licensed VASPs via Circle Account
- Maintain a blacklist (Ethereum `isBlacklisted` function in USDC contract)
- Can call `blacklist(address)` to prevent any future transfers
- Can call `destroyBlackFunds(address)` to burn frozen USDC

Compliance hook: If our system flags a wallet, we can request Circle to freeze it. But this takes hours/days — hence pre-execution screening is critical.

## 11.2 How Tether (USDT Issuer) Works — Primary Rail

Tether operates the largest stablecoin by volume across TRON, Ethereum, and BSC:
- Issues USDT against reserves (subject to ongoing transparency debates)
- Maintains a blacklist on both TRON (`addBlackList`) and Ethereum (`addBlackList`) contracts
- Can freeze addresses but **governance and response time are less transparent than Circle**
- Does not hold MiCA authorization as of mid-2026 for EU issuance
- TRON contract address: `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`

**Critical operational implication:** Tether's freeze mechanism works similarly to Circle's but with slower and less predictable response times. For a KYB-only platform where each wallet is tied to a verified business, a Tether freeze on a customer wallet is a business-impacting event, not just a compliance event. See Section 11.4.

## 11.3 How Payments Banks Like Modulr (Sokin's EMI Partner) Work

Modulr Finance B.V. (Sokin's EU licensed partner):
- Holds e-money license from DNB (Dutch Central Bank)
- Safeguards client funds in segregated accounts (not on balance sheet)
- Provides Sokin with account issuance, payment rail access (SEPA, SWIFT)
- Runs its own AML/sanctions screening; Sokin must also run its own
- Double screening creates false positive risk (both systems must agree to clear)

## 11.4 Operational Implications of Tether Freeze Risk for KYB Customers

Unlike the consumer/KYC model where a frozen wallet affects an individual, a Tether freeze on a KYB customer wallet directly disrupts that business's payment operations. The platform must manage two distinct risks:

**Risk 1 — Regulatory reconstruction risk:** If Tether subsequently freezes an address that transacted through the platform, regulators may query whether the platform identified the risk before processing. To protect against this inference, the system maintains a **freeze_risk_register** — a Redis set of wallet addresses that have received any non-zero screening flag in the last 90 days. If Tether subsequently freezes an address in this register, the platform has a documented prior-screening record demonstrating it identified the risk.

**Risk 2 — Customer business disruption:** A freeze on a KYB-verified customer wallet freezes that business's USDT holdings without immediate recourse. The platform should maintain a documented escalation path to Tether for KYB customers (business-level freeze dispute), distinct from the individual consumer path.

**Audit trail requirement:** The audit-trail domain (Section 4) logs every screening decision against a wallet address with the wallet address as a **primary index key** in addition to the entity ID. This enables full reconstruction of the screening history for any wallet address, independently of the entity record — which is critical when a wallet changes beneficial ownership or is reassigned.

```python
# Audit record primary keys — wallet-indexed in addition to entity-indexed
audit_record = {
    "wallet_address": "TXxx...",          # PRIMARY index for freeze-risk reconstruction
    "entity_id": "ENT-20240613-8821",     # SECONDARY index
    "screening_timestamp": "2026-06-13T...",
    "screening_result": { ... },
    "list_version_ofac": "2026-06-12",
    "list_version_ofsi": "2026-06-11",
    "algorithm_version": "v1.1",
}
```

## 11.5 Compliance Stack for a KYB-First Stable Crypto Neobank (Reference)

```
Business Customer
    │
    ▼
KYB Onboarding
    ├── Company registry verification (Companies House, OpenCorporates, GLEIF)
    ├── UBO resolution (mandatory gate — FULL status required for activation)
    ├── Director screening against all applicable sanctions lists
    ├── Wallet address registration (wallet linked to KYB-verified entity)
    └── Risk score assigned at entity level
    │ Account activated only on FULL or PARTIAL UBO status
    ▼
Account Opening (allowed/denied based on UBO gate + entity score)
    │
    ▼
Payment Instruction Received
    │
    ├──→ Fiat: SWIFT/SEPA → Sanctions screen → Clear → Execute
    │
    └──→ Stablecoin (primary: TRON/USDT):
              ├── KYB Registry Check (internal vs external counterparty)
              ├── OFAC wallet list match
              ├── Issuer blacklist check (Tether contract query)
              ├── Hop analysis (depth 1 for internal, depth 3 for external)
              ├── MiCA compliance flag (if EU corridor + USDT)
              ├── Travel Rule data packet (from KYB record, pre-validated)
              └── → Clear → Broadcast transaction on TRON
```

> **KYC Extension Note:** When KYC onboarding is activated, the individual customer path joins the same stack at the onboarding step. KYC replaces UBO resolution with biometric + document verification. The account activation gate, payment screening flow, wallet registry, and audit trail are shared infrastructure and require no modification.

---

# 12. UI/UX RESEARCH — ANALYST EXPERIENCE

*(Treated separately from system architecture per your direction)*

## 12.1 State of the Industry: What's Broken

From AML platform reviews and industry research:

- **85–99% of alerts are false positives** (BCG/Celent finding on legacy systems)
- Legacy tools (NICE Actimize, Oracle Mantas) have "outdated, cumbersome interfaces" with "tiny fonts and too many useless buttons"
- Analysts frequently deal with queues of 200+ items; prioritization is manual and poor
- Information needed to make a decision is scattered across multiple systems
- No visual explanation of why an alert was raised
- No network/cluster view to see connected entities

## 12.2 What Analysts Actually Need (From Research)

Interviews with AML analysts consistently identify:

1. **Single-screen case view**: Everything needed to make a decision in one screen — no tab-switching
2. **Risk score breakdown**: Not just "0.64 REVIEW" but *why* — what drove the score
3. **Entity relationship map**: Who is connected to this entity, and how
4. **Prioritized queue**: Highest-risk cases first, not FIFO
5. **One-click actions**: Approve/escalate/request-more-info without form navigation
6. **Audit trail auto-generation**: Decisions should auto-generate regulatory justification
7. **Collaborative notes**: Multiple analysts can annotate a case
8. **Time pressure visibility**: SLA clock showing how long this alert has been open

## 12.3 UI Principles for This System

**Principle 1: Verdict first, evidence second**
The analyst sees MATCH/REVIEW/NO_MATCH immediately, then can drill into evidence.

**Principle 2: Everything in one screen**
Payment details + entity profile + score breakdown + network graph + action buttons — no navigation required for a routine decision.

**Principle 3: Graph is the primary view for complex cases**
For REVIEW cases involving multiple entities, the network graph is the primary interface, not a list.

**Principle 4: Machine proposes, human disposes**
LLM-generated explanation is pre-populated as a draft; analyst edits and confirms.

**Principle 5: Progressive disclosure**
Simple cases get a simple view. Complex cluster cases progressively reveal more layers.

## 12.4 Analyst Workflow Screens

```
Screen 1: QUEUE DASHBOARD
- Priority-sorted list of REVIEW items
- SLA timer, entity name, score, flagged lists, country
- Batch approve buttons for low-confidence no-match clusters
- Filter: by score range, by list type, by country, by assigned analyst
- Transfer type filter: Internal (KYB↔KYB) | Outbound (KYB→External) |
  Inbound (External→KYB) — most useful filter for a TRON/USDT-primary platform;
  inbound from unknown external wallets is highest risk, internal is lowest

Screen 2: CASE DETAIL VIEW
- Left panel: Payment instruction (sender/receiver/amount/corridor)
  + UBO resolution status badge for both parties
  + MiCA compliance tag if applicable (EU + USDT corridor)
- Center panel: Score tree (interactive graph of contributing factors)
- Right panel: Entity profile (corporate info, UBO chain, history)
  + KYB wallet registry status (internal/external/unresolved)
- Bottom panel: Network map (connected entities, cluster score)
- Action bar (top): CLEAR | BLOCK | ESCALATE | REQUEST INFO | DEFER

Screen 3: NETWORK EXPLORER
- Full-screen force-directed graph
- Nodes: entities (size = score, color = verdict)
- Edges: relationship type (shared address, shared director, transaction link,
  shared UBO — the highest-weight edge type in a KYB context)
- Click node: see entity detail panel slide in from right
- Select multiple nodes: see cluster aggregate score

Screen 4: AUDIT EXPORT
- Generates regulatory-format report for any decision
- Pre-populated from LLM explanation + analyst notes
- Export as PDF or structured JSON for regulator submission
- Wallet-address-indexed audit trail available for freeze-risk reconstruction
```

## 12.5 Color System for Risk Visualization

```
RED (#DC2626)       → MATCH — payment blocked
AMBER (#D97706)     → REVIEW — human required
GREEN (#16A34A)     → NO_MATCH — payment cleared
PURPLE (#7C3AED)    → CLUSTER ELEVATED — individual moderate, cluster elevated
GREY (#6B7280)      → PENDING — in-queue, not yet processed
BLUE (#2563EB)      → INFORMATIONAL — PEP flag without sanction /
                       MiCA compliance tag / TRON EU corridor flag
ORANGE (#EA580C)    → UBO UNRESOLVED — KYB gate not cleared; treat as external
```

---

# 13. CLAUDE CODE PROMPTS

These prompts are designed for use with Claude Code (terminal or VS Code extension).

---

## PROMPT CC-01: Initialize Project Structure

```
I'm building a sanctions screening system as domain-based microservices in Docker.

Create the full project directory structure with:
- 10 domain services: screening-api, entity-resolution, graph-engine, 
  regulatory-engine, crypto-screener, llm-service, list-sync, 
  review-queue, audit-trail, notification-service
- Each domain has: Dockerfile, app/main.py, requirements.txt, .env.example
- Root: docker-compose.yml with all services, volumes, and networks
- Infrastructure: postgres, neo4j, redis, elasticsearch, minio directories 
  with init scripts
- Frontend directory: React app scaffold

Use Python 3.12 + FastAPI for all backend services.
PostgreSQL 16 for transactional data.
Neo4j 5 Community Edition for graph.
Redis 7 for cache/queue.
Elasticsearch 8 for fuzzy search.
MinIO for object storage (audit documents).

The platform is KYB-only at launch (business onboarding only). All data
models must include nullable KYC fields (dob, passport_number,
biometric_reference) so that individual onboarding can be activated in a
future phase without schema migration.

Include a Makefile with: make build, make up, make down, make logs, 
make test, make init-models (pulls Ollama models).
```

---

## PROMPT CC-02: Entity Resolution Service

```
Build the entity-resolution FastAPI service for a sanctions screening system.

This service receives a name + country and returns match candidates from 
our Elasticsearch index with confidence scores.

Implement:

1. FuzzyMatcher class using RapidFuzz:
   - Levenshtein distance
   - Jaro-Winkler similarity  
   - Token sort ratio (handles word order differences)
   - Combine into composite similarity score

2. PhoneticMatcher class:
   - Soundex, Metaphone, Double Metaphone
   - Handles English-language phonetic variations
   - "Sergei" and "Sergey" should score > 0.90

3. TransliterationNormalizer class:
   - Arabic → Latin transliteration (use arabic-transliteration library)
   - Russian/Cyrillic → Latin (use transliterate library)
   - Chinese pinyin normalization
   - Strip diacritics (José = Jose)
   - Normalize to NFKD

4. ElasticsearchMatcher class:
   - ES index with edge-ngram tokenizer for partial matching
   - Phonetic analysis plugin (elasticsearch-analysis-phonetic)
   - Query: bool query with must (exact), should (fuzzy), boost on country match

5. POST /match endpoint:
   - Input: {"name": "Muammar Gaddafi", "country": "LY", "entity_type": "business"}
   - Output: list of MatchCandidate with score, matched_name, list_source, 
     list_entry_id, match_methods_used
   - entity_type field accepts "business" (current) or "individual" (future KYC)
     and adjusts corroborating identifier requirements accordingly:
     business -> registration number, jurisdiction
     individual -> dob, passport_number (nullable, used when KYC activated)

6. All matches cached in Redis with 1-hour TTL

Include unit tests using pytest. Target: < 80ms p99 response time.
```

---

## PROMPT CC-03: Network Risk Scorer (noisy-OR)

```
Build the network risk scoring module for our Neo4j-backed graph engine
service. This implements the Section 6.4 mechanism (Option A, Bayesian
noisy-OR) — NOT Louvain community detection or quadratic score amplification.
Those mechanisms lacked per-entity attribution and have been removed.

The function: given an entity, traverse its 3-hop neighbourhood in the
ownership/shared-attribute graph, find flagged nodes (confirmed SDN or
currently in REVIEW), and compute a per-entity network risk score with
per-neighbour leave-one-out attribution for the explainability layer.

IMPORTANT CONSTRAINT: Network risk analysis may only escalate entities to
REVIEW, never autonomously to MATCH. The only path to MATCH via the graph
is the deterministic 50% ownership rule (Track A), handled separately.
The EscalationEngine must enforce this ceiling strictly.

Implement in Python with the neo4j Python driver:

1. EntityGraphBuilder class:
   - Ingest entity data (name, address, directors, UBOs, registration date/country)
   - Create Neo4j nodes: (:Entity {id, name, country, individual_score,
     ubo_resolution_status, track_a_verdict})
   - Create edges: [:SHARES_ATTRIBUTE {type, weight}] where type is one of:
     registered_address, phone, director, ubo, registration_date+country
   - Attribute weights: address=0.7, phone=0.6, director=0.8, ubo=0.9
   - UBO edges carry the highest weight as they represent true beneficial
     ownership linkage — the primary risk signal in a KYB context

2. NetworkRiskScorer class:
   Implements the noisy-OR model from Section 6.4:

     network_risk(e) = 1 - ∏_f [ 1 - p_f × lambda^d(e,f) ]

   where:
     f      = each flagged neighbour within 3 hops
     p_f    = 1.0 for confirmed SDN (Track A MATCH) nodes;
              entity's Track B risk score for REVIEW nodes
     lambda = 0.5 (per-hop decay constant)
     d(e,f) = shortest-path hop count from e to f (cap at 3)

   Methods:
   - compute_network_risk(entity_id: str, graph: NetworkXGraph)
       -> (network_risk_score: float, attribution: Dict[str, float])
     network_risk_score: the noisy-OR result ∈ [0, 1]
     attribution: {neighbour_id: marginal_contribution}
     marginal_contribution = risk_with_all - risk_excluding_this_neighbour
     (leave-one-out; drives the per-node explanation panel)

   - get_flagged_neighbours(entity_id: str, max_hops: int = 3)
       -> List[FlaggedNeighbour]
     Queries Neo4j for nodes within max_hops that are either:
       - Track A MATCH (confirmed SDN) — p_f = 1.0
       - Track B REVIEW with risk_score >= REVIEW_RISK_THRESHOLD — p_f = risk_score

   NOTE: CommunityDetector (Louvain) and ClusterScorer (quadratic-bias ×
   network amplifier) are NOT implemented here — those mechanisms were rejected
   in Section 6.4 for lacking per-entity attribution. Do not add them.

3. EscalationEngine class:
   - Takes network_risk_score (float), attribution (Dict), individual_verdict (Verdict)
   - CEILING RULE: output verdict is always capped at REVIEW.
     Assert: output is never MATCH. Test this explicitly with parametrize.
   - If network_risk_score >= REVIEW_RISK_THRESHOLD AND individual_verdict == NO_MATCH:
     escalate to REVIEW
   - If network_risk_score >= 0.70 AND individual_verdict is already REVIEW:
     raise queue priority (verdict class unchanged — still REVIEW)
   - Returns EscalationDecision with:
       escalated (bool), new_verdict (Verdict), priority_boost (bool),
       justification (str) — must cite noisy-OR score and top contributing
       neighbours by ID and marginal contribution, e.g.:
       "Network risk 0.58 (noisy-OR, λ=0.5): 1 hop from confirmed SDN [id]
        (marginal 0.25), 1 hop from REVIEW entity [id] (marginal 0.30).
        Routed to REVIEW — not blocked on association alone."

4. POST /analyze-network endpoint:
   - Input: {"entity_id": "ENT-8821"}
   - Output: network_risk_score, per_neighbour_attribution (leave-one-out),
             escalation_decision, cypher_paths_used
   - Note: no "cluster" concept here — each entity's score is computed
     independently from its local 3-hop neighbourhood via noisy-OR.
     There is no community-detection step.

Write Neo4j Cypher queries in queries.py for:
- Building shared-attribute edges
- Finding k-hop neighbours (up to 3 hops) of an entity
- Finding flagged neighbours (SDN or REVIEW) within 3 hops
- Shortest-path distance between two entities (for d(e,f))
- Detecting circular ownership
- Finding entities sharing the same UBO (highest-priority KYB signal)

Write tests with a mock Neo4j using neo4j-mock:
- noisy-OR gives correct result for 1-hop SDN neighbour:
  1 - (1 - 1.0×0.5^1) = 0.50
- noisy-OR is monotonically non-decreasing as more flagged neighbours are added
- leave-one-out attribution is positive for each contributing neighbour
- EscalationEngine NEVER returns MATCH (parametrize across many score values)
- justification text contains "noisy-OR" and the top contributing neighbour IDs
```

---

## PROMPT CC-04: Regulatory Engine — Country-Based Rules

```
Build the regulatory-engine FastAPI service.

This service takes a payment (originator country, beneficiary country, 
corridor type, amount, entity type, chain) and returns:
- Which sanction lists MUST be checked
- What score thresholds apply for MATCH/REVIEW
- What reporting obligations are triggered
- Country risk tier (FATF black/grey/high-risk/offshore)
- Policy flags (MiCA compliance risk, TRON EU corridor flag)

Implement:

1. Abstract base class JurisdictionRule with methods:
   - applies_to(payment: Payment) -> bool
   - get_required_lists() -> List[str]
   - get_thresholds() -> ScoreThresholds  
   - get_reporting_requirements() -> ReportingRequirements
   - get_retention_period_days() -> int

2. Concrete implementations:
   - OFACRule (US, FinCEN): OFAC SDN + all programs mandatory; 50% ownership rule
   - FCARule (UK): UK Sanctions List + OFSI; PEP EDD mandatory
   - EUAMLRule (EU/EEA): EU Consolidated + UN; MiCA stablecoin provisions;
     emit MiCA_COMPLIANCE_RISK tag for any USDT transfer on EU corridors
   - AUSTRACRule (Australia): DFAT list; AUD 10k+ threshold reporting
   - FINTRACRule (Canada): OSFI list; CAD 10k+ cash reporting
   - DFSARule (UAE): UAE local list + OFAC + UN; VARA crypto provisions
   - FATFBaseRule: Applied as fallback when no specific rule matches

3. TRONCorriderPolicyRule (new):
   - applies_to: any payment where chain == "tron" AND corridor involves EU or UK
   - Emits TRON_EU_CORRIDOR_REVIEW informational tag
   - Does NOT modify numeric score — policy flag only
   - Rationale: Tether USDT not MiCA-authorized as of mid-2026; EU/UK corridor
     TRON/USDT transfers require additional legal review

4. CountryRiskClassifier:
   - Returns: BLACK, GREY, HIGH_RISK, OFFSHORE, STANDARD
   - Loads from YAML config file (easy to update as FATF lists change)
   - FATF grey list is re-assessed every 4 months — include update script
   - Score multipliers per tier: 2.0, 1.35, 1.50, 1.20, 1.0
   - Current grey list excludes Bulgaria and Croatia (both exited 2023)

5. RegulatoryEngineRouter:
   - Payment enters, returns union of all applicable rules
   - Example: UK→UAE TRON payment applies FCARule + DFSARule + 
     FATFBaseRule + TRONCorriderPolicyRule
   - Strictest threshold wins; union of required lists applies
   - Policy flags are additive (all applicable flags returned)

6. POST /get-requirements endpoint:
   - Input: {"originator_country": "GB", "beneficiary_country": "AE", 
             "amount_usd": 50000, "entity_type": "business",
             "asset_type": "stablecoin", "chain": "tron", "token": "USDT"}
   - Output: required_lists, thresholds, reporting_obligations, country_risk_tiers,
             applicable_rules, travel_rule_required, policy_flags

Include integration tests that verify:
- UK→Iran payment always triggers auto-block regardless of score
- EU+TRON+USDT payment always carries MiCA_COMPLIANCE_RISK tag
- UK+TRON+USDT payment always carries TRON_EU_CORRIDOR_REVIEW tag
- USDC on EU corridors carries neither MiCA flag
```

---

## PROMPT CC-05: Stablecoin Screener (TRON/USDT Primary)

```
Build the crypto-screener FastAPI service focused on stablecoin compliance.
Primary rail: USDT on TRON. Secondary: USDT/USDC on Ethereum. Tertiary: USDC on Solana.

The platform is KYB-only: every platform-side wallet is registered to a
verified business entity. The screener must use this to optimize the
common case (internal KYB-to-KYB transfer) while applying full
scrutiny to external counterparties.

Implement:

1. KYBWalletRegistry class:
   - Redis hash: wallet_address -> {entity_id, ubo_resolution_status, 
     onboarding_score, kyb_verified_at}
   - lookup(address) -> KYBRecord | None
   - is_internal_pair(address_a, address_b) -> bool
   - Internal pair: both addresses in KYB registry with FULL or PARTIAL UBO status
   - UNRESOLVED UBO status -> treated as external regardless of registry presence

2. OFACWalletScreener:
   - Load OFAC SDN crypto address list (download from ofac.treasury.gov)
   - Store in Redis sorted set for O(log n) lookup
   - Exact match returns score=1.0 immediately
   - Schedule daily refresh via Celery beat

3. IssuerBlacklistChecker:
   - USDT/TRON: Query Tether blacklist via TRON RPC
     Contract: TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t
     Function: isBlackListed(address) -> bool (use tronpy)
   - USDT/ETH: Query Tether blacklist on Ethereum (use web3.py)
   - USDC/ETH: Query Circle blacklist (isBlacklisted on 0xA0b86...)
   - Return: {frozen: bool, chain: str, issuer: str}

4. OnChainHopTracer:
   - Input: wallet address + chain + is_internal_pair bool
   - TRON: use Tronscan API (primary, highest throughput allocation)
   - Ethereum: use Etherscan API (secondary)
   - BFS traversal: depth=1 for internal KYB pairs, depth=3 for external
   - Score: 1.0 direct / 0.7 at 1 hop / 0.4 at 2 hops / 0.1 at 3 hops
   - Stop traversal when total value traced < $1,000 (de minimis)
   - Cache results in Redis with 24h TTL
   - Handle rate limits with exponential backoff (TRON: 5 req/sec free tier)

5. WalletAttributor:
   - Only called for non-KYB-verified addresses (external counterparties)
   - Use free attribution from Etherscan labels API + Tronscan labels
   - Classify: exchange, mixer, darknet, defi_protocol, sanctioned, unknown
   - Mixers (Tornado Cash variants, ChipMixer successors, etc.) = score boost +0.40

6. MiCAComplianceTagger:
   - check_mica_compliance(token: str, chain: str, corridor: str) -> MiCAFlag | None
   - USDT on any EU-corridor transfer → MiCA_COMPLIANCE_RISK (informational)
   - USDC on EU corridor → None (MiCA-authorized)
   - Flag is metadata only — does not modify composite score

7. FreezeRiskRegister:
   - Redis set: wallet addresses that received any non-zero screening flag
     in the last 90 days
   - update_register(address, screening_result) -> None
   - is_in_register(address) -> bool
   - Used for post-hoc regulatory reconstruction if Tether later freezes address

8. TravelRuleEnforcer:
   - For KYB platform members: Travel Rule data packet auto-generated from
     KYB record (legal name, registered address, LEI/registration number)
   - For external counterparties: collect at transaction time or route to REVIEW
   - Check if beneficiary VASP supports Travel Rule protocol
     (TRUST, OpenVASP, Notabene, Sygna)

9. StablecoinTransaction model:
   - chain: tron | ethereum | solana | base | arbitrum (tron is primary)
   - stablecoin: USDT | USDC | PYUSD | EURC
   - from_address, to_address
   - amount (in stablecoin units)
   - originator_vasp, beneficiary_vasp
   - is_internal: bool (set by KYBWalletRegistry)

10. POST /screen-wallet:
    - Input: {"address": "TXxx...", "chain": "tron", "stablecoin": "USDT",
              "amount_usd": 25000, "counterparty_address": "TYyy..."}
    - Output: kyb_status, ofac_match, issuer_frozen, hop_analysis,
              attribution, mica_flag, travel_rule_status,
              composite_score, score_breakdown, recommended_verdict

Use tronpy for TRON (primary). Use web3.py for Ethereum (secondary).
Do NOT store private keys or sign transactions — read-only operations only.
Log every screening decision to audit trail with wallet_address as primary key.
```

---

## PROMPT CC-06: Score Explanation Graph API

```
Build the explainability API for the screening-api service.

Every verdict must produce a structured explanation tree that:
1. Can be serialized to JSON for storage in audit trail
2. Can be consumed by the frontend to render an interactive graph
3. Can be passed to the LLM service to generate natural-language explanation

Implement:

1. ScoreNode dataclass:
   - id: str
   - label: str
   - score: float
   - weight: float
   - weighted_contribution: float
   - detail: str
   - children: List[ScoreNode]
   - metadata: Dict (any extra evidence)

2. ExplanationTreeBuilder:
   - Takes all component scores from all domain services
   - Builds tree structure with root = composite score
   - Hierarchy: Composite → (NameMatch, CountryRisk, UBOAnalysis, 
     AdverseMedia, CryptoHops) → individual list results per component
   - Computes weighted_contribution at each level
   - Attaches raw evidence (matched list entry IDs, article URLs, 
     cypher paths from Neo4j)
   - Includes ubo_resolution_status in UBO node metadata
   - Includes mica_flag and tron_corridor_flag as informational leaf nodes
     (these are policy flags, not scored — render in blue in the UI)

3. NetworkContextBuilder:
   - If entity is in a cluster: add NetworkContext to the explanation
   - NetworkContext includes: cluster_id, cluster_size, cluster_score,
     connected_entities (with their scores and shared attributes),
     escalation_reason
   - NOTE: cluster_escalation_applied=true can only coexist with
     verdict=REVIEW, never verdict=MATCH. Assert this invariant in tests.

4. LLMExplanationGenerator:
   - Takes ExplanationTree as input
   - Calls Ollama (qwen2.5:14b via local API) with structured prompt
   - Returns 2-3 paragraph natural language explanation
   - Prompt format:
     "You are a compliance analyst reviewing a KYB (business) screening
     result. Explain why this payment received a {verdict} verdict.
     Score: {score}. Key factors: {factors}. UBO status: {ubo_status}.
     Write for a regulator who may read this in 2 years. Be precise, 
     cite specific list names and match scores. Do not speculate."

5. GET /explanation/{payment_id}:
   - Returns full JSON explanation tree
   - Includes: tree, network_context, llm_explanation, timestamp, analyst_id

6. POST /generate-sar-draft:
   - Takes payment_id + analyst_notes
   - Generates draft Suspicious Activity Report text using LLM
   - Structured to meet FinCEN/FCA SAR format requirements

Write unit tests that verify:
- Every MATCH verdict has a sanctions_list_match node with score >= 0.85
- Every cluster escalation has a network_context node AND verdict == REVIEW
  (never MATCH — assert this)
- Every UBO node includes ubo_resolution_status field
- UNRESOLVED UBO status triggers REVIEW flag in explanation tree
```

---

## PROMPT CC-07: List Sync Service

```
Build the list-sync Celery service that keeps all sanction list data 
fresh without system downtime.

Implement parsers for:

1. OFAC SDN XML (ofac.treasury.gov/ofac/downloads/sdn.xml):
   - Parse: SDN_ENTRY, AKA (aliases), ADDRESS, ID (passport/NIN)
   - Extract crypto addresses from FEATURE elements
     (OFAC publishes sanctioned TRON, ETH, and other chain addresses)
   - Store in PostgreSQL (entities) + Elasticsearch (for fuzzy search) + 
     Redis (wallet addresses for instant lookup, keyed by chain)

2. UK OFSI (assets.publishing.service.gov.uk/...):
   - Parse consolidated list CSV
   - Map OFSI fields to canonical schema

3. EU Consolidated (data.europa.eu/...):
   - Parse XML, handle multilingual aliases (all language variants stored)
   - Store entity_type: individual / entity / vessel / aircraft

4. UN Consolidated (scsanctions.un.org/...):
   - Parse XML with narrative sections
   - Preserve narrative text for LLM processing

5. PEP Lists:
   - OpenSanctions PEP dataset (free, daily updated)
   - Parse JSON Lines format
   - Store separately from sanctions (different risk weighting)
   - PEPs are directors/UBOs in KYB context — flag on UBO resolution,
     not just entity-level match

6. DiffEngine:
   - On each sync: compare new list with current stored version
   - Detect: new entries, removed entries, modified entries (new aliases)
   - For new sanctions entries: trigger re-screening of all existing customers 
     matching the new entity, including UBO-chain matches
   - For new OFAC wallet addresses: immediately update Redis wallet registry
     and trigger re-screening of any KYB customers whose registered wallets
     appear in the new list
   - Emit events to notification-service for compliance officer alerts

7. Celery beat schedule:
   - OFAC: every 6 hours (they update frequently; wallet additions are time-critical)
   - UK OFSI: daily at 08:00 UTC
   - EU: daily at 09:00 UTC
   - UN: daily at 10:00 UTC
   - PEP: daily at 06:00 UTC

8. Zero-downtime update:
   - Write to a "staging" index in Elasticsearch
   - Validate entry count (reject if < 95% of previous count — indicates parsing error)
   - Atomic alias swap: staging → live
   - Update Redis atomically with MULTI/EXEC

Include error handling: if a source is unreachable, keep existing data 
and alert; never serve stale data older than 48 hours without alerting.

Add monitoring: Prometheus metrics for sync duration, entry counts, 
diff sizes, last successful sync timestamp, new wallet addresses detected.
```

---

# 14. CLAUDE DESIGN PROMPTS

These prompts are designed for Claude Design or any design AI for UI/UX work.

---

## PROMPT CD-01: Overall System Design Brief

```
Design a professional compliance and sanctions screening platform for 
financial analysts working in fintech/banking environments.

AUDIENCE: AML compliance analysts, 25-45 years old, working under 
time pressure, often reviewing 50-200 cases per day. High stakes — 
wrong decisions have regulatory consequences. All cases are KYB
(business entities), not individual consumers — the UI should reflect
corporate complexity: UBO chains, corporate structure, wallet registries.

TONE: Authoritative, clinical, efficient. NOT corporate-bland. 
Think Bloomberg Terminal meets modern fintech — serious tooling that 
communicates expertise and trustworthiness.

COLOR SYSTEM:
- Semantic colors are critical and must be immediately recognizable:
  MATCH (block): #DC2626 (red)
  REVIEW (human needed): #D97706 (amber)  
  CLEARED (pass): #16A34A (green)
  CLUSTER ELEVATED: #7C3AED (purple)
  PENDING: #6B7280 (grey)
  INFORMATIONAL (MiCA/TRON flags, PEP): #2563EB (blue)
  UBO UNRESOLVED: #EA580C (orange)
- Background: #0F172A (dark navy — reduces eye strain for long sessions)
- Surface: #1E293B 
- Text primary: #F1F5F9
- Text secondary: #94A3B8
- Accent (interactive): #3B82F6 (blue)

TYPOGRAPHY:
- Headings: Inter or similar geometric sans — professional, not corporate
- Data/numbers: JetBrains Mono — monospaced for score alignment
- Body: Inter Regular

LAYOUT PHILOSOPHY:
- Information density > whitespace for analyst tools
- Every pixel earns its place
- Three primary density modes: compact (200 cases/screen), 
  standard (analyst default), expanded (complex case investigation)
```

---

## PROMPT CD-02: Queue Dashboard Screen

```
Design the analyst queue dashboard — the first screen an analyst sees.

LEFT SIDEBAR (240px):
- Company logo + "Compliance Engine" text
- Navigation: Queue | Cases | Search | Reports | Admin
- Stats widget: Today's queue count, cleared %, SLA breaches
- Analyst info + status toggle (available/busy/offline)

MAIN CONTENT — Queue Table:
Columns: Priority | Entity Name | Country | Score | Lists Flagged | 
         Payment Amount | Transfer Type | Time in Queue | SLA Status | Assigned To

Row design:
- Color-coded left border by verdict (RED/AMBER/PURPLE)
- Score displayed as number + small horizontal bar
- Transfer Type column: badge showing INTERNAL (KYB↔KYB, lowest risk) |
  OUTBOUND (KYB→External) | INBOUND (External→KYB, highest risk)
- SLA column: green if >4h remaining, amber if 1-4h, red if <1h
- Orange dot indicator if UBO status is UNRESOLVED
- Blue tag if MiCA or TRON EU corridor flag is present
- Click row → opens Case Detail in right panel (master-detail pattern)
- Checkboxes for batch actions

FILTERS BAR (above table):
- Score range slider (0.50–1.0)
- Country multiselect
- List type filter (OFAC / EU / UK / UN / PEP)
- Asset type (Fiat / TRON-USDT / ETH-USDT / USDC / Other)
- Transfer type (Internal / Outbound / Inbound / All)
- UBO status (All / Full / Partial / Unresolved)
- Policy flags (MiCA risk / TRON EU corridor / None)
- Assigned to (All / Mine / Unassigned)
- Date range

TOP RIGHT:
- "Batch Clear Selected" button (for low-risk REVIEW items)
- "Export Queue" CSV
- Refresh toggle (auto/manual)

DESIGN NOTE: This screen is used for 60-90 minutes at a time. 
Optimize for scanning speed. Score numbers should be prominent.
SLA urgency and UBO status must be scannable at a glance.
The Transfer Type filter is the most important operational filter —
make it prominent.
```

---

## PROMPT CD-03: Case Detail View — The Core Screen

```
Design the case detail view — the most important screen in the system.
Analysts spend 2-8 minutes here per case. Every second counts.
All cases are KYB (business entities).

LAYOUT: 3-panel horizontal layout (no scrolling required for typical case)

LEFT PANEL (320px) — Payment Instruction:
- Payment reference number (large, copyable)
- Originator: business name, country, wallet/account
  + UBO resolution status badge (FULL=green / PARTIAL=amber / UNRESOLVED=orange)
  + KYB registry status (INTERNAL / EXTERNAL)
- Beneficiary: business name, country, wallet/account
  + Same UBO and registry badges
- Amount + currency + equivalent USD
- Payment type badge: SWIFT | SEPA | TRON-USDT | ETH-USDT | USDC
- Transfer type badge: INTERNAL | OUTBOUND | INBOUND
- Corridor risk badge (HIGH / MEDIUM / LOW)
- Policy flags row: [MiCA COMPLIANCE RISK] [TRON EU CORRIDOR] if applicable
- Timestamp

CENTER PANEL (variable width) — Score Breakdown Graph:
- Interactive tree/waterfall visualization
- Root node (top): verdict badge + composite score (e.g., "REVIEW 0.64")
- Branch nodes: each scoring domain (Name Match, Country Risk, UBO,
  Adverse Media, Crypto Hops)
- UBO node prominently sized (most important in KYB context)
- Leaf nodes: specific evidence items
- Policy flag nodes (blue, informational — not scored): MiCA / TRON corridor
- Each node: score bar, weighted contribution, click to expand detail
- Color: node fill matches risk level
- Connecting lines: thickness = weight

BELOW CENTER — Network Cluster Panel (collapsible):
- Only shown if entity is in a cluster
- Mini force-directed graph showing cluster (max 10 nodes)
- Edge types: UBO link (thick solid) | Director link (thin solid) |
  Address link (dashed) | Transaction link (dotted)
- Cluster score badge (PURPLE if elevated)
- "Explore full network" button → opens Network Explorer overlay

RIGHT PANEL (360px) — Entity Profile:
- Entity name, type (Ltd / LLC / Trust / Partnership)
- Registered address, incorporation date, jurisdiction
- UBO section: EXPANDED by default (unlike v1; UBO is primary signal in KYB)
  Shows full ownership chain with each UBO's screening status
- Director list with individual screening scores + PEP flags
- Wallet registry: platform wallets linked to this entity + KYB status
- Transaction history (last 90 days, with amounts and transfer types)
- Previous screening history

ACTION BAR (sticky bottom, full width):
Buttons: [CLEAR PAYMENT] [BLOCK PAYMENT] [ESCALATE TO SENIOR] 
         [REQUEST MORE INFO] [DEFER 24h]
- Each button: confirmation modal with pre-populated justification text
- Justification text: LLM-generated but editable
- "Add Note" text area always visible

KEYBOARD SHORTCUTS displayed in footer:
C = Clear | B = Block | E = Escalate | N = Add Note | ← → = Navigate cases
```

---

## PROMPT CD-04: Network Explorer Visualization

```
Design the network explorer — a full-screen overlay for investigating 
connected entity clusters.

This screen is used for complex KYB cases where multiple businesses are 
connected and the cluster score has been elevated.

CANVAS (main area, ~80% of screen):
- Force-directed graph using D3.js
- Nodes:
  * Size = proportional to individual risk score (larger = riskier)
  * Color fill = verdict color (RED/AMBER/GREEN/PURPLE)
  * Label: entity short name + score badge
  * UBO UNRESOLVED entities: orange border ring
  * Currently-selected entity: pulsing white border ring
  * Sanctioned entities: red outer glow
- Edges (KYB-specific types, in descending weight):
  * Double solid line = same UBO (strongest link; weight 0.9)
  * Solid thick = same director (weight 0.8)
  * Solid thin = same registered address (weight 0.7)
  * Dashed = same phone number (weight 0.6)
  * Dotted = transaction link
  * Edge label: relationship type + ownership % if UBO link
- Background: dark (#0F172A)

LEFT SIDEBAR (280px) — Graph Controls:
- Legend (edge types + node colors including orange for UBO UNRESOLVED)
- Filter: show only edges of type X
  (UBO edges shown by default; others togglable)
- Layout toggle: Force-directed | Circular | Hierarchical (ownership tree)
- Zoom controls
- "Export graph as PNG" button

RIGHT SIDEBAR (320px) — Entity Detail Panel (slides in on node click):
- Entity name + verdict
- UBO resolution status (prominent)
- Individual score breakdown (compact version)
- List of relationships (what links this entity to others in cluster)
- KYB wallet registry status
- Action buttons: BLOCK THIS ENTITY | ESCALATE THIS ENTITY

CLUSTER SUMMARY BAR (top):
- Cluster ID | Total entities: N | Cluster score: 0.82 | Verdict: REVIEW ELEVATED
  NOTE: label says REVIEW ELEVATED, never MATCH ELEVATED — cluster analysis
  cannot autonomously produce MATCH
- Shared attributes summary: "3 entities share UBO; 2 share registered address"
- "Escalate all to senior review" CTA (requires confirmation)
- "Export cluster report"

INTERACTION:
- Click node: detail panel slides in from right
- Right-click node: context menu (Add note / Block / Highlight connections)
- Scroll to zoom
- Drag canvas to pan
- Double-click node: expand to load 1 more hop from database
```

---

## PROMPT CD-05: Score Explanation Card — Component

```
Design a reusable Score Explanation Card component used in multiple 
screens to show exactly how a score was computed.

This component must:
1. Work at multiple sizes (full panel / compact card / tooltip-size)
2. Be usable by non-technical compliance officers who must explain 
   decisions to regulators

FULL SIZE (used in Case Detail center panel):

TOP: 
- Large score number (e.g., "0.64") in JetBrains Mono
- Verdict badge: "REVIEW" in amber
- Threshold context: "Track B: R < 0.50 = NO_MATCH | R ≥ 0.50 = REVIEW (high-priority above 0.85) — risk score never produces a block"
- Track label: "Track B: Risk Intelligence" or "Track A: Sanctions Gate"
  (shows which track drove the verdict)

WATERFALL CHART:
Horizontal stacked bars showing how each component contributes (six-factor weights per Section 6.3):
│ Identity Match Signal    ████████░░  +0.178  (71% × 0.25 weight)  │
│ Behavioral Anomaly       ██████░░░░  +0.120  (60% × 0.20 weight)  │
│ Network Exposure         ██████░░░░  +0.116  (58% × 0.20 weight)  │
│ Entity Risk Profile      ██████░░░░  +0.120  (80% × 0.15 weight)  │
│ Doc / Onboarding Integ.  ███░░░░░░░  +0.060  (60% × 0.10 weight)  │
│ Historical Flag Rate     ██░░░░░░░░  +0.046  (46% × 0.10 weight)  │
│ ──────────────────────────────────────────────────────────────     │
│ TOTAL                                         0.640                │
Note: country-risk multiplier (×1.35 for UAE) is applied within the
Entity Risk Profile sub-score, not as a separate additive row.
UBO status is surfaced in the UBO STATUS SECTION below and in Entity
Risk Profile metadata, not as a standalone weighted factor.

POLICY FLAGS SECTION (below waterfall, in blue):
│ [ℹ TRON EU CORRIDOR]  [ℹ MiCA COMPLIANCE RISK]              │
  These are informational tags, not score components.
  Click each for regulatory context.

UBO STATUS SECTION (prominent, below waterfall):
│ UBO Resolution: PARTIAL                                       │
│ Ahmad Khalid Mansour — verified, no list match               │
│ Secondary UBO — unresolved at 3-hop depth                    │
│ [View UBO chain →]                                           │

Each waterfall row:
- Clickable → expands to show sub-components (which list, what match)
- Tooltip on hover: raw score + evidence source
- "No match" rows shown in greyed state

BOTTOM:
- "Network cluster context" section (shown if elevated)
- "LLM Explanation" collapsible section with "Edit before saving" option

COMPACT SIZE (used in queue table rows):
- Just the score bar + verdict badge + top 2 contributing factors as pills
- Orange dot if UBO UNRESOLVED
- Blue dot if any policy flag active

Design all three sizes. Use the dark theme color system.
Ensure accessibility: all information conveyed through text, not just color.
```

---

## PROMPT CD-06: Mobile Approval View (Urgent Escalations)

```
Design a mobile view (375px width) for senior compliance officers 
who need to approve or block escalated cases on mobile.

This is not a full mobile app — it's a mobile-optimized view for 
urgent decisions that can't wait for desktop access.
All cases are KYB (business entities).

SCENARIO: Senior analyst is away from desk. Gets push notification 
that a $2M TRON/USDT transfer from an external counterparty has been
flagged REVIEW with UBO UNRESOLVED on the receiving entity.

SCREEN 1 — URGENT ALERT:
- Full-screen amber alert card
- "URGENT: Payment Review Required"
- Sending entity: business name + KYB status badge
- Receiving entity: business name + UBO UNRESOLVED badge (orange)
- Transfer type: INBOUND (External→KYB)
- Chain + token: TRON / USDT
- Amount (large text)
- Policy flags if present: [MiCA COMPLIANCE RISK] [TRON EU CORRIDOR]
- Top risk factor summary (2 lines): e.g. "Name match 0.71 on EU List +
  UBO chain unresolved at depth 3"
- Two primary actions: [VIEW FULL CASE] [ESCALATE TO TEAM]

SCREEN 2 — QUICK DECISION:
- Condensed score card (compact size from CD-05)
- UBO chain summary (collapsed, expandable)
- LLM-generated 2-sentence summary of why this is flagged
- Action buttons: [BLOCK] [CLEAR] [ESCALATE] — each requires
  biometric or PIN confirmation before executing
- "View full desktop case" link
```

---

*End of Master Plan — Version 1.1*

---

---

## CHANGELOG: v1.1 → v1.2

| Section | Change |
|---|---|
| Header | Version bumped to 1.2 |
| Section 2.2 | Softened "Flagged Patterns" label to "Observed Patterns (hypotheses)"; replaced "classic shell-layer deflection pattern" with neutral language marking the characterisation as unverified |
| Section 3.3 | Added reconciling note clarifying the cumulative/network layer's role is REVIEW-prioritization, not blocking; aligned marketing language with conservative engine behaviour |
| Section 6.1 | Added third Track A deterministic block path: comprehensive-sanctions jurisdiction (BLACK-tier country) |
| Section 6.1 | Noted that 50%-rule requires established ownership chain (all percentages known); cross-referenced 8.3 fix |
| Section 6.2 | Added `A:country-sanctions` branch in `resolve_verdict` for BLACK-tier country blocks |
| Section 6.2 | Updated INVARIANT comment to enumerate all three Track A MATCH paths |
| Section 6.6 | Added Country-sanctions (Track A) row to "What You Show a Court" evidence table |
| Section 7.1 | **Rewrote JSON example** to use Section 6.3 six-factor weights (was: Name 0.40, Country Risk 0.08, UBO 0.07, Adverse Media 0.10); new factors: Identity Match 0.25, Behavioral 0.20, Network 0.20, Entity Profile 0.15, Doc Integrity 0.10, Historical 0.10 |
| Section 7.1 | Recomputed weighted contributions — now sum correctly to 0.640 (were 0.435) |
| Section 7.1 | Country risk moved inside Entity Risk Profile sub-score as a multiplier; UBO info inside Entity Risk Profile metadata; adverse media inside Entity Risk Profile detail |
| Section 7.1 | Updated `network_context` to use `network_risk_score` (noisy-OR) and `network_escalation_applied`; replaced old cluster-score terminology |
| Section 7.1 | Updated `ubo_resolution_status` note to reflect new factor structure |
| Section 8.3 | **Fixed coalesce bug**: removed `coalesce(r.ownership_pct, 0.5)` default; added `WHERE all(r ... r.ownership_pct IS NOT NULL)` filter; chains with unknown percentages now route to REVIEW, not to a fabricated 50%-rule calculation |
| Section 8.3 | Added note: chains with missing ownership_pct are UNESTABLISHED and cannot satisfy the deterministic 50%-rule |
| Section 8.3 | Added UBO depth reconciliation note: resolver max_depth=8 vs. gate requirement of 4 vs. illustrative examples of 3 |
| Section 9.3 | **Removed Venezuela from GREY tier** — it appeared in both GREY (×1.35) and HIGH_RISK (×1.50) with no precedence rule; HIGH_RISK retained as primary classification |
| Section 9.3 | Added `auto_block` comment in BLACK tier: clarifies this is a Track A legal block (A:country-sanctions), not a score override |
| Section 10.3 | **Fixed `is_internal` latent bug**: added `result.is_internal = False` reset inside the UNRESOLVED UBO branch; without it, hop depth remained 1 (internal) after UBO downgrade, contradicting the external-treatment comment and the CC-05 spec |
| Section 10.3 | Added note to `trace_hops` docstring: linear −0.3/hop decay is intentionally distinct from geometric 0.5^d in Section 6.4; explains the domain-specific rationale |
| CC-03 | **Complete rewrite**: removed Louvain CommunityDetector and quadratic ClusterScorer (rejected in Section 6.4); replaced with NetworkRiskScorer implementing noisy-OR (λ=0.5, cap 3 hops, leave-one-out per-neighbour attribution); updated EscalationEngine justification text to reference noisy-OR score; renamed endpoint to `/analyze-network`; updated tests to verify noisy-OR formula, monotonicity, attribution, and MATCH-ceiling invariant |
| CD-05 | **Fixed waterfall** to use Section 6.3 six-factor weights summing to 0.640 (was: 4 factors summing to 0.435 while claiming 0.64) |
| CD-05 | **Fixed band label**: "REVIEW band: 0.50 → 0.85" replaced with explicit label that R ≥ 0.85 is high-priority REVIEW, not MATCH — Track B risk score never produces a block |

---

## CHANGELOG: v1.0 → v1.1

| Section | Change |
|---|---|
| Executive Summary | Added KYB-first framing; KYC extension note; TRON/USDT as primary rail |
| Section 1 | KYC extension note added throughout |
| Section 3.2 | KYC extension note added |
| Section 4.2 | `crypto-screener` domain updated: `kyb_registry.py` added; stablecoin files restructured by chain priority (TRON first) |
| Section 4.3 | KYB Registry Check added as first branch in data flow; MiCA tag added to crypto branch |
| Section 6.2 | Identity corroboration identifiers updated to distinguish KYB (registration number) from KYC (DOB/passport) |
| Section 7.1 | `ubo_resolution_status` field added to explanation tree JSON |
| Section 7.1 | Note added on UNRESOLVED UBO triggering mandatory REVIEW |
| Section 8.5 | `ubo_unresolved` and `kyb_wallet_ubo_mismatch` signals added to `CORPORATE_RISK_SIGNALS` |
| Section 8.6 | **New subsection** — KYB-Specific UBO Mandatory Verification Gate |
| Section 9.2 EU | MiCA Article 48 / USDT authorization status added |
| Section 9.2 | **New entry** — TRON Network protocol-level policy rule |
| Section 9.3 | Bulgaria and Croatia removed from FATF grey list (both exited 2023); maintenance note added |
| Section 10.1 | **Rewritten** — TRON/USDT established as primary rail; KYB attribution advantage documented |
| Section 10.2 | KYB advantage for pre-execution screening added |
| Section 10.3 | **Step 1b added** — KYB Registry Lookup as first step; hop depth scaled by internal/external status; MiCA check added as Step 6; FreezeRiskRegister added as Step 7 |
| Section 10.4 | TRON moved to top of table as primary chain |
| Section 10.5 | KYB Travel Rule advantage added |
| Section 11.2 | **New subsection** — Tether/USDT issuer mechanics added as primary rail reference |
| Section 11.3 | Renamed to 11.3; updated compliance stack to KYB-first flow |
| Section 11.4 | **New subsection** — Operational implications of Tether freeze risk for KYB customers; wallet-indexed audit trail requirement |
| Section 11.5 | **New subsection** — KYB-first compliance stack reference architecture |
| Section 12.4 | Transfer type filter added to Queue Dashboard; UBO and policy flag columns added |
| Section 12.5 | Orange (#EA580C) added for UBO UNRESOLVED |
| CC-01 | KYB-only launch note + nullable KYC fields requirement added |
| CC-02 | entity_type field handling updated for KYB/KYC distinction |
| CC-03 | MATCH ceiling constraint made explicit; UBO edge weight noted; escalation logic corrected |
| CC-04 | `TRONCorriderPolicyRule` added; MiCA tag logic added; FATF grey list correction noted |
| CC-05 | **Substantially rewritten** — TRON as primary; KYBWalletRegistry as Step 1; hop depth scaling; MiCAComplianceTagger; FreezeRiskRegister; Travel Rule KYB advantage |
| CC-06 | LLM prompt updated for KYB context; UBO status in tree; MATCH/cluster invariant test added |
| CC-07 | PEP note updated for KYB UBO context; TRON wallet diff detection added |
| CD-01 | KYB audience note added; orange added to color system |
| CD-02 | Transfer type column + filter; UBO status indicator; asset type filter updated for TRON |
| CD-03 | UBO section expanded by default; wallet registry panel added; policy flags row added |
| CD-04 | Edge types updated for KYB (UBO as primary edge); REVIEW ELEVATED label clarified |
| CD-05 | Track label added; UBO status section added; policy flags section added |
| CD-06 | Mobile scenario updated to TRON/USDT inbound with UBO UNRESOLVED |
