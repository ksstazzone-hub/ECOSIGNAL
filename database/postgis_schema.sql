CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS study_areas (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ecosystem VARCHAR(80) NOT NULL,
    geometry_type VARCHAR(40) DEFAULT 'polygon',
    geometry geometry(MultiPolygon, 4326) NOT NULL,
    source VARCHAR(255) NOT NULL,
    source_version VARCHAR(80) DEFAULT 'unknown',
    country VARCHAR(120),
    admin_region VARCHAR(120),
    is_global BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS data_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(255) NOT NULL,
    connector_key VARCHAR(80) NOT NULL,
    coverage_status VARCHAR(40) NOT NULL,
    license VARCHAR(255),
    metadata_url VARCHAR(255),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS observations (
    id SERIAL PRIMARY KEY,
    scientific_name VARCHAR(255) NOT NULL,
    canonical_name VARCHAR(255) NOT NULL,
    common_name VARCHAR(255),
    taxon_rank VARCHAR(80),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geometry geometry(Point, 4326),
    observed_at TIMESTAMPTZ NOT NULL,
    original_date_precision VARCHAR(40),
    timezone VARCHAR(80) DEFAULT 'UTC',
    data_source_id INTEGER NOT NULL REFERENCES data_sources(id),
    ecosystem VARCHAR(80) NOT NULL,
    uncertainty_m DOUBLE PRECISION DEFAULT 0.0,
    sampling_effort VARCHAR(255),
    license VARCHAR(255),
    source_schema TEXT
);

CREATE TABLE IF NOT EXISTS measurements (
    id SERIAL PRIMARY KEY,
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    variable_name VARCHAR(255) NOT NULL,
    variable_value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(80) NOT NULL,
    timestamp_utc TIMESTAMPTZ NOT NULL,
    method VARCHAR(255),
    uncertainty DOUBLE PRECISION DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS administrative_boundaries (
    id SERIAL PRIMARY KEY,
    boundary_name VARCHAR(255) NOT NULL,
    country VARCHAR(120),
    admin_level VARCHAR(80),
    geometry geometry(MultiPolygon, 4326) NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    source_version VARCHAR(80) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_study_areas_geometry ON study_areas USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_observations_geometry ON observations USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_admin_boundaries_geometry ON administrative_boundaries USING GIST (geometry);
