from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from ecosignal.domain import NormalizedOccurrence, parse_iso_datetime


@dataclass(frozen=True)
class SourceInfo:
    source_id: str
    name: str
    kind: str
    api_url: str
    coverage_note: str
    access_note: str
    license_note: str


SOURCES = {
    "gbif": SourceInfo("gbif", "GBIF", "occurrence", "https://api.gbif.org/v1", "Coverage varies by taxon, dataset, time, and sampling effort; geographic availability must be assessed per query.", "Public occurrence search API; page size is bounded by the service.", "Licenses and dataset metadata are record-specific; preserve the returned license and attribution."),
    "obis": SourceInfo("obis", "OBIS", "occurrence", "https://api.obis.org/v3", "Marine-focused occurrence data; spatial, taxonomic, and temporal gaps remain.", "Public occurrence API; query and export limits are service-controlled.", "Use record/dataset license metadata; do not infer one license for all records."),
    "inat": SourceInfo("inat", "iNaturalist", "occurrence", "https://api.inaturalist.org/v1", "Community observations; taxonomic, regional, and temporal sampling are uneven.", "Public API; rate limits and terms can change. Requests are deliberately bounded.", "Observation-level license and quality grade must be retained; attribution is required by applicable terms."),
    "nasa_cmr": SourceInfo("nasa_cmr", "NASA Earthdata CMR", "environmental_catalog", "https://cmr.earthdata.nasa.gov/search", "Catalog search is broad, but product footprints, dates, resolution, and usable access vary by collection.", "Metadata search is public; many granule downloads require Earthdata Login.", "License and use constraints are product-specific; inspect collection metadata before use."),
    "copernicus_stac": SourceInfo("copernicus_stac", "Copernicus Data Space STAC", "environmental_catalog", "https://catalogue.dataspace.copernicus.eu/stac", "Collection coverage, acquisition dates, resolution, and processing level are product-specific.", "STAC metadata search is public for accessible collections; downloads and services may require authentication.", "Terms are collection/product-specific; check them before redistribution or analysis."),
}


@dataclass
class SourceResult:
    source_id: str
    ok: bool
    total_available: int | None = None
    records: list[NormalizedOccurrence] = field(default_factory=list)
    catalog_items: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    caveats: list[str] = field(default_factory=list)


class OccurrenceConnector(Protocol):
    source_id: str

    async def search(self, bbox: tuple[float, float, float, float], start_date: str | None,
                     end_date: str | None, scientific_name: str | None, limit: int) -> SourceResult: ...


def _record_datetime(value: str | None, year: Any = None) -> tuple[datetime | None, str, str | None]:
    if value:
        return parse_iso_datetime(value)
    if year:
        return parse_iso_datetime(str(year))
    return None, "unknown", None


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _wkt_bbox(bbox: tuple[float, float, float, float]) -> str:
    west, south, east, north = bbox
    return f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"


