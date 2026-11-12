import pytest
from ecosignal.main import SearchRequest
from pydantic import ValidationError


def test_search_accepts_multiple_ecosystems_and_global_bbox():
    request = SearchRequest(
        bbox=[170, -20, -170, 20], ecosystems=["marine", "coastal"],
        sources=["gbif", "obis"],
    )

    assert request.ecosystems == ["marine", "coastal"]


def test_search_rejects_unknown_geographic_or_ecosystem_assumptions():
    with pytest.raises(ValidationError):
        SearchRequest(bbox=[-200, -10, 10, 10], ecosystems=["marine"])
    with pytest.raises(ValidationError):
        SearchRequest(bbox=[-10, -10, 10, 10], ecosystems=["patagonia"])


def test_search_requires_an_explicit_area():
    with pytest.raises(ValidationError):
        SearchRequest(ecosystems=["marine"])