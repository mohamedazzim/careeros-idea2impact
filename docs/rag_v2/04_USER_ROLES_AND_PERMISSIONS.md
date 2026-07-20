---
title: "User Roles And Permissions"
document_id: "04_user_roles_and_permissions"
domain: "security"
feature: "roles"
audience:
  - user
  - developer
  - operator
implementation_status: "PARTIALLY_IMPLEMENTED"
source_of_truth: "codebase"
last_verified: "2026-07-19"
tags:
  - roles
  - auth
---

# User Roles And Permissions

CareerOS primarily implements authenticated candidate/user access. The backend uses JWT claims to identify the user and enforce ownership filters on user-specific resources. Role schemas and role requirement helpers exist, but most registered business APIs are user-owned rather than deeply role-scoped.

## Authentication Dependency

Routes use `Depends(get_current_user)` or `Depends(get_current_user_id)`. The auth dependency decodes the JWT and exposes `sub` as the user identifier. Auth endpoints set HttpOnly cookies and also return token pairs for client storage.

## Ownership Isolation

User-specific tables commonly store `user_id` or `candidate_id`. Routes filter by `user["sub"]` in jobs, opportunities, knowledge docs, outcome intelligence, applications, and voice sessions. Resume vectors carry `user_id` in Qdrant payloads. The docs-RAG collection is product documentation, not user-specific data.

## Common Questions This Document Answers

- What is implemented in CareerOS for this area?
- Which frontend, backend, data model, and integration files are source of truth?
- Which parts are implemented, partial, mocked, configured but unused, or not found?

## Verified Source Files

- `backend/src/api/deps.py`
- `backend/src/services/security/auth.py`
- `backend/src/api/v1/endpoints/auth.py`

## Implementation Gaps and Limitations

- Claims are limited to repository evidence inspected on 2026-07-19.
- External dashboards for ElevenLabs, Twilio, Make.com, Pipedream, TheirStack, and hosting were not available and are marked `EXTERNAL_CONFIGURATION_NOT_AVAILABLE` where relevant.
