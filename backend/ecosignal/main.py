from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import secrets
from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from shapely.geometry import Point, shape

from ecosignal.analysis import assess_modules, module_catalog
from ecosignal.database import Database, configured_cache_ttl
from ecosignal.domain import (
    ECOSYSTEMS,
    NormalizedMeasurement,
    NormalizedOccurrence,
    classify_coverage,
    parse_iso_datetime,
)
from ecosignal.geospatial import (
    bbox_to_geometry,
    geometry_to_query_bboxes,
    normalize_study_geometry,
    transform_geometry_to_wgs84,
    transform_point_to_wgs84,
)
from ecosignal.sources import (
    SOURCES,
    CopernicusSTACCatalog,
    GBIFConnector,
    INaturalistConnector,
    NASAEarthdataCatalog,
    OBISConnector,
    SourceResult,
    public_source_catalog,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await Database.connect_from_env()
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=8.0), headers={
        "User-Agent": "ECOSIGNAL/0.1 (global ecological research platform)",
    })
    yield
    await app.state.http.aclose()
    if app.state.db:
        await app.state.db.close()


app = FastAPI(title="ECOSIGNAL Global Ecosystem Monitor", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


class SearchRequest(BaseModel):
    geometry: dict[str, Any] | None = None
    bbox: list[float] | None = None
    source_crs_epsg: int = Field(default=4326, ge=1, le=999999)
    ecosystems: list[str] = Field(min_length=1, max_length=16)
    sources: list[str] = Field(default_factory=lambda: ["gbif", "obis", "inat"], min_length=1, max_length=5)
    start_date: str | None = None
    end_date: str | None = None
    scientific_name: str | None = Field(default=None, max_length=200)
    limit_per_source: int = Field(default=200, ge=1, le=200)

    @model_validator(mode="after")
    def validate_request(self) -> SearchRequest:
        if (self.geometry is None) == (self.bbox is None):
            raise ValueError("Provide exactly one of geometry or bbox")
        unknown_ecosystems = set(self.ecosystems) - ECOSYSTEMS
        if unknown_ecosystems:
            raise ValueError(f"Unknown ecosystem codes: {', '.join(sorted(unknown_ecosystems))}")
        if len(set(self.ecosystems)) != len(self.ecosystems):
            raise ValueError("Ecosystem codes must be unique")
        if len(set(self.sources)) != len(self.sources):
            raise ValueError("Source identifiers must be unique")
        if self.bbox is not None and self.source_crs_epsg != 4326:
            raise ValueError("Bounding boxes are WGS84; source_crs_epsg applies to GeoJSON geometry")
        if self.bbox is not None:
            try:
                bbox_to_geometry(self.bbox)
            except (TypeError, ValueError) as error:
                raise ValueError(str(error)) from error
        unsupported = set(self.sources) - {"gbif", "obis", "inat"}
        if unsupported:
            raise ValueError("Occurrence search sources must be GBIF, OBIS, or iNaturalist")
        for value in (self.start_date, self.end_date):
            if value and parse_iso_datetime(value)[0] is None:
                raise ValueError("Dates must be ISO dates or timestamps")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be earlier than end_date")
        return self


class StudyAreaRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    geometry: dict[str, Any]
    source_crs_epsg: int = Field(default=4326, ge=1, le=999999)
    ecosystems: list[str] = Field(min_length=1, max_length=16)


class AnalysisAssessmentRequest(BaseModel):
    ecosystems: list[str] = Field(min_length=1)
    taxonomic_group: str = "species"
    sample_count: int = Field(ge=0)
    available_data: set[str] = Field(default_factory=set)
    time_span_years: float = Field(ge=0)
    temporal_bins: int = Field(ge=0)
    quality_score: float = Field(ge=0, le=1)
    comparable_sampling: bool = False


class DatasetImportRequest(BaseModel):
    dataset_name: str = Field(min_length=1, max_length=200)
    dataset_type: Literal["occurrence", "environmental"] = "occurrence"
    source_crs_epsg: int = Field(default=4326, ge=1, le=999999)
    license_id: str = Field(min_length=1, max_length=100)
    source_url: str | None = Field(default=None, max_length=1000)
    fields: dict[str, str] = Field(default_factory=dict)
    feature_collection: dict[str, Any]


class ReferenceLayerImportRequest(BaseModel):
    layer_type: Literal["administrative_boundaries", "ecosystem_mask"]
    source: str = Field(min_length=2, max_length=120)
    source_version: str = Field(min_length=1, max_length=120)
    source_crs_epsg: int = Field(default=4326, ge=1, le=999999)
    license_id: str = Field(min_length=1, max_length=120)
    feature_collection: dict[str, Any]
    ecosystem_code: str | None = None


class CatalogSearchRequest(BaseModel):
    geometry: dict[str, Any] | None = None
    bbox: list[float] | None = None
    source_crs_epsg: int = Field(default=4326, ge=1, le=999999)
    start_date: str | None = None
    end_date: str | None = None

    @model_validator(mode="after")
    def validate_area(self) -> CatalogSearchRequest:
        if (self.geometry is None) == (self.bbox is None):
            raise ValueError("Provide exactly one of geometry or bbox")
        if self.bbox is not None and self.source_crs_epsg != 4326:
            raise ValueError("Bounding boxes are WGS84; source_crs_epsg applies to GeoJSON geometry")
        if self.bbox is not None:
            try:
                bbox_to_geometry(self.bbox)
            except (TypeError, ValueError) as error:
                raise ValueError(str(error)) from error
        return self


def _normalized_geometry(request: SearchRequest | CatalogSearchRequest | StudyAreaRequest) -> dict[str, Any]:
    try:
        if getattr(request, "geometry", None) is not None:
            transformed = transform_geometry_to_wgs84(request.geometry, request.source_crs_epsg)
            return normalize_study_geometry(transformed)
        return normalize_study_geometry(bbox_to_geometry(request.bbox))
    except (ValueError, TypeError, IndexError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _connector(source_id: str, client: httpx.AsyncClient):
    return {
        "gbif": GBIFConnector(client), "obis": OBISConnector(client), "inat": INaturalistConnector(client),
    }[source_id]


def _record_is_inside(record: NormalizedOccurrence, geometry: dict[str, Any]) -> bool:
    if record.longitude is None or record.latitude is None:
        return False
    if not (-180 <= record.longitude <= 180 and -90 <= record.latitude <= 90):
        return False
    return shape(geometry).covers(Point(record.longitude, record.latitude))


def _record_summary(record: NormalizedOccurrence) -> dict[str, Any]:
    return {
        "source_id": record.source_id,
        "source_record_id": record.source_record_id,
        "scientific_name": record.scientific_name,
        "taxon_identifier_scheme": record.taxon_identifier_scheme,
        "taxon_identifier_value": record.source_taxon_id,
        "observed_at": record.observed_at_utc.isoformat() if record.observed_at_utc else None,
        "date_precision": record.date_precision,
        "license_id": record.license_id,
        "basis_of_record": record.basis_of_record,
        "coordinate_uncertainty_m": record.coordinate_uncertainty_m,
        "source_url": record.source_url,
    }


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _feature_coordinates(feature: dict[str, Any], properties: dict[str, Any], fields: dict[str, str],
                         source_crs_epsg: int = 4326) -> tuple[float | None, float | None]:
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") if geometry.get("type") == "Point" else None
    if coordinates and len(coordinates) >= 2:
        longitude, latitude = _finite_number(coordinates[0]), _finite_number(coordinates[1])
    else:
        longitude = _finite_number(properties.get(fields.get("longitude", "longitude")))
        latitude = _finite_number(properties.get(fields.get("latitude", "latitude")))
    if longitude is not None and latitude is not None:
        longitude, latitude = transform_point_to_wgs84(longitude, latitude, source_crs_epsg)
    if longitude is not None and not (-180 <= longitude <= 180 and latitude is not None and -90 <= latitude <= 90):
        raise ValueError("Coordinates must use WGS84 longitude [-180, 180] and latitude [-90, 90]")
    if (longitude is None) != (latitude is None):
        raise ValueError("Longitude and latitude must both be provided")
    return longitude, latitude


async def _search_occurrences(app: FastAPI, request: SearchRequest) -> dict[str, Any]:
    geometry = _normalized_geometry(request)
    boxes = geometry_to_query_bboxes(geometry)
    key_payload = request.model_dump(mode="json") | {"normalized_geometry": geometry}
    cache_key = hashlib.sha256(json.dumps(key_payload, sort_keys=True).encode()).hexdigest()
    db: Database | None = app.state.db
    if db and configured_cache_ttl() > 0:
        cached = await db.cache_get(cache_key)
        if cached is not None:
            cached["cached"] = True
            return cached

    tasks = []
    for source_id in request.sources:
        connector = _connector(source_id, app.state.http)
        for bbox in boxes:
            tasks.append(connector.search(bbox, request.start_date, request.end_date,
                                          request.scientific_name, request.limit_per_source))
    results: list[SourceResult] = await asyncio.gather(*tasks)
    records_by_key: dict[tuple[str, str], NormalizedOccurrence] = {}
    source_records: dict[str, list[NormalizedOccurrence]] = {source: [] for source in request.sources}
    source_totals: dict[str, int] = {source: 0 for source in request.sources}
    source_errors: dict[str, str] = {}
    for result in results:
        source_totals[result.source_id] += result.total_available if result.total_available is not None else len(result.records)
        if not result.ok:
            source_errors[result.source_id] = result.error or "Source request failed"
        for record in result.records:
            if _record_is_inside(record, geometry):
                records_by_key[(record.source_id, record.source_record_id)] = record
    for record in records_by_key.values():
        source_records.setdefault(record.source_id, []).append(record)

    all_records = list(records_by_key.values())
    if db:
        await db.store_occurrences(all_records)
        ecosystem_filter_applied, filtered_records = await db.filter_by_ecosystem_masks(
            geometry, request.ecosystems, all_records,
        )
    else:
        ecosystem_filter_applied, filtered_records = False, all_records
    all_records = filtered_records
    source_records = {source: [] for source in request.sources}
    for record in all_records:
        source_records.setdefault(record.source_id, []).append(record)

    usable_count = len(all_records)
    threshold = max(1, int(os.getenv("COVERAGE_REVIEW_THRESHOLD", "30")))
    successful_sources = len(request.sources) - len(source_errors)
    coverage_status = classify_coverage(usable_count, successful_sources, len(request.sources), threshold)

    caveats = [
        "Coverage status reflects records returned by this explicit search, not ecological stability or population abundance.",
        f"The threshold of {threshold} georeferenced records is an operational screening threshold, not a scientific sample-size guarantee.",
        "Ecosystem categories are search context unless a versioned mask layer covers the entire study area; only then are records filtered by that mask.",
    ]
    source_results = {}
    for source_id in request.sources:
        info = SOURCES[source_id]
        source_results[source_id] = {
            "name": info.name, "ok": source_id not in source_errors,
            "retrieved_records": len(source_records.get(source_id, [])),
            "source_reported_count": source_totals[source_id],
            "error": source_errors.get(source_id), "license_note": info.license_note,
            "coverage_note": info.coverage_note,
        }
    response = {
        "coverage": {
            "status": coverage_status,
            "label": {
                "sufficient": "Datos suficientes para revisión inicial",
                "limited": "Datos limitados o consulta parcial",
                "no_usable_data": "Sin datos usables en las fuentes consultadas",
                "source_unavailable": "Fuentes no disponibles; cobertura desconocida",
            }[coverage_status],
            "retrieved_records": usable_count,
            "screening_threshold": threshold,
            "is_ecological_stability": False,
            "ecosystem_filter_applied": ecosystem_filter_applied,
        },
        "ecosystems": request.ecosystems,
        "sources": source_results,
        "records": [_record_summary(record) for record in all_records],
        "caveats": caveats,
        "cached": False,
    }
    if db:
        assessment_id = await db.save_assessment(
            geometry=geometry, ecosystems=request.ecosystems, source_ids=request.sources,
            source_results=source_results, total_records=sum(source_totals.values()),
            usable_records=usable_count, status=coverage_status, threshold=threshold,
            caveats=caveats, source_crs_epsg=request.source_crs_epsg,
        )
        response["assessment_id"] = assessment_id
        ttl = configured_cache_ttl()
        if ttl > 0:
            await db.cache_put(cache_key, ",".join(request.sources), response, ttl)
    return response


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("frontend/index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "postgis_configured": app.state.db is not None,
            "data_coverage": "not_assumed", "message": "No-data areas are not interpreted as stable."}


@app.get("/api/sources")
async def sources() -> list[dict[str, str]]:
    return public_source_catalog()


@app.get("/api/ecosystems")
async def ecosystems() -> list[dict[str, str]]:
    labels = {
        "marine": "Marine", "coastal": "Coastal", "freshwater": "Freshwater", "wetland": "Wetland",
        "tropical_forest": "Tropical forest", "temperate_forest": "Temperate forest",
        "boreal_forest": "Boreal forest", "grassland": "Grassland", "savanna": "Savanna",
        "desert": "Desert", "tundra": "Tundra", "polar": "Polar", "mountain": "Mountain",
        "urban": "Urban", "agricultural": "Agricultural", "transitional_mixed": "Transitional and mixed",
    }
    return [{"code": code, "label": label} for code, label in labels.items()]


@app.get("/api/analysis/modules")
async def analysis_modules() -> list[dict[str, Any]]:
    return module_catalog()


@app.get("/api/areas/search")
async def search_areas(q: str = Query(min_length=2, max_length=120)) -> dict[str, Any]:
    if not app.state.db:
        return {"boundaries": [], "available": False,
                "message": "No hay límites administrativos importados; no se usan fronteras inventadas."}
    boundaries = await app.state.db.search_boundaries(q)
    return {"boundaries": boundaries, "available": True,
            "message": "Resultados con fuente y versión del límite administrativo."}


@app.get("/api/case-studies")
async def case_studies() -> dict[str, Any]:
    if not app.state.db:
        return {"case_studies": [], "available": False,
                "message": "Los perfiles de caso se cargan junto con el esquema PostGIS."}
    return {"case_studies": await app.state.db.list_case_studies(), "available": True}


@app.post("/api/study-areas")
async def create_study_area(request: StudyAreaRequest) -> dict[str, Any]:
    unknown = set(request.ecosystems) - ECOSYSTEMS
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown ecosystems: {', '.join(sorted(unknown))}")
    if not app.state.db:
        raise HTTPException(status_code=503, detail="PostGIS is required to save study areas")
    geometry = _normalized_geometry(request)
    area_id = await app.state.db.create_study_area(
        name=request.name, geometry=geometry, ecosystems=request.ecosystems,
        source_crs_epsg=request.source_crs_epsg,
    )
    return {"area_id": area_id, "name": request.name, "geometry": geometry,
            "ecosystems": request.ecosystems, "privacy": "not publicly listed"}


@app.post("/api/ecology/search")
async def search_ecology(request: SearchRequest) -> dict[str, Any]:
    return await _search_occurrences(app, request)


@app.post("/api/environment/search")
async def search_environment(request: CatalogSearchRequest) -> dict[str, Any]:
    geometry = _normalized_geometry(request)
    boxes = geometry_to_query_bboxes(geometry)
    results = []
    for source_id in ("nasa_cmr", "copernicus_stac"):
        connector = NASAEarthdataCatalog(app.state.http) if source_id == "nasa_cmr" else CopernicusSTACCatalog(app.state.http)
        calls = [connector.search(bbox, request.start_date, request.end_date) for bbox in boxes]
        responses = await asyncio.gather(*calls)
        items = [item for result in responses for item in result.catalog_items]
        errors = [result.error for result in responses if not result.ok]
        results.append({
            "source_id": source_id, "name": SOURCES[source_id].name,
            "ok": not errors, "catalog_items": items,
            "error": "; ".join(filter(None, errors)) or None,
            "coverage_note": SOURCES[source_id].coverage_note,
            "access_note": SOURCES[source_id].access_note,
            "license_note": SOURCES[source_id].license_note,
            "interpretation": "Catalog metadata only; this is not evidence that a validated environmental layer is available.",
        })
    return {"catalogs": results, "is_environmental_measurement": False}


@app.post("/api/analysis/assessment")
async def assess_analysis(request: AnalysisAssessmentRequest) -> dict[str, Any]:
    unknown = set(request.ecosystems) - ECOSYSTEMS
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown ecosystems: {', '.join(sorted(unknown))}")
    assessments = assess_modules(
        ecosystems=request.ecosystems, taxonomic_group=request.taxonomic_group,
        sample_count=request.sample_count, available_data=request.available_data,
        time_span_years=request.time_span_years, temporal_bins=request.temporal_bins,
        quality_score=request.quality_score, comparable_sampling=request.comparable_sampling,
    )
    return {"assessments": assessments,
            "note": "An eligible module is a candidate for expert review, not a computed ecological signal."}


@app.post("/api/datasets/import")
async def import_dataset(
    request: DatasetImportRequest,
    x_import_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_import_token(x_import_token)
    if not app.state.db:
        raise HTTPException(status_code=503, detail="PostGIS is required to import scientific datasets")
    collection = request.feature_collection
    if collection.get("type") != "FeatureCollection" or not isinstance(collection.get("features"), list):
        raise HTTPException(status_code=422, detail="Expected a GeoJSON FeatureCollection")
    features = collection["features"]
    if not features or len(features) > 50000:
        raise HTTPException(status_code=413, detail="Import must contain between 1 and 50000 features")
    source_id = f"upload:{uuid4()}"
    await app.state.db.register_user_source(source_id, request.dataset_name, {
        "source_url": request.source_url, "license_id": request.license_id,
        "field_mapping": request.fields, "source_crs_epsg": request.source_crs_epsg,
        "original_collection_metadata": collection.get("metadata", {}),
    })
    if request.dataset_type == "environmental":
        measurements = []
        for index, feature in enumerate(features):
            properties = feature.get("properties") or {}
            fields = request.fields
            variable_code = properties.get(fields.get("variable_code", "variableCode"))
            unit = properties.get(fields.get("unit", "unit"))
            value = _finite_number(properties.get(fields.get("value", "value")))
            if not variable_code or not unit or value is None:
                raise HTTPException(status_code=422, detail=f"Feature {index} needs variable code, finite value, and unit")
            try:
                longitude, latitude = _feature_coordinates(feature, properties, fields, request.source_crs_epsg)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=f"Feature {index}: {error}") from error
            event_date = properties.get(fields.get("event_date", "eventDate"))
            measured_at, precision, zone = parse_iso_datetime(str(event_date)) if event_date else (None, "unknown", None)
            coordinate_uncertainty = _finite_number(properties.get(fields.get("coordinate_uncertainty_m", "coordinateUncertaintyInMeters")))
            measurement_uncertainty = _finite_number(properties.get(fields.get("measurement_uncertainty", "measurementUncertainty")))
            if any(value is not None and value < 0 for value in (coordinate_uncertainty, measurement_uncertainty)):
                raise HTTPException(status_code=422, detail=f"Feature {index} has negative uncertainty")
            record_id = properties.get(fields.get("record_id", "id")) or feature.get("id") or str(index)
            effort = properties.get(fields.get("sampling_effort", "samplingEffort")) or {}
            measurements.append(NormalizedMeasurement(
                source_id=source_id, source_record_id=str(record_id), variable_code=str(variable_code),
                value=value, unit=str(unit), measured_at=measured_at,
                original_event_date=str(event_date) if event_date else None,
                date_precision=precision, original_timezone=zone, longitude=longitude, latitude=latitude,
                coordinate_uncertainty_m=coordinate_uncertainty, measurement_uncertainty=measurement_uncertainty,
                sampling_effort=effort if isinstance(effort, dict) else {"original": effort},
                license_id=request.license_id, source_metadata={
                    "dataset_name": request.dataset_name, "field_mapping": fields,
                    "source_crs_epsg": request.source_crs_epsg,
                },
                original_record=feature,
            ))
        saved = await app.state.db.store_measurements(measurements)
        return {"source_id": source_id, "dataset_type": request.dataset_type,
                "records_received": len(features), "records_saved": saved,
                "license_id": request.license_id, "original_records_retained": True}
    records = []
    for index, feature in enumerate(features):
        properties = feature.get("properties") or {}
        try:
            longitude, latitude = _feature_coordinates(feature, properties, request.fields, request.source_crs_epsg)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"Feature {index}: {error}") from error
        fields = request.fields
        event_date = properties.get(fields.get("event_date", "eventDate"))
        observed_at, precision, zone = parse_iso_datetime(str(event_date)) if event_date else (None, "unknown", None)
        taxon_id = properties.get(fields.get("taxon_id", "taxon_id"))
        scientific_name = properties.get(fields.get("scientific_name", "scientificName"))
        uncertainty = properties.get(fields.get("coordinate_uncertainty_m", "coordinateUncertaintyInMeters"))
        uncertainty = _finite_number(uncertainty)
        if uncertainty is not None and uncertainty < 0:
            raise HTTPException(status_code=422, detail=f"Feature {index} has negative coordinate uncertainty")
        record_id = properties.get(fields.get("record_id", "id")) or feature.get("id") or str(index)
        records.append(NormalizedOccurrence(
            source_id=source_id, source_record_id=str(record_id), source_taxon_id=str(taxon_id) if taxon_id else None,
            taxon_identifier_scheme=fields.get("taxon_identifier_scheme", "userProvided") if taxon_id else None,
            scientific_name=str(scientific_name) if scientific_name else None,
            longitude=longitude, latitude=latitude, coordinate_uncertainty_m=uncertainty,
            observed_at=observed_at, original_event_date=str(event_date) if event_date else None,
            date_precision=precision, original_timezone=zone, license_id=request.license_id,
            basis_of_record=str(properties.get(fields.get("basis_of_record", "basisOfRecord"))) if properties.get(fields.get("basis_of_record", "basisOfRecord")) else None,
            source_url=request.source_url, source_metadata={
                "dataset_name": request.dataset_name, "field_mapping": fields,
                "source_crs_epsg": request.source_crs_epsg,
            },
            original_record=feature,
        ))
    saved = await app.state.db.store_occurrences(records)
    return {"source_id": source_id, "records_received": len(features), "records_saved": saved,
            "license_id": request.license_id, "original_records_retained": True,
            "message": "Imported records are not automatically taxonomically harmonized or analyzed."}


@app.post("/api/reference-layers/import")
async def import_reference_layer(
    request: ReferenceLayerImportRequest,
    x_import_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_import_token(x_import_token)
    if not app.state.db:
        raise HTTPException(status_code=503, detail="PostGIS is required to import reference layers")
    collection = request.feature_collection
    features = collection.get("features") if collection.get("type") == "FeatureCollection" else None
    if not isinstance(features, list) or not features or len(features) > 50000:
        raise HTTPException(status_code=422, detail="Expected a FeatureCollection with 1 to 50000 features")
    normalized = []
    for index, feature in enumerate(features):
        try:
            feature = dict(feature)
            transformed = transform_geometry_to_wgs84(feature.get("geometry") or {}, request.source_crs_epsg)
            feature["geometry"] = normalize_study_geometry(transformed)
            normalized.append(feature)
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=422, detail=f"Feature {index}: {error}") from error
    try:
        if request.layer_type == "administrative_boundaries":
            imported = await app.state.db.import_boundaries(
                source=request.source, version=request.source_version,
                license_id=request.license_id, features=normalized,
                source_crs_epsg=request.source_crs_epsg,
            )
        else:
            if request.ecosystem_code not in ECOSYSTEMS:
                raise HTTPException(status_code=422, detail="A valid ecosystem_code is required for ecosystem masks")
            source_id = f"layer:{request.source}:{request.source_version}"[:120]
            await app.state.db.register_layer_source(source_id, request.source, {
                "version": request.source_version, "license_id": request.license_id,
                "source_crs_epsg": request.source_crs_epsg,
            })
            imported = await app.state.db.import_ecosystem_masks(
                source_id=source_id, ecosystem_code=request.ecosystem_code,
                version=request.source_version, features=normalized,
                source_crs_epsg=request.source_crs_epsg,
            )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"layer_type": request.layer_type, "source": request.source,
            "source_version": request.source_version, "license_id": request.license_id,
            "features_imported": imported}


