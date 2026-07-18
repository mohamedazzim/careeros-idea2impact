# Frontend Surface

Last verified from source code: 2026-06-14

## Frontend architecture

The frontend uses the Next.js App Router under `frontend/src/app`.
Most data access flows through `useCareerOS()`, while realtime interview traffic uses `useInterviewWebSocket()`.
Shared auth state is stored in `careeros_token` and mirrored into cookies.

## Shared frontend helpers

- `frontend/src/hooks/useCareerOS.ts` is the main application data hook.
- `frontend/src/hooks/useWebSocket.ts` provides realtime and interview socket helpers.
- `frontend/src/lib/resilience.ts` implements `resilientFetch()` and a type-safe API client wrapper.
- `frontend/src/lib/auth-session.ts` reads and clears the auth session.
- `frontend/src/lib/rbac.ts` defines public and role-gated routes.
- `frontend/src/lib/datetime.ts` centralizes date/time formatting.

## Current route map

| Route | Page component | Purpose |
| --- | --- | --- |
| `/` | redirect page | Redirects into the authenticated app |
| `/dashboard` | `DashboardView` | Resume/job intelligence dashboard |
| `/jobs` | `JobsIntelligenceView` | Ranked job matches and pipeline status |
| `/jobs/alerts` | `AlertRecordsView` | Alert records and alert pipeline visibility |
| `/jobs/library` | `JobLibraryView` | Job inventory and refresh actions |
| `/knowledge` | `KnowledgeHub` | Upload, analyze, and manage knowledge docs |
| `/packages` | `ApplicationPackagesView` | Generate and manage application assets |
| `/coach` | `CareerCoachDashboard` + `InterviewCoachView` | Coaching and interview surfaces |
| `/interview` | live interview page | Live voice interview experience |
| `/opportunities` | `OpportunityCenterView` | Opportunity intelligence and outcomes |
| `/command-center` | `CommandCenterView` | Readiness and agent status dashboard |
| `/approvals` | `HumanApprovalCenterView` | Human approval queue |
| `/ops` | `OpsCenterView` | Operational health and circuit controls |
| `/orchestration` | orchestration overview | Orchestration timelines and runs |
| `/orchestration/governance` | governance page | Governance decisions and rules |
| `/orchestration/history` | history page | Past orchestration sessions |
| `/orchestration/live` | live page | Active orchestration step view |
| `/orchestration/traces` | traces page | Orchestration trace viewer |
| `/rerank` | `RerankMonitoringDashboard` | Reranking monitoring and stats |
| `/preferences` | `PreferencesPanel` | User preferences |
| `/roadmap` | `CareerRoadmapView` | Roadmap and planning surface |
| `/account` | account page | Profile and auth state |
| `/demo-rag` | `demo-rag` page | Mentor/HR chatbot demo surface |
| `/evaluation` | `EvaluationView` | Evaluation runs and benchmark tools |
| `/login` | login page | Auth entry point |
| `/forgot-password` | forgot password page | Password reset request |
| `/reset-password` | reset password page | Password reset completion |
| `/workflow/alignment-report/[runId]` | alignment report page | Detailed analysis report for a run |

## Source anchors

- `frontend/src/app`
- `frontend/src/components`
- `frontend/src/hooks/useCareerOS.ts`
- `frontend/src/hooks/useWebSocket.ts`
- `frontend/src/lib/resilience.ts`
- `frontend/src/lib/rbac.ts`
- `frontend/src/lib/auth-session.ts`
- `frontend/src/lib/datetime.ts`
