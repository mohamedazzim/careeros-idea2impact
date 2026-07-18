"""
Resume experience extraction service.

Extracts years of experience and experience level from resume text
or analysis results without requiring LLM calls.
"""

import re
import logging
from typing import Any, Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)

# Patterns for explicit year mentions
YEAR_PATTERNS = [
    # "3+ years experience"
    r'(\d+(?:\.\d+)?)\+?\s*years?\s*(?:of\s+)?(?:experience|exp)',
    # "experience: 5 years"
    r'(?:experience|exp)\s*[:=]\s*(\d+(?:\.\d+)?)\+?\s*years?',
    # "worked for 4 years"
    r'worked\s+(?:for|as)\s+.*?(\d+(?:\.\d+)?)\+?\s*years?',
    # "3 year experience"
    r'(\d+(?:\.\d+)?)\+?\s*year(?:s)?\s+(?:of\s+)?(?:experience|exp)',
    # "experience of 6 years"
    r'experience\s+of\s+(\d+(?:\.\d+)?)\+?\s*years?',
    # "having 2 years"
    r'having\s+(\d+(?:\.\d+)?)\+?\s*years?',
    # "over 10 years"
    r'over\s+(\d+(?:\.\d+)?)\+?\s*years?',
]

# Patterns for date range extraction ("2021-2024", "Jan 2020 to present")
DATE_RANGE_PATTERNS = [
    # "2021 - 2024" or "2021-2024"
    r'(\d{4})\s*[-–—]\s*(\d{4}|present|current|now)',
    # "Jan 2020 to Mar 2024"
    r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{4})\s+to\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{4})',
    # "from 2019 to present"
    r'from\s+(\d{4})\s+to\s+(present|current|now|\d{4})',
]

# Internship patterns (should count as less than 1 year)
INTERNSHIP_PATTERNS = [
    r'intern(?:ship)?',
    r'trainee',
    r'fresher',
    r'entry[- ]level',
    r'fresh\s+graduate',
]

# Seniority keywords
SENIORITY_KEYWORDS = {
    'lead': ['lead', 'tech lead', 'technical lead', 'team lead'],
    'senior': ['senior', 'sr.', 'sr ', 'principal', 'staff', 'architect'],
    'mid': ['associate', 'ii', 'software engineer ii', 'mid-level', 'mid level'],
    'junior': ['junior', 'jr.', 'jr ', 'entry', 'fresher', 'graduate', 'trainee'],
}


def extract_resume_experience(
    resume_text: Optional[str] = None,
    analysis_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extract years of experience and experience level from resume.

    Args:
        resume_text: Raw resume text content
        analysis_results: Existing analysis JSON from knowledge_doc

    Returns:
        Dict with years_of_experience, experience_level, evidence
    """
    text = ""
    years_from_analysis = None

    # Try to get from existing analysis first
    if analysis_results:
        years_from_analysis = _extract_from_analysis(analysis_results)
        text_parts = []
        if analysis_results.get("summary"):
            text_parts.append(analysis_results["summary"])
        if analysis_results.get("skills"):
            text_parts.append(" ".join(analysis_results["skills"]) if isinstance(analysis_results["skills"], list) else str(analysis_results["skills"]))
        if analysis_results.get("experience"):
            exp = analysis_results["experience"]
            if isinstance(exp, list):
                for item in exp:
                    if isinstance(item, dict):
                        text_parts.append(f"{item.get('title', '')} {item.get('company', '')} {item.get('duration', '')} {item.get('description', '')}")
                    else:
                        text_parts.append(str(item))
            elif isinstance(exp, str):
                text_parts.append(exp)
        text = " ".join(text_parts)

    # Also check raw resume text
    if resume_text:
        text = f"{text} {resume_text}" if text else resume_text

    if not text.strip() and years_from_analysis is None:
        return {
            "years_of_experience": None,
            "experience_level": "unknown",
            "evidence": [],
            "is_intern": False,
        }

    evidence: List[str] = []
    detected_years: List[float] = []

    # Check for internship first
    is_intern = False
    for pattern in INTERNSHIP_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            is_intern = True
            evidence.append(f"Internship pattern detected: {pattern}")
            break

    # Try explicit year patterns
    for pattern in YEAR_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                years = float(match)
                if 0 <= years <= 50:
                    detected_years.append(years)
                    evidence.append(f"Year pattern matched: {match} years")
            except (ValueError, TypeError):
                pass

    # Try date range extraction
    for pattern in DATE_RANGE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                start_year = int(match[0])
                end_str = match[1].lower()
                if end_str in ('present', 'current', 'now'):
                    from datetime import datetime
                    end_year = datetime.now().year
                else:
                    end_year = int(match[1])
                years = end_year - start_year
                if 0 <= years <= 50:
                    detected_years.append(years)
                    evidence.append(f"Date range: {start_year}-{end_year} = {years} years")
            except (ValueError, TypeError):
                pass

    # Use analysis results years if available
    if years_from_analysis is not None:
        detected_years.append(years_from_analysis)
        evidence.append(f"Analysis results: {years_from_analysis} years")

    # Determine final years estimate (use the maximum, most conservative)
    final_years = None
    if detected_years:
        final_years = max(detected_years)

    # Determine experience level
    if is_intern and (final_years is None or final_years < 1):
        experience_level = "entry"
        evidence.append("Classified as entry (internship detected)")
    elif final_years is None:
        experience_level = "unknown"
        evidence.append("Could not determine years of experience")
    elif final_years < 1:
        experience_level = "entry"
    elif final_years < 2:
        experience_level = "junior"
    elif final_years < 5:
        experience_level = "mid"
    elif final_years < 8:
        experience_level = "senior"
    else:
        experience_level = "lead"

    return {
        "years_of_experience": final_years,
        "experience_level": experience_level,
        "evidence": evidence,
        "is_intern": is_intern,
    }


def _extract_from_analysis(analysis: Dict[str, Any]) -> Optional[float]:
    """Try to extract years from existing analysis JSON."""
    # Check common field names
    for key in ("years_of_experience", "total_experience_years", "experience_years"):
        val = analysis.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass

    # Check nested experience entries
    experience = analysis.get("experience", analysis.get("work_experience", []))
    if isinstance(experience, list) and experience:
        # Try to calculate from date ranges in experience entries
        total_years = 0.0
        for entry in experience:
            if isinstance(entry, dict):
                duration = entry.get("duration", entry.get("period", ""))
                if duration:
                    years = _parse_duration_string(str(duration))
                    if years is not None:
                        total_years += years
        if total_years > 0:
            return total_years

    return None


def _parse_duration_string(duration: str) -> Optional[float]:
    """Parse duration strings like '2 years 3 months', '1 yr 6 mo', '3.5 years'."""
    total_months = 0.0

    # Years
    year_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr)', duration, re.IGNORECASE)
    if year_match:
        total_months += float(year_match.group(1)) * 12

    # Months
    month_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:months?|mos?|mo)', duration, re.IGNORECASE)
    if month_match:
        total_months += float(month_match.group(1))

    if total_months > 0:
        return total_months / 12.0

    return None
