# SANCTIONS SCREENING SYSTEM — BUILD SPEC
## Day-1 Hackathon Target (derived from VISION.md)

Full architecture, regulatory research, and design prompts → **VISION.md**
This file contains ONLY what gets built on day 1 and day 2.

---

## WHAT WE ARE BUILDING

One in-process FastAPI service (`screening-api`) that:
1. Receives a business entity name + country (or TRON wallet address)
2. Runs Track A — deterministic sanctions gate via yente/OpenSanctions
3. Runs Track B — probabilistic risk score (6 factors, weighted sum)
4. Returns a structured verdict (MATCH / REVIEW / NO_MATCH) + explanation tree
5. Serves a React frontend: Queue screen + Case Detail with explanation panel

**No Kong. No Celery. No Neo4j. No Elasticsearch. No MinIO. No live Ollama calls.**
Replace each with the in-process or synthetic equivalent listed below.

---

## ARCHITECTURE (Day 1)

Single Docker service: `screening-api` (FastAPI, port 8001)

In-process dependencies:
- **yente** (OpenSanctions API) — real OFAC data, no local install needed on day 1
- **RapidFuzz** — in-process name matching, replaces Elasticsearch
- **networkx** — in-memory ownership graph, replaces Neo4j
- **Redis** — KYB wallet registry + review queue (keep this real)
- **SQLite** — audit trail for day 1 (Postgres migration is day 2)

---

## TRACK A — SANCTIONS GATE (deterministic)

Three deterministic paths to MATCH:
1. **Identity match**: name composite ≥ 0.92 AND ≥1 corroborating identifier
2. **50%-rule**: ownership chain ≥ 50% by a named SDN (all percentages established)
3. **Country-sanctions**: BLACK-tier jurisdiction (Iran / North Korea / Myanmar)

Partial match (name 0.70–0.92, no corroboration) → **REVIEW** (Track A:partial)

**Implementation:** yente public OpenSanctions API for OFAC SDN.
**Matcher:** RapidFuzz composite — Jaro-Winkler + Levenshtein + token-sort ratio.
**Identity thresholds** (tune on demo data):
- composite ≥ 0.92 + ≥1 corroborating id → MATCH
- composite 0.85–0.92 no corroboration, or 0.70–0.92 partial corroboration → REVIEW
- below 0.70 → falls through to Track B

---

## TRACK B — RISK SCORE (6 factors)

```
R = clamp01( sum(w_i * factor_i) )     # six factors, sum(w_i) = 1.0
```

R ≥ 0.50 → REVIEW. **Track B can NEVER produce MATCH.**

| # | Factor | Weight | Day 1 source |
|---|--------|--------|--------------|
| 1 | Identity match signal | 25% | yente match score (mirrored from Track A as feature only) |
| 2 | Behavioral anomaly | 20% | Synthetic: fake tx history for 3 demo entities |
| 3 | Network noisy-OR | 20% | networkx synthetic graph + 1 real OFAC SDN node |
| 4 | Entity risk profile | 15% | Deterministic flags on submitted metadata |
| 5 | Doc / onboarding integrity | 10% | Stub: fixed 0.5 with "pending" note |
| 6 | Historical flag rate | 10% | Beta-Binomial on synthetic prior screenings |

---

## NETWORK RISK (Factor 3) — noisy-OR

```
network_risk(e) = 1 - ∏_f [ 1 - p_f × λ^d(e,f) ]
```

- `λ = 0.5` per-hop decay; `d` capped at 3
- `p_f = 1.0` for confirmed SDN; entity's Track B score for REVIEW nodes
- **Graph:** networkx, ~20 synthetic nodes + 1 real OFAC SDN node
- Per-neighbour leave-one-out attribution drives the explanation panel
- **Hard ceiling:** noisy-OR result escalates to REVIEW only, never MATCH

Worked example already in code:
```
entity e: 1 hop from SDN S (p=1.0), 2 hops from REVIEW M (p=0.6)
network_risk = 1 - (1 - 1.0×0.5¹) × (1 - 0.6×0.5²) = 0.575 → REVIEW
```

---

## REGULATORY ENGINE (one real ruleset)

Wire **OFAC (US) only**. Stub the remaining 7 as passthrough.

OFAC rule returns:
- Required lists: OFAC SDN + all programs
- MATCH/REVIEW thresholds
- SAR obligation flag (within 30 days)
- Retention: 5 years

Country risk tiers loaded from `app/config/country_risk_tiers.yaml`.
BLACK-tier jurisdiction check feeds Track A:country-sanctions.

---

## CRYPTO SCREENER (hardcoded TRON/USDT scenario)

No live Tronscan/Etherscan calls on day 1.

- **OFAC wallet list:** download once from `ofac.treasury.gov`; store in Redis
- **KYB wallet registry:** 5 synthetic entities in Redis
- **Demo scenario:** `TXxx...` (KYB-verified, FULL UBO) → `TYyy...` (external, 2-hop from OFAC SDN wallet)
- **MiCA flag:** emit `MiCA_COMPLIANCE_RISK` on EU corridor + USDT (policy tag, no score impact)
- **Hop trace:** return hardcoded result for demo wallets; real BFS is day 2

