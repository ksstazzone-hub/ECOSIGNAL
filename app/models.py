from __future__ import annotations

from sqlalchemy import Column, Float, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class StudyArea(Base):
    __tablename__ = "study_areas"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    ecosystem = Column(String(80), nullable=False)
    geometry_type = Column(String(40), default="polygon")
    geometry_wkt = Column(Text, nullable=False)
    source = Column(String(255), nullable=False)
    source_version = Column(String(80), default="unknown")
    country = Column(String(120), nullable=True)
    admin_region = Column(String(120), nullable=True)
    is_global = Column(String(10), default="false")


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    provider = Column(String(255), nullable=False)
    connector_key = Column(String(80), nullable=False)
    coverage_status = Column(String(40), nullable=False)
    license = Column(String(255), nullable=True)
    metadata_url = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    observations = relationship("Observation", back_populates="source")


class Observation(Base):
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True)
    scientific_name = Column(String(255), nullable=False)
    canonical_name = Column(String(255), nullable=False)
    common_name = Column(String(255), nullable=True)
    taxon_rank = Column(String(80), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geometry_wkt = Column(Text, nullable=True)
    observed_at = Column(DateTime, nullable=False)
    original_date_precision = Column(String(40), nullable=True)
    timezone = Column(String(80), default="UTC")
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    ecosystem = Column(String(80), nullable=False)
    uncertainty_m = Column(Float, default=0.0)
    sampling_effort = Column(String(255), nullable=True)
    license = Column(String(255), nullable=True)
    source_schema = Column(Text, nullable=True)

    source = relationship("DataSource", back_populates="observations")


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True)
    observation_id = Column(Integer, ForeignKey("observations.id"), nullable=False)
    variable_name = Column(String(255), nullable=False)
    variable_value = Column(Float, nullable=False)
    unit = Column(String(80), nullable=False)
    timestamp_utc = Column(DateTime, nullable=False)
    method = Column(String(255), nullable=True)
    uncertainty = Column(Float, default=0.0)


class AdministrativeBoundary(Base):
    __tablename__ = "administrative_boundaries"

    id = Column(Integer, primary_key=True)
    boundary_name = Column(String(255), nullable=False)
    country = Column(String(120), nullable=True)
    admin_level = Column(String(80), nullable=True)
    geometry_wkt = Column(Text, nullable=False)
    source_name = Column(String(255), nullable=False)
    source_version = Column(String(80), nullable=False)


class AnalyticalModuleDefinition(Base):
    __tablename__ = "analytical_module_definitions"

    id = Column(Integer, primary_key=True)
    module_id = Column(String(120), nullable=False, unique=True)
    ecosystem = Column(String(80), nullable=False)
    required_data = Column(Text, nullable=False)
    methods = Column(Text, nullable=False)
    minimum_sample_requirements = Column(String(255), nullable=True)
    known_limitations = Column(Text, nullable=True)
    validation_criteria = Column(Text, nullable=True)
    geographic_scales = Column(Text, nullable=True)
    temporal_scales = Column(Text, nullable=True)
