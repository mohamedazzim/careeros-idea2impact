# Data Models and Persistence

Last verified from source code: 2026-06-14

## Persistence overview

CareerOS persists data primarily in PostgreSQL, with Qdrant for vector-backed retrieval and Redis for operational coordination.

## Model inventory

Current ORM model classes discovered in `backend/src/models`: 67

## Functional grouping

- Identity and access
- Content and knowledge
- Jobs and matching
- Opportunity execution and communications
- Orchestration and governance
- Interview and evaluation
- Reranking, memory, and learning
- Planning
- Operations

## Retrieval and vector layer

The codebase uses Qdrant collections for resumes, jobs, and knowledge.

## Source anchors

- `backend/src/models`
- `backend/src/services/retrieval`
- `backend/src/services/opportunity`
- `backend/src/services/intelligence`
