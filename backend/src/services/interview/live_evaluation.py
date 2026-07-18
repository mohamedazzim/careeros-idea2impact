"""Phase 14 — Realtime Interview Evaluation Analysis.

Streams live coaching signals during interview sessions:
- speaking pace (words per minute)
- filler word detection
- STAR format detection
- confidence scoring
- communication clarity
- technical depth estimation
"""

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

FILLER_WORDS = {
    "um", "uh", "like", "you know", "i mean", "so", "actually",
    "basically", "literally", "right", "okay", "well", "sort of",
    "kind of", "i guess", "you see",
}

STAR_PATTERNS = [
    r"\b(situation|context)\b.*\b(task|goal)\b",
    r"\b(action|steps|approach)\b.*\b(result|outcome|impact)\b",
    r"\bi\s+(built|created|led|designed|implemented|developed)\b",
    r"\b(then|after that|subsequently)\b.*\b(as a result|consequently)\b",
]


@dataclass
class LiveAnalysisResult:
    """Streaming evaluation signals for a user utterance."""
    timestamp: float = field(default_factory=time.time)
    word_count: int = 0
    speaking_pace_wpm: float = 0.0
    filler_count: int = 0
    filler_ratio: float = 0.0
    filler_words_found: List[str] = field(default_factory=list)
    star_score: float = 0.0
    star_patterns_matched: List[str] = field(default_factory=list)
    communication_score: float = 0.0
    confidence_score: float = 0.0
    technical_depth_score: float = 0.0
    technical_terms_found: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word_count": self.word_count,
            "speaking_pace_wpm": self.speaking_pace_wpm,
            "filler_count": self.filler_count,
            "filler_ratio": round(self.filler_ratio, 3),
            "filler_words_found": self.filler_words_found[:5],
            "star_score": round(self.star_score, 2),
            "star_patterns_matched": self.star_patterns_matched,
            "communication_score": round(self.communication_score, 2),
            "confidence_score": round(self.confidence_score, 2),
            "technical_depth_score": round(self.technical_depth_score, 2),
            "technical_terms_found": self.technical_terms_found[:10],
        }


def analyze_live_response(transcript: str, duration_seconds: float = 0.0) -> LiveAnalysisResult:
    """Analyze a live interview response and return streaming feedback signals.

    Args:
        transcript: The user's utterance text.
        duration_seconds: How long the user took to speak (from VAD/timer).

    Returns:
        LiveAnalysisResult with all streaming evaluation signals.
    """
    if not transcript or not transcript.strip():
        return LiveAnalysisResult()

    words = transcript.strip().split()
    word_count = len(words)
    lower_text = transcript.lower()

    # Speaking pace (words per minute)
    pace = 0.0
    if duration_seconds > 0:
        pace = (word_count / duration_seconds) * 60

    # Filler words
    found_fillers = []
    filler_hits = 0
    for filler in FILLER_WORDS:
        count = len(re.findall(r'\b' + re.escape(filler) + r'\b', lower_text))
        if count > 0:
            found_fillers.append(filler)
            filler_hits += count
    filler_ratio = filler_hits / max(word_count, 1)

    # STAR detection
    star_matches = []
    for pattern in STAR_PATTERNS:
        if re.search(pattern, lower_text):
            star_matches.append(pattern)

    # Technical terms
    technical_terms = re.findall(
        r'\b(api|sdk|docker|kubernetes|redis|postgres|graphql|rest|grpc'
        r'|microservice|pipeline|cicd|deploy|scale|latency|throughput'
        r'|database|algorithm|architecture|distributed|concurrent'
        r'|optimiz|refactor|testing|monitoring|observability)\w*\b',
        lower_text,
    )
    unique_tech = list(set(technical_terms))

    # Communication score (inverse of filler ratio, bounded)
    comm_score = max(0, min(100, (1.0 - filler_ratio) * 100))

    # Confidence score (presence of STAR + technical depth)
    conf_score = 0.0
    if star_matches:
        conf_score += 40
    if unique_tech:
        conf_score += min(40, len(unique_tech) * 5)
    if word_count > 50:
        conf_score += 20
    conf_score = min(100, conf_score)

    # STAR score
    star_score = min(100, len(star_matches) * 33.3)

    # Technical depth
    tech_score = min(100, len(unique_tech) * 10 + min(20, word_count * 0.05))

    return LiveAnalysisResult(
        word_count=word_count,
        speaking_pace_wpm=round(pace, 1),
        filler_count=filler_hits,
        filler_ratio=filler_ratio,
        filler_words_found=found_fillers,
        star_score=star_score,
        star_patterns_matched=star_matches,
        communication_score=comm_score,
        confidence_score=conf_score,
        technical_depth_score=tech_score,
        technical_terms_found=unique_tech,
    )
