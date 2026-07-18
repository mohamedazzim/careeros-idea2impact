"""Human-readable explanations for evidence-backed skill gaps."""

from __future__ import annotations

from typing import Any, Iterable


class SkillGapExplanationService:
    @staticmethod
    def _format_evidence_labels(evidence: Iterable[dict[str, Any]]) -> str:
        labels: list[str] = []
        for item in evidence:
            evidence_type = str(item.get("evidence_type") or item.get("type") or "").replace("_", " ").strip()
            source = str(item.get("source_table") or item.get("source_type") or "").replace("_", " ").strip()
            label = " ".join(part for part in [evidence_type, f"from {source}" if source else ""] if part).strip()
            if label:
                labels.append(label)
        unique: list[str] = []
        for label in labels:
            if label not in unique:
                unique.append(label)
        return ", ".join(unique[:4])

    def explain_missing(
        self,
        *,
        skill_name: str,
        required_by_type: str,
        evidence: list[dict[str, Any]],
        missing_evidence: list[dict[str, Any]],
    ) -> str:
        required_label = required_by_type.replace("_", " ")
        if evidence:
            support_text = self._format_evidence_labels(evidence)
            return f"{skill_name} is required by {required_label} evidence, but only absence checks were recorded after searching {support_text}."
        if missing_evidence:
            checked = self._format_evidence_labels(missing_evidence)
            return f"{skill_name} is required by {required_label} evidence, and the engine found no matching user evidence after checking {checked}."
        return f"{skill_name} is required by {required_label} evidence, but no supporting or absence evidence was available."

    def explain_learning(
        self,
        *,
        skill_name: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        labels = self._format_evidence_labels(evidence)
        if labels:
            return f"{skill_name} is actively being learned from {labels}."
        return f"{skill_name} is actively being learned, but the evidence feed is sparse."

    def explain_evidenced(
        self,
        *,
        skill_name: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        labels = self._format_evidence_labels(evidence)
        if labels:
            return f"{skill_name} has stored evidence from {labels}, but not enough proof to mark it validated."
        return f"{skill_name} has stored evidence, but the engine could not build a fuller explanation."

    def explain_validated(
        self,
        *,
        skill_name: str,
        evidence: list[dict[str, Any]],
    ) -> str:
        labels = self._format_evidence_labels(evidence)
        if labels:
            return f"{skill_name} is validated by stronger stored evidence from {labels}."
        return f"{skill_name} is validated by stronger stored evidence."

    def explain_insufficient_data(
        self,
        *,
        skill_name: str,
        required_by_type: str,
        evidence: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> str:
        required_label = required_by_type.replace("_", " ")
        checked = self._format_evidence_labels(evidence)
        detail = str(metadata.get("reason") or metadata.get("source_scope") or "the available sources")
        if checked:
            return f"{skill_name} could not be classified from {required_label} evidence because the engine could only inspect {checked} ({detail})."
        return f"{skill_name} could not be classified from {required_label} evidence because the engine only had {detail}."

    def recommend_next_action(self, gap_status: str, skill_name: str) -> str:
        if gap_status == "validated":
            return f"Keep a fresh project or outcome note for {skill_name} so the evidence stays current."
        if gap_status == "evidenced":
            return f"Turn the current {skill_name} evidence into a completed project or repeated outcome."
        if gap_status == "learning":
            return f"Finish the current {skill_name} learning step and record progress or feedback."
        if gap_status == "missing":
            return f"Close the {skill_name} gap with one focused resource and one proof artifact."
        return f"Collect more stored evidence for {skill_name} before making a stronger claim."


_SERVICE: SkillGapExplanationService | None = None


def get_skill_gap_explanation_service() -> SkillGapExplanationService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = SkillGapExplanationService()
    return _SERVICE
