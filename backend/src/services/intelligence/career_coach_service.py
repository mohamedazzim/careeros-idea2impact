"""Phase 6 Career Intelligence and Coach Agent Services."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.outcome_intelligence import (
    ApplicationLifecycle,
    CareerCoachGoal,
    CareerCoachPlan,
    CareerCoachRecommendation,
    CareerProgressMetric,
    OpportunityCallOutcome,
    OpportunityRerankingRecord,
)
from src.models.jobs import CareerMemory
from src.observability.langsmith import traceable


class CareerIntelligenceService:
    """Aggregates all career data into comprehensive intelligence metrics."""

    @traceable(name="career_intelligence_compute")
    async def compute(self, db: AsyncSession, user_id: str) -> Dict[str, Any]:
        apps_submitted = await self._count_lifecycle_states(db, user_id)
        interview_count = apps_submitted.get("INTERVIEW", 0) + apps_submitted.get("FINAL_ROUND", 0)
        offer_count = apps_submitted.get("OFFER", 0)
        total_apps = sum(apps_submitted.values())
        interview_rate = round(interview_count / total_apps, 3) if total_apps else 0.0
        offer_rate = round(offer_count / total_apps, 3) if total_apps else 0.0

        rejected_count = apps_submitted.get("REJECTED", 0)
        responded_count = total_apps - apps_submitted.get("DISCOVERED", 0)
        response_rate = round(responded_count / total_apps, 3) if total_apps else 0.0

        reranking = (await db.execute(
            select(OpportunityRerankingRecord)
            .where(OpportunityRerankingRecord.candidate_id == user_id)
            .order_by(desc(OpportunityRerankingRecord.final_opportunity_ranking))
        )).scalars().all()

        top_opportunities = [
            {
                "job_id": r.job_id,
                "final_score": r.final_opportunity_ranking,
                "match_score": r.existing_match_score,
                "memory_affinity": r.memory_affinity_score,
                "outcome_success": r.outcome_success_score,
            }
            for r in reranking[:10]
        ]

        career_memory = (await db.execute(
            select(CareerMemory)
            .where(CareerMemory.user_id == user_id, CareerMemory.event_type == "preference")
            .order_by(desc(CareerMemory.created_at))
        )).scalars().all()

        preferred_roles = []
        preferred_locations = []
        preferred_salary = []
        for m in career_memory:
            dim = (m.data or {}).get("dimension", "")
            val = (m.data or {}).get("value", "")
            if dim == "preferred_roles" and val not in preferred_roles:
                preferred_roles.append(val)
            elif dim == "preferred_locations" and val not in preferred_locations:
                preferred_locations.append(val)
            elif dim == "preferred_salary_bands" and val not in preferred_salary:
                preferred_salary.append(val)

        progress = (await db.execute(
            select(CareerProgressMetric)
            .where(CareerProgressMetric.candidate_id == user_id)
            .order_by(desc(CareerProgressMetric.conversion_rate))
        )).scalars().all()

        top_skills_improving = [p.dimension_value for p in progress if p.conversion_rate > 0][:5]
        top_skills_missing = [p.dimension_value for p in progress if p.conversion_rate == 0][:5]

        outcomes = (await db.execute(
            select(OpportunityCallOutcome).where(OpportunityCallOutcome.candidate_id == user_id)
        )).scalars().all()

        outcome_summary = {}
        for o in outcomes:
            outcome_summary[o.outcome] = outcome_summary.get(o.outcome, 0) + 1

        return {
            "applications_submitted": total_apps,
            "interviews_scheduled": interview_count,
            "interview_rate": interview_rate,
            "offer_rate": offer_rate,
            "response_rate": response_rate,
            "lifecycle_breakdown": apps_submitted,
            "top_opportunities": top_opportunities,
            "preferred_roles": preferred_roles[:10],
            "preferred_locations": preferred_locations[:10],
            "preferred_salary_bands": preferred_salary[:5],
            "top_skills_improving": top_skills_improving,
            "top_skills_missing": top_skills_missing,
            "outcome_summary": outcome_summary,
            "career_memory_count": len(career_memory),
        }

    async def _count_lifecycle_states(self, db: AsyncSession, user_id: str) -> Dict[str, int]:
        rows = (await db.execute(
            select(ApplicationLifecycle.state, func.count(ApplicationLifecycle.id))
            .where(ApplicationLifecycle.candidate_id == user_id)
            .group_by(ApplicationLifecycle.state)
        )).all()
        return {row[0]: row[1] for row in rows}

    @traceable(name="career_intelligence_generate_summary")
    async def generate_weekly_summary(self, db: AsyncSession, user_id: str) -> Dict[str, Any]:
        intelligence = await self.compute(db, user_id)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_outcomes = (await db.execute(
            select(OpportunityCallOutcome)
            .where(
                OpportunityCallOutcome.candidate_id == user_id,
                OpportunityCallOutcome.created_at >= week_ago,
            )
        )).scalars().all()

        recent_applications = (await db.execute(
            select(ApplicationLifecycle)
            .where(
                ApplicationLifecycle.candidate_id == user_id,
                ApplicationLifecycle.created_at >= week_ago,
            )
        )).scalars().all()

        return {
            "week_ending": datetime.utcnow().isoformat(),
            "summary": intelligence,
            "weekly_outcomes": len(recent_outcomes),
            "weekly_applications": len(recent_applications),
            "weekly_breakdown": {
                o.outcome: sum(1 for x in recent_outcomes if x.outcome == o.outcome)
                for o in recent_outcomes
            },
        }


class CareerCoachService:
    """Career coaching agent that generates actionable career advice."""

    VALID_GOAL_TYPES = ("skill_improvement", "application_target", "interview_prep", "career_growth")
    VALID_PLAN_TYPES = ("weekly_coaching", "monthly_goals", "skill_roadmap", "interview_prep")

    @traceable(name="career_coach_generate_plans")
    async def generate_plans(self, db: AsyncSession, user_id: str) -> List[CareerCoachPlan]:
        intelligence_svc = CareerIntelligenceService()
        intel = await intelligence_svc.compute(db, user_id)

        plans = []

        skill_gap_items = []
        for skill in intel.get("top_skills_missing", []):
            skill_gap_items.append({
                "skill": skill,
                "action": f"Complete a learning module on {skill}",
                "priority": "high",
                "estimated_hours": 10,
            })

        if skill_gap_items:
            plan = CareerCoachPlan(
                user_id=user_id,
                plan_type="skill_roadmap",
                title="Skill Improvement Roadmap",
                description=f"Focus areas: {', '.join(intel.get('top_skills_missing', [])[:3])}",
                items=skill_gap_items,
                status="active",
            )
            db.add(plan)
            plans.append(plan)

        coaching_items = []
        if intel.get("interview_rate", 0) < 0.2:
            coaching_items.append({
                "action": "Practice behavioral interview questions",
                "category": "interview_prep",
                "priority": "high",
            })
        if intel.get("response_rate", 0) < 0.3:
            coaching_items.append({
                "action": "Review and optimize resume keywords",
                "category": "resume_optimization",
                "priority": "high",
            })
        coaching_items.append({
            "action": f"Apply to {max(5 - intel.get('applications_submitted', 0), 1)} more positions this week",
            "category": "application_target",
            "priority": "medium",
        })

        if coaching_items:
            plan = CareerCoachPlan(
                user_id=user_id,
                plan_type="weekly_coaching",
                title="Weekly Career Coaching Plan",
                description="Personalized recommendations based on your career data",
                items=coaching_items,
                status="active",
            )
            db.add(plan)
            plans.append(plan)

        monthly_items = []
        if intel.get("interviews_scheduled", 0) == 0:
            monthly_items.append({
                "target": "Schedule 2+ interviews",
                "category": "interview_target",
                "priority": "high",
            })
        monthly_items.append({
            "target": f"Reach {intel.get('applications_submitted', 0) + 10} total applications",
            "category": "application_target",
            "priority": "medium",
        })

        plan = CareerCoachPlan(
            user_id=user_id,
            plan_type="monthly_goals",
            title="Monthly Career Goals",
            description="Long-term career objectives",
            items=monthly_items,
            status="active",
        )
        db.add(plan)
        plans.append(plan)

        await db.flush()
        return plans

    @traceable(name="career_coach_generate_goals")
    async def generate_goals(self, db: AsyncSession, user_id: str) -> List[CareerCoachGoal]:
        existing = (await db.execute(
            select(CareerCoachGoal)
            .where(CareerCoachGoal.user_id == user_id, CareerCoachGoal.status == "active")
        )).scalars().all()

        if existing:
            return existing

        intelligence_svc = CareerIntelligenceService()
        intel = await intelligence_svc.compute(db, user_id)

        goals = []
        goal_specs = [
            ("application_target", "Applications This Week", "Target number of applications", 5.0, "applications"),
            ("interview_prep", "Interview Readiness", "Complete interview preparation", 3.0, "sessions"),
            ("skill_improvement", "Skill Development Hours", "Hours spent learning new skills", 10.0, "hours"),
        ]
        for gtype, title, desc_text, target, unit in goal_specs:
            current = 0.0
            if gtype == "application_target":
                current = float(intel.get("applications_submitted", 0))
            goal = CareerCoachGoal(
                user_id=user_id,
                goal_type=gtype,
                title=title,
                description=desc_text,
                target_value=target,
                current_value=current,
                unit=unit,
                priority=1 if gtype == "application_target" else 2,
            )
            db.add(goal)
            goals.append(goal)

        await db.flush()
        return goals

    @traceable(name="career_coach_generate_recommendations")
    async def generate_recommendations(self, db: AsyncSession, user_id: str) -> List[CareerCoachRecommendation]:
        week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
        existing = (await db.execute(
            select(CareerCoachRecommendation)
            .where(
                CareerCoachRecommendation.user_id == user_id,
                CareerCoachRecommendation.week_of >= week_start,
            )
        )).scalars().all()

        if existing:
            return existing

        intelligence_svc = CareerIntelligenceService()
        intel = await intelligence_svc.compute(db, user_id)
        recommendations = []

        if intel.get("top_skills_missing"):
            recommendations.append(CareerCoachRecommendation(
                user_id=user_id,
                category="skill_gap",
                title=f"Learn: {intel['top_skills_missing'][0]}",
                description=f"Your top missing skill is {intel['top_skills_missing'][0]}. Consider a course or project.",
                priority=1,
                week_of=week_start,
            ))

        if intel.get("interview_rate", 0) < 0.3:
            recommendations.append(CareerCoachRecommendation(
                user_id=user_id,
                category="interview_prep",
                title="Improve Interview Conversion",
                description=f"Your interview rate is {intel.get('interview_rate', 0)*100:.0f}%. Practice mock interviews.",
                priority=1,
                week_of=week_start,
            ))

        recommendations.append(CareerCoachRecommendation(
            user_id=user_id,
            category="application_strategy",
            title="Diversify Application Targets",
            description="Apply to roles in at least 2 different companies this week.",
            priority=2,
            week_of=week_start,
        ))

        if intel.get("preferred_roles"):
            recommendations.append(CareerCoachRecommendation(
                user_id=user_id,
                category="career_focus",
                title=f"Focus on {intel['preferred_roles'][0]} roles",
                description=f"Your data shows preference for {intel['preferred_roles'][0]} positions. Target these.",
                priority=2,
                week_of=week_start,
            ))

        for rec in recommendations:
            db.add(rec)
        await db.flush()
        return recommendations


def get_career_intelligence_service() -> CareerIntelligenceService:
    return CareerIntelligenceService()


def get_career_coach_service() -> CareerCoachService:
    return CareerCoachService()
