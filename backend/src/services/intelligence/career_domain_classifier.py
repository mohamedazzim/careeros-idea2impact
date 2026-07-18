"""Career Domain Classification Service.

Classifies jobs and resumes into career domains and families.
Used to filter out non-relevant matches (e.g., Voice Actor for AI Engineer).
"""

from typing import Any, Dict, List, Optional, Tuple

# Career families and their domains
CAREER_FAMILIES = {
    "ai_ml": {
        "display": "AI & Machine Learning",
        "domains": [
            "ai engineer", "machine learning engineer", "ml engineer",
            "data scientist", "deep learning engineer", "nlp engineer",
            "computer vision engineer", "mlops engineer", "ai researcher",
            "generative ai engineer", "llm engineer", "applied scientist",
        ],
        "keywords": [
            "artificial intelligence", "machine learning", "deep learning",
            "neural network", "tensorflow", "pytorch", "scikit-learn",
            "nlp", "natural language processing", "computer vision",
            "generative ai", "llm", "large language model", "mlops",
            "model training", "model deployment", "feature engineering",
        ],
        "adjacent": ["data_analytics", "backend", "devops"],
    },
    "data_analytics": {
        "display": "Data & Analytics",
        "domains": [
            "data analyst", "data engineer", "analytics engineer",
            "business intelligence analyst", "bi developer",
            "business analyst", "quantitative analyst",
        ],
        "keywords": [
            "data analysis", "sql", "tableau", "power bi", "looker",
            "etl", "data pipeline", "data warehouse", "analytics",
            "business intelligence", "reporting", "dashboard",
        ],
        "adjacent": ["ai_ml", "backend"],
    },
    "backend": {
        "display": "Backend Engineering",
        "domains": [
            "backend engineer", "backend developer", "software engineer",
            "python developer", "java developer", "golang developer",
            "rust developer", "api engineer", "platform engineer",
            "systems engineer", "infrastructure engineer",
        ],
        "keywords": [
            "backend", "api", "microservices", "rest", "graphql",
            "python", "java", "golang", "rust", "node.js",
            "database", "postgresql", "mongodb", "redis",
            "fastapi", "django", "flask", "spring",
        ],
        "adjacent": ["ai_ml", "devops", "frontend"],
    },
    "frontend": {
        "display": "Frontend Engineering",
        "domains": [
            "frontend engineer", "frontend developer", "react developer",
            "vue developer", "angular developer", "ui engineer",
            "web developer", "javascript developer", "typescript developer",
        ],
        "keywords": [
            "frontend", "react", "vue", "angular", "javascript",
            "typescript", "html", "css", "ui", "ux",
            "responsive", "web development", "spa",
        ],
        "adjacent": ["backend", "design"],
    },
    "devops": {
        "display": "DevOps & Infrastructure",
        "domains": [
            "devops engineer", "sre", "site reliability engineer",
            "cloud engineer", "infrastructure engineer",
            "platform engineer", "release engineer",
        ],
        "keywords": [
            "devops", "ci/cd", "docker", "kubernetes", "aws",
            "azure", "gcp", "terraform", "ansible", "jenkins",
            "monitoring", "logging", "infrastructure",
        ],
        "adjacent": ["backend", "security"],
    },
    "product": {
        "display": "Product Management",
        "domains": [
            "product manager", "senior product manager",
            "director of product", "vp of product",
            "product owner", "technical product manager",
        ],
        "keywords": [
            "product management", "product strategy", "roadmap",
            "user stories", "agile", "scrum", "backlog",
            "stakeholder", "product development",
        ],
        "adjacent": ["design", "marketing"],
    },
    "marketing": {
        "display": "Marketing",
        "domains": [
            "marketing manager", "digital marketing", "content marketer",
            "growth marketer", "seo specialist", "ppc specialist",
            "brand manager", "marketing analyst",
        ],
        "keywords": [
            "marketing", "seo", "sem", "content marketing",
            "social media", "email marketing", "growth",
            "brand", "advertising", "campaign",
        ],
        "adjacent": ["product", "sales"],
    },
    "sales": {
        "display": "Sales",
        "domains": [
            "sales manager", "account executive", "sales representative",
            "business development", "sales engineer",
            "account manager", "customer success",
        ],
        "keywords": [
            "sales", "revenue", "pipeline", "quota",
            "account management", "business development",
            "customer acquisition", "crm",
        ],
        "adjacent": ["marketing", "customer_success"],
    },
    "design": {
        "display": "Design",
        "domains": [
            "ux designer", "ui designer", "product designer",
            "graphic designer", "visual designer", "interaction designer",
            "design lead", "creative director",
        ],
        "keywords": [
            "design", "ux", "ui", "figma", "sketch",
            "adobe", "wireframe", "prototype", "user research",
            "usability", "visual design",
        ],
        "adjacent": ["frontend", "product"],
    },
    "finance": {
        "display": "Finance",
        "domains": [
            "financial analyst", "accountant", "controller",
            "cfo", "finance manager", "investment analyst",
            "risk analyst", "compliance officer",
        ],
        "keywords": [
            "finance", "accounting", "financial", "budget",
            "forecast", "audit", "compliance", "tax",
            "investment", "risk management",
        ],
        "adjacent": ["product", "operations"],
    },
    "hr": {
        "display": "Human Resources",
        "domains": [
            "hr manager", "recruiter", "talent acquisition",
            "hr business partner", "people operations",
            "compensation analyst", "learning & development",
        ],
        "keywords": [
            "human resources", "hr", "recruiting", "talent",
            "hiring", "onboarding", "compensation", "benefits",
            "employee relations", "people operations",
        ],
        "adjacent": ["operations"],
    },
    "operations": {
        "display": "Operations",
        "domains": [
            "operations manager", "project manager", "program manager",
            "scrum master", "agile coach", "coo",
        ],
        "keywords": [
            "operations", "project management", "program management",
            "process improvement", "efficiency", "logistics",
            "supply chain", "scrum", "agile",
        ],
        "adjacent": ["product", "hr"],
    },
    "security": {
        "display": "Security",
        "domains": [
            "security engineer", "cybersecurity analyst", "infosec",
            "penetration tester", "security architect", "ciso",
        ],
        "keywords": [
            "security", "cybersecurity", "infosec", "penetration testing",
            "vulnerability", "compliance", "encryption", "firewall",
        ],
        "adjacent": ["devops", "backend"],
    },
    "creative": {
        "display": "Creative & Entertainment",
        "domains": [
            "voice actor", "actor", "content creator", "video editor",
            "photographer", "musician", "writer", "journalist",
            "animator", "game designer",
        ],
        "keywords": [
            "voice acting", "acting", "content creation", "video",
            "photography", "music", "writing", "animation",
            "game design", "entertainment",
        ],
        "adjacent": ["design", "marketing"],
    },
    "healthcare": {
        "display": "Healthcare",
        "domains": [
            "nurse", "doctor", "physician", "medical",
            "healthcare", "clinical", "pharmacist",
        ],
        "keywords": [
            "healthcare", "medical", "clinical", "patient",
            "hospital", "nursing", "pharmacy",
        ],
        "adjacent": [],
    },
    "education": {
        "display": "Education",
        "domains": [
            "teacher", "professor", "instructor", "tutor",
            "curriculum designer", "educational",
        ],
        "keywords": [
            "education", "teaching", "curriculum", "learning",
            "student", "classroom", "training",
        ],
        "adjacent": ["hr"],
    },
}


