// Sanctions Screening System — Neo4j schema setup
// Run on startup via the neo4j import volume (see docker-compose.yml).
// Matches node labels/relationships used in domains/graph-engine/app/queries.py

// ─── Uniqueness constraints ────────────────────────────────────────────────
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT person_id_unique IF NOT EXISTS
FOR (p:Person) REQUIRE p.id IS UNIQUE;

// ─── Lookup indexes ─────────────────────────────────────────────────────────
CREATE INDEX entity_name_index IF NOT EXISTS
FOR (e:Entity) ON (e.name);

CREATE INDEX entity_country_index IF NOT EXISTS
FOR (e:Entity) ON (e.country);

CREATE INDEX entity_track_a_verdict_index IF NOT EXISTS
FOR (e:Entity) ON (e.track_a_verdict);

CREATE INDEX entity_individual_score_index IF NOT EXISTS
FOR (e:Entity) ON (e.individual_score);

CREATE INDEX entity_ubo_resolution_status_index IF NOT EXISTS
FOR (e:Entity) ON (e.ubo_resolution_status);

CREATE INDEX person_name_index IF NOT EXISTS
FOR (p:Person) ON (p.name);

// ─── Relationship property indexes ─────────────────────────────────────────
// Used by UBO resolution (50%-rule requires ownership_pct on every hop).
CREATE INDEX owned_by_ownership_pct_index IF NOT EXISTS
FOR ()-[r:OWNED_BY]-() ON (r.ownership_pct);

CREATE INDEX controlled_by_ownership_pct_index IF NOT EXISTS
FOR ()-[r:CONTROLLED_BY]-() ON (r.ownership_pct);

CREATE INDEX shares_attribute_type_index IF NOT EXISTS
FOR ()-[r:SHARES_ATTRIBUTE]-() ON (r.type);
