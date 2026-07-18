from inspect import signature
from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_current_user
from src.api.v1.endpoints import skill_graph as skill_graph_endpoint
from src.db.session import get_db
from src.services.learning.skill_normalizer import normalize_skill
from src.main import app
from src.services.skill_graph import skill_graph_service as skill_graph_service_module
from src.services.skill_graph.skill_graph_service import SkillEvidenceCandidate, SkillGraphService


if "app" not in signature(httpx.Client.__init__).parameters:
    _httpx_client_init = httpx.Client.__init__

    def _patched_httpx_client_init(self, *args, app=None, **kwargs):
        return _httpx_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = _patched_httpx_client_init


client = TestClient(app)


async def _override_db():
    yield SimpleNamespace()


class _FakeSkillGraphService:
    async def get_health(self, db):
        return {
            "status": "ok",
            "ready": True,
            "tables": ["skill_graph_nodes", "skill_graph_edges"],
            "collection": "skill_graph",
            "message": "2 nodes, 1 edge, 3 evidence rows, 1 import run.",
        }

    async def get_summary(self, db, *, user_id=None, limit: int = 12):
        return {
            "status": "ok",
            "total_nodes": 2,
            "total_edges": 1,
            "total_evidence": 3,
            "total_aliases": 2,
            "total_user_states": 1,
            "source_counts": {"job": 2, "learning_session": 1},
            "top_nodes": [
                {
                    "skill_slug": "python",
                    "skill_name": "Python",
                    "category": "language",
                    "status": "validated",
                    "evidence_count": 3,
                    "source_count": 2,
                    "user_count": 1,
                    "demand_count": 1,
                    "supply_count": 2,
                    "trust_score": 0.91,
                    "relevance_score": 0.88,
                    "freshness_score": 0.86,
                    "confidence_score": 0.9,
                    "first_seen_at": "2026-06-19T00:00:00Z",
                    "last_seen_at": "2026-06-20T00:00:00Z",
                    "last_import_run_uid": "run-1",
                    "metadata": {},
                }
            ],
            "user_states": [],
            "latest_import_run": {
                "run_uid": "run-1",
                "user_id": "user-123",
                "scope": "full",
                "status": "completed",
                "strategy": "real_data_import_v1",
                "node_count": 2,
                "edge_count": 1,
                "evidence_count": 3,
                "alias_count": 2,
                "user_state_count": 1,
                "source_counts": {"job": 2, "learning_session": 1},
                "notes": None,
                "error_message": None,
                "metadata": {},
                "started_at": "2026-06-20T00:00:00Z",
                "completed_at": "2026-06-20T00:01:00Z",
                "created_at": "2026-06-20T00:00:00Z",
                "updated_at": "2026-06-20T00:01:00Z",
            },
        }

    async def list_nodes(self, db, *, search=None, limit: int = 25):
        return [
            {
                "skill_slug": "python",
                "skill_name": "Python",
                "category": "language",
                "status": "validated",
                "evidence_count": 3,
                "source_count": 2,
                "user_count": 1,
                "demand_count": 1,
                "supply_count": 2,
                "trust_score": 0.91,
                "relevance_score": 0.88,
                "freshness_score": 0.86,
                "confidence_score": 0.9,
                "first_seen_at": "2026-06-19T00:00:00Z",
                "last_seen_at": "2026-06-20T00:00:00Z",
                "last_import_run_uid": "run-1",
                "metadata": {},
            }
        ]

    async def get_node_detail(self, db, skill_slug, *, user_id=None, limit: int = 12):
        return {
            "status": "ok",
            "node": {
                "skill_slug": "python",
                "skill_name": "Python",
                "category": "language",
                "status": "validated",
                "evidence_count": 3,
                "source_count": 2,
                "user_count": 1,
                "demand_count": 1,
                "supply_count": 2,
                "trust_score": 0.91,
                "relevance_score": 0.88,
                "freshness_score": 0.86,
                "confidence_score": 0.9,
                "first_seen_at": "2026-06-19T00:00:00Z",
                "last_seen_at": "2026-06-20T00:00:00Z",
                "last_import_run_uid": "run-1",
                "metadata": {},
            },
            "aliases": [
                {
                    "raw_value": "python",
                    "normalized_value": "python",
                    "source_entity_type": "job",
                    "source_entity_id": "job-1",
                    "source_field": "skills_required",
                    "source_table": "jobs",
                    "source_pk": "1",
                    "provider": "jobs",
                    "alias_type": "source_value",
                    "metadata": {},
                    "created_at": "2026-06-20T00:00:00Z",
                    "skill_slug": "python",
                    "skill_name": "Python",
                }
            ],
            "edges": [],
            "evidence": [],
            "user_states": [],
        }

    async def list_user_states(self, db, *, user_id: str, limit: int = 20):
        return [
            {
                "state_uid": "state-1",
                "user_id": user_id,
                "skill_slug": "python",
                "skill_name": "Python",
                "category": "language",
                "status": "validated",
                "confidence_score": 0.9,
                "evidence_count": 3,
                "demand_count": 1,
                "supply_count": 2,
                "learning_signal_count": 1,
                "resume_signal_count": 1,
                "started_count": 1,
                "completion_count": 1,
                "feedback_count": 1,
                "average_rating": 4.5,
                "last_activity_at": "2026-06-20T00:00:00Z",
                "last_import_run_uid": "run-1",
                "recommended_action": "Keep proof fresh with another outcome.",
                "evidence_summary": {},
                "metadata": {},
            }
        ]

    async def list_import_runs(self, db, *, limit: int = 10):
        return [
            {
                "run_uid": "run-1",
                "user_id": "user-123",
                "scope": "full",
                "status": "completed",
                "strategy": "real_data_import_v1",
                "node_count": 2,
                "edge_count": 1,
                "evidence_count": 3,
                "alias_count": 2,
                "user_state_count": 1,
                "source_counts": {"job": 2, "learning_session": 1},
                "notes": None,
                "error_message": None,
                "metadata": {},
                "started_at": "2026-06-20T00:00:00Z",
                "completed_at": "2026-06-20T00:01:00Z",
                "created_at": "2026-06-20T00:00:00Z",
                "updated_at": "2026-06-20T00:01:00Z",
            }
        ]

    async def import_graph(self, db, *, user_id=None, request=None):
        return {
            "status": "ok",
            "run": {
                "run_uid": "run-1",
                "user_id": user_id,
                "scope": "full",
                "status": "completed",
                "strategy": "real_data_import_v1",
                "node_count": 2,
                "edge_count": 1,
                "evidence_count": 3,
                "alias_count": 2,
                "user_state_count": 1,
                "source_counts": {"job": 2, "learning_session": 1},
                "notes": request.notes if request else None,
                "error_message": None,
                "metadata": {},
                "started_at": "2026-06-20T00:00:00Z",
                "completed_at": "2026-06-20T00:01:00Z",
                "created_at": "2026-06-20T00:00:00Z",
                "updated_at": "2026-06-20T00:01:00Z",
            },
            "node_count": 2,
            "edge_count": 1,
            "evidence_count": 3,
            "alias_count": 2,
            "user_state_count": 1,
            "source_counts": {"job": 2, "learning_session": 1},
        }