def _require_import_token(token: str | None) -> None:
    configured_token = os.getenv("DATASET_IMPORT_TOKEN")
    if not configured_token:
        raise HTTPException(status_code=503, detail="Dataset imports are disabled until DATASET_IMPORT_TOKEN is configured")
    if not token or not secrets.compare_digest(token, configured_token):
        raise HTTPException(status_code=401, detail="Invalid import token")


@app.post("/api/ingestion/jobs", status_code=202)
async def enqueue_ingestion(request: SearchRequest) -> dict[str, Any]:
    if not app.state.db:
        raise HTTPException(status_code=503, detail="PostGIS is required for durable ingestion jobs")
    job_ids = []
    payload = request.model_dump(mode="json")
    for source_id in request.sources:
        job_ids.append(await app.state.db.enqueue_job(source_id, payload | {"sources": [source_id]}))
    return {"jobs": [{"job_id": job_id, "status": "queued"} for job_id in job_ids],
            "message": "Jobs are durable; start the worker service to process them."}


@app.get("/api/ingestion/jobs/{job_id}")
async def ingestion_status(job_id: str) -> dict[str, Any]:
    if not app.state.db:
        raise HTTPException(status_code=503, detail="PostGIS is required for job status")
    try:
        status = await app.state.db.job_status(job_id)
    except Exception as error:
        raise HTTPException(status_code=422, detail="Invalid job identifier") from error
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return status