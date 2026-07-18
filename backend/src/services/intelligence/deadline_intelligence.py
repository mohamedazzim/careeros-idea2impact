"""Deadline Intelligence Engine.

Extracts, parses, and estimates application deadlines for jobs.
Tracks deadline source, confidence, and status.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import re


# Deadline patterns to match in job descriptions
DEADLINE_PATTERNS = [
    # Explicit dates
    (r"(?:deadline|closing|apply by|application deadline|last date)[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})", "explicit_date", 0.95),
    (r"(?:deadline|closing|apply by|application deadline|last date)[:\s]*(\w+ \d{1,2},?\s*\d{4})", "explicit_date", 0.95),
    (r"(?:deadline|closing|apply by|application deadline|last date)[:\s]*(\d{1,2}\s+\w+\s+\d{4})", "explicit_date", 0.95),
    
    # Relative deadlines
    (r"(?:closing|deadline|apply)[:\s]*(?:in|within)\s*(\d+)\s*(?:days?|business days?)", "relative_days", 0.85),
    (r"(?:closing|deadline|apply)[:\s]*(?:in|within)\s*(\d+)\s*(?:weeks?)", "relative_weeks", 0.80),
    
    # Urgency indicators
    (r"(?:immediate|urgent|asap|immediately)", "immediate", 0.70),
    (r"(?:rolling|open until filled|until filled)", "rolling", 0.60),
    (r"(?:no deadline|open|continuous)", "open", 0.50),
]

# Date format parsers
DATE_FORMATS = [
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%m.%d.%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%Y-%m-%d",
]


class DeadlineIntelligence:
    """Extract and track job application deadlines."""

    def extract_deadline(
        self,
        job_title: str,
        job_description: str,
        posted_date: Optional[datetime] = None,
        provider_deadline: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract deadline from job data.

        Priority:
        1. Provider supplied deadline
        2. Parsed deadline from description
        3. Estimated deadline based on posting date
        """
        now = datetime.utcnow()

        # 1. Provider supplied deadline
        if provider_deadline:
            parsed = self._parse_date(provider_deadline)
            if parsed:
                return self._build_result(
                    deadline=parsed,
                    source="provider_supplied",
                    confidence=0.95,
                    posted_date=posted_date,
                    now=now,
                )

        # 2. Parse from description
        description = job_description or ""
        parsed_result = self._parse_description(description)
        if parsed_result:
            deadline, source, confidence = parsed_result
            return self._build_result(
                deadline=deadline,
                source=source,
                confidence=confidence,
                posted_date=posted_date,
                now=now,
            )

        # 3. Estimate based on posting date
        if posted_date:
            estimated = self._estimate_deadline(posted_date, description)
            return self._build_result(
                deadline=estimated,
                source="estimated",
                confidence=0.40,
                posted_date=posted_date,
                now=now,
            )

        # No deadline information available
        return {
            "application_deadline": None,
            "deadline_source": "unknown",
            "deadline_confidence": 0.0,
            "deadline_status": "UNKNOWN",
            "hours_until_deadline": None,
            "deadline_display": "No deadline",
        }

    def _parse_description(self, description: str) -> Optional[Tuple[datetime, str, float]]:
        """Parse deadline from job description."""
        text = description.lower()

        for pattern, source, confidence in DEADLINE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if source == "explicit_date":
                    date_str = match.group(1)
                    parsed = self._parse_date(date_str)
                    if parsed:
                        return parsed, "parsed_description", confidence

                elif source == "relative_days":
                    days = int(match.group(1))
                    return datetime.utcnow() + timedelta(days=days), "parsed_description", confidence

                elif source == "relative_weeks":
                    weeks = int(match.group(1))
                    return datetime.utcnow() + timedelta(weeks=weeks), "parsed_description", confidence

                elif source == "immediate":
                    return datetime.utcnow() + timedelta(days=7), "parsed_description", confidence

                elif source == "rolling":
                    return datetime.utcnow() + timedelta(days=90), "estimated_rolling", confidence

                elif source == "open":
                    return datetime.utcnow() + timedelta(days=180), "estimated_open", confidence

        return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a date string into datetime."""
        date_str = date_str.strip().rstrip(".")

        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _estimate_deadline(self, posted_date: datetime, description: str) -> datetime:
        """Estimate deadline based on posting date and description content."""
        text = description.lower()

        # Tech jobs typically have 2-4 week deadlines
        if any(term in text for term in ["urgent", "immediate", "asap"]):
            return posted_date + timedelta(days=7)

        if any(term in text for term in ["senior", "lead", "principal", "staff"]):
            return posted_date + timedelta(days=30)

        # Default: 21 days from posting
        return posted_date + timedelta(days=21)

    def _build_result(
        self,
        deadline: datetime,
        source: str,
        confidence: float,
        posted_date: Optional[datetime],
        now: datetime,
    ) -> Dict[str, Any]:
        """Build deadline result dictionary."""
        hours_until = (deadline - now).total_seconds() / 3600

        # Determine status
        if hours_until <= 0:
            status = "CLOSED"
        elif hours_until <= 72:  # 3 days
            status = "CLOSING_SOON"
        else:
            status = "OPEN"

        # Format display
        if hours_until <= 0:
            display = "Closed"
        elif hours_until <= 24:
            display = f"{int(hours_until)} hours left"
        elif hours_until <= 72:
            display = f"{int(hours_until / 24)} days left"
        else:
            display = deadline.strftime("%b %d, %Y")

        return {
            "application_deadline": deadline.isoformat(),
            "deadline_source": source,
            "deadline_confidence": confidence,
            "deadline_status": status,
            "hours_until_deadline": round(hours_until, 1),
            "deadline_display": display,
        }

    def classify_batch(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classify deadlines for a batch of jobs."""
        results = []
        for job in jobs:
            posted_date = job.get("posted_date")
            if isinstance(posted_date, str):
                try:
                    posted_date = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    posted_date = None

            result = self.extract_deadline(
                job_title=job.get("title", ""),
                job_description=job.get("description", ""),
                posted_date=posted_date,
                provider_deadline=job.get("provider_deadline"),
            )
            results.append({**job, **result})

        return results


_deadline_intelligence: Optional[DeadlineIntelligence] = None


def get_deadline_intelligence() -> DeadlineIntelligence:
    global _deadline_intelligence
    if _deadline_intelligence is None:
        _deadline_intelligence = DeadlineIntelligence()
    return _deadline_intelligence
