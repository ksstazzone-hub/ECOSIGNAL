from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisModule:
    module_id: str
    title: str
    ecosystems: frozenset[str]
    taxonomic_groups: frozenset[str]
    required_data: tuple[str, ...]
    methods: tuple[str, ...]
    minimum_records: int
    minimum_time_span_years: int
    minimum_temporal_bins: int
    minimum_quality_score: float
    limitations: tuple[str, ...]
    validation: tuple[str, ...]
    geographic_scale: str
    temporal_scale: str


ALL_ECOSYSTEMS = frozenset({
    "marine", "coastal", "freshwater", "wetland", "tropical_forest", "temperate_forest",
    "boreal_forest", "grassland", "savanna", "desert", "tundra", "polar", "mountain",
    "urban", "agricultural", "transitional_mixed",
})
TERRESTRIAL = frozenset(ALL_ECOSYSTEMS - {"marine", "freshwater"})
FORESTS = frozenset({"tropical_forest", "temperate_forest", "boreal_forest"})
POLAR_MOUNTAIN = frozenset({"polar", "tundra", "mountain"})


MODULES = (
    AnalysisModule("marine_invasion_screen", "Marine invasion screening", frozenset({"marine", "coastal"}), frozenset({"species"}), ("georeferenced_occurrences", "taxonomic_identity", "survey_method"), ("occupancy trend", "validated range expansion tests"), 50, 3, 3, 0.8, ("Occurrence records do not establish non-native status or population growth.", "Requires an authoritative native-range and introduction-status source."), ("Verify identity and status with regional experts; validate against independent surveys."), "Local to basin; cross-border only with compatible protocols", "At least three comparable annual periods"),
    AnalysisModule("coral_reef_change", "Coral reef change", frozenset({"marine", "coastal"}), frozenset({"species", "habitat"}), ("reef habitat mask", "repeat imagery or survey", "environmental covariates"), ("image classification change detection", "benthic cover time series"), 30, 2, 2, 0.85, ("Requires reef-specific spatial masks and comparable imagery or field protocol.", "General occurrence data are not a coral health metric."), ("Validate classifications with field observations and independent image samples."), "Reef sites to reef systems", "Seasonally matched multi-year observations"),
    AnalysisModule("marine_biodiversity", "Marine biodiversity patterns", frozenset({"marine", "coastal"}), frozenset({"species", "community"}), ("georeferenced_occurrences", "sampling_effort", "taxonomic_identity"), ("effort-standardized richness", "occupancy models"), 100, 2, 2, 0.8, ("Raw record counts are not abundance; uneven observer and survey effort biases patterns.",), ("Compare matched protocols; validate with independent transects or monitoring programs."), "Site to marine ecoregion", "Seasonally matched periods over multiple years"),
    AnalysisModule("coastal_change", "Coastal ecosystem change", frozenset({"coastal", "marine", "wetland"}), frozenset({"habitat", "community"}), ("coastal habitat mask", "repeat remote sensing", "tide or season metadata"), ("time-series segmentation", "habitat transition matrix"), 20, 3, 3, 0.85, ("Tide, season, sensor, and shoreline definitions affect comparability.",), ("Check against local shoreline/habitat surveys and sensor-specific accuracy assessment."), "Coast segment to regional coastline", "Seasonally matched multi-year periods"),
    AnalysisModule("marine_environmental_anomaly", "Marine environmental anomaly", frozenset({"marine", "coastal"}), frozenset({"environmental"}), ("quality-controlled environmental measurements", "product metadata", "baseline period"), ("seasonal climatology residuals", "change-point models"), 100, 10, 12, 0.9, ("Requires product-specific units, resolution, baseline, and sensor quality flags.", "Catalog presence alone is insufficient."), ("Cross-check independent products and in-situ measurements; document baseline sensitivity."), "Product grid to ocean basin", "Product cadence and at least a decade-long baseline"),
    AnalysisModule("species_distribution_change", "Species distribution change", ALL_ECOSYSTEMS, frozenset({"species"}), ("georeferenced_occurrences", "taxonomic_identity", "sampling_effort", "environmental predictors"), ("occupancy or distribution models", "bias-aware range comparison"), 100, 5, 5, 0.8, ("Presence-only records need bias correction and comparable observation effort.", "Model transfer beyond sampled environmental space is uncertain."), ("Spatially blocked validation; independent records; sensitivity to sampling bias and predictor choice."), "Species range to ecoregion", "At least five comparable annual periods"),
    AnalysisModule("habitat_fragmentation", "Habitat fragmentation", TERRESTRIAL, frozenset({"habitat"}), ("validated habitat classes", "repeat land-cover maps", "analysis scale"), ("patch metrics", "connectivity graph", "landscape configuration"), 20, 3, 3, 0.85, ("Metrics are scale- and classification-dependent; do not compare incompatible map products.",), ("Validate land-cover maps; report resolution, edge rules, and scale sensitivity."), "Landscape to region", "Comparable multi-year land-cover epochs"),
    AnalysisModule("forest_biodiversity", "Forest biodiversity change", FORESTS, frozenset({"species", "community"}), ("forest mask", "georeferenced_occurrences", "sampling_effort"), ("effort-standardized richness", "occupancy models"), 100, 3, 3, 0.8, ("Forest type and survey method must be comparable; occurrence counts are not abundance.",), ("Independent plot validation and protocol-stratified sensitivity analysis."), "Plot to forest landscape", "Seasonally matched multi-year periods"),
    AnalysisModule("invasive_expansion", "Potential invasive species expansion", ALL_ECOSYSTEMS, frozenset({"species"}), ("georeferenced_occurrences", "taxonomic_identity", "introduction_status", "sampling_effort"), ("validated occupancy trend", "range edge comparison"), 50, 3, 3, 0.85, ("Must not infer invasive status from geographic novelty or a single observation.",), ("Expert-confirmed status; voucher/photo review; independent survey confirmation."), "Local range to ecoregion", "Comparable multi-year periods"),
    AnalysisModule("ecological_disturbance", "Ecological disturbance screening", TERRESTRIAL | frozenset({"freshwater", "wetland"}), frozenset({"habitat", "community"}), ("baseline environmental series", "disturbance event metadata", "repeat ecological measurements"), ("interrupted time series", "before-after-control-impact"), 60, 3, 3, 0.85, ("Disturbance attribution requires a baseline and controls; correlation is not causation.",), ("Use control sites where possible; validate event dates and independent field indicators."), "Site to landscape", "Event-centered with pre-event baseline and recovery period"),
    AnalysisModule("freshwater_biodiversity", "Freshwater biodiversity change", frozenset({"freshwater", "wetland"}), frozenset({"species", "community"}), ("georeferenced_occurrences", "waterbody identity", "sampling_effort", "taxonomic_identity"), ("occupancy models", "effort-standardized richness"), 80, 2, 2, 0.8, ("Catchment connectivity and seasonal sampling strongly affect comparisons.",), ("Stratify by waterbody and season; validate with standardized field surveys."), "Waterbody to catchment", "Seasonally matched periods across multiple years"),
    AnalysisModule("freshwater_invasion", "Freshwater invasive species screening", frozenset({"freshwater", "wetland"}), frozenset({"species"}), ("georeferenced_occurrences", "waterbody identity", "introduction_status"), ("catchment network spread models", "validated occupancy change"), 40, 2, 2, 0.85, ("Requires confirmed introduction status and hydrologic connectivity.",), ("Confirm records and pathways with local authorities and independent sampling."), "Waterbody network to catchment", "Seasonally matched multi-year periods"),
    AnalysisModule("wetland_change", "Wetland extent and condition change", frozenset({"wetland", "coastal", "freshwater"}), frozenset({"habitat", "environmental"}), ("wetland mask", "repeat remote sensing", "sensor and seasonal metadata"), ("water extent time series", "habitat transition analysis"), 20, 3, 3, 0.85, ("Seasonal inundation and sensor resolution can mimic change.",), ("Validate against local wetland inventories and independent seasonal observations."), "Wetland complex to basin", "Seasonally matched multi-year periods"),
    AnalysisModule("water_quality_anomaly", "Water-quality anomaly", frozenset({"freshwater", "wetland", "coastal"}), frozenset({"environmental"}), ("quality-controlled water measurements", "variable and unit", "sampling protocol", "baseline period"), ("variable-specific seasonal control charts", "robust baseline residuals"), 60, 3, 12, 0.9, ("Only comparable variable, unit, depth, and protocols may be combined.", "Requires measured values; satellite proxies need separate calibration."), ("Calibrate with reference methods; validate on independent samples and document detection limits."), "Station to waterbody", "Variable-specific cadence with seasonal baseline"),
    AnalysisModule("polar_mountain_distribution", "Polar and mountain distribution change", POLAR_MOUNTAIN, frozenset({"species", "habitat"}), ("georeferenced_occurrences", "elevation or climate covariates", "sampling_effort"), ("elevation-band occupancy", "bias-aware distribution model"), 60, 5, 5, 0.8, ("Sparse access, shifting ice/snow, and steep environmental gradients create uneven sampling.",), ("Spatially blocked validation across elevation/climate gradients; independent surveys."), "Elevation gradient to mountain/polar region", "Comparable multi-year periods"),
    AnalysisModule("climate_associated_change", "Climate-associated ecological change", ALL_ECOSYSTEMS, frozenset({"species", "habitat", "community"}), ("ecological time series", "climate time series", "sampling_effort", "temporal alignment"), ("hierarchical time-series models", "climate-response models"), 100, 10, 10, 0.85, ("Association does not establish climate causality; climate products have their own resolution and uncertainty.",), ("Validate with independent data, confounder checks, temporal holdouts, and product sensitivity."), "Site to ecoregion", "Aligned seasonal multi-year series"),
    AnalysisModule("urban_biodiversity", "Urban biodiversity patterns", frozenset({"urban"}), frozenset({"species", "community"}), ("georeferenced_occurrences", "green-space layer", "sampling_effort", "urban boundary version"), ("effort-standardized richness", "stratified occupancy models"), 80, 2, 2, 0.8, ("Observer access and reporting bias covary with park access and demographics.",), ("Stratify by greenspace and sampling protocol; audit spatial and observer bias."), "Park to metropolitan area", "Seasonally matched multi-year periods"),
    AnalysisModule("urban_green_space", "Urban green-space change", frozenset({"urban"}), frozenset({"habitat"}), ("urban boundary", "repeat green-space maps", "map resolution and dates"), ("land-cover transition", "patch and connectivity metrics"), 20, 2, 2, 0.85, ("Map definitions and resolution must match; greenness is not equivalent to habitat quality.",), ("Validate map classifications and report resolution and seasonal effects."), "Neighborhood to metropolitan area", "Comparable annual or seasonal map epochs"),
    AnalysisModule("urban_connectivity", "Urban ecological connectivity", frozenset({"urban"}), frozenset({"species", "habitat"}), ("validated habitat patches", "species movement assumptions", "barrier layer"), ("least-cost paths", "circuit connectivity models"), 20, 1, 1, 0.85, ("Connectivity is species-specific and depends on movement/barrier assumptions.",), ("Validate movement resistance against telemetry or independent field evidence."), "Neighborhood to metropolitan area", "Static or scenario-based; revisit with habitat updates"),
    AnalysisModule("agricultural_habitat_change", "Agricultural habitat change", frozenset({"agricultural", "grassland", "savanna"}), frozenset({"habitat", "species"}), ("land-use layer", "repeat habitat map", "sampling effort for species data"), ("land-use transition", "occupancy comparison"), 50, 3, 3, 0.8, ("Season, crop rotation, and management practices confound habitat signals.",), ("Validate land-use classes and stratify by crop and management regime."), "Field mosaic to agricultural landscape", "Seasonally matched multi-year periods"),
    AnalysisModule("desert_tundra_habitat", "Desert and tundra habitat transformation", frozenset({"desert", "tundra", "polar", "mountain"}), frozenset({"habitat", "environmental"}), ("repeat habitat or vegetation product", "sensor metadata", "seasonal baseline"), ("phenology-adjusted time-series change", "habitat transition analysis"), 30, 5, 5, 0.85, ("Sparse vegetation and short growing seasons make sensor and phenology effects important.",), ("Validate across local field sites and independent remote-sensing products."), "Site to regional ecosystem", "Phenology-matched multi-year series"),
)