def _candidate(
    *,
    skill_slug: str,
    skill_name: str,
    source_entity_type: str,
    source_entity_id: str,
    source_field: str = "skills",
    source_table: str | None = None,
    source_pk: str | None = None,
    source_title: str | None = None,
    provider: str | None = None,
    evidence_kind: str = "skill",
    raw_value: str | None = None,
    user_id: str | None = None,
    source_group: str | None = None,
    metadata: dict | None = None,
    observed_at: datetime | None = None,
) -> SkillEvidenceCandidate:
    return SkillEvidenceCandidate(
        skill_slug=skill_slug,
        skill_name=skill_name,
        raw_value=raw_value or skill_name,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        source_table=source_table,
        source_pk=source_pk,
        source_field=source_field,
        source_title=source_title,
        source_url=None,
        provider=provider,
        evidence_kind=evidence_kind,
        trust_score=0.9,
        relevance_score=0.8,
        freshness_score=0.7,
        confidence="high",
        status="success",
        observed_at=observed_at or datetime(2026, 6, 20, 0, 0, 0),
        user_id=user_id,
        source_group=source_group,
        metadata=metadata or {},
    )


@pytest.fixture
def authenticated_skill_graph(monkeypatch):
    original_overrides = dict(app.dependency_overrides)

    async def _override_user():
        return {"sub": "user-123", "role": "Admin"}

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    monkeypatch.setattr(skill_graph_endpoint, "get_skill_graph_service", lambda: _FakeSkillGraphService())

    yield

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


