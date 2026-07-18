# Known Limitations

Last verified from source code: 2026-06-14

## Missing pieces

- The backend docs-RAG runtime is implemented, but the optional Make.com scenario still needs to be configured outside the repo if you want external orchestration.
- A live deployment still needs the correct Qdrant and LLM credentials for the environment it runs in.

## External dependency limitations

- Voice calls depend on ElevenLabs and Twilio configuration.
- Outbound call handoff can depend on Pipedream when that bridge is configured.
- Browser voice interview tests require microphone permission and websocket access.

## Demo-only assumptions

- Some examples assume a local development environment.
- Login examples assume a valid account already exists.
- Workflow examples assume the user has a resume uploaded or a matching job feed available.

## Production risks

- Outbound voice workflows should be verified carefully before production calls.
- Autonomous actions must stay behind governance gates.
- Any new RAG ingestion pipeline must keep candidate PII out of shared docs.
- The docs RAG chatbot should be regression-tested after any docs or prompt change.

## What needs verification

- The final Make.com scenario wiring
- Whether Make is acting only as orchestration or also as a transport relay
- Qdrant availability and collection readiness in the target deployment
- Any roadmap or coach flow that is not explicitly exercised in a demo
