"""Tests for strict India location eligibility classifier.

Verifies that the classifier correctly accepts India-eligible jobs
and rejects non-India jobs, including edge cases around remote jobs.
"""
import pytest
from src.services.job_location_filter import classify_job_location


class TestIndiaAccept:
    """Jobs that MUST be accepted as India-eligible."""

    def test_bengaluru_india(self):
        r = classify_job_location(location_raw="Bengaluru, Karnataka, India")
        assert r.is_india_eligible is True
        assert r.location_city == "bengaluru"

    def test_bangalore_india(self):
        r = classify_job_location(location_raw="Bangalore, India")
        assert r.is_india_eligible is True

    def test_chennai(self):
        r = classify_job_location(location_raw="Chennai, Tamil Nadu")
        assert r.is_india_eligible is True

    def test_hyderabad(self):
        r = classify_job_location(location_raw="Hyderabad, Telangana")
        assert r.is_india_eligible is True

    def test_pune(self):
        r = classify_job_location(location_raw="Pune, Maharashtra")
        assert r.is_india_eligible is True

    def test_mumbai(self):
        r = classify_job_location(location_raw="Mumbai, India")
        assert r.is_india_eligible is True

    def test_delhi(self):
        r = classify_job_location(location_raw="New Delhi, India")
        assert r.is_india_eligible is True

    def test_gurgaon(self):
        r = classify_job_location(location_raw="Gurugram, Haryana")
        assert r.is_india_eligible is True

    def test_remote_india(self):
        r = classify_job_location(location_raw="Remote India")
        assert r.is_india_eligible is True

    def test_india_remote(self):
        r = classify_job_location(location_raw="India Remote")
        assert r.is_india_eligible is True

    def test_india_keyword_in_location(self):
        r = classify_job_location(location_raw="Anywhere in India")
        assert r.is_india_eligible is True

    def test_india_eligible_in_title(self):
        r = classify_job_location(
            location_raw="Remote",
            title="Software Engineer - India Eligible",
        )
        assert r.is_india_eligible is True

    def test_country_code_IN(self):
        r = classify_job_location(location_raw="IN", country_code="IN")
        assert r.is_india_eligible is True

    def test_kolkata(self):
        r = classify_job_location(location_raw="Kolkata, West Bengal")
        assert r.is_india_eligible is True

    def test_coimbatore(self):
        r = classify_job_location(location_raw="Coimbatore, Tamil Nadu")
        assert r.is_india_eligible is True

    def test_ahmedabad(self):
        r = classify_job_location(location_raw="Ahmedabad, Gujarat")
        assert r.is_india_eligible is True


class TestIndiaReject:
    """Jobs that MUST be rejected as non-India."""

    def test_uk_london(self):
        r = classify_job_location(location_raw="London, UK; Ontario, CAN; Remote-Friendly, United States; San Francisco, CA")
        assert r.is_india_eligible is False
        assert "non_india_location" in (r.exclusion_reason or "")

    def test_germany_berlin(self):
        r = classify_job_location(location_raw="Berlin, Germany")
        assert r.is_india_eligible is False
        assert "non_india_location" in (r.exclusion_reason or "")

    def test_remote_uk_germany(self):
        r = classify_job_location(location_raw="Remote - United Kingdom, Germany")
        assert r.is_india_eligible is False

    def test_remote_us(self):
        r = classify_job_location(location_raw="Remote US")
        assert r.is_india_eligible is False

    def test_remote_europe(self):
        r = classify_job_location(location_raw="Remote Europe")
        assert r.is_india_eligible is False

    def test_canada_ontario(self):
        r = classify_job_location(location_raw="Ontario, Canada")
        assert r.is_india_eligible is False

    def test_san_francisco(self):
        r = classify_job_location(location_raw="San Francisco, CA")
        assert r.is_india_eligible is False

    def test_new_york(self):
        r = classify_job_location(location_raw="New York, NY")
        assert r.is_india_eligible is False

    def test_worldwide_without_india(self):
        r = classify_job_location(location_raw="Worldwide Remote")
        assert r.is_india_eligible is False

    def test_global_remote_without_india(self):
        r = classify_job_location(location_raw="Global Remote")
        assert r.is_india_eligible is False

    def test_remote_friendly_without_india(self):
        r = classify_job_location(location_raw="Remote-Friendly")
        assert r.is_india_eligible is False

    def test_bare_remote(self):
        r = classify_job_location(location_raw="Remote")
        assert r.is_india_eligible is False

    def test_empty_location(self):
        r = classify_job_location(location_raw="")
        assert r.is_india_eligible is False

    def test_none_location(self):
        r = classify_job_location(location_raw=None)
        assert r.is_india_eligible is False

    def test_usa(self):
        r = classify_job_location(location_raw="United States of America")
        assert r.is_india_eligible is False

    def test_germany_only(self):
        r = classify_job_location(location_raw="Germany")
        assert r.is_india_eligible is False

    def test_australia(self):
        r = classify_job_location(location_raw="Sydney, Australia")
        assert r.is_india_eligible is False

    def test_france_paris(self):
        r = classify_job_location(location_raw="Paris, France")
        assert r.is_india_eligible is False

    def test_netherlands_amsterdam(self):
        r = classify_job_location(location_raw="Amsterdam, Netherlands")
        assert r.is_india_eligible is False

    def test_singapore(self):
        r = classify_job_location(location_raw="Singapore")
        assert r.is_india_eligible is False

    def test_japan_tokyo(self):
        r = classify_job_location(location_raw="Tokyo, Japan")
        assert r.is_india_eligible is False


class TestEdgeCases:
    """Edge cases for location classification."""

    def test_india_city_in_description_not_location(self):
        """City in description should NOT make Berlin eligible."""
        r = classify_job_location(
            location_raw="Berlin, Germany",
            title="Backend Engineer",
            description="Work with our Bengaluru team on AI projects",
        )
        assert r.is_india_eligible is False

    def test_india_city_in_title_yes(self):
        """India city in title should make eligible."""
        r = classify_job_location(
            location_raw="Remote",
            title="Software Engineer - Bengaluru, India",
        )
        assert r.is_india_eligible is True

    def test_worldwide_with_india_in_title(self):
        r = classify_job_location(
            location_raw="Worldwide Remote",
            title="Software Engineer - India",
        )
        assert r.is_india_eligible is True

    def test_remote_region_india(self):
        r = classify_job_location(
            location_raw="Remote India",
            remote_region="india",
        )
        assert r.is_india_eligible is True
        assert r.remote_region == "india"

    def test_location_decision_fields(self):
        r = classify_job_location(location_raw="Bengaluru, India")
        assert r.location_country == "IN"
        assert r.location_city == "bengaluru"
        assert r.exclusion_reason is None

    def test_exclusion_reason_for_non_india(self):
        r = classify_job_location(location_raw="Berlin, Germany")
        assert r.exclusion_reason is not None
        assert "Berlin" in r.exclusion_reason or "Germany" in r.exclusion_reason or "non_india" in r.exclusion_reason