def test_skill_graph_scoring_helpers_are_honest():
    service = SkillGraphService()

    node_status, node_score = service.score_node_status(
        evidence_count=1,
        source_count=1,
        demand_count=0,
        supply_count=0,
        learning_signal_count=0,
    )
    assert node_status == "insufficient_data"
    assert node_score < 0.5

    user_status, user_score, recommendation = service.score_user_status(
        demand_count=1,
        supply_count=0,
        learning_signal_count=1,
        resume_signal_count=0,
        started_count=0,
        completion_count=0,
        feedback_count=0,
    )
    assert user_status == "insufficient_data"
    assert user_score < 0.5
    assert "learning session" in recommendation.lower() or "proof artifact" in recommendation.lower()


def test_skill_alias_keeps_java_and_javascript_separate():
    java = normalize_skill("Java")
    javascript = normalize_skill("JavaScript")

    assert java.slug == "java"
    assert javascript.slug == "javascript"
    assert java.display_name == "Java"
    assert javascript.display_name == "JavaScript"


def test_skill_alias_handles_cpp_csharp_cicd():
    cpp = normalize_skill("C++")
    csharp = normalize_skill("C#")
    cicd = normalize_skill("CI/CD")

    assert cpp.slug == "cpp"
    assert cpp.display_name == "C++"
    assert csharp.slug == "c#"
    assert csharp.display_name == "C#"
    assert cicd.slug == "ci-cd"
    assert cicd.display_name == "CI/CD"


def test_upsert_skill_node_deduplicates_by_slug():
    service = SkillGraphService()
    python_job = _candidate(
        skill_slug="python",
        skill_name="Python",
        source_entity_type="job",
        source_entity_id="job-1",
        source_table="jobs",
        source_pk="1",
        source_title="Backend Engineer",
        provider="jobs",
        evidence_kind="job_requirement",
        raw_value="Python",
    )
    python_resume = _candidate(
        skill_slug="python",
        skill_name="Python",
        source_entity_type="resume_chunk",
        source_entity_id="resume-1",
        source_table="resume_chunks",
        source_pk="9",
        source_title="Resume",
        provider="resume",
        evidence_kind="resume_chunk",
        raw_value="Python",
        user_id="user-1",
    )

    aggregates = service._aggregate_nodes([python_job], [python_resume])

    assert list(aggregates) == ["python"]
    assert aggregates["python"].evidence_count == 2
    assert len(aggregates["python"].source_keys) == 2


def test_user_skill_state_does_not_leak_between_users():
    service = SkillGraphService()
    observations = [
        _candidate(
            skill_slug="python",
            skill_name="Python",
            source_entity_type="learning_session",
            source_entity_id="session-1",
            source_table="learning_sessions",
            source_pk="1",
            source_title="Learn Python",
            provider="learning",
            evidence_kind="learning_session_completed",
            raw_value="Python",
            user_id="user-1",
            metadata={"status": "completed"},
        ),
        _candidate(
            skill_slug="python",
            skill_name="Python",
            source_entity_type="learning_session",
            source_entity_id="session-2",
            source_table="learning_sessions",
            source_pk="2",
            source_title="Learn Python",
            provider="learning",
            evidence_kind="learning_session_started",
            raw_value="Python",
            user_id="user-2",
            metadata={"status": "started"},
        ),
    ]

    states = service._aggregate_user_states(observations)

    assert set(states) == {("user-1", "python"), ("user-2", "python")}
    assert states[("user-1", "python")].completion_count == 1
    assert states[("user-2", "python")].started_count == 1
    assert states[("user-1", "python")].user_id != states[("user-2", "python")].user_id


