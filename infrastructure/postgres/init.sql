-- Sanctions Screening System — PostgreSQL schema
-- Tables: entities, sanctions_entities, audit_log, review_queue, kyb_wallet_registry, list_sync_state

-- ─── entities ──────────────────────────────────────────────────────────────
-- Onboarded KYB customers (businesses) and resolved UBOs (persons).
CREATE TABLE entities (
    entity_id               VARCHAR(64) PRIMARY KEY,
    entity_type             VARCHAR(16) NOT NULL DEFAULT 'business', -- business | individual | person
    legal_name              VARCHAR(512) NOT NULL,
    trading_name            VARCHAR(512),
    aliases                 JSONB NOT NULL DEFAULT '[]'::jsonb,
    country                 VARCHAR(2),
    registration_number     VARCHAR(128),
    incorporation_date      DATE,
    ubo_resolution_status   VARCHAR(16) NOT NULL DEFAULT 'UNRESOLVED'
                                CHECK (ubo_resolution_status IN ('FULL', 'PARTIAL', 'UNRESOLVED')),
    onboarding_score        NUMERIC(5,4),
    individual_risk_score   NUMERIC(5,4),
    track_a_verdict         VARCHAR(32),
    -- nullable KYC-extension fields (Section 3.2 KYC extension note)
    dob                     DATE,
    passport_number         VARCHAR(64),
    biometric_reference     TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_entities_country ON entities(country);
CREATE INDEX idx_entities_ubo_status ON entities(ubo_resolution_status);
CREATE INDEX idx_entities_legal_name ON entities(legal_name);

-- ─── sanctions_entities ────────────────────────────────────────────────────
-- Synced from OFAC SDN, UK OFSI, EU Consolidated, UN, OpenSanctions PEP (list-sync, CC-07).
CREATE TABLE sanctions_entities (
    id                  BIGSERIAL PRIMARY KEY,
    source_list         VARCHAR(32) NOT NULL
                            CHECK (source_list IN ('OFAC_SDN', 'UK_OFSI', 'EU_CONSOLIDATED', 'UN', 'PEP')),
    source_id           VARCHAR(128) NOT NULL,
    entity_type         VARCHAR(16), -- individual | entity | vessel | aircraft
    primary_name        VARCHAR(512) NOT NULL,
    aliases             JSONB NOT NULL DEFAULT '[]'::jsonb,
    addresses           JSONB NOT NULL DEFAULT '[]'::jsonb,
    identification      JSONB NOT NULL DEFAULT '[]'::jsonb, -- passport/NIN/etc
    programs            JSONB NOT NULL DEFAULT '[]'::jsonb,
    crypto_addresses    JSONB NOT NULL DEFAULT '[]'::jsonb, -- [{chain, address}]
    narrative           TEXT,
    list_version        VARCHAR(64),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_list, source_id)
);

CREATE INDEX idx_sanctions_entities_name ON sanctions_entities(primary_name);
CREATE INDEX idx_sanctions_entities_active ON sanctions_entities(source_list, is_active);
CREATE INDEX idx_sanctions_entities_crypto ON sanctions_entities USING GIN (crypto_addresses);

-- ─── audit_log ─────────────────────────────────────────────────────────────
-- Write-once audit record. wallet_address is the PRIMARY index for freeze-risk
-- reconstruction (Section 11.4); entity_id is a secondary index.
CREATE TABLE audit_log (
    id                   BIGSERIAL PRIMARY KEY,
    wallet_address       VARCHAR(128),
    entity_id            VARCHAR(64),
    payment_id           VARCHAR(64) NOT NULL,
    screening_timestamp  TIMESTAMPTZ NOT NULL DEFAULT now(),
    screening_result     JSONB NOT NULL,
    verdict              VARCHAR(16) NOT NULL CHECK (verdict IN ('MATCH', 'REVIEW', 'NO_MATCH')),
    list_version_ofac    VARCHAR(64),
    list_version_ofsi    VARCHAR(64),
    algorithm_version    VARCHAR(16) NOT NULL DEFAULT 'v1.2',
    document_refs        JSONB NOT NULL DEFAULT '[]'::jsonb, -- MinIO object keys
    retention_until      TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- wallet_address is the primary index for freeze-risk reconstruction (Section 11.4)
CREATE INDEX idx_audit_log_wallet_address ON audit_log(wallet_address);
CREATE INDEX idx_audit_log_entity_id ON audit_log(entity_id);
CREATE INDEX idx_audit_log_payment_id ON audit_log(payment_id);

-- Enforce write-once: no UPDATE or DELETE on audit_log rows.
CREATE OR REPLACE FUNCTION reject_audit_log_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log records are write-once and cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_log_no_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();

CREATE TRIGGER trg_audit_log_no_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();

-- ─── review_queue ──────────────────────────────────────────────────────────
-- Priority-sorted analyst review queue (score DESC, SLA ASC).
CREATE TABLE review_queue (
    payment_id        VARCHAR(64) PRIMARY KEY,
    entity_id         VARCHAR(64),
    verdict           VARCHAR(16) NOT NULL CHECK (verdict IN ('MATCH', 'REVIEW', 'NO_MATCH')),
    track             VARCHAR(32) NOT NULL,
    composite_score   NUMERIC(5,4) NOT NULL,
    priority          NUMERIC(5,4) NOT NULL,
    sla_due_at        TIMESTAMPTZ NOT NULL,
    status            VARCHAR(16) NOT NULL DEFAULT 'PENDING'
                          CHECK (status IN ('PENDING', 'IN_REVIEW', 'DECIDED', 'ESCALATED')),
    assigned_analyst  VARCHAR(128),
    decision          VARCHAR(16) CHECK (decision IN ('CLEAR', 'BLOCK', 'ESCALATE')),
    decision_notes    TEXT,
    payload           JSONB NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at        TIMESTAMPTZ
);

CREATE INDEX idx_review_queue_priority ON review_queue(status, priority DESC, sla_due_at ASC);

-- ─── kyb_wallet_registry ───────────────────────────────────────────────────
-- Durable store mirroring the Redis KYB wallet registry hash (CC-05).
CREATE TABLE kyb_wallet_registry (
    wallet_address          VARCHAR(128) PRIMARY KEY,
    chain                   VARCHAR(16) NOT NULL,
    entity_id               VARCHAR(64) NOT NULL REFERENCES entities(entity_id),
    ubo_resolution_status   VARCHAR(16) NOT NULL DEFAULT 'UNRESOLVED'
                                CHECK (ubo_resolution_status IN ('FULL', 'PARTIAL', 'UNRESOLVED')),
    onboarding_score        NUMERIC(5,4),
    kyb_verified_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active               BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_kyb_wallet_registry_entity ON kyb_wallet_registry(entity_id);

-- ─── list_sync_state ───────────────────────────────────────────────────────
-- DiffEngine bookkeeping for zero-downtime list-sync (CC-07).
CREATE TABLE list_sync_state (
    source_list      VARCHAR(32) PRIMARY KEY
                         CHECK (source_list IN ('OFAC_SDN', 'UK_OFSI', 'EU_CONSOLIDATED', 'UN', 'PEP')),
    list_version     VARCHAR(64),
    entry_count      INTEGER,
    last_synced_at   TIMESTAMPTZ,
    last_success_at  TIMESTAMPTZ,
    last_diff        JSONB NOT NULL DEFAULT '{}'::jsonb
);
