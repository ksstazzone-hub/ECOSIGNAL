INSERT INTO case_study_profile (profile_id, display_name, ecosystem_codes, status, description)
VALUES (
    'puerto-madryn-patagonia-marine',
    'Puerto Madryn and Patagonian marine environments',
    ARRAY['marine', 'coastal'],
    'awaiting_area_and_data',
    'Initial validation profile only. No boundary or coverage is bundled; attach a versioned study area and assess real source data before analysis.'
)
ON CONFLICT (profile_id) DO NOTHING;