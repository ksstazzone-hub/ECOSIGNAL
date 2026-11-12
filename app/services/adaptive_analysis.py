from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ModuleSelection:
    module_id: str
    ecosystem: str
    rationale: str
    confidence: float
    required_data: List[str]


class AdaptiveAnalyzer:
    """Selects the correct combination of analytical modules based on ecosystem and data constraints."""

    def __init__(self) -> None:
        self.modules: Dict[str, Dict[str, object]] = {
            "marine_biodiversity_patterns": {
                "ecosystems": ["marine", "coastal"],
                "required_data": ["occurrences", "environmental_covariates", "spatial_geometry"],
                "methods": ["species richness modeling", "spatial clustering", "anomaly detection"],
                "minimum_sample_size": 30,
                "limitations": ["Sampling bias, taxonomic incompleteness"],
                "validation": ["distributional plausibility", "cross-validation"],
            },
            "species_distribution_changes": {
                "ecosystems": ["marine", "freshwater", "temperate_forest", "tropical_forest", "mountain", "polar"],
                "required_data": ["occurrences", "sampling_effort", "time_series"],
                "methods": ["occupancy modeling", "range shift analysis"],
                "minimum_sample_size": 40,
                "limitations": ["observer bias", "range truncation"],
                "validation": ["presence-likelihood checks", "benchmark reconstruction"],
            },
            "habitat_fragmentation": {
                "ecosystems": ["tropical_forest", "temperate_forest", "grassland", "urban", "transitional_mixed"],
                "required_data": ["land_cover", "patch_geometry", "connectivity"],
                "methods": ["fragmentation metrics", "network analysis"],
                "minimum_sample_size": 10,
                "limitations": ["Resolution effects", "classification error"],
                "validation": ["land-cover agreement", "reference patch review"],
            },
            "wetland_changes": {
                "ecosystems": ["wetland", "freshwater"],
                "required_data": ["water_extent", "hydrology", "inundation"],
                "methods": ["water mask comparison", "hydroperiod analysis"],
                "minimum_sample_size": 12,
                "limitations": ["Cloud interference", "seasonal variation"],
                "validation": ["field validation", "historical reference comparison"],
            },
            "urban_biodiversity_patterns": {
                "ecosystems": ["urban"],
                "required_data": ["green_space", "biodiversity_records", "land_cover"],
                "methods": ["landscape metrics", "species richness gradients"],
                "minimum_sample_size": 20,
                "limitations": ["Uneven observer effort"],
                "validation": ["sampling stratification", "land cover reconciliation"],
            },
            "climate_associated_ecological_changes": {
                "ecosystems": ["polar", "mountain", "desert", "tundra", "marine"],
                "required_data": ["climate_anomalies", "occurrences", "time_series"],
                "methods": ["trend decomposition", "correlative analysis"],
                "minimum_sample_size": 25,
                "limitations": ["Non-stationary drivers", "lagged responses"],
                "validation": ["climate-signal coherence", "temporal consistency checks"],
            },
        }

    def select_modules(
        self,
        ecosystem: str,
        taxonomic_group: str,
        data_quality: str,
        temporal_resolution: str,
        geographic_resolution: str,
        available_data: Optional[Dict[str, object]] = None,
    ) -> List[ModuleSelection]:
        ecosystem = ecosystem.lower()
        available_data = available_data or {}

        selected: List[ModuleSelection] = []
        for module_id, definition in self.modules.items():
            supported_ecosystems = [item.lower() for item in definition["ecosystems"]]
            if ecosystem not in supported_ecosystems:
                continue

            if data_quality == "low":
                rationale = "Data quality is low; only robust and conservative modules should be used."
            elif temporal_resolution == "annual" and ecosystem in {"marine", "wetland", "polar"}:
                rationale = "Annual data are weak for short-timescale ecological dynamics; use broad trend indicators only."
            else:
                rationale = f"{ecosystem} analysis is compatible with {module_id} given the observed data quality and scale."

            selected.append(
                ModuleSelection(
                    module_id=module_id,
                    ecosystem=ecosystem,
                    rationale=rationale,
                    confidence=self._confidence_score(data_quality, temporal_resolution, geographic_resolution),
                    required_data=[str(item) for item in definition["required_data"]],
                )
            )

        if not selected:
            selected.append(
                ModuleSelection(
                    module_id="ecosystem_coverage_assessment",
                    ecosystem=ecosystem,
                    rationale="No ecosystem-specific analytical module is currently justified; the platform should defer to coverage assessment and metadata review.",
                    confidence=0.25,
                    required_data=["coverage_metadata", "study_area", "taxonomy_context"],
                )
            )

        return selected

    @staticmethod
    def _confidence_score(data_quality: str, temporal_resolution: str, geographic_resolution: str) -> float:
        quality_score = {"low": 0.35, "moderate": 0.65, "good": 0.9}.get(data_quality, 0.5)
        temporal_score = {"monthly": 0.95, "seasonal": 0.8, "annual": 0.6}.get(temporal_resolution, 0.5)
        geo_score = {"local": 0.9, "regional": 0.8, "continent": 0.6}.get(geographic_resolution, 0.5)
        return round(min(1.0, (quality_score + temporal_score + geo_score) / 3.0), 2)
