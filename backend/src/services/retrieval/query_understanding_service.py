"""
Query understanding service for production retrieval intelligence.

Capabilities:
- Skill extraction from natural language queries
- Acronym normalization and expansion
- Query intent classification
- Query rewriting and decomposition
- Tech-stack expansion with variant generation
- Synonym expansion
- Context-aware retrieval strategy selection

Stateless, async-safe, observable. Worker-safe.
"""
import logging
import re
from typing import List, Dict, Any, Set, Optional

from src.schemas.retrieval import (
    QueryUnderstandingResult,
    QueryIntent,
)
from src.observability.metrics import (
    QUERY_INTENT_COUNT,
    QUERY_EXPANSION_COUNT,
    QUERY_EXPANDED_TERMS,
    QUERY_SKILL_EXTRACTIONS,
)

logger = logging.getLogger(__name__)

# ── Skill Lexicon ───────────────────────────────────────────────────

SKILLS_LEXICON: Dict[str, List[str]] = {
    # Frontend
    "react": ["React", "React.js", "React 18", "React 19", "React Hooks", "Redux", "Next.js", "Gatsby"],
    "javascript": ["JavaScript", "TypeScript", "ES6+", "Node.js", "Deno"],
    "typescript": ["TypeScript"],
    "angular": ["Angular", "AngularJS", "Angular 2+", "RxJS"],
    "vue": ["Vue.js", "Vue 3", "Nuxt", "Vuex"],
    "css": ["CSS3", "SCSS", "SASS", "Tailwind CSS", "Bootstrap", "Styled Components", "CSS Modules"],
    "html": ["HTML5", "Semantic HTML", "ARIA"],
    "frontend": ["React", "Angular", "Vue", "Svelte", "TypeScript", "JavaScript", "SPA", "SSR"],
    
    # Backend
    "fastapi": ["FastAPI", "Python", "ASGI", "Uvicorn"],
    "django": ["Django", "Django REST Framework", "Python"],
    "flask": ["Flask", "Python", "WSGI"],
    "spring": ["Spring Boot", "Java", "Spring Framework"],
    "express": ["Express.js", "Node.js", "JavaScript"],
    "go": ["Go", "Golang", "Gin"],
    "dotnet": [".NET", "C#", "ASP.NET", "Entity Framework"],
    "graphql": ["GraphQL", "Apollo", "Relay", "gRPC"],
    "rest": ["REST", "RESTful API", "OpenAPI", "Swagger"],
    
    # Cloud & DevOps
    "aws": ["AWS", "EC2", "S3", "Lambda", "RDS", "DynamoDB", "EKS", "ECS", "CloudFormation", "IAM"],
    "azure": ["Azure", "Azure Functions", "AKS", "Azure DevOps"],
    "gcp": ["Google Cloud", "GCP", "GKE", "BigQuery", "Cloud Run"],
    "kubernetes": ["Kubernetes", "k8s", "Docker", "Helm", "Istio", "Service Mesh"],
    "docker": ["Docker", "Docker Compose", "Container", "OCI"],
    "terraform": ["Terraform", "IaC", "HashiCorp"],
    "ci/cd": ["CI/CD", "Jenkins", "GitHub Actions", "GitLab CI", "CircleCI", "ArgoCD"],
    "devops": ["DevOps", "SRE", "Platform Engineering", "Kubernetes", "Docker", "Terraform", "CI/CD"],
    
    # Databases
    "postgresql": ["PostgreSQL", "Postgres", "SQL"],
    "mysql": ["MySQL", "MariaDB", "SQL"],
    "mongodb": ["MongoDB", "NoSQL", "DocumentDB"],
    "redis": ["Redis", "ElastiCache", "Cache"],
    "elasticsearch": ["Elasticsearch", "ELK", "OpenSearch"],
    "sql": ["SQL", "PostgreSQL", "MySQL", "SQL Server", "Oracle"],
    "nosql": ["MongoDB", "Cassandra", "DynamoDB", "Couchbase"],
    
    # AI/ML
    "machine learning": ["Machine Learning", "ML", "Deep Learning", "TensorFlow", "PyTorch", "Scikit-learn"],
    "pytorch": ["PyTorch", "Torch", "Deep Learning"],
    "tensorflow": ["TensorFlow", "Keras", "Deep Learning"],
    "nlp": ["NLP", "Natural Language Processing", "Transformers", "BERT", "GPT"],
    "llm": ["LLM", "Large Language Model", "GPT", "Claude", "LangChain", "LangGraph"],
    "langgraph": ["LangGraph", "LangChain", "AI Agent", "LLM Orchestration"],
    "mcp": ["MCP", "Model Context Protocol", "AI Tools"],
    "data science": ["Data Science", "Pandas", "NumPy", "Scikit-learn", "Jupyter", "R"],
    "ai": ["AI", "Artificial Intelligence", "Machine Learning", "Deep Learning", "LLM"],
    
    # General Tech
    "systems design": ["Systems Design", "System Architecture", "Distributed Systems", "Microservices"],
    "microservices": ["Microservices", "Service Mesh", "API Gateway", "Event-Driven"],
    "api": ["API", "REST", "GraphQL", "gRPC"],
    "architecture": ["System Architecture", "Enterprise Architecture", "Solution Design"],
    
    # Soft Skills
    "leadership": ["Leadership", "Team Management", "Mentoring", "Agile", "Scrum"],
    "agile": ["Agile", "Scrum", "Kanban", "SAFe", "JIRA"],
}

