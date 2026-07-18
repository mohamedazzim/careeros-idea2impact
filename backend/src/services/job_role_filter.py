"""
Job role classification and experience requirement extraction.

Classifies jobs as tech/non-tech roles and extracts experience requirements
for filtering jobs against candidate resume experience levels.
"""

import re
import logging
from typing import Any, Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)

# Tech role keywords (title must contain at least one)
TECH_TITLE_KEYWORDS = [
    "software engineer", "software developer", "full stack", "fullstack",
    "frontend", "front-end", "backend", "back-end",
    "ai engineer", "ml engineer", "machine learning",
    "data scientist", "data analyst", "data engineer",
    "devops", "mlops", "sre", "site reliability",
    "cloud engineer", "cloud architect",
    "qa engineer", "quality assurance", "test engineer", "automation engineer",
    "mobile developer", "ios developer", "android developer",
    "cybersecurity", "security engineer",
    "product engineer", "platform engineer",
    "systems engineer", "infrastructure engineer",
    "scrum master", "technical program manager",
    "support engineer", "system support", "production support", "it support",
    "database administrator", "dba",
    "network engineer",
    "embedded engineer", "firmware engineer",
    "blockchain engineer", "web3",
    "unity developer", "game developer",
    "site architect", "technical architect",
    "solution architect",
]

# Non-tech exclusion keywords (title)
NON_TECH_TITLE_KEYWORDS = [
    "sales", "selling", "business development", "account executive",
    "marketing", "content writer", "copywriter", "social media",
    "human resources", "hr manager", "hr executive", "talent acquisition",
    "finance", "accountant", "accounting", "financial analyst",
    "operations coordinator",
    "customer service",
    "business analyst",
    "consultant", "advisory",
    "recruiter", "recruitment",
    "legal", "paralegal", "attorney",
    "executive assistant", "office manager",
    "designer", "ux designer", "ui designer", "graphic designer",
    "content strategist", "brand manager",
    "public relations", "communications",
    "warehouse", "logistics coordinator",
]

# Tech skills that indicate tech role even if title is ambiguous
TECH_SKILL_INDICATORS = [
    "python", "javascript", "typescript", "java", "c++", "c#", "golang", "rust",
    "react", "angular", "vue", "node.js", "express", "fastapi", "django",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
    "sql", "postgresql", "mongodb", "redis", "elasticsearch",
    "machine learning", "deep learning", "tensorflow", "pytorch",
    "git", "ci/cd", "jenkins", "github actions",
    "linux", "bash", "shell scripting",
    "microservices", "rest api", "graphql", "grpc",
    "support", "help desk", "service desk", "scrum", "agile", "jira", "incident",
]

# Experience requirement patterns — ORDER MATTERS: range patterns first
EXPERIENCE_PATTERNS = [
    # "3-5 years" or "3 to 5 years" or "3–5 years" (range must come first)
    (r'(\d+)\s*[-–—to]+\s*(\d+)\s*years?', lambda m: (float(m.group(1)), float(m.group(2)))),
    # "minimum 4 years"
    (r'minimum\s+(\d+)\s*years?', lambda m: (float(m.group(1)), None)),
    # "at least 2 years"
    (r'at\s+least\s+(\d+)\s*years?', lambda m: (float(m.group(1)), None)),
    # "5+ years" or "5+ years of experience"
    (r'(\d+)\+?\s*years?\s*(?:of\s+)?(?:experience|exp)', lambda m: (float(m.group(1)), None)),
]

# Seniority keywords in title
SENIORITY_PATTERNS = {
    "lead": [r'\blead\b', r'\btech lead\b', r'\bteam lead\b', r'\btechnical lead\b'],
    "senior": [r'\bsenior\b', r'\bsr\.\b', r'\bsr\b', r'\bprincipal\b', r'\bstaff\b', r'\barchitect\b'],
    "mid": [r'\bassociate\b', r'\bII\b', r'\bmid[- ]level\b', r'\bmid[- ]senior\b'],
    "junior": [r'\bjunior\b', r'\bjr\.\b', r'\bjr\b', r'\bentry\b', r'\bfresher\b', r'\bgraduate\b', r'\btrainee\b', r'\bintern\b'],
}

# Minimum experience by seniority (years)
SENIORITY_MIN_YEARS = {
    "lead": 8.0,
    "senior": 5.0,
    "mid": 2.0,
    "junior": 0.0,
    "entry": 0.0,
}