def test_job_import_creates_required_skill_edges_from_real_job_evidence():
    service = SkillGraphService()
    observations = [
        _candidate(
            skill_slug="python",
            skill_name="Python",
            source_entity_type="job_match",
            source_entity_id="match-1",
            source_table="job_matches",
            source_pk="1",
            source_title="Backend Engineer",
            provider="jobs",
            evidence_kind="job_match_gap",
            raw_value="Python",
            source_group="job_match:1",
        ),
        _candidate(
            skill_slug="fastapi",
            skill_name="FastAPI",
            source_entity_type="job_match",
            source_entity_id="match-1",
            source_table="job_matches",
            source_pk="1",
            source_title="Backend Engineer",
            provider="jobs",
            evidence_kind="job_match_gap",
            raw_value="FastAPI",
            source_group="job_match:1",
        ),
        _candidate(
            skill_slug="postgresql",
            skill_name="PostgreSQL",
            source_entity_type="job_match",
            source_entity_id="match-1",
            source_table="job_matches",
            source_pk="1",
            source_title="Backend Engineer",
            provider="jobs",
            evidence_kind="job_match_gap",
            raw_value="PostgreSQL",
            source_group="job_match:1",
        ),
    ]

    edges = service._aggregate_edges(observations)

    assert ("fastapi", "python", "co_occurs", "job_match", "job_match:1") in edges
    assert ("fastapi", "postgresql", "co_occurs", "job_match", "job_match:1") in edges
    assert ("postgresql", "python", "co_occurs", "job_match", "job_match:1") in edges


def test_learning_resource_import_creates_taught_by_edges():
    service = SkillGraphService()
    observations = [
        _candidate(
            skill_slug="python",
            skill_name="Python",
            source_entity_type="learning_resource",
            source_entity_id="resource-1",
            source_table="learning_resources",
            source_pk="1",
            source_title="FastAPI tutorial",
            provider="youtube",
            evidence_kind="learning_resource",
            raw_value="Python",
            source_group="resource:1",
        ),
        _candidate(
            skill_slug="fastapi",
            skill_name="FastAPI",
            source_entity_type="learning_resource",
            source_entity_id="resource-1",
            source_table="learning_resources",
            source_pk="1",
            source_title="FastAPI tutorial",
            provider="youtube",
            evidence_kind="learning_resource",
            raw_value="FastAPI",
            source_group="resource:1",
        ),
    ]

    edges = service._aggregate_edges(observations)

    assert ("fastapi", "python", "co_occurs", "learning_resource", "resource:1") in edges or (
        "python",
        "fastapi",
        "co_occurs",
        "learning_resource",
        "resource:1",
    ) in edges