class GBIFConnector:
    source_id = "gbif"
    endpoint = "https://api.gbif.org/v1/occurrence/search"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search(self, bbox: tuple[float, float, float, float], start_date: str | None,
                     end_date: str | None, scientific_name: str | None, limit: int = 200) -> SourceResult:
        west, south, east, north = bbox
        params: dict[str, Any] = {
            "decimalLatitude": f"{south},{north}", "decimalLongitude": f"{west},{east}",
            "hasCoordinate": "true", "limit": min(max(limit, 1), 300), "offset": 0,
        }
        if start_date:
            params["eventDate"] = f"{start_date},{end_date or '*'}"
        elif end_date:
            params["eventDate"] = f"*,{end_date}"
        if scientific_name:
            params["scientificName"] = scientific_name
        try:
            response = await self.client.get(self.endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
            records = []
            for item in payload.get("results", []):
                longitude = _safe_float(item.get("decimalLongitude"))
                latitude = _safe_float(item.get("decimalLatitude"))
                if longitude is None or latitude is None:
                    continue
                observed_at, precision, zone = _record_datetime(item.get("eventDate"), item.get("year"))
                key = item.get("key")
                records.append(NormalizedOccurrence(
                    source_id=self.source_id,
                    source_record_id=str(key or item.get("occurrenceID") or item.get("gbifID")),
                    source_taxon_id=str(item["taxonKey"]) if item.get("taxonKey") else None,
                    taxon_identifier_scheme="gbifTaxonKey" if item.get("taxonKey") else None,
                    scientific_name=item.get("scientificName"), longitude=longitude, latitude=latitude,
                    coordinate_uncertainty_m=_safe_float(item.get("coordinateUncertaintyInMeters")),
                    observed_at=observed_at, original_event_date=item.get("eventDate"),
                    date_precision=precision, original_timezone=zone, license_id=item.get("license"),
                    basis_of_record=item.get("basisOfRecord"),
                    source_url=f"https://www.gbif.org/occurrence/{key}" if key else None,
                    source_metadata={"datasetKey": item.get("datasetKey"), "institutionCode": item.get("institutionCode"), "collectionCode": item.get("collectionCode")},
                    original_record=item,
                ))
            return SourceResult(self.source_id, True, payload.get("count"), records,
                                caveats=["GBIF result count is not a measure of sampling effort or ecological abundance."])
        except (httpx.HTTPError, ValueError) as error:
            return SourceResult(self.source_id, False, error=str(error))


class OBISConnector:
    source_id = "obis"
    endpoint = "https://api.obis.org/v3/occurrence"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search(self, bbox: tuple[float, float, float, float], start_date: str | None,
                     end_date: str | None, scientific_name: str | None, limit: int = 200) -> SourceResult:
        params: dict[str, Any] = {"geometry": _wkt_bbox(bbox), "size": min(max(limit, 1), 500)}
        if start_date:
            params["startdate"] = start_date
        if end_date:
            params["enddate"] = end_date
        if scientific_name:
            params["scientificname"] = scientific_name
        try:
            response = await self.client.get(self.endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
            items = payload.get("results", [])
            records = []
            for item in items:
                longitude = _safe_float(item.get("decimalLongitude"))
                latitude = _safe_float(item.get("decimalLatitude"))
                if longitude is None or latitude is None:
                    continue
                event_date = item.get("eventDate")
                observed_at, precision, zone = _record_datetime(event_date, item.get("date_year"))
                identifier = item.get("id") or item.get("occurrenceID")
                records.append(NormalizedOccurrence(
                    source_id=self.source_id, source_record_id=str(identifier or f"{item.get('datasetID')}:{len(records)}"),
                    source_taxon_id=str(item["scientificNameID"]) if item.get("scientificNameID") else None,
                    taxon_identifier_scheme="obisScientificNameID" if item.get("scientificNameID") else None,
                    scientific_name=item.get("scientificName"), longitude=longitude, latitude=latitude,
                    coordinate_uncertainty_m=_safe_float(item.get("coordinateUncertaintyInMeters")),
                    observed_at=observed_at, original_event_date=event_date, date_precision=precision,
                    original_timezone=zone, license_id=item.get("license"), basis_of_record=item.get("basisOfRecord"),
                    source_url=item.get("references"),
                    source_metadata={"datasetID": item.get("datasetID"), "institutionCode": item.get("institutionCode")},
                    original_record=item,
                ))
            return SourceResult(self.source_id, True, payload.get("total", len(items)), records,
                                caveats=["OBIS is marine-focused; non-marine records and geographic coverage are not assumed."])
        except (httpx.HTTPError, ValueError) as error:
            return SourceResult(self.source_id, False, error=str(error))


class INaturalistConnector:
    source_id = "inat"
    endpoint = "https://api.inaturalist.org/v1/observations"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search(self, bbox: tuple[float, float, float, float], start_date: str | None,
                     end_date: str | None, scientific_name: str | None, limit: int = 200) -> SourceResult:
        west, south, east, north = bbox
        params: dict[str, Any] = {
            "swlat": south, "swlng": west, "nelat": north, "nelng": east,
            "per_page": min(max(limit, 1), 200), "page": 1,
        }
        if start_date:
            params["d1"] = start_date
        if end_date:
            params["d2"] = end_date
        if scientific_name:
            params["taxon_name"] = scientific_name
        try:
            response = await self.client.get(self.endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
            records = []
            for item in payload.get("results", []):
                location = item.get("location")
                if not location:
                    continue
                try:
                    latitude, longitude = map(float, location.split(",", 1))
                except (TypeError, ValueError):
                    continue
                observed_at, precision, zone = _record_datetime(item.get("observed_on"))
                taxon = item.get("taxon") or {}
                identifier = item.get("id")
                records.append(NormalizedOccurrence(
                    source_id=self.source_id, source_record_id=str(identifier),
                    source_taxon_id=str(taxon["id"]) if taxon.get("id") else None,
                    taxon_identifier_scheme="inatTaxonId" if taxon.get("id") else None,
                    scientific_name=taxon.get("name"), longitude=longitude, latitude=latitude,
                    coordinate_uncertainty_m=_safe_float(item.get("positional_accuracy")),
                    observed_at=observed_at, original_event_date=item.get("observed_on"),
                    date_precision=precision, original_timezone=zone, license_id=item.get("license_code"),
                    basis_of_record="HumanObservation", source_url=item.get("uri"),
                    source_metadata={"quality_grade": item.get("quality_grade"), "taxon_id": taxon.get("id")},
                    original_record=item,
                ))
            return SourceResult(self.source_id, True, payload.get("total_results", len(records)), records,
                                caveats=["Community observations are unevenly sampled; quality grade and license remain record-specific."])
        except (httpx.HTTPError, ValueError) as error:
            return SourceResult(self.source_id, False, error=str(error))


class NASAEarthdataCatalog:
    source_id = "nasa_cmr"
    endpoint = "https://cmr.earthdata.nasa.gov/search/granules.json"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search(self, bbox: tuple[float, float, float, float], start_date: str | None,
                     end_date: str | None, limit: int = 20) -> SourceResult:
        west, south, east, north = bbox
        params: dict[str, Any] = {"bounding_box": f"{west},{south},{east},{north}", "page_size": min(limit, 100)}
        if start_date or end_date:
            params["temporal"] = f"{start_date or ''}T00:00:00Z,{end_date or ''}T23:59:59Z"
        try:
            response = await self.client.get(self.endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
            feed = payload.get("feed", {})
            return SourceResult(self.source_id, True, feed.get("hits"), catalog_items=feed.get("entry", []),
                                caveats=["CMR granule metadata only; product resolution and download authentication are collection-specific."])
        except (httpx.HTTPError, ValueError) as error:
            return SourceResult(self.source_id, False, error=str(error))


class CopernicusSTACCatalog:
    source_id = "copernicus_stac"
    endpoint = "https://catalogue.dataspace.copernicus.eu/stac/search"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search(self, bbox: tuple[float, float, float, float], start_date: str | None,
                     end_date: str | None, limit: int = 20) -> SourceResult:
        temporal = f"{start_date or '..'}/{end_date or '..'}"
        body = {"bbox": list(bbox), "datetime": temporal, "limit": min(limit, 100)}
        try:
            response = await self.client.post(self.endpoint, json=body)
            response.raise_for_status()
            payload = response.json()
            items = payload.get("features", [])
            return SourceResult(self.source_id, True, payload.get("numberMatched", len(items)), catalog_items=items,
                                caveats=["STAC items are discovery metadata, not validated ecological measurements."])
        except (httpx.HTTPError, ValueError) as error:
            return SourceResult(self.source_id, False, error=str(error))


def public_source_catalog() -> list[dict[str, str]]:
    return [info.__dict__ for info in SOURCES.values()]