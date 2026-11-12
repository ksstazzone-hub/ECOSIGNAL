from ecosignal.analysis import MODULES, assess_modules


def test_marine_modules_are_not_recommended_for_urban_studies():
    assessments = assess_modules(
        ecosystems=["urban"], taxonomic_group="species", sample_count=1000,
        available_data={"georeferenced_occurrences", "sampling_effort", "taxonomic_identity"},
        time_span_years=10, temporal_bins=10, quality_score=1, comparable_sampling=True,
    )

    module_ids = {item["module_id"] for item in assessments}
    assert "marine_invasion_screen" not in module_ids
    assert "urban_biodiversity" in module_ids


def test_module_eligibility_requires_its_own_inputs_and_is_not_a_signal():
    module = next(item for item in MODULES if item.module_id == "marine_biodiversity")
    assessments = assess_modules(
        ecosystems=["marine"], taxonomic_group="community", sample_count=120,
        available_data=set(module.required_data), time_span_years=3, temporal_bins=3,
        quality_score=0.95, comparable_sampling=True,
    )

    assessment = next(item for item in assessments if item["module_id"] == "marine_biodiversity")
    assert assessment["status"] == "eligible_for_review"
    assert "not an ecological finding" in assessment["interpretation"]


def test_missing_sampling_effort_blocks_effort_sensitive_analysis():
    assessments = assess_modules(
        ecosystems=["marine"], taxonomic_group="community", sample_count=200,
        available_data={"georeferenced_occurrences", "taxonomic_identity"},
        time_span_years=5, temporal_bins=5, quality_score=1, comparable_sampling=False,
    )

    marine_biodiversity = next(item for item in assessments if item["module_id"] == "marine_biodiversity")
    assert marine_biodiversity["status"] == "not_suitable"
    assert any("sampling_effort" in reason for reason in marine_biodiversity["reasons"])