# ── Query Intent Classification Patterns ────────────────────────────

INTENT_PATTERNS: Dict[QueryIntent, List[str]] = {
    QueryIntent.ATS_SCORING: [
        r"\bats\b", r"\bscore\b", r"\bmatch\b.*\bjob\b", r"\brelevance\b",
        r"\bhow\s+well\b", r"\bfit\s+for\b",
    ],
    QueryIntent.RESUME_ANALYSIS: [
        r"\banalyze\b", r"\breview\b", r"\bevaluate\b", r"\bassess\b",
        r"\bstrengths?\b", r"\bweaknesses?\b", r"\bgaps?\b",
    ],
    QueryIntent.JOB_MATCHING: [
        r"\bmatch\b", r"\bfit\b", r"\balign.*role\b", r"\bsuitable\b",
        r"\bqualifications?\b", r"\brequirements?\b",
    ],
    QueryIntent.INTERVIEW_PREP: [
        r"\binterview\b", r"\bprepare\b", r"\bquestions?\b", r"\banswers?\b",
        r"\btips?\b", r"\bassess\s+my\b",
    ],
    QueryIntent.RECOMMENDATION: [
        r"\brecommend\b", r"\bsuggest\b", r"\bimprove\b", r"\benhance\b",
        r"\boptimize\b", r"\bbetter\b",
    ],
    QueryIntent.RECRUITER_SEARCH: [
        r"\bfind\b.*\bcandidates?\b", r"\bsearch\b", r"\bqualified\b",
        r"\bexperience\b\s+\d+\s+\byears?\b", r"\bsenior\b", r"\bjunior\b",
        r"\bfrontend\b", r"\bbackend\b", r"\bfull\s*stack\b",
    ],
}


