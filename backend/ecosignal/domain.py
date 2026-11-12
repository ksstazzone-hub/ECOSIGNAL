from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

ECOSYSTEMS = {
    "marine", "coastal", "freshwater", "wetland", "tropical_forest", "temperate_forest",
    "boreal_forest", "grassland", "savanna", "desert", "tundra", "polar", "mountain",
    "urban", "agricultural", "transitional_mixed",
}


@dataclass(frozen=True)
class NormalizedOccurrence:
    source_id: str
    source_record_id: str
    source_taxon_id: str | None
    taxon_identifier_scheme: str | None
    scientific_name: str | None
    longitude: float | None
    latitude: float | None
    coordinate_uncertainty_m: float | None
    observed_at: datetime | None
    original_event_date: str | None
    date_precision: str
    original_timezone: str | None
    license_id: str | None
    basis_of_record: str | None
    source_url: str | None
    source_metadata: dict[str, Any] = field(default_factory=dict)
    sampling_effort: dict[str, Any] = field(default_factory=dict)
    original_record: dict[str, Any] = field(default_factory=dict)

    @property
    def observed_at_utc(self) -> datetime | None:
        if self.observed_at is None:
            return None
        if self.observed_at.tzinfo is None:
            return self.observed_at.replace(tzinfo=UTC)
        return self.observed_at.astimezone(UTC)


@dataclass(frozen=True)
class NormalizedMeasurement:
    source_id: str
    source_record_id: str
    variable_code: str
    value: float
    unit: str
    measured_at: datetime | None
    original_event_date: str | None
    date_precision: str
    original_timezone: str | None
    longitude: float | None
    latitude: float | None
    coordinate_uncertainty_m: float | None
    measurement_uncertainty: float | None
    sampling_effort: dict[str, Any] = field(default_factory=dict)
    license_id: str | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)
    original_record: dict[str, Any] = field(default_factory=dict)

    @property
    def measured_at_utc(self) -> datetime | None:
        if self.measured_at is None:
            return None
        if self.measured_at.tzinfo is None:
            return self.measured_at.replace(tzinfo=UTC)
        return self.measured_at.astimezone(UTC)


def parse_iso_datetime(value: str | None) -> tuple[datetime | None, str, str | None]:
    if not value:
        return None, "unknown", None
    original = value.strip()
    precision = "day"
    if len(original) == 4:
        precision = "year"
        parsed = datetime.fromisoformat(f"{original}-01-01")
    elif len(original) == 7:
        precision = "month"
        parsed = datetime.fromisoformat(f"{original}-01")
    else:
        try:
            parsed = datetime.fromisoformat(original)
            if "T" in original:
                precision = "second" if len(original.split("T", 1)[1]) >= 8 else "minute"
        except ValueError:
            return None, "unknown", None
    original_timezone = parsed.tzinfo.tzname(parsed) if parsed.tzinfo else None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC), precision, original_timezone


def classify_coverage(retrieved_records: int, successful_sources: int,
                      selected_sources: int, threshold: int) -> str:
    if selected_sources <= 0 or successful_sources <= 0:
        return "source_unavailable"
    if successful_sources < selected_sources:
        return "limited"
    if retrieved_records <= 0:
        return "no_usable_data"
    if retrieved_records < max(1, threshold):
        return "limited"
    return "sufficient"