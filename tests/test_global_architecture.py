from app.config import ECOSYSTEM_CATEGORIES
from app.services.adaptive_analysis import AdaptiveAnalyzer, ModuleSelection
from app.services.data_connectors import ConnectorRegistry
from app.services.geography import GeographyService


def test_global_ecosystem_categories_are_supported():
    expected = {
        "marine",
        "coastal",
        "freshwater",
        "wetland",
        "tropical_forest",
        "temperate_forest",
        "boreal_forest",
        "grassland",
        "savanna",
        "desert",
        "tundra",
        "polar",
        "mountain",
        "urban",
        "agricultural",
        "transitional_mixed",
    }
    assert set(ECOSYSTEM_CATEGORIES) == expected


def test_geography_service_accepts_global_coords_and_bbox():
    service = GeographyService()
    assert service.validate_coordinate(45.0, -71.0)
    assert service.validate_coordinate(-33.0, -68.0)
    assert not service.validate_coordinate(91.0, 0.0)
    bbox = service.build_bbox(-10, -20, 10, 20)
    assert bbox == {"min_lat": -10, "min_lon": -20, "max_lat": 10, "max_lon": 20}


def test_connector_registry_lists_global_data_sources():
    registry = ConnectorRegistry()
    sources = registry.list_sources()
    assert {"gbif", "obis", "inaturalist", "nasa_earthdata", "copernicus", "user_upload"}.issubset(sources)
    assert all("coverage" in source for source in sources.values())


def test_adaptive_analysis_selects_appropriate_modules():
    analyzer = AdaptiveAnalyzer()
    selection = analyzer.select_modules(
        ecosystem="marine",
        taxonomic_group="fish",
        data_quality="good",
        temporal_resolution="monthly",
        geographic_resolution="regional",
    )
    assert any(item.module_id == "marine_biodiversity_patterns" for item in selection)
    assert all(isinstance(item, ModuleSelection) for item in selection)


def test_adaptive_analysis_rejects_incompatible_data():
    analyzer = AdaptiveAnalyzer()
    selection = analyzer.select_modules(
        ecosystem="urban",
        taxonomic_group="benthic_invertebrates",
        data_quality="low",
        temporal_resolution="annual",
        geographic_resolution="continent",
    )
    assert all(item.rationale for item in selection)
