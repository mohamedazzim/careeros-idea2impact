from inspect import signature
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_current_user
from src.api.v1.endpoints import skill_gaps as skill_gaps_endpoint
from src.main import app
from src.schemas.security import Role
from src.schemas.skill_gap import (
    SkillGapEvidenceResponse,
    SkillGapFindingResponse,
    SkillGapRunDetailResponse,
    SkillGapRunSummaryResponse,
    SkillGapSummaryResponse,
)
from src.services.events import get_career_event_service
from src.services.skill_gap.skill_gap_engine import SkillGapEngineService
from src.services.skill_gap.skill_gap_evidence_service import (
    SkillGapEvidenceRecord,
    SkillGapRequirement,
)


if "app" not in signature(httpx.Client.__init__).parameters:
    _httpx_client_init = httpx.Client.__init__

    def _patched_httpx_client_init(self, *args, app=None, **kwargs):
        return _httpx_client_init(self, *args, **kwargs)

    httpx.Client.__init__ = _patched_httpx_client_init


client = TestClient(app)


async def _override_db():
    yield SimpleNamespace()


def _auth_headers() -> dict[str, str]:
    from src.services.security.auth import auth_service

    token = auth_service.generate_token_pair("user-123", Role.USER).access_token
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def skill_gap_overrides():
    original_overrides = dict(app.dependency_overrides)

    async def _override_user():
        return {"sub": "user-123", "role": "User"}

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[skill_gaps_endpoint.get_db] = _override_db
    yield
    app.dependency_overrides = original_overrides


@pytest.mark.asyncio
async def test_skill_gap_engine_persists_run_findings_and_snapshot(monkeypatch):
    service = SkillGapEngineService()
    fake_evidence_service = SimpleNamespace()
    fake_evidence_service.collect_required_skill_evidence = AsyncMock(
        return_value=[
            SkillGapRequirement(
                skill_slug="python",
                skill_name="Python",
                required_by_type="job",
                required_by_id="41",
                source_table="job_matches",
                source_id="11",
                source_title="Senior Python Engineer",
                source_url="https://example.com/jobs/41",
                source_strength="strong",
                metadata={"job_id": 41},
            )
        ]
    )
    fake_evidence_service.collect_resume_evidence = AsyncMock(
        return_value={
            "python": [
                SkillGapEvidenceRecord(
                    skill_slug="python",
                    skill_name="Python",
                    evidence_type="resume_skill",
                    source_table="resume_versions",
                    source_id="77",
                    source_url=None,
                    evidence_strength="weak",
                    supports_status="evidenced",
                    quote_or_snippet="Resume skills list matched for resume.pdf",
                    metadata_json={"resume_filename": "resume.pdf"},
                    confidence="low",
                    source_title="resume.pdf",
                )
            ]
        }
    )
    fake_evidence_service.collect_project_evidence = AsyncMock(return_value={})
    fake_evidence_service.collect_learning_evidence = AsyncMock(return_value={})
    fake_evidence_service.collect_outcome_evidence = AsyncMock(return_value={})
    fake_evidence_service.collect_provenance_evidence = AsyncMock(return_value={})
    fake_evidence_service.collect_skill_graph_evidence = AsyncMock(return_value={})
    fake_evidence_service.build_absence_evidence = AsyncMock(return_value=[])
    fake_explanation_service = SimpleNamespace(
        recommend_next_action=lambda *args, **kwargs: "Build one small Python proof project.",
        explain_validated=lambda **kwargs: f"{kwargs.get('skill_name')} is validated.",
        explain_evidenced=lambda **kwargs: f"{kwargs.get('skill_name')} is evidenced.",
        explain_learning=lambda **kwargs: f"{kwargs.get('skill_name')} is in learning.",
        explain_missing=lambda **kwargs: f"{kwargs.get('skill_name')} is still missing.",
        explain_insufficient_data=lambda **kwargs: f"Not enough evidence for {kwargs.get('skill_name')}.",
    )
    fake_events = SimpleNamespace(
        emit_event=AsyncMock(return_value=None),
        emit_insufficient_data_event=AsyncMock(return_value=None),
        build_evidence_ref=lambda **kwargs: kwargs,
    )
    service.evidence_service = fake_evidence_service
    service.explanation_service = fake_explanation_service
    service.career_events = fake_events

    added_objects = []

    class FakeDB:
        def add(self, obj):
            added_objects.append(obj)

        async def flush(self):
            return None

        async def commit(self):
            return None

        async def execute(self, statement):
            return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=17, skill_slug="python"))

    result = await service.analyze(FakeDB(), user_id="user-123", source_scope="job", job_id=41, limit=5)

    assert result["status"] == "ok"
    assert result["run_uid"].startswith("sgar_")
    assert result["summary"]["required_skill_count"] == 1
    assert result["summary"]["evidenced_skill_count"] == 1
    assert result["findings"][0]["skill_slug"] == "python"
    assert any(obj.__class__.__name__ == "SkillGapAnalysisRun" for obj in added_objects)
    assert any(obj.__class__.__name__ == "SkillGapFinding" for obj in added_objects)
    assert any(obj.__class__.__name__ == "SkillGapFindingEvidence" for obj in added_objects)
    assert any(obj.__class__.__name__ == "UserSkillGapSnapshot" for obj in added_objects)
    assert fake_events.emit_event.await_count == 1