# Maximum experience by seniority (years) — above this, candidate may be overqualified
SENIORITY_MAX_YEARS = {
    "lead": None,
    "senior": 15.0,
    "mid": 8.0,
    "junior": 4.0,
    "entry": 2.0,
}


def classify_tech_role(
    title: str,
    description: Optional[str] = None,
    skills: Optional[List[str]] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Classify whether a job is a tech role.

    Args:
        title: Job title
        description: Job description text
        skills: List of required skills
        category: Provider-supplied category

    Returns:
        Dict with is_tech_role, tech_role_category, confidence, reason
    """
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()

    # Check title against non-tech exclusion first
    for pattern in NON_TECH_TITLE_KEYWORDS:
        if pattern in title_lower:
            return {
                "is_tech_role": False,
                "tech_role_category": None,
                "confidence": 0.9,
                "reason": f"Non-tech title pattern: {pattern}",
            }

    # Check title against tech keywords
    for keyword in TECH_TITLE_KEYWORDS:
        if keyword in title_lower:
            return {
                "is_tech_role": True,
                "tech_role_category": _categorize_role(keyword),
                "confidence": 0.95,
                "reason": f"Title contains tech keyword: {keyword}",
            }

    if any(keyword in title_lower for keyword in ("manager", "lead", "principal", "director")):
        if skills:
            tech_skill_count = sum(
                1 for skill in skills
                if any(indicator in skill.lower() for indicator in TECH_SKILL_INDICATORS)
            )
            if tech_skill_count >= 1:
                return {
                    "is_tech_role": True,
                    "tech_role_category": "general_tech",
                    "confidence": 0.82,
                    "reason": "Management title with strong technical skill signals",
                }
        if any(indicator in desc_lower for indicator in ("devops", "mlops", "platform", "infrastructure", "support engineer", "site reliability", "scrum", "agile")):
            return {
                "is_tech_role": True,
                "tech_role_category": "general_tech",
                "confidence": 0.8,
                "reason": "Management/support title with technical description signals",
            }

    # Check skills if title is ambiguous
    if skills:
        tech_skill_count = sum(
            1 for skill in skills
            if any(indicator in skill.lower() for indicator in TECH_SKILL_INDICATORS)
        )
        if tech_skill_count >= 2:
            return {
                "is_tech_role": True,
                "tech_role_category": "general_tech",
                "confidence": 0.7,
                "reason": f"Multiple tech skills detected: {tech_skill_count}",
            }

    # Check description for tech indicators
    if description:
        tech_desc_count = sum(
            1 for indicator in TECH_SKILL_INDICATORS
            if indicator in desc_lower
        )
        if tech_desc_count >= 3:
            return {
                "is_tech_role": True,
                "tech_role_category": "general_tech",
                "confidence": 0.6,
                "reason": f"Description contains {tech_desc_count} tech indicators",
            }

    # Check category from provider
    if category and category.lower() in ("engineering", "technology", "software", "it", "tech"):
        return {
            "is_tech_role": True,
            "tech_role_category": "general_tech",
            "confidence": 0.6,
            "reason": f"Provider category is tech: {category}",
        }

    # Default: not clearly tech
    return {
        "is_tech_role": False,
        "tech_role_category": None,
        "confidence": 0.5,
        "reason": "No tech indicators found in title, skills, or description",
    }


def extract_job_experience_requirement(
    title: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract experience requirement from job title and description.

    Returns:
        Dict with min_years, max_years, seniority_level, evidence
    """
    text = f"{title or ''} {description or ''}"
    evidence: List[str] = []

    # Detect seniority from title
    seniority = None
    for level, patterns in SENIORITY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, title or "", re.IGNORECASE):
                seniority = level
                evidence.append(f"Seniority from title: {level}")
                break
        if seniority:
            break

    # Extract explicit experience years
    min_years = None
    max_years = None

    for pattern, extractor in EXPERIENCE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            min_y, max_y = extractor(match)
            if min_years is None or min_y > min_years:
                min_years = min_y
            if max_y is not None:
                if max_years is None or max_y < max_years:
                    max_years = max_y
            evidence.append(f"Experience pattern: {min_y}-{max_y or 'open'} years")
            break

    # Infer from seniority if no explicit years found
    if min_years is None and seniority:
        min_years = SENIORITY_MIN_YEARS.get(seniority, 0.0)
        evidence.append(f"Inferred min from seniority ({seniority}): {min_years} years")

    if max_years is None and seniority:
        max_years = SENIORITY_MAX_YEARS.get(seniority)
        if max_years:
            evidence.append(f"Inferred max from seniority ({seniority}): {max_years} years")

    return {
        "min_years": min_years,
        "max_years": max_years,
        "seniority_level": seniority or _infer_seniority_from_years(min_years),
        "evidence": evidence,
    }


