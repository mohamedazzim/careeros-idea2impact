# CareerOS Data Flow

Last verified from source code: 2026-06-19

## 1. High-level request flow

```mermaid
flowchart LR
  UI["Next.js frontend"] --> API["FastAPI router"]
  API --> SVC["Domain service"]
  SVC --> DB["PostgreSQL"]
  SVC --> REDIS["Redis cache / queue / event bus"]
  SVC --> QDRANT["Qdrant vectors"]
  SVC --> EXT["External provider"]
  EXT --> SVC
  DB --> API
  REDIS --> API
  QDRANT --> API
  API --> UI
```

## 2. Learning-resource flow

```mermaid
flowchart TD
  A["Skill gaps from job matches"] --> B["skill_normalizer"]
  B --> C["learning_path_service.aggregate_skill_gaps"]
  C --> D["learning_resource_service.ensure_skill_resources"]
  D --> E1["Seeded resources"]
  D --> E2["YouTube provider"]
  D --> E3["Web provider"]
  D --> E4["Coursera provider"]
  D --> E5["Udemy provider"]
  E1 --> F["learning_resources table"]
  E2 --> F
  E3 --> F
  E4 --> F
  E5 --> F
  F --> G["learning_path_service.list_paths / get_path"]
  G --> H["frontend learning panels"]
```

### What actually happens

- `JobMatch` rows and job extraction data are read from PostgreSQL.
- Missing skills are normalized.
- Seeded resources are loaded first.
- Live providers are called only when enabled by configuration.
- Verified resources are written to `learning_resources`.
- Learning paths and gap actions read the stored resources and generate ordered steps or proof actions.

## 3. GitHub project discovery flow

```mermaid
flowchart TD
  A["Skill gaps / job_id"] --> B["learning/gap_action or github_project_service"]
  B --> C["GitHubProjectDiscoveryProvider"]
  C --> D1["/search/repositories"]
  C --> D2["/search/issues"]
  D1 --> E["Repository candidates"]
  D2 --> F["Good-first-issue candidates"]
  E --> G["Redis cache"]
  F --> G
  G --> H["frontend GitHubProjectsPanel"]
```

### What actually happens

- Repo search uses GitHub public search.
- Issue search uses GitHub public issue search.
- Tokens are used when configured; otherwise anonymous search is used.
- Results are ranked and cached, then returned to the frontend.

## 4. Opportunity and outcome flow

```mermaid
flowchart TD
  A["Opportunity discovery / alert"] --> B["CommunicationRequest"]
  B --> C["VoiceSession / VoiceConversation"]
  C --> D["Outcome persistence"]
  D --> E["ConversationSession / ConversationTranscript"]
  D --> F["OpportunityCallOutcome"]
  D --> G["CareerProgressMetric"]
  D --> H["OpportunityRerankingRecord"]
  D --> I["FollowupTask"]
  I --> J["Career coach / dashboard"]
```

### What actually happens

- Opportunity calls and notifications create communication and voice rows.
- Transcript sync stores the conversation transcript separately.
- Outcome intelligence writes funnel and conversion metrics.
- Follow-up and reranking services consume those persisted records.

## 5. Orchestration and event flow

```mermaid
flowchart LR
  S["Orchestration service"] --> W["ARQ worker"]
  W --> B["Redis event bus"]
  B --> R["Redis stream replay"]
  B --> DLQ["Dead-letter list"]
  R --> O["Orchestration history / replay"]
```

### What actually happens

- Orchestration events are published to Redis streams.
- Event replay reads from the stream by session UID.
- Dead letters are stored for later inspection.

## 6. Interview / realtime flow

```mermaid
flowchart TD
  A["Frontend interview page"] --> B["WebSocket connection"]
  B --> C["FastAPI realtime router"]
  C --> D["Interview runtime"]
  D --> E["Transcript / scoring / memory"]
  E --> F["Interview history and report endpoints"]
```

### Notes

- Auth is enforced on websocket connect.
- The frontend uses a dedicated websocket hook.
- The runtime keeps transcript and report data separate from the base interview session record.

## 7. Current gaps in the data flow

The request describes future data streams that are not present in the current code:

- resource score history tables
- learning session completion tables
- resource feedback tables
- resource outcome aggregates
- formal graph traversal engine for skills
- explicit replayable event sourcing for all learning actions

Those ideas are reasonable future additions, but they are not current runtime behavior.

