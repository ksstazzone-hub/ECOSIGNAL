from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ConnectorInfo:
    key: str
    label: str
    provider: str
    coverage: Dict[str, str]
    access_constraints: str
    temporal_coverage: str
    spatial_resolution: str
    notes: str


class ConnectorRegistry:
    """Registry of scientific data connectors and their real-world constraints."""

    def __init__(self) -> None:
        self._sources: Dict[str, ConnectorInfo] = {
            "gbif": ConnectorInfo(
                key="gbif",
                label="GBIF",
                provider="Global Biodiversity Information Facility",
                coverage={"status": "partial", "summary": "Global biodiversity occurrence data, uneven by region and taxon"},
                access_constraints="Requires API key or rate-limited public access; check licensing and taxonomic validation.",
                temporal_coverage="Variable by taxon and country; often multi-decade historical and modern data.",
                spatial_resolution="Occurrence-level coordinates with varying precision; not uniform globally.",
                notes="Global coverage is not uniform; quality, taxonomic consistency, and sampling bias vary substantially.",
            ),
            "obis": ConnectorInfo(
                key="obis",
                label="OBIS",
                provider="Ocean Biodiversity Information System",
                coverage={"status": "partial", "summary": "Marine biodiversity data with strong ocean coverage but not complete for all coastal zones"},
                access_constraints="Open data access subject to provider metadata, licensing, and regional integration limits.",
                temporal_coverage="Historical to current, with stronger marine records in certain basins and monitoring programs.",
                spatial_resolution="Point observations and gridded products where available; marine coverage is uneven.",
                notes="Marine records are extensive, but coverage is patchy across remote and under-sampled seas.",
            ),
            "inaturalist": ConnectorInfo(
                key="inaturalist",
                label="iNaturalist",
                provider="iNaturalist",
                coverage={"status": "partial", "summary": "Community observations available globally but biased toward accessible and populated areas"},
                access_constraints="API subject to platform terms, rate limits, and data-use constraints.",
                temporal_coverage="Recent decades to current, with strong recent growth in observations.",
                spatial_resolution="Occurrence-level coordinates with varied spatial precision.",
                notes="Highly valuable for community science, but not equivalent to systematic monitoring data.",
            ),
            "nasa_earthdata": ConnectorInfo(
                key="nasa_earthdata",
                label="NASA Earthdata",
                provider="NASA Earth Science Data Systems",
                coverage={"status": "partial", "summary": "Global satellite and environmental products; suitability depends on product and ecological question"},
                access_constraints="Requires authentication and product-specific access controls for some collections.",
                temporal_coverage="Daily through multi-decadal archives depending on product.",
                spatial_resolution="1 m to 1 km or coarser depending on sensor and product.",
                notes="Not all environmental products are directly applicable to every ecosystem or taxon.",
            ),
            "copernicus": ConnectorInfo(
                key="copernicus",
                label="Copernicus",
                provider="European Union Copernicus Programme",
                coverage={"status": "partial", "summary": "Global and regional environmental products, especially land, climate, and ocean variables"},
                access_constraints="Dataset licensing and access vary across services and products.",
                temporal_coverage="Multiple years to near-real time, product-dependent.",
                spatial_resolution="10 m to tens of km depending on dataset.",
                notes="Strong operational capability, but not all products are globally or ecologically equivalent.",
            ),
            "user_upload": ConnectorInfo(
                key="user_upload",
                label="User Uploads",
                provider="User-submitted scientific datasets",
                coverage={"status": "variable", "summary": "Depends on dataset structure, metadata completeness, and scientific quality"},
                access_constraints="Schema validation and metadata checks required before integration.",
                temporal_coverage="Dataset dependent.",
                spatial_resolution="Dataset dependent.",
                notes="This connector allows global scientific contributions while preserving provenance and license metadata.",
            ),
            "regional_database": ConnectorInfo(
                key="regional_database",
                label="Regional / National Databases",
                provider="Future country and regional biodiversity repositories",
                coverage={"status": "limited", "summary": "Strong local coverage in some regions; absent or fragmented elsewhere"},
                access_constraints="Jurisdictional and institutional access rules apply.",
                temporal_coverage="Variable by region and program.",
                spatial_resolution="Variable by source.",
                notes="ECOSIGNAL must support integration without assuming universal coverage.",
            ),
        }

    def list_sources(self) -> Dict[str, Dict[str, object]]:
        return {
            key: {
                "label": source.label,
                "provider": source.provider,
                "coverage": source.coverage,
                "access_constraints": source.access_constraints,
                "temporal_coverage": source.temporal_coverage,
                "spatial_resolution": source.spatial_resolution,
                "notes": source.notes,
            }
            for key, source in self._sources.items()
        }

    def get_source(self, key: str) -> ConnectorInfo:
        if key not in self._sources:
            raise KeyError(f"Unknown connector: {key}")
        return self._sources[key]