def is_job_eligible_for_candidate(
    job_min_years: Optional[float],
    job_max_years: Optional[float],
    job_seniority: Optional[str],
    candidate_years: Optional[float],
    candidate_level: Optional[str],
) -> Dict[str, Any]:
    """
    Check if a job is compatible with a candidate's experience level.

    Args:
        job_min_years: Minimum experience required by job
        job_max_years: Maximum experience preferred by job
        job_seniority: Job seniority level
        candidate_years: Candidate's years of experience
        candidate_level: Candidate's experience level

    Returns:
        Dict with eligible, reason, match_type
    """
    # Unknown candidate experience — allow but mark
    if candidate_years is None or candidate_level == "unknown":
        return {
            "eligible": True,
            "reason": "unknown_candidate_experience",
            "match_type": "unknown",
        }

    # No job experience requirement — allow
    if job_min_years is None and job_max_years is None and job_seniority is None:
        return {
            "eligible": True,
            "reason": "no_job_experience_requirement",
            "match_type": "open",
        }

    # Check hard mismatch: candidate is way below job minimum
    if job_min_years is not None:
        if candidate_years < job_min_years - 1:
            return {
                "eligible": False,
                "reason": f"candidate_too_junior (has {candidate_years}y, needs {job_min_years}+)",
                "match_type": "mismatch",
            }

    # Check hard mismatch: candidate is way above job maximum
    if job_max_years is not None:
        if candidate_years > job_max_years + 5:
            return {
                "eligible": False,
                "reason": f"candidate_too_senior (has {candidate_years}y, max {job_max_years})",
                "match_type": "mismatch",
            }

    # Check seniority-based mismatch
    level_order = {"entry": 0, "junior": 1, "mid": 2, "senior": 3, "lead": 4}
    cand_rank = level_order.get(candidate_level, 2)
    job_rank = level_order.get(job_seniority, 2)

    if cand_rank < job_rank - 1:
        return {
            "eligible": False,
            "reason": f"candidate_too_junior ({candidate_level} vs {job_seniority})",
            "match_type": "mismatch",
        }

    if cand_rank > job_rank + 2:
        return {
            "eligible": True,
            "reason": f"candidate_overqualified ({candidate_level} vs {job_seniority})",
            "match_type": "overqualified",
        }

    return {
        "eligible": True,
        "reason": "experience_compatible",
        "match_type": "compatible",
    }


def _categorize_role(keyword: str) -> str:
    """Map a tech keyword to a broader category."""
    keyword = keyword.lower()
    if any(w in keyword for w in ("frontend", "front-end", "ui", "ux")):
        return "frontend"
    if any(w in keyword for w in ("backend", "back-end", "server")):
        return "backend"
    if any(w in keyword for w in ("full stack", "fullstack")):
        return "fullstack"
    if any(w in keyword for w in ("ai", "ml", "machine learning", "data scientist")):
        return "ai_ml"
    if any(w in keyword for w in ("data", "analytics")):
        return "data"
    if any(w in keyword for w in ("devops", "sre", "infrastructure", "cloud", "platform")):
        return "devops"
    if any(w in keyword for w in ("mobile", "ios", "android")):
        return "mobile"
    if any(w in keyword for w in ("security", "cyber")):
        return "security"
    if any(w in keyword for w in ("qa", "quality", "test", "automation")):
        return "qa"
    if any(w in keyword for w in ("embedded", "firmware")):
        return "embedded"
    return "general_tech"


def _infer_seniority_from_years(min_years: Optional[float]) -> Optional[str]:
    """Infer seniority from minimum years if no title signal."""
    if min_years is not None and min_years >= 8:
        return "lead"
    if min_years is not None and min_years >= 5:
        return "senior"
    if min_years is not None and min_years >= 2:
        return "mid"
    return "unknown"
