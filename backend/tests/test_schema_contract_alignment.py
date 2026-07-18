from pathlib import Path

from src.models.interview import (
    InterviewQuestion,
    InterviewSession,
    InterviewWeaknessHistory,
)
from src.models.skill_gap import SkillGapAnalysisRun, SkillGapFindingEvidence


def test_interview_defaulted_fields_match_non_nullable_db_contract() -> None:
    assert InterviewSession.__table__.c.status.nullable is False
    assert InterviewSession.__table__.c.difficulty_level.nullable is False
    assert InterviewSession.__table__.c.current_question_index.nullable is False
    assert InterviewSession.__table__.c.total_score.nullable is False
    assert InterviewSession.__table__.c.created_at.nullable is False

    assert InterviewQuestion.__table__.c.answer_text.nullable is False
    assert InterviewQuestion.__table__.c.rubric_scores.nullable is False
    assert InterviewQuestion.__table__.c.governance_flags.nullable is False
    assert InterviewQuestion.__table__.c.created_at.nullable is False

    assert InterviewWeaknessHistory.__table__.c.occurrences.nullable is False
    assert InterviewWeaknessHistory.__table__.c.severity.nullable is False
    assert InterviewWeaknessHistory.__table__.c.created_at.nullable is False


def test_skill_gap_updated_at_columns_remain_model_owned() -> None:
    assert "updated_at" in SkillGapAnalysisRun.__table__.c
    assert SkillGapAnalysisRun.__table__.c.updated_at.nullable is False
    assert "updated_at" in SkillGapFindingEvidence.__table__.c
    assert SkillGapFindingEvidence.__table__.c.updated_at.nullable is False


def test_schema_alignment_migration_backfills_before_not_null() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "033_schema_contract_alignment.py"
    )
    text = migration.read_text(encoding="utf-8")

    assert "NOT_NULL_BACKFILLS" in text
    assert "WHERE {column_sql} IS NULL" in text
    assert "nullable=False" in text
    assert "drop_column" not in text
    assert "drop_constraint" not in text
