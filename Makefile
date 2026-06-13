.PHONY: build up down logs test init-models migrate lint fmt

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
