CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS ecosystem_category (
    code text PRIMARY KEY,
    label text NOT NULL,
    group_name text NOT NULL
);

INSERT INTO ecosystem_category (code, label, group_name) VALUES
    ('marine', 'Marine', 'aquatic'),
    ('coastal', 'Coastal', 'transitional'),
    ('freshwater', 'Freshwater', 'aquatic'),
    ('wetland', 'Wetland', 'aquatic'),
    ('tropical_forest', 'Tropical forest', 'forest'),
    ('temperate_forest', 'Temperate forest', 'forest'),
    ('boreal_forest', 'Boreal forest', 'forest'),
    ('grassland', 'Grassland', 'terrestrial'),
    ('savanna', 'Savanna', 'terrestrial'),
    ('desert', 'Desert', 'terrestrial'),
    ('tundra', 'Tundra', 'terrestrial'),
    ('polar', 'Polar', 'terrestrial'),
    ('mountain', 'Mountain', 'terrestrial'),
    ('urban', 'Urban', 'human_modified'),
    ('agricultural', 'Agricultural', 'human_modified'),
    ('transitional_mixed', 'Transitional and mixed ecosystems', 'transitional')
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS data_source (
    source_id text PRIMARY KEY,
    display_name text NOT NULL,
    source_type text NOT NULL,
    base_url text NOT NULL,
    access_notes text NOT NULL,
    coverage_claim text NOT NULL DEFAULT 'Not assessed',
    enabled boolean NOT NULL DEFAULT true,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS taxon_concept (
    taxon_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name text NOT NULL,
    rank text,
    parent_taxon_id uuid REFERENCES taxon_concept(taxon_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS taxon_identifier (
    taxon_id uuid NOT NULL REFERENCES taxon_concept(taxon_id) ON DELETE CASCADE,
    identifier_scheme text NOT NULL,
    identifier_value text NOT NULL,
    PRIMARY KEY (identifier_scheme, identifier_value),
    UNIQUE (taxon_id, identifier_scheme, identifier_value)
);

CREATE TABLE IF NOT EXISTS taxon_common_name (
    taxon_id uuid NOT NULL REFERENCES taxon_concept(taxon_id) ON DELETE CASCADE,
    language_code text NOT NULL,
    common_name text NOT NULL,
    source_id text REFERENCES data_source(source_id),
    source_record jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (taxon_id, language_code, common_name)
);

CREATE TABLE IF NOT EXISTS observation (
    observation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id text NOT NULL REFERENCES data_source(source_id),
    source_record_id text NOT NULL,
    taxon_id uuid REFERENCES taxon_concept(taxon_id),
    taxon_identifier_scheme text,
    taxon_identifier_value text,
    scientific_name text,
    observed_at timestamptz,
    original_event_date text,
    date_precision text NOT NULL DEFAULT 'unknown',
    original_timezone text,
    location geometry(Point, 4326),
    coordinate_uncertainty_m double precision CHECK (coordinate_uncertainty_m IS NULL OR coordinate_uncertainty_m >= 0),
    sampling_effort jsonb NOT NULL DEFAULT '{}'::jsonb,
    basis_of_record text,
    license_id text,
    source_url text,
    source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    original_record jsonb NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id, source_record_id)
);

CREATE INDEX IF NOT EXISTS observation_location_gix ON observation USING gist (location);
CREATE INDEX IF NOT EXISTS observation_time_idx ON observation (observed_at);
CREATE INDEX IF NOT EXISTS observation_taxon_idx ON observation (taxon_id, taxon_identifier_scheme, taxon_identifier_value);
CREATE INDEX IF NOT EXISTS observation_source_idx ON observation (source_id, ingested_at);

CREATE TABLE IF NOT EXISTS environmental_measurement (
    measurement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id text NOT NULL REFERENCES data_source(source_id),
    source_record_id text NOT NULL,
    variable_code text NOT NULL,
    value double precision NOT NULL,
    unit text NOT NULL,
    measured_at timestamptz,
    original_event_date text,
    date_precision text NOT NULL DEFAULT 'unknown',
    original_timezone text,
    location geometry(Point, 4326),
    coordinate_uncertainty_m double precision CHECK (coordinate_uncertainty_m IS NULL OR coordinate_uncertainty_m >= 0),
    measurement_uncertainty double precision CHECK (measurement_uncertainty IS NULL OR measurement_uncertainty >= 0),
    sampling_effort jsonb NOT NULL DEFAULT '{}'::jsonb,
    license_id text,
    source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    original_record jsonb NOT NULL,
    UNIQUE (source_id, source_record_id, variable_code)
);

CREATE INDEX IF NOT EXISTS measurement_location_gix ON environmental_measurement USING gist (location);
CREATE INDEX IF NOT EXISTS measurement_time_idx ON environmental_measurement (measured_at);
CREATE INDEX IF NOT EXISTS measurement_variable_idx ON environmental_measurement (variable_code, unit);

CREATE TABLE IF NOT EXISTS study_area (
    area_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    geometry geometry(MultiPolygon, 4326) NOT NULL,
    ecosystem_codes text[] NOT NULL DEFAULT '{}',
    created_by text,
    source_id text,
    source_version text,
    source_crs_epsg integer NOT NULL DEFAULT 4326,
    is_public boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ST_IsValid(geometry))
);

CREATE INDEX IF NOT EXISTS study_area_geometry_gix ON study_area USING gist (geometry);

CREATE TABLE IF NOT EXISTS case_study_profile (
    profile_id text PRIMARY KEY,
    display_name text NOT NULL,
    ecosystem_codes text[] NOT NULL,
    study_area_id uuid REFERENCES study_area(area_id),
    status text NOT NULL CHECK (status IN ('awaiting_area_and_data', 'ready_for_review', 'active')),
    description text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS administrative_boundary (
    boundary_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    boundary_source text NOT NULL,
    source_version text NOT NULL,
    source_boundary_id text NOT NULL,
    name text NOT NULL,
    name_localized jsonb NOT NULL DEFAULT '{}'::jsonb,
    country_code text,
    admin_level text NOT NULL,
    geometry geometry(MultiPolygon, 4326) NOT NULL,
    source_license text,
    source_crs_epsg integer NOT NULL DEFAULT 4326,
    imported_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (boundary_source, source_version, source_boundary_id, admin_level),
    CHECK (ST_IsValid(geometry))
);

CREATE INDEX IF NOT EXISTS administrative_boundary_geometry_gix ON administrative_boundary USING gist (geometry);
CREATE INDEX IF NOT EXISTS administrative_boundary_name_trgm_idx ON administrative_boundary USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS administrative_boundary_country_idx ON administrative_boundary (country_code, admin_level);

CREATE TABLE IF NOT EXISTS ecosystem_mask (
    mask_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ecosystem_code text NOT NULL REFERENCES ecosystem_category(code),
    source_id text NOT NULL REFERENCES data_source(source_id),
    source_version text NOT NULL,
    source_crs_epsg integer NOT NULL DEFAULT 4326,
    geometry geometry(MultiPolygon, 4326) NOT NULL,
    source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    imported_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ST_IsValid(geometry))
);

CREATE INDEX IF NOT EXISTS ecosystem_mask_geometry_gix ON ecosystem_mask USING gist (geometry);
CREATE INDEX IF NOT EXISTS ecosystem_mask_code_idx ON ecosystem_mask (ecosystem_code, source_version);

CREATE TABLE IF NOT EXISTS coverage_assessment (
    assessment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    requested_at timestamptz NOT NULL DEFAULT now(),
    geometry geometry(MultiPolygon, 4326) NOT NULL,
    ecosystem_codes text[] NOT NULL DEFAULT '{}',
    source_crs_epsg integer NOT NULL DEFAULT 4326,
    source_ids text[] NOT NULL,
    source_results jsonb NOT NULL,
    total_records integer NOT NULL DEFAULT 0,
    usable_records integer NOT NULL DEFAULT 0,
    status text NOT NULL CHECK (status IN ('sufficient', 'limited', 'no_usable_data', 'source_unavailable', 'monitoring')),
    status_threshold integer NOT NULL,
    caveats text[] NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS coverage_assessment_geometry_gix ON coverage_assessment USING gist (geometry);
CREATE INDEX IF NOT EXISTS coverage_assessment_requested_idx ON coverage_assessment (requested_at DESC);

CREATE TABLE IF NOT EXISTS api_cache (
    cache_key text PRIMARY KEY,
    source_id text NOT NULL,
    response jsonb NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS api_cache_expiry_idx ON api_cache (expires_at);

CREATE TABLE IF NOT EXISTS ingestion_job (
    job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id text NOT NULL,
    request jsonb NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    attempts integer NOT NULL DEFAULT 0,
    records_ingested bigint NOT NULL DEFAULT 0,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS ingestion_job_queue_idx ON ingestion_job (created_at) WHERE status = 'queued';

INSERT INTO data_source (source_id, display_name, source_type, base_url, access_notes) VALUES
    ('gbif', 'GBIF', 'occurrence', 'https://api.gbif.org/v1', 'Public occurrence search API; record-level licenses and dataset provenance must be retained.'),
    ('obis', 'OBIS', 'occurrence', 'https://api.obis.org/v3', 'Public marine biodiversity API; record and dataset terms can vary.'),
    ('inat', 'iNaturalist', 'occurrence', 'https://api.inaturalist.org/v1', 'Community observations; quality grade and observation license are record-specific.'),
    ('nasa_cmr', 'NASA Earthdata CMR', 'environmental_catalog', 'https://cmr.earthdata.nasa.gov/search', 'Metadata search is public; many data downloads require Earthdata Login and product-specific terms.'),
    ('copernicus_stac', 'Copernicus Data Space STAC', 'environmental_catalog', 'https://catalogue.dataspace.copernicus.eu/stac', 'Catalog and product access vary by collection; authentication and product terms must be checked.'),
    ('user_upload', 'User uploaded dataset', 'user', 'local://upload', 'Uploader must provide source, schema mapping, and license; original records are retained.')
ON CONFLICT (source_id) DO NOTHING;