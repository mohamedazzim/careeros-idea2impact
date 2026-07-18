"""Canonical skill normalization helpers for learning paths."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


_ALIAS_MAP = {
    "c++": ("cpp", "C++"),
    "cpp": ("cpp", "C++"),
    "amazon web services": ("aws", "AWS"),
    "amazon aws": ("aws", "AWS"),
    "aws": ("aws", "AWS"),
    "ci cd": ("ci-cd", "CI/CD"),
    "ci/cd": ("ci-cd", "CI/CD"),
    "ci-cd": ("ci-cd", "CI/CD"),
    "pytorch": ("pytorch", "PyTorch"),
    "torch": ("pytorch", "PyTorch"),
    "tensorflow": ("tensorflow", "TensorFlow"),
    "deep learning": ("deep-learning", "Deep Learning"),
    "dl": ("deep-learning", "Deep Learning"),
    "machine learning": ("machine-learning", "Machine Learning"),
    "ml": ("machine-learning", "Machine Learning"),
    "node js": ("node-js", "Node.js"),
    "nodejs": ("node-js", "Node.js"),
    "node.js": ("node-js", "Node.js"),
    "fast api": ("fastapi", "FastAPI"),
    "fastapi": ("fastapi", "FastAPI"),
    "react js": ("react", "React"),
    "reactjs": ("react", "React"),
    "react": ("react", "React"),
    "postgresql": ("postgresql", "PostgreSQL"),
    "postgres": ("postgresql", "PostgreSQL"),
    "docker": ("docker", "Docker"),
    "kubernetes": ("kubernetes", "Kubernetes"),
    "langchain": ("langchain", "LangChain"),
    "javascript": ("javascript", "JavaScript"),
    "java script": ("javascript", "JavaScript"),
    "js": ("javascript", "JavaScript"),
    "java": ("java", "Java"),
    "core java": ("java", "Java"),
    "java programming": ("java", "Java"),
    "java se": ("java", "Java"),
    "jdk": ("java", "Java"),
    "openjdk": ("java", "Java"),
    "spring boot": ("spring-boot", "Spring Boot"),
    "typescript": ("typescript", "TypeScript"),
    "python": ("python", "Python"),
    "git": ("git", "Git"),
    "github": ("github", "GitHub"),
}

_REVERSE_ALIAS_MAP: dict[str, set[str]] = {}
for _raw_alias, (_slug, _display) in _ALIAS_MAP.items():
    bucket = _REVERSE_ALIAS_MAP.setdefault(_slug, set())
    bucket.add(_raw_alias)
    bucket.add(_display)
    bucket.add(_slug)


@dataclass(frozen=True)
class NormalizedSkill:
    slug: str
    display_name: str
    aliases: tuple[str, ...] = ()


def _simplify(text: str) -> str:
    cleaned = re.sub(r"[\s/_-]+", " ", text.strip().lower())
    cleaned = re.sub(r"[^a-z0-9.+# ]+", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def slugify_skill(text: str) -> str:
    simplified = _simplify(text)
    if not simplified:
        return ""
    normalized = simplified.replace("c++", "cpp").replace(".", " ")
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = normalized.replace("fast-api", "fastapi")
    normalized = normalized.replace("machine-learning", "machine-learning")
    normalized = normalized.replace("deep-learning", "deep-learning")
    normalized = normalized.replace("postgres-sql", "postgresql")
    return normalized.strip("-")


def normalize_skill(raw_skill: object) -> NormalizedSkill:
    if raw_skill is None:
        return NormalizedSkill(slug="", display_name="")

    if isinstance(raw_skill, dict):
        value = (
            raw_skill.get("skill")
            or raw_skill.get("name")
            or raw_skill.get("title")
            or raw_skill.get("category")
            or raw_skill.get("description")
            or raw_skill.get("id")
            or ""
        )
    else:
        value = str(raw_skill)

    cleaned = str(value).strip()
    if not cleaned:
        return NormalizedSkill(slug="", display_name="")

    simplified = _simplify(cleaned)
    if simplified in _ALIAS_MAP:
        slug, display = _ALIAS_MAP[simplified]
        return NormalizedSkill(slug=slug, display_name=display, aliases=(cleaned,))

    slug = slugify_skill(cleaned)
    if not slug:
        return NormalizedSkill(slug="", display_name="")

    display_name = cleaned.replace("  ", " ").strip()
    if display_name.lower() == "node js":
        display_name = "Node.js"
    elif display_name.lower() == "fast api":
        display_name = "FastAPI"
    elif display_name.lower() == "aws":
        display_name = "AWS"
    elif display_name.lower() in {"java", "jdk", "openjdk", "core java", "java se", "java programming"}:
        display_name = "Java"
    elif display_name.lower() == "js":
        display_name = "JavaScript"
    elif display_name.lower() == "ml":
        display_name = "Machine Learning"
    elif display_name.lower() == "dl":
        display_name = "Deep Learning"

    return NormalizedSkill(slug=slug, display_name=display_name, aliases=(cleaned,))


def normalize_skill_list(raw_skills: Iterable[object]) -> list[NormalizedSkill]:
    seen: set[str] = set()
    result: list[NormalizedSkill] = []
    for item in raw_skills:
        normalized = normalize_skill(item)
        if not normalized.slug or normalized.slug in seen:
            continue
        seen.add(normalized.slug)
        result.append(normalized)
    return result


def canonical_display_name(skill_slug: str, fallback: str = "") -> str:
    for slug, display in _ALIAS_MAP.values():
        if slug == skill_slug:
            return display
    return fallback or skill_slug.replace("-", " ").title()


def skill_search_terms(raw_skill: object) -> tuple[str, ...]:
    normalized = normalize_skill(raw_skill)
    if not normalized.slug:
        return ()
    terms = {
        normalized.slug,
        normalized.slug.replace("-", " "),
        normalized.slug.replace("-", ""),
        normalized.display_name,
        normalized.display_name.lower(),
        _simplify(normalized.display_name),
        _simplify(normalized.slug.replace("-", " ")),
    }
    terms.update(_REVERSE_ALIAS_MAP.get(normalized.slug, set()))
    cleaned_terms = []
    for term in terms:
        simplified = _simplify(str(term))
        if simplified:
            cleaned_terms.append(simplified)
    return tuple(sorted(set(cleaned_terms), key=len, reverse=True))