def test_skill_gap_routes_and_openapi_visibility(skill_gap_overrides, monkeypatch):
    fake_engine = SimpleNamespace(
        analyze=AsyncMock(
            return_value={
                "status": "ok",
                "run_uid": "run-1",
                "summary": {
                    "required_skill_count": 1,
                    "missing_skill_count": 0,
                    "learning_skill_count": 0,
                    "evidenced_skill_count": 1,
                    "validated_skill_count": 0,
                    "insufficient_data_count": 0,
                },
                "findings": [],
            }
        )
    )
    fake_query = SimpleNamespace(
        get_run=AsyncMock(
            return_value=SkillGapRunDetailResponse(
                status="ok",
                run=SkillGapRunSummaryResponse(
                    run_uid="run-1",
                    user_id="user-123",
                    job_id=41,
                    target_role_slug=None,
                    source_scope="job",
                    source_service="services.skill_gap.skill_gap_engine",
                    status="completed",
                    started_at="2026-06-20T00:00:00Z",
                    completed_at="2026-06-20T00:00:02Z",
                    duration_ms=2000,
                    required_skill_count=1,
                    missing_skill_count=0,
                    evidenced_skill_count=1,
                    learning_skill_count=0,
                    validated_skill_count=0,
                    insufficient_data_count=0,
                    confidence="medium",
                    failure_reason=None,
                    metadata_json={},
                    created_at="2026-06-20T00:00:00Z",
                ),
                summary=SkillGapSummaryResponse(
                    required_skill_count=1,
                    missing_skill_count=0,
                    learning_skill_count=0,
                    evidenced_skill_count=1,
                    validated_skill_count=0,
                    insufficient_data_count=0,
                ),
                findings=[
                    SkillGapFindingResponse(
                        finding_uid="finding-1",
                        run_uid="run-1",
                        user_id="user-123",
                        job_id=41,
                        skill_node_uid="17",
                        skill_slug="python",
                        skill_name="Python",
                        required_by_type="job",
                        required_by_id="41",
                        gap_status="evidenced",
                        confidence="medium",
                        evidence_count=1,
                        missing_evidence=[],
                        reason_summary="Python is evidenced.",
                        recommendation_summary="Build one small Python proof project.",
                        calculation_metadata_json={"evidence_types": ["resume_skill"]},
                        evidence=[
                            SkillGapEvidenceResponse(
                                evidence_uid="evidence-1",
                                finding_uid="finding-1",
                                user_id="user-123",
                                skill_slug="python",
                                evidence_type="resume_skill",
                                source_table="resume_versions",
                                source_id="77",
                                source_url=None,
                                evidence_strength="weak",
                                supports_status="evidenced",
                                quote_or_snippet="Resume skills list matched for resume.pdf",
                                metadata_json={"resume_filename": "resume.pdf"},
                                confidence="low",
                                created_at="2026-06-20T00:00:00Z",
                            )
                        ],
                        created_at="2026-06-20T00:00:00Z",
                        updated_at="2026-06-20T00:00:02Z",
                    )
                ],
            )
        ),
        list_runs=AsyncMock(return_value=None),
        get_snapshot=AsyncMock(return_value=None),
        get_skill_evidence=AsyncMock(return_value=None),
        get_job_response=AsyncMock(return_value=None),
        list_findings=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(skill_gaps_endpoint, "get_skill_gap_engine_service", lambda: fake_engine)
    monkeypatch.setattr(skill_gaps_endpoint, "get_skill_gap_query_service", lambda: fake_query)

    response = client.get("/api/v1/skill-gaps/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    analyze_response = client.post(
        "/api/v1/skill-gaps/analyze",
        headers=_auth_headers(),
        json={"source_scope": "user"},
    )
    assert analyze_response.status_code == 200
    payload = analyze_response.json()
    assert payload["run_uid"] == "run-1"
    assert payload["summary"]["evidenced_skill_count"] == 1
    assert payload["findings"][0]["skill_slug"] == "python"

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    spec = openapi.json()
    paths = spec.get("paths", {})
    assert "/api/v1/skill-gaps/health" in paths
    assert "/api/v1/skill-gaps/analyze" in paths
    assert "/api/v1/skill-gaps/jobs/{job_id}" in paths
