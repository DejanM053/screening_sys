"""Cypher queries for the graph engine (CC-03)."""

MERGE_ENTITY = """
MERGE (e:Entity {id: $entity_id})
SET e.name = $name,
    e.country = $country,
    e.individual_score = $individual_score,
    e.ubo_resolution_status = $ubo_resolution_status,
    e.track_a_verdict = $track_a_verdict,
    e.updated_at = datetime()
RETURN e
"""

MERGE_SHARED_ATTRIBUTE_EDGE = """
MATCH (a:Entity {id: $entity_a}), (b:Entity {id: $entity_b})
MERGE (a)-[r:SHARES_ATTRIBUTE {type: $attr_type}]->(b)
SET r.weight = $weight,
    r.updated_at = datetime()
RETURN r
"""

GET_FLAGGED_NEIGHBOURS = """
MATCH path = (e:Entity {id: $entity_id})-[:SHARES_ATTRIBUTE|OWNED_BY|CONTROLLED_BY*1..3]-(f:Entity)
WHERE (f.track_a_verdict = 'MATCH' OR f.individual_score >= $review_threshold)
  AND f.id <> $entity_id
WITH f, min(length(path)) AS hop_distance
RETURN f.id AS neighbour_id,
       f.name AS neighbour_name,
       f.track_a_verdict AS track_a_verdict,
       f.individual_score AS risk_score,
       hop_distance
ORDER BY hop_distance ASC, f.individual_score DESC
LIMIT 50
"""

SHORTEST_PATH = """
MATCH (a:Entity {id: $entity_a}), (b:Entity {id: $entity_b})
MATCH path = shortestPath((a)-[:SHARES_ATTRIBUTE|OWNED_BY|CONTROLLED_BY*..6]-(b))
RETURN length(path) AS distance
"""

DETECT_CIRCULAR_OWNERSHIP = """
MATCH p = (e:Entity {id: $entity_id})-[:OWNED_BY*2..10]->(e)
RETURN e.id AS entity_id, length(p) AS cycle_length
LIMIT 5
"""

UBO_RESOLUTION = """
MATCH p=(start:Entity {id: $entity_id})-[:OWNED_BY|CONTROLLED_BY*1..{max_depth}]->(ubo:Person)
WHERE NOT (ubo)-[:OWNED_BY|CONTROLLED_BY]->()
  AND all(r in relationships(p) WHERE r.ownership_pct IS NOT NULL)
RETURN p, ubo,
       reduce(pct = 1.0, r in relationships(p) | pct * r.ownership_pct) AS effective_ownership
ORDER BY effective_ownership DESC
"""

ENTITIES_BY_SHARED_UBO = """
MATCH (a:Entity)-[:OWNED_BY|CONTROLLED_BY*1..4]->(ubo:Person)<-[:OWNED_BY|CONTROLLED_BY*1..4]-(b:Entity)
WHERE a.id = $entity_id AND b.id <> $entity_id
RETURN b.id AS related_entity_id, b.name AS name, ubo.id AS shared_ubo_id
"""
