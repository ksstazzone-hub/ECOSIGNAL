# ECOSIGNAL Architecture

ECOSIGNAL is a global ecological intelligence platform. The core model does not assign a home region; study areas, administrative boundaries, ecosystem masks, and case studies are data. Puerto Madryn is loaded as an optional validation profile only and has no seeded geometry or asserted coverage.

## Runtime

- FastAPI serves the monitor and API; PostgreSQL 16 with PostGIS stores spatial records.
- `api` instances are stateless apart from a bounded connection pool. A durable PostgreSQL queue uses `FOR UPDATE SKIP LOCKED` so multiple worker instances can claim independent ingestion jobs.
- External query responses are cached in PostGIS with a configurable TTL. Connector requests and imports have explicit record/page limits.
- `docker compose up --build` starts the API, database, and worker. PostGIS initializes from `db/schema.sql`; the separately mounted case-study seed adds metadata only. For a fresh schema, use a new database volume or run migrations deliberately; Docker initialization scripts do not rerun on an existing volume.
- Set a long random `DATASET_IMPORT_TOKEN` before enabling scientific-data or reference-layer imports. The Compose database password is for local development only.

## Spatial Model

- Coordinates and GeoJSON requests default to WGS84 / EPSG:4326. Geometry, boundary, and dataset import requests may declare an EPSG code; `pyproj` transforms input into WGS84 and the original EPSG is retained in provenance columns/metadata. Bounding-box APIs are explicitly WGS84.
- PostGIS geometry columns use SRID 4326 and GiST indexes. PostGIS remains available for metric distance/area operations using geography or explicit projected transforms; do not measure planar distances directly in degrees.
- Polygon rings that cross the antimeridian are unwrapped, split at the 180-degree meridian, and normalized into a MultiPolygon before search/storage. Queries split into bounded boxes and returned observations are checked against the exact normalized geometry.
- Administrative boundaries are imported GeoJSON with required provider, version, license, feature ID, and administrative level. The search interface returns only imported boundaries and preserves their source metadata. No country list or boundary is embedded in an analytical algorithm.
- Ecosystem masks are independently versioned polygons. A category selection is only applied to occurrence records if the union of selected masks covers the entire study area; partial or missing masks produce an explicit unclassified result rather than silently dropping records.

## Data Model

`observation` and `environmental_measurement` normalize taxon identifiers, UTC timestamps, original event date/precision/time zone, WGS84 geometry, coordinate and measurement uncertainty, sampling effort, units, license, source metadata, and the complete original record. Taxonomic IDs retain their namespace (GBIF, OBIS, iNaturalist, or uploader); IDs are not equated across providers unless an explicit taxonomy mapping is added. Scientific names are retained as supplied. `taxon_common_name` supports BCP-47 language codes while the scientific taxon concept remains canonical.

Raw coordinates are never returned by the public search response; it returns source IDs, names, dates, licenses, and uncertainty. Study geometries are stored as private by default and are not listed by a public endpoint. Database operators still have access to raw coordinates: production deployments must apply least-privilege database access, storage encryption, retention policies, and authenticated ownership controls appropriate to sensitive-species data.

## Coverage Semantics

Coverage describes only an explicit query, its selected sources, its date filters, and records retrieved inside the requested geometry:

- `sufficient`: at least the configurable operational review threshold was retrieved and all selected sources responded. This is not a scientific sample-size determination.
- `limited`: some records were retrieved below that threshold, or at least one selected source failed.
- `no_usable_data`: all selected sources responded and returned no usable records.
- `source_unavailable`: no selected source responded; spatial coverage is unknown.
- `monitoring`: transient frontend state while a query is running.

No status means ecological stability. Provider-reported bounding-box totals are not treated as exact polygon totals. A catalog entry is discovery metadata, not proof that its product is accessible, sufficiently resolved, or validated for an ecological method.

## Analysis Contract

`backend/ecosignal/analysis.py` defines independently configured marine, coastal, freshwater, forest, grassland/savanna, wetland, polar/mountain, urban, agricultural, and cross-ecosystem modules. Each declares required inputs, methods, minimum records/time bins, caveats, scales, and validation criteria. Suitability considers ecosystem, taxonomic group, available fields, sample count, time span, temporal bins, quality review, and comparable sampling.

The current analysis endpoint returns eligibility for expert review, not ecological findings. It intentionally computes no universal anomaly score. A production method must be implemented and validated against its module-specific criteria before its output can be shown as an ecological signal. Remote-sensing catalog metadata is not ingested as measurements automatically.

## Interfaces

The Global Ecosystem Monitor uses a world map, custom polygon/rectangle drawing, available imported boundary search, multi-ecosystem filters, taxonomic name/date filters, source selectors, actual-query coverage, NASA GIBS visual context layers, environmental catalog discovery, module suitability, background job status, and explicit multi-area query comparison. A comparison shows raw retrieved counts only and warns that effort normalization is required. The initial Puerto Madryn profile prompts for a real boundary; it contains no coordinates or data claims.

## API Endpoints

- `GET /api/health`, `/api/sources`, `/api/ecosystems`, `/api/analysis/modules`, `/api/case-studies`
- `GET /api/areas/search?q=...` searches imported/versioned administrative boundaries only
- `POST /api/ecology/search` performs bounded GBIF/OBIS/iNaturalist occurrence queries
- `POST /api/environment/search` discovers NASA CMR and Copernicus STAC metadata only
- `POST /api/study-areas` saves a private study area; `POST /api/analysis/assessment` checks method suitability
- `POST /api/datasets/import` imports a GeoJSON FeatureCollection as occurrences or environmental measurements
- `POST /api/reference-layers/import` imports administrative boundaries or ecosystem masks
- `POST /api/ingestion/jobs`, `GET /api/ingestion/jobs/{job_id}` enqueue/check durable background jobs

Import endpoints require `X-Import-Token`. Administrative boundary features need a name, stable source ID (`id`, `shapeID`, or `shapeISO`), and polygon. Uploaders remain responsible for verifying that their source, version, CRS, and license are accurate.

## Operational Gaps

The development stack does not bundle global boundary or ecosystem-mask datasets, user identity/authentication, a distributed rate limiter, or validated ecological signal algorithms. Search results and coverage are therefore data-dependent. Production deployment needs an authenticated identity gateway, per-user ownership policies, shared rate limiting/backoff, job monitoring, managed PostGIS backups/replicas, and reviewed data-source license workflows before serving multiple research organizations.