class CareerDomainClassifier:
    """Classifies jobs and resumes into career domains and families."""

    def classify_job(self, job_title: str, job_description: str = "", skills: List[str] = None) -> Dict[str, Any]:
        """Classify a job into career domain and family."""
        text = f"{job_title} {job_description[:500]}".lower()
        skill_text = " ".join(skills or []).lower()
        full_text = f"{text} {skill_text}"

        # Score each family
        family_scores: Dict[str, float] = {}
        for family_id, family in CAREER_FAMILIES.items():
            score = 0.0

            # Check domain matches (exact title match = high score)
            for domain in family["domains"]:
                if domain in text:
                    score += 100.0
                    break

            # Check keyword matches
            keyword_hits = sum(1 for kw in family["keywords"] if kw in full_text)
            score += keyword_hits * 15.0

            if score > 0:
                family_scores[family_id] = score

        if not family_scores:
            return {
                "career_family": "unknown",
                "career_domain": job_title.lower().strip(),
                "confidence": 0.2,
                "family_display": "Unknown",
                "all_scores": {},
            }

        # Get best match
        best_family = max(family_scores, key=family_scores.get)
        best_score = family_scores[best_family]
        family = CAREER_FAMILIES[best_family]

        # Find best domain match
        best_domain = job_title.lower().strip()
        for domain in family["domains"]:
            if domain in text:
                best_domain = domain
                break

        # Normalize confidence (0-1)
        max_possible = 100.0 + len(family["keywords"]) * 15.0
        confidence = min(1.0, best_score / max_possible)

        return {
            "career_family": best_family,
            "career_domain": best_domain,
            "confidence": round(confidence, 2),
            "family_display": family["display"],
            "all_scores": {k: round(v, 1) for k, v in sorted(family_scores.items(), key=lambda x: -x[1])},
        }

    def classify_resume(self, resume_text: str, skills: List[str] = None, target_role: str = "") -> Dict[str, Any]:
        """Classify a resume into career domain and family."""
        text = resume_text[:2000].lower()
        skill_text = " ".join(skills or []).lower()
        target = target_role.lower()
        full_text = f"{text} {skill_text} {target}"

        # Score each family
        family_scores: Dict[str, float] = {}
        for family_id, family in CAREER_FAMILIES.items():
            score = 0.0

            # Check domain matches (target role match = high score)
            for domain in family["domains"]:
                if domain in target or domain in text:
                    score += 100.0
                    break

            # Check keyword matches
            keyword_hits = sum(1 for kw in family["keywords"] if kw in full_text)
            score += keyword_hits * 15.0

            if score > 0:
                family_scores[family_id] = score

        if not family_scores:
            return {
                "career_family": "unknown",
                "career_domain": target_role.lower().strip() if target_role else "unknown",
                "confidence": 0.2,
                "family_display": "Unknown",
                "all_scores": {},
            }

        # Get best match
        best_family = max(family_scores, key=family_scores.get)
        best_score = family_scores[best_family]
        family = CAREER_FAMILIES[best_family]

        # Find best domain match
        best_domain = target_role.lower().strip() if target_role else "unknown"
        for domain in family["domains"]:
            if domain in target or domain in text:
                best_domain = domain
                break

        # Normalize confidence (0-1)
        max_possible = 100.0 + len(family["keywords"]) * 15.0
        confidence = min(1.0, best_score / max_possible)

        return {
            "career_family": best_family,
            "career_domain": best_domain,
            "confidence": round(confidence, 2),
            "family_display": family["display"],
            "all_scores": {k: round(v, 1) for k, v in sorted(family_scores.items(), key=lambda x: -x[1])},
        }

    def calculate_domain_alignment(
        self,
        resume_family: str,
        job_family: str,
    ) -> Tuple[int, str]:
        """Calculate domain alignment score between resume and job.

        Returns:
            (score, reason) where score is 0-100
        """
        if resume_family == "unknown" or job_family == "unknown":
            return 50, "unknown_domain"

        if resume_family == job_family:
            return 100, "same_family"

        # Check adjacency
        resume_info = CAREER_FAMILIES.get(resume_family, {})
        adjacent = resume_info.get("adjacent", [])
        if job_family in adjacent:
            return 50, "adjacent_family"

        return 0, "unrelated_family"


_classifier: Optional[CareerDomainClassifier] = None


def get_career_domain_classifier() -> CareerDomainClassifier:
    global _classifier
    if _classifier is None:
        _classifier = CareerDomainClassifier()
    return _classifier