class QueryUnderstandingService:
    """Production-grade query understanding for retrieval optimization.

    Determines intent, extracts and expands skills, normalizes acronyms,
    and generates optimized search queries for improved recall.
    """

    async def understand(
        self,
        query: str,
        enable_expansion: bool = True,
        max_expanded_queries: int = 5,
    ) -> QueryUnderstandingResult:
        """Analyze a query and produce understanding with expansions.

        Args:
            query: Natural language search query
            enable_expansion: Generate expanded query variants
            max_expanded_queries: Maximum number of expanded queries

        Returns:
            QueryUnderstandingResult with intent, skills, expansions
        """
        QUERY_EXPANSION_COUNT.inc()

        # 1. Intent classification
        intent, confidence = self._classify_intent(query)
        QUERY_INTENT_COUNT.labels(intent=intent.value).inc()

        # 2. Skill extraction
        skills = self._extract_skills(query)
        QUERY_SKILL_EXTRACTIONS.inc()

        # 3. Tech-stack expansion
        expanded_skills = self._expand_skills(skills)

        # 4. Acronym normalization
        acronyms = self._expand_acronyms(query)

        # 5. Synonym expansion
        synonyms = self._find_synonyms(query)

        # 6. Generate expanded queries
        expanded_queries = []
        if enable_expansion:
            expanded_queries = self._generate_expanded_queries(
                query, skills, expanded_skills, max_expanded_queries
            )
            QUERY_EXPANDED_TERMS.observe(len(expanded_queries))

        # 7. Spatial retrieval hints
        hints = self._build_retrieval_hints(intent, skills)

        # 8. Determine strategy
        strategy = self._determine_strategy(intent)

        tech_stack = list(set(
            term for variants in expanded_skills.values() for term in variants
        ))

        return QueryUnderstandingResult(
            original_query=query,
            intent=intent,
            intent_confidence=round(confidence, 3),
            extracted_skills=skills,
            expanded_skills=expanded_skills,
            tech_stack=tech_stack,
            synonyms=synonyms,
            acronyms_expanded=acronyms,
            expanded_queries=expanded_queries,
            spatial_hints=hints,
            retrieval_strategy=strategy,
        )

    # ── Intent Classification ────────────────────────────────────────

    def _classify_intent(self, query: str) -> tuple:
        """Classify query intent using pattern matching."""
        query_lower = query.lower()
        best_intent = QueryIntent.GENERAL
        best_confidence = 0.0

        for intent, patterns in INTENT_PATTERNS.items():
            matches = sum(1 for p in patterns if re.search(p, query_lower))
            if matches > 0:
                confidence = min(1.0, matches / max(len(patterns) * 0.3, 1))
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_intent = intent

        return best_intent, best_confidence

    # ── Skill Extraction ─────────────────────────────────────────────

    def _extract_skills(self, query: str) -> List[str]:
        """Extract skills from query using lexicon matching."""
        found: Set[str] = set()
        query_lower = query.lower()

        for skill, variants in SKILLS_LEXICON.items():
            if skill in query_lower or any(v.lower() in query_lower for v in variants):
                found.add(skill)

        return sorted(found)

    def _expand_skills(self, skills: List[str]) -> Dict[str, List[str]]:
        """Expand extracted skills into their full variant sets."""
        expanded: Dict[str, List[str]] = {}
        for skill in skills:
            if skill in SKILLS_LEXICON:
                expanded[skill] = SKILLS_LEXICON[skill]
        return expanded

    # ── Acronym Expansion ────────────────────────────────────────────

    ACRONYMS: Dict[str, str] = {
        "aws": "Amazon Web Services",
        "mcp": "Model Context Protocol",
        "spa": "Single Page Application",
        "ssr": "Server Side Rendering",
        "ssg": "Static Site Generation",
        "cicd": "Continuous Integration Continuous Deployment",
        "ci/cd": "Continuous Integration Continuous Deployment",
        "orm": "Object Relational Mapping",
        "k8s": "Kubernetes",
        "ml": "Machine Learning",
        "nlp": "Natural Language Processing",
        "llm": "Large Language Model",
        "rag": "Retrieval Augmented Generation",
        "api": "Application Programming Interface",
        "iam": "Identity and Access Management",
        "cdn": "Content Delivery Network",
        "waf": "Web Application Firewall",
        "vpc": "Virtual Private Cloud",
    }

    def _expand_acronyms(self, query: str) -> Dict[str, str]:
        """Find and expand known acronyms in the query."""
        expanded: Dict[str, str] = {}
        query_lower = query.lower()
        for acronym, expansion in self.ACRONYMS.items():
            pattern = rf"\b{re.escape(acronym)}\b"
            if re.search(pattern, query_lower):
                expanded[acronym] = expansion
        return expanded

    # ── Synonym Expansion ────────────────────────────────────────────

    SYNONYMS: Dict[str, str] = {
        "strong": "experienced",
        "senior": "experienced",
        "engineer": "developer",
        "building": "developing",
        "coding": "programming",
        "frontend": "UI",
        "backend": "server",
        "devops": "platform",
        "fullstack": "full stack",
        "full-stack": "full stack",
        "sre": "reliability engineering",
        "architect": "systems design",
    }

    def _find_synonyms(self, query: str) -> Dict[str, str]:
        """Extract synonyms from the query."""
        found: Dict[str, str] = {}
        query_lower = query.lower()
        for term, synonym in self.SYNONYMS.items():
            if re.search(rf"\b{re.escape(term)}\b", query_lower):
                found[term] = synonym
        return found

    # ── Query Expansion ──────────────────────────────────────────────

    def _generate_expanded_queries(
        self,
        query: str,
        skills: List[str],
        expanded_skills: Dict[str, List[str]],
        max_queries: int = 5,
    ) -> List[str]:
        """Generate expanded query variants for improved recall."""
        variants: list[str] = []

        # Variant 1: original query + skill expansions
        for skill, variants_list in list(expanded_skills.items())[:3]:
            expanded = query
            for v in variants_list[:3]:
                if v.lower() not in query.lower():
                    expanded += f" {v}"
            variants.append(expanded.strip())

        # Variant 2: query with acronym expansions
        acronyms = self._expand_acronyms(query)
        if acronyms:
            expanded_q = query
            for expansion in acronyms.values():
                if expansion.lower() not in query.lower():
                    expanded_q += f" ({expansion})"
            variants.append(expanded_q)

        # Variant 3: synonym-swapped query
        synonyms = self._find_synonyms(query)
        if synonyms:
            swapped = query
            for term, synonym in synonyms.items():
                swapped = re.sub(
                    rf"\b{re.escape(term)}\b", synonym, swapped, count=1
                )
            variants.append(swapped)

        # Variant 4: skills-only query for sparse retrieval
        if skills:
            variants.append(" ".join(skills))

        # Variant 5: title-format query
        title_format = query.title()
        if title_format not in variants and title_format != query:
            variants.append(title_format)

        return variants[:max_queries]

    # ── Retrieval Strategy ───────────────────────────────────────────

    def _determine_strategy(self, intent: QueryIntent) -> str:
        """Determine optimal retrieval strategy based on intent."""
        strategy_map = {
            QueryIntent.ATS_SCORING: "hybrid_weighted",
            QueryIntent.RECRUITER_SEARCH: "hybrid-weighted",
            QueryIntent.JOB_MATCHING: "semantic_primary",
            QueryIntent.RESUME_ANALYSIS: "semantic_primary",
            QueryIntent.INTERVIEW_PREP: "hybrid_balanced",
            QueryIntent.RECOMMENDATION: "hybrid_balanced",
            QueryIntent.GENERAL: "hybrid_default",
        }
        return strategy_map.get(intent, "hybrid_default")

    def _build_retrieval_hints(
        self, intent: QueryIntent, skills: List[str]
    ) -> Dict[str, Any]:
        """Build spatial hints for retrieval optimization."""
        hints: Dict[str, Any] = {
            "use_sparse": intent in (QueryIntent.RECRUITER_SEARCH, QueryIntent.ATS_SCORING),
            "use_dense": True,
            "boost_skills": skills,
            "max_queries": 3,
        }

        if intent == QueryIntent.RECRUITER_SEARCH:
            hints["section_boost"] = ["skills", "experience"]
            hints["exact_match_boost"] = True
        elif intent == QueryIntent.ATS_SCORING:
            hints["section_boost"] = ["skills", "experience", "summary"]
            hints["threshold_score"] = 0.3
        elif intent == QueryIntent.INTERVIEW_PREP:
            hints["section_boost"] = ["experience", "projects"]

        return hints


# Module-level singleton
_query_understanding_service: Optional[QueryUnderstandingService] = None


def get_query_understanding_service() -> QueryUnderstandingService:
    global _query_understanding_service
    if _query_understanding_service is None:
        _query_understanding_service = QueryUnderstandingService()
    return _query_understanding_service


def reset_query_understanding_service() -> None:
    global _query_understanding_service
    _query_understanding_service = None


def __getattr__(name: str):
    if name == "query_understanding_service":
        return get_query_understanding_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
