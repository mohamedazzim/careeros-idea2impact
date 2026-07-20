---
title: "Deployment Docker And Infrastructure"
document_id: "22_deployment_docker_and_infrastructure"
domain: "ops"
feature: "deployment"
audience:
  - user
  - developer
  - operator
implementation_status: "PARTIALLY_IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - deployment
  - docker
  - infra
---

# Deployment, Docker, And Infrastructure

The repository contains backend, frontend, Docker, Alembic, worker, and infrastructure-oriented files. Runtime services include FastAPI, PostgreSQL, Redis, Qdrant, Celery workers, frontend application code, and external AI/provider APIs.

## Runtime Components

- FastAPI app is assembled in `backend/src/main.py`.
- Database migrations live under `backend/alembic/versions`.
- Workers live under `backend/src/workers` and include job ingestion, autonomous engagement, transcript sync, and related async tasks.
- Frontend routes live under `frontend/src/app` with major views in `frontend/src/components`.
- Docker and compose files configure local and deployable service topology where present.

## Operational Boundary

This documentation validates repository-defined infrastructure and settings. Cloud host configuration, external dashboards, DNS, Twilio numbers, ElevenLabs agents, Make scenarios, and Pipedream workflows must be verified outside the repository.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/main.py`
- `backend/alembic/versions`
- `backend/src/workers`
- `frontend/src/app`
- `docker-compose.yml`
- `Dockerfile`
- `backend/Dockerfile`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
