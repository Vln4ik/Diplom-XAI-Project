# Architecture Overview

## Runtime

- `backend-api` — synchronous REST API
- `backend-worker` — Celery worker for document and report jobs
- `postgres` — transactional store, FTS, `pgvector`
- `redis` — task broker and result backend
- `frontend` — React SPA

## Domain Boundaries

- Auth and access control
- Organization management
- Document ingestion and indexing
- Requirement registry and evidence mapping
- Report lifecycle and export
- XAI explanation layer

## First-Cut Processing Flow

1. User uploads document to organization scope.
2. API persists metadata and queues `document_process`.
3. Worker extracts text, chunks the content, stores fragments, calculates placeholder embeddings.
4. User creates a report and queues `report_analyze`.
5. Worker derives requirements, evidence, risks, explanations, and report sections.
6. User reviews the registry and generates exports.

## Storage Strategy

- Source files: filesystem storage through the backend storage service
- Metadata and business entities: PostgreSQL
- Fragment vectors: `pgvector` in PostgreSQL
- Generated exports: filesystem storage plus `export_files` table