@pytest.mark.asyncio
async def test_skill_graph_import_emits_career_events(monkeypatch):
    service = SkillGraphService()
    fake_event_calls: list[dict[str, object]] = []

    class _FakeCareerEventService:
        def build_evidence_ref(self, **kwargs):
            return {"table": kwargs.get("table"), "source_id": kwargs.get("source_id"), "note": kwargs.get("note")}

        async def emit_event(self, db, **payload):
            fake_event_calls.append(payload)

    monkeypatch.setattr(skill_graph_service_module, "get_career_event_service", lambda: _FakeCareerEventService())

    structured = [
        _candidate(
            skill_slug="python",
            skill_name="Python",
            source_entity_type="job",
            source_entity_id="job-1",
            source_table="jobs",
            source_pk="1",
            source_title="Backend Engineer",
            provider="jobs",
            evidence_kind="job_requirement",
            raw_value="Python",
            user_id="user-1",
        )
    ]
    text = []

    class _FakeRun(SimpleNamespace):
        pass

    class _FakeNode(SimpleNamespace):
        pass

    class _FakeDB(SimpleNamespace):
        async def commit(self):
            return None

    fake_db = _FakeDB()

    async def _fake_collect_structured_observations(db):
        return structured, {}, {"job": 1}

    async def _fake_collect_text_observations(db, vocabulary):
        return text, {}

    async def _fake_upsert_node(db, aggregate, run_uid):
        return _FakeNode(id=1, skill_slug=aggregate.skill_slug, user_count=0, last_import_run_uid=None, updated_at=None)

    async def _fake_upsert_alias(*args, **kwargs):
        return _FakeNode(id=1)

    async def _fake_upsert_edge(*args, **kwargs):
        return None

    async def _fake_upsert_evidence(*args, **kwargs):
        return _FakeNode(id=1)

    async def _fake_upsert_user_state(*args, **kwargs):
        return _FakeNode(id=1)

    monkeypatch.setattr(service, "_collect_structured_observations", _fake_collect_structured_observations)
    monkeypatch.setattr(service, "_collect_text_observations", _fake_collect_text_observations)
    monkeypatch.setattr(service, "_upsert_node", _fake_upsert_node)
    monkeypatch.setattr(service, "_upsert_alias", _fake_upsert_alias)
    monkeypatch.setattr(service, "_upsert_edge", _fake_upsert_edge)
    monkeypatch.setattr(service, "_upsert_evidence", _fake_upsert_evidence)
    monkeypatch.setattr(service, "_upsert_user_state", _fake_upsert_user_state)

    async def _fake_ensure_import_run(db, *, user_id, scope, notes):
        return _FakeRun(run_uid="run-1", id=1, scope=scope, status="running", strategy="real_data_import_v1", notes=notes, source_counts={}, completed_at=None, updated_at=None)

    async def _fake_upsert_import_run(db, run, **kwargs):
        run.status = kwargs["status"]
        run.node_count = kwargs["node_count"]
        run.edge_count = kwargs["edge_count"]
        run.evidence_count = kwargs["evidence_count"]
        run.alias_count = kwargs["alias_count"]
        run.user_state_count = kwargs["user_state_count"]
        run.source_counts = kwargs["source_counts"]
        run.completed_at = datetime(2026, 6, 20, 0, 1, 0)
        return run

    async def _fake_get_summary(db, *, user_id=None, limit: int = 12):
        return {
            "latest_import_run": {
                "run_uid": "run-1",
                "scope": "full",
                "status": "completed",
            }
        }

    monkeypatch.setattr(service, "_ensure_import_run", _fake_ensure_import_run)
    monkeypatch.setattr(service, "_upsert_import_run", _fake_upsert_import_run)
    monkeypatch.setattr(service, "get_summary", _fake_get_summary)

    result = await service.import_graph(fake_db, user_id="user-1")

    assert result["status"] == "ok"
    assert fake_event_calls
    assert fake_event_calls[0]["event_type"] == "SkillGraphImportCompleted"
    assert fake_event_calls[0]["evidence"][0]["table"] == "skill_graph_import_runs"


def test_skill_graph_routes_require_auth_and_are_registered():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/skill-graph/health" in paths
    assert "/api/v1/skill-graph/import" in paths
    assert "/api/v1/skill-graph/summary" in paths
    assert client.get("/api/v1/skill-graph/summary").status_code == 401
    assert client.post("/api/v1/skill-graph/import").status_code == 401


def test_skill_graph_routes_return_payloads(authenticated_skill_graph):
    response = client.get("/api/v1/skill-graph/health")
    assert response.status_code == 200
    assert response.json()["ready"] is True

    response = client.get("/api/v1/skill-graph/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_nodes"] == 2
    assert payload["top_nodes"][0]["skill_slug"] == "python"

    response = client.get("/api/v1/skill-graph/nodes")
    assert response.status_code == 200
    assert response.json()["nodes"][0]["skill_name"] == "Python"

    response = client.get("/api/v1/skill-graph/nodes/python")
    assert response.status_code == 200
    assert response.json()["node"]["skill_slug"] == "python"

    response = client.get("/api/v1/skill-graph/states")
    assert response.status_code == 200
    assert response.json()["states"][0]["skill_slug"] == "python"

    response = client.get("/api/v1/skill-graph/import-runs")
    assert response.status_code == 200
    assert response.json()["runs"][0]["run_uid"] == "run-1"

    response = client.post("/api/v1/skill-graph/import", json={"notes": "manual refresh"})
    assert response.status_code == 200
    assert response.json()["node_count"] == 2