def module_catalog() -> list[dict[str, Any]]:
    return [{
        "module_id": item.module_id, "title": item.title, "ecosystems": sorted(item.ecosystems),
        "taxonomic_groups": sorted(item.taxonomic_groups), "required_data": list(item.required_data),
        "methods": list(item.methods), "minimum_records": item.minimum_records,
        "minimum_time_span_years": item.minimum_time_span_years,
        "minimum_temporal_bins": item.minimum_temporal_bins,
        "minimum_quality_score": item.minimum_quality_score,
        "limitations": list(item.limitations), "validation": list(item.validation),
        "geographic_scale": item.geographic_scale, "temporal_scale": item.temporal_scale,
    } for item in MODULES]


def assess_modules(*, ecosystems: list[str], taxonomic_group: str, sample_count: int,
                   available_data: set[str], time_span_years: float, temporal_bins: int,
                   quality_score: float, comparable_sampling: bool) -> list[dict[str, Any]]:
    assessments = []
    for module in MODULES:
        if not (module.ecosystems & set(ecosystems)):
            continue
        reasons = []
        if taxonomic_group not in module.taxonomic_groups:
            reasons.append(f"Taxonomic group '{taxonomic_group}' is not supported by this module.")
        missing = sorted(set(module.required_data) - available_data)
        if missing:
            reasons.append("Missing required data: " + ", ".join(missing) + ".")
        if sample_count < module.minimum_records:
            reasons.append(f"Requires at least {module.minimum_records} records for initial screening; got {sample_count}.")
        if time_span_years < module.minimum_time_span_years:
            reasons.append(f"Requires at least {module.minimum_time_span_years} years; got {time_span_years:g}.")
        if temporal_bins < module.minimum_temporal_bins:
            reasons.append(f"Requires at least {module.minimum_temporal_bins} temporal bins; got {temporal_bins}.")
        if quality_score < module.minimum_quality_score:
            reasons.append(f"Data quality score {quality_score:.2f} is below {module.minimum_quality_score:.2f}.")
        if not comparable_sampling and "sampling_effort" in module.required_data:
            reasons.append("Sampling effort is not known to be comparable.")
        assessments.append({
            "module_id": module.module_id,
            "title": module.title,
            "status": "eligible_for_review" if not reasons else "not_suitable",
            "methods": list(module.methods),
            "limitations": list(module.limitations),
            "validation": list(module.validation),
            "reasons": reasons,
            "geographic_scale": module.geographic_scale,
            "temporal_scale": module.temporal_scale,
            "interpretation": "Eligibility is not an ecological finding. Scientific review and validation are required.",
        })
    return assessments