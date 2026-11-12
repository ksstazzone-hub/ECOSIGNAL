from __future__ import annotations

import json
import os
from typing import Any

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ecosignal.domain import NormalizedMeasurement, NormalizedOccurrence


class Database:
    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    @classmethod
    async def connect_from_env(cls) -> Database | None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            return None
        pool = AsyncConnectionPool(dsn, min_size=1, max_size=int(os.getenv("DB_POOL_SIZE", "10")), open=False)
        await pool.open()
        await pool.wait()
        return cls(pool)

    async def close(self) -> None:
        await self.pool.close()

    async def cache_get(self, cache_key: str) -> dict[str, Any] | None:
        async with self.pool.connection() as conn:
            row = await (await conn.execute(
                "SELECT response FROM api_cache WHERE cache_key = %s AND expires_at > now()",
                (cache_key,),
            )).fetchone()
        return row[0] if row else None

    async def cache_put(self, cache_key: str, source_id: str, response: dict[str, Any], ttl_seconds: int) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                """INSERT INTO api_cache (cache_key, source_id, response, expires_at)
                   VALUES (%s, %s, %s, now() + (%s * interval '1 second'))
                   ON CONFLICT (cache_key) DO UPDATE SET response = EXCLUDED.response,
                   source_id = EXCLUDED.source_id, expires_at = EXCLUDED.expires_at""",
                (cache_key, source_id, Jsonb(response), ttl_seconds),
            )

    async def store_occurrences(self, occurrences: list[NormalizedOccurrence]) -> int:
        if not occurrences:
            return 0
        async with self.pool.connection() as conn, conn.transaction():
            for item in occurrences:
                await conn.execute(
                    """INSERT INTO observation (
                        source_id, source_record_id, taxon_identifier_scheme, taxon_identifier_value,
                        scientific_name, observed_at, original_event_date, date_precision,
                        original_timezone, location, coordinate_uncertainty_m, sampling_effort,
                        basis_of_record, license_id, source_url, source_metadata, original_record
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        CASE WHEN %s IS NULL OR %s IS NULL THEN NULL
                             ELSE ST_SetSRID(ST_MakePoint(%s, %s), 4326) END,
                        %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT (source_id, source_record_id) DO NOTHING""",
                    (
                        item.source_id, item.source_record_id, item.taxon_identifier_scheme,
                        item.source_taxon_id, item.scientific_name, item.observed_at_utc,
                        item.original_event_date, item.date_precision, item.original_timezone,
                        item.longitude, item.latitude, item.longitude, item.latitude,
                        item.coordinate_uncertainty_m, Jsonb(item.sampling_effort),
                        item.basis_of_record, item.license_id, item.source_url,
                        Jsonb(item.source_metadata), Jsonb(item.original_record),
                    ),
                )
        return len(occurrences)

    async def store_measurements(self, measurements: list[NormalizedMeasurement]) -> int:
        if not measurements:
            return 0
        async with self.pool.connection() as conn, conn.transaction():
            for item in measurements:
                await conn.execute(
                    """INSERT INTO environmental_measurement (
                            source_id, source_record_id, variable_code, value, unit, measured_at,
                            original_event_date, date_precision, original_timezone, location,
                            coordinate_uncertainty_m, measurement_uncertainty, sampling_effort,
                            license_id, source_metadata, original_record
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            CASE WHEN %s IS NULL OR %s IS NULL THEN NULL
                                 ELSE ST_SetSRID(ST_MakePoint(%s, %s), 4326) END,
                            %s, %s, %s, %s, %s, %s
                        ) ON CONFLICT (source_id, source_record_id, variable_code) DO NOTHING""",
                    (
                        item.source_id, item.source_record_id, item.variable_code, item.value,
                        item.unit, item.measured_at_utc, item.original_event_date,
                        item.date_precision, item.original_timezone, item.longitude, item.latitude,
                        item.longitude, item.latitude, item.coordinate_uncertainty_m,
                        item.measurement_uncertainty, Jsonb(item.sampling_effort), item.license_id,
                        Jsonb(item.source_metadata), Jsonb(item.original_record),
                    ),
                )
        return len(measurements)

    async def filter_by_ecosystem_masks(
        self, geometry: dict[str, Any], ecosystems: list[str], occurrences: list[NormalizedOccurrence]
    ) -> tuple[bool, list[NormalizedOccurrence]]:
        if not ecosystems:
            return False, occurrences
        geojson = json.dumps(geometry)
        async with self.pool.connection() as conn:
            row = await (await conn.execute(
                """WITH study AS (
                     SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) AS geom
                   ), masks AS (
                     SELECT ST_UnaryUnion(ST_Collect(m.geometry)) AS geom
                     FROM ecosystem_mask m, study s
                     WHERE m.ecosystem_code = ANY(%s) AND ST_Intersects(m.geometry, s.geom)
                   )
                   SELECT COALESCE(ST_CoveredBy(study.geom, masks.geom), false)
                   FROM study CROSS JOIN masks""",
                (geojson, ecosystems),
            )).fetchone()
            if not row or not row[0]:
                return False, occurrences
            located = [item for item in occurrences if item.longitude is not None and item.latitude is not None]
            if not located:
                return True, []
            longitudes = [item.longitude for item in located]
            latitudes = [item.latitude for item in located]
            matched_rows = await (await conn.execute(
                """SELECT points.ordinality
                   FROM unnest(%s::double precision[], %s::double precision[])
                        WITH ORDINALITY AS points(longitude, latitude, ordinality)
                   WHERE EXISTS (
                     SELECT 1 FROM ecosystem_mask m
                     WHERE m.ecosystem_code = ANY(%s)
                       AND ST_Covers(m.geometry, ST_SetSRID(ST_MakePoint(points.longitude, points.latitude), 4326))
                   )""",
                (longitudes, latitudes, ecosystems),
            )).fetchall()
        matching = {row[0] for row in matched_rows}
        return True, [item for index, item in enumerate(located, start=1) if index in matching]

    async def save_assessment(self, *, geometry: dict[str, Any], ecosystems: list[str],
                              source_ids: list[str], source_results: dict[str, Any],
                              total_records: int, usable_records: int, status: str,
                              threshold: int, caveats: list[str], source_crs_epsg: int = 4326) -> str:
        geojson = json.dumps(geometry)
        async with self.pool.connection() as conn:
            row = await (await conn.execute(
                """INSERT INTO coverage_assessment
                   (geometry, ecosystem_codes, source_crs_epsg, source_ids, source_results, total_records,
                    usable_records, status, status_threshold, caveats)
                   VALUES (ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), %s, %s, %s, %s,
                       %s, %s, %s, %s, %s)
                   RETURNING assessment_id::text""",
                (geojson, ecosystems, source_crs_epsg, source_ids, Jsonb(source_results), total_records,
                 usable_records, status, threshold, caveats),
            )).fetchone()
        return row[0]

    async def create_study_area(self, *, name: str, geometry: dict[str, Any],
                                ecosystems: list[str], source_crs_epsg: int = 4326,
                                is_public: bool = False) -> str:
        async with self.pool.connection() as conn:
            row = await (await conn.execute(
                     """INSERT INTO study_area (name, geometry, ecosystem_codes, source_crs_epsg, is_public)
                         VALUES (%s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), %s, %s, %s)
                   RETURNING area_id::text""",
                     (name, json.dumps(geometry), ecosystems, source_crs_epsg, is_public),
            )).fetchone()
        return row[0]

    async def search_boundaries(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            rows = await (await conn.execute(
                """SELECT boundary_id::text, name, name_localized, country_code, admin_level,
                          boundary_source, source_version, source_license,
                          ST_AsGeoJSON(ST_Transform(ST_SimplifyPreserveTopology(
                              ST_Transform(geometry, 3857), 750), 4326)) AS geometry
                   FROM administrative_boundary
                   WHERE name % %s OR name ILIKE %s
                   ORDER BY similarity(name, %s) DESC
                   LIMIT %s""",
                (query, f"%{query}%", query, min(max(limit, 1), 20)),
            )).fetchall()
        result = []
        for row in rows:
            result.append({
                "boundary_id": row[0], "name": row[1], "name_localized": row[2],
                "country_code": row[3], "admin_level": row[4], "source": row[5],
                "source_version": row[6], "license": row[7], "geometry": json.loads(row[8]),
            })
        return result

    async def list_case_studies(self) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            rows = await (await conn.execute(
                """SELECT profile_id, display_name, ecosystem_codes, study_area_id::text,
                          status, description
                   FROM case_study_profile ORDER BY created_at"""
            )).fetchall()
        return [dict(zip(("profile_id", "display_name", "ecosystems", "study_area_id", "status", "description"), row)) for row in rows]

    async def register_user_source(self, source_id: str, name: str, metadata: dict[str, Any]) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                """INSERT INTO data_source (source_id, display_name, source_type, base_url, access_notes, metadata)
                   VALUES (%s, %s, 'user', 'local://upload', 'User supplied source; license and provenance provided by uploader.', %s)
                   ON CONFLICT (source_id) DO UPDATE SET metadata = data_source.metadata || EXCLUDED.metadata""",
                (source_id, name, Jsonb(metadata)),
            )

    async def register_layer_source(self, source_id: str, name: str, metadata: dict[str, Any]) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                """INSERT INTO data_source (source_id, display_name, source_type, base_url, access_notes, metadata)
                   VALUES (%s, %s, 'reference_layer', 'user-supplied', 'Reference layer; source, version, and license supplied by importer.', %s)
                   ON CONFLICT (source_id) DO UPDATE SET metadata = data_source.metadata || EXCLUDED.metadata""",
                (source_id, name, Jsonb(metadata)),
            )

    async def import_boundaries(self, *, source: str, version: str, license_id: str,
                                features: list[dict[str, Any]], source_crs_epsg: int = 4326) -> int:
        async with self.pool.connection() as conn, conn.transaction():
            for feature in features:
                props = feature.get("properties") or {}
                name = props.get("name") or props.get("shapeName") or props.get("NAME")
                source_key = props.get("id") or props.get("shapeID") or props.get("shapeISO")
                geometry = feature.get("geometry")
                if not name or not source_key or not geometry:
                    raise ValueError("Every boundary feature needs name, id, and polygon geometry")
                await conn.execute(
                    """INSERT INTO administrative_boundary
                       (boundary_source, source_version, source_boundary_id, name, name_localized,
                        country_code, admin_level, geometry, source_license, source_crs_epsg)
                       VALUES (%s, %s, %s, %s, %s, %s, %s,
                           ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), %s, %s)
                       ON CONFLICT (boundary_source, source_version, source_boundary_id, admin_level)
                       DO UPDATE SET name = EXCLUDED.name, name_localized = EXCLUDED.name_localized,
                         country_code = EXCLUDED.country_code, geometry = EXCLUDED.geometry,
                         source_license = EXCLUDED.source_license, source_crs_epsg = EXCLUDED.source_crs_epsg,
                         imported_at = now()""",
                    (source, version, str(source_key), str(name), Jsonb(props.get("name_localized", {})),
                     props.get("country_code") or props.get("shapeGroup"),
                     str(props.get("admin_level") or props.get("shapeType") or "unknown"),
                     json.dumps(geometry), license_id, source_crs_epsg),
                )
        return len(features)

    async def import_ecosystem_masks(self, *, source_id: str, ecosystem_code: str,
                                     version: str, features: list[dict[str, Any]],
                                     source_crs_epsg: int = 4326) -> int:
        async with self.pool.connection() as conn, conn.transaction():
            for feature in features:
                geometry = feature.get("geometry")
                if not geometry:
                    raise ValueError("Every ecosystem feature needs polygon geometry")
                await conn.execute(
                    """INSERT INTO ecosystem_mask
                       (ecosystem_code, source_id, source_version, source_crs_epsg, geometry, source_metadata)
                       VALUES (%s, %s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), %s)""",
                    (ecosystem_code, source_id, version, source_crs_epsg, json.dumps(geometry),
                     Jsonb(feature.get("properties") or {})),
                )
        return len(features)

    async def enqueue_job(self, source_id: str, request: dict[str, Any]) -> str:
        async with self.pool.connection() as conn:
            row = await (await conn.execute(
                "INSERT INTO ingestion_job (source_id, request) VALUES (%s, %s) RETURNING job_id::text",
                (source_id, Jsonb(request)),
            )).fetchone()
        return row[0]

    async def job_status(self, job_id: str) -> dict[str, Any] | None:
        async with self.pool.connection() as conn:
            row = await (await conn.execute(
                "SELECT job_id::text, source_id, status, records_ingested, error_message, created_at, started_at, completed_at FROM ingestion_job WHERE job_id = %s",
                (job_id,),
            )).fetchone()
        if not row:
            return None
        return dict(zip(("job_id", "source_id", "status", "records_ingested", "error_message", "created_at", "started_at", "completed_at"), row))

    async def claim_job(self) -> dict[str, Any] | None:
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                """UPDATE ingestion_job SET status = 'queued'
                   WHERE status = 'running' AND started_at < now() - interval '30 minutes' AND attempts < 3"""
            )
            row = await (await conn.execute(
                """SELECT job_id::text, source_id, request FROM ingestion_job
                   WHERE status = 'queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"""
            )).fetchone()
            if not row:
                return None
            await conn.execute(
                "UPDATE ingestion_job SET status = 'running', started_at = now(), attempts = attempts + 1 WHERE job_id = %s",
                (row[0],),
            )
        return {"job_id": row[0], "source_id": row[1], "request": row[2]}

    async def finish_job(self, job_id: str, *, records_ingested: int = 0, error: str | None = None) -> None:
        status = "failed" if error else "completed"
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE ingestion_job SET status = %s, records_ingested = %s, error_message = %s, completed_at = now() WHERE job_id = %s",
                (status, records_ingested, error, job_id),
            )


def configured_cache_ttl() -> int:
    return max(0, int(os.getenv("CACHE_TTL_SECONDS", "900")))