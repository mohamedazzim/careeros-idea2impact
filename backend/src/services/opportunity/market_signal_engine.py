"""Phase 5 — Market Signal Engine.

Market demand signals, hiring trends, and competitive intelligence.
Computes demand scores from opportunity metadata and candidate profile signals.
"""

import time
from typing import Any, Dict, List, Optional

HIGH_DEMAND_KEYWORDS = {
    "ai", "artificial intelligence", "machine learning", "ml", "deep learning",
    "llm", "large language model", "generative ai", "genai", "nlp",
    "python", "typescript", "rust", "go", "kubernetes", "docker",
    "aws", "gcp", "azure", "terraform", "react", "next.js",
    "langchain", "langgraph", "vector search", "rag",
    "distributed systems", "microservices", "data engineering",
    "mlops", "devops", "sre", "platform engineering",
    "cybersecurity", "zero trust", "fintech", "healthtech",
    "blockchain", "web3", "edge computing", "iot",
}

ENTERPRISE_PREMIUM_COMPANIES = {
    "google", "meta", "amazon", "microsoft", "apple", "netflix",
    "stripe", "airbnb", "uber", "openai", "anthropic", "databricks",
    "snowflake", "palantir", "anduril", "spacex", "tesla",
}

_HOT_DOMAINS = {
    "ai_ml": 1.0,
    "llm_genai": 1.0,
    "infrastructure": 0.85,
    "data": 0.80,
    "security": 0.85,
    "fintech": 0.75,
    "healthtech": 0.70,
    "web3": 0.60,
    "enterprise_saas": 0.65,
    "ecommerce": 0.55,
    "gaming": 0.50,
    "iot": 0.55,
}


class MarketSignalEngine:

    def get_signals(self, role: str = "", domain: str = "") -> Dict[str, Any]:
        role_lower = role.lower() if role else ""
        domain_lower = domain.lower() if domain else ""

        keyword_hits = [kw for kw in HIGH_DEMAND_KEYWORDS if kw in role_lower or kw in domain_lower]

        signals = self._base_signals()
        signals["keyword_hits"] = len(keyword_hits)
        signals["matched_keywords"] = keyword_hits
        signals["demand_velocity"] = self._compute_demand_velocity(keyword_hits)
        signals["competition_intensity"] = self._compute_competition_intensity(keyword_hits, role_lower)
        signals["timestamp"] = time.time()

        return {
            "role": role,
            "domain": domain,
            "signals": signals,
            "timestamp": signals["timestamp"],
        }

    def _base_signals(self) -> Dict[str, Any]:
        return {
            "hiring_velocity": "moderate",
            "competition_level": "standard",
            "salary_band_competitive": True,
            "remote_friendly": True,
            "growth_trajectory": "stable",
        }

    def _compute_demand_velocity(self, keyword_hits: List[str]) -> str:
        if len(keyword_hits) >= 5:
            return "very_high"
        elif len(keyword_hits) >= 3:
            return "high"
        elif len(keyword_hits) >= 1:
            return "moderate"
        return "standard"

    def _compute_competition_intensity(self, keyword_hits: List[str], role_lower: str) -> str:
        hot_kw = sum(1 for kw in keyword_hits if kw in HIGH_DEMAND_KEYWORDS)
        if hot_kw >= 4:
            return "fierce"
        elif hot_kw >= 2:
            return "high"
        elif hot_kw >= 1:
            return "moderate"
        return "standard"

    def market_demand_score(self, opportunity: Dict[str, Any]) -> float:
        text = (opportunity.get("title", "") + " " + opportunity.get("text", "") + " " +
                opportunity.get("description", "")).lower()
        company = (opportunity.get("company", "") or "").lower()

        components = []

        # Keyword match density
        keyword_hits = [kw for kw in HIGH_DEMAND_KEYWORDS if kw in text]
        kw_score = min(len(keyword_hits) / 6.0, 1.0)
        components.append(("keyword_density", 0.35, kw_score))

        # Domain hotness
        domain_score = 0.5
        for domain_key, weight in _HOT_DOMAINS.items():
            if domain_key.replace("_", " ") in text or domain_key in text:
                domain_score = max(domain_score, weight)
        components.append(("domain_hotness", 0.25, domain_score))

        # Company premium
        company_score = 0.85 if any(prem in company for prem in ENTERPRISE_PREMIUM_COMPANIES) else 0.55
        components.append(("company_premium", 0.20, company_score))

        # Role specificity (longer, more specific titles = higher demand signal)
        title_len = len(opportunity.get("title", ""))
        specificity_score = min(title_len / 40.0, 1.0) if title_len > 5 else 0.4
        components.append(("role_specificity", 0.10, specificity_score))

        # Remote/hybrid signals from any description
        remote_score = 0.65
        if any(tag in text for tag in ("remote", "remote-first", "remote friendly", "distributed")):
            remote_score = 0.85
        components.append(("remote_signal", 0.10, remote_score))

        total = sum(weight * score for _, weight, score in components)
        return round(min(total, 1.0), 4)

    def get_demand_breakdown(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        text = (opportunity.get("title", "") + " " + opportunity.get("text", "") + " " +
                opportunity.get("description", "")).lower()
        company = (opportunity.get("company", "") or "").lower()

        keyword_hits = [kw for kw in HIGH_DEMAND_KEYWORDS if kw in text]
        premium = any(prem in company for prem in ENTERPRISE_PREMIUM_COMPANIES)
        remote = any(tag in text for tag in ("remote", "remote-first", "distributed"))

        return {
            "overall_demand": self.market_demand_score(opportunity),
            "keyword_hits": keyword_hits,
            "keyword_count": len(keyword_hits),
            "enterprise_premium": premium,
            "remote_friendly": remote,
            "title_length": len(opportunity.get("title", "")),
        }


# ── Singleton ────────────────────────────────────────────────────────

_engine: Optional[MarketSignalEngine] = None


def get_market_signal_engine() -> MarketSignalEngine:
    global _engine
    if _engine is None:
        _engine = MarketSignalEngine()
    return _engine