Scoring decay for on-chain hops (linear, distinct from noisy-OR geometric):
- Direct hit: 1.0 | 1 hop: 0.7 | 2 hops: 0.4 | 3 hops: 0.1

---

## EXPLANATION GRAPH API

Every verdict produces a `ScoreNode` DAG:
```
Root (composite score)
  ├── Track A result (identity / country-sanctions / 50%-rule / partial)
  ├── Factor 1: Identity match signal
  │     ├── OFAC SDN (score, detail)
  │     └── EU Consolidated (score, detail)
  ├── Factor 2: Behavioral anomaly
  ├── Factor 3: Network noisy-OR
  │     └── per-neighbour attribution (leave-one-out)
  ├── Factor 4: Entity risk profile
  │     └── corporate risk flags
  ├── Factor 5: Doc integrity (stub)
  └── Factor 6: Historical flag rate
```

Serialize to JSON for:
1. Audit trail (SQLite, day 1)
2. Frontend explanation panel

**LLM explanation:** pre-generated text string, not a live Ollama call.
Swap to real `qwen2.5:14b` on day 2 once model is pulled.

---

## FRONTEND (2 screens wired)

**Screen 1 — Queue Dashboard** (`/`)
- Priority-sorted REVIEW queue fetched from Redis via `/queue` endpoint
- Columns: priority rank | entity name | country | score | verdict badge | time in queue
- Transfer type badge: INTERNAL / OUTBOUND / INBOUND
- Orange dot if UBO UNRESOLVED; blue tag if MiCA/TRON flag present
- Click row → Screen 2

**Screen 2 — Case Detail** (`/case/:id`)
- Left panel: payment instruction + UBO resolution status badge
- Center panel: score waterfall (6 factors, weighted contributions, click to expand)
- Right panel: network cluster mini-graph (networkx output, D3 force-directed, ≤10 nodes)
- Action bar: CLEAR | BLOCK | ESCALATE (write decision to audit trail)

**Not wired on day 1:** Network Explorer full-screen / Mobile Approval / Audit Export

---

## DEMO CHECKPOINT (end of day 1)

1. POST `/screen/fiat` with `{"name": "Al-Qadir Trading LLC", "country": "AE"}`
   - Hits EU Consolidated List at 0.71 name score → Track A:partial → REVIEW
   - Track B adds 0.116 network risk from synthetic SDN neighbour
   - Response: `{"verdict": "REVIEW", "composite_score": 0.64, "explanation_tree": {...}}`

2. POST `/screen/wallet` with `{"address": "TYyy...", "chain": "tron", "stablecoin": "USDT", "corridor": "GB→AE"}`
   - 2 hops from OFAC SDN wallet → hop score 0.4 → REVIEW
   - MiCA flag absent (not EU corridor); TRON corridor note emitted
   - Response: `{"verdict": "REVIEW", "hop_analysis": {...}, "mica_flag": null}`

3. Frontend: Queue shows 3 synthetic REVIEW cases; click case → explanation panel
   renders waterfall + mini network graph.

---

## DAY 1 BUILD SEQUENCE (first 24 hours)

1. `screening-api` skeleton: FastAPI app, `/screen/fiat`, `/screen/wallet` endpoints
2. Track A: yente integration, RapidFuzz composite, identity + country-sanctions paths
3. Track B: 6-factor scorer (factors 2, 5, 6 on synthetic data)
4. Network noisy-OR on synthetic networkx graph (one real OFAC SDN node)
5. Explanation tree builder → JSON serialization
6. OFAC ruleset wired to screening-api
7. Redis: KYB wallet registry + priority review queue
8. Frontend Screen 1 wired to `/queue` endpoint
9. Frontend Screen 2 wired to `/screen` + `/explanation/{id}` endpoints

---

## DAY 2 BUILD SEQUENCE (second 24 hours)

- Swap SQLite → PostgreSQL (audit trail migration)
- Swap networkx → Neo4j (migrate synthetic graph to Cypher, use CC-03 queries)
- Swap RapidFuzz-only → Elasticsearch + RapidFuzz (entity-resolution service)
- Pull `ollama qwen2.5:14b`; swap pre-generated text → live explanation calls
- Add list-sync: Celery + OFAC SDN daily refresh (CC-07)
- Add Frontend Screen 3: Network Explorer (full D3 force-directed graph)
- Add 2nd jurisdiction ruleset: FCA (UK)
- Add transliteration: Arabic/Russian → Latin (entity-resolution service)
- Wire entity-resolution, graph-engine, list-sync as separate Docker services

---

## WHAT IS SLIDES / ROADMAP (do not build yet)

- API Gateway (Kong/Traefik)
- 6 additional jurisdiction rulesets: FCA, EU, AUSTRAC, FINTRAC, DFSA, MiCA
  (stubs exist; wire one per sprint after day 2)
- Celery on day 1
- MinIO (audit document object storage)
- Live Tronscan/Etherscan hop tracing
- OFSI / EU Consolidated / UN / PEP list parsers (day 1)
- Live Ollama calls (day 1)
- ML layer: LightGBM + SHAP + Isolation Forest (no labels yet)
- Factor 5: document integrity (no doc verification pipeline yet)
- Notification service
- Travel Rule enforcement (VASP registry needed)
- Mobile Approval screen (CD-06)
- Audit Export screen
- Adverse media classification (no article corpus)
- SAR generation
