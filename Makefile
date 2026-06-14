.PHONY: build up down logs test init-models migrate lint fmt \
        day1-build day1-up day1-down day1-logs seed-demo

# ── Day-1 (no Neo4j / ES / Minio / Postgres / Ollama) ───────────────────────
day1-build:
	docker compose -f docker-compose.day1.yml build

day1-up:
	docker compose -f docker-compose.day1.yml up -d

day1-down:
	docker compose -f docker-compose.day1.yml down

day1-logs:
	docker compose -f docker-compose.day1.yml logs -f

seed-demo:
	python3 -m pip install httpx -q --break-system-packages && python3 scripts/seed_demo.py

# ── Full stack ────────────────────────────────────────────────────────────────
build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose run --rm screening-api pytest tests/ -v
	docker compose run --rm entity-resolution pytest tests/ -v
	docker compose run --rm graph-engine pytest tests/ -v
	docker compose run --rm regulatory-engine pytest tests/ -v
	docker compose run --rm crypto-screener pytest tests/ -v

init-models:
	docker compose exec llm-ollama ollama pull mistral:7b
	docker compose exec llm-ollama ollama pull llama3.2:3b
	docker compose exec llm-ollama ollama pull qwen2.5:14b
	docker compose exec llm-ollama ollama pull aya:8b

migrate:
	docker compose exec postgres psql -U sanctions -d sanctions_db -f /docker-entrypoint-initdb.d/init.sql

es-setup:
	curl -X PUT "http://localhost:9200/sanctions_entities" \
	     -H "Content-Type: application/json" \
	     -d @infrastructure/elasticsearch/mappings.json

neo4j-setup:
	docker compose exec neo4j cypher-shell -u neo4j -p sanctions_neo4j \
	     --file /var/lib/neo4j/import/setup.cypher

minio-setup:
	./infrastructure/minio/buckets.sh

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

shell-%:
	docker compose exec $* /bin/bash

lint:
	docker compose run --rm screening-api ruff check .
	docker compose run --rm entity-resolution ruff check .

fmt:
	docker compose run --rm screening-api ruff format .
