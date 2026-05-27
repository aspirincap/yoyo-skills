# Output Contract

Use these contracts for final deliverables. JSON, YAML, Markdown tables, or structured text are acceptable as long as the keys are preserved.

## Generic Targeting Field

```text
id: Internal field ID, e.g. gen_meta_001
audience_name: Human-readable audience segment name
platform: meta | tiktok
country: Country or region code/name
field_type: location | interest | behavior | demographic | age | gender | language | placement | device
label: Human-readable targeting label
description: Why this field fits the product/audience
funnel_role: cold_audience | warm_audience | retargeting | broad_test
confidence: high | medium | low
source: product_page | user_input | motata_exact | motata_suggestion | model_inferred
mapping_status: exact | suggested | needs_lookup | unavailable
```

Rules:

- Use `source: motata_exact` only when motata returned a concrete field.
- Use `source: motata_suggestion` for motata suggestion/expansion results.
- Use `mapping_status: needs_lookup` when the strategy is valid but platform lookup still needs to run.
- Use `mapping_status: unavailable` when lookup failed or the field is unsupported.

## Motata Targeting Field

```text
platform: meta | tiktok
account_scope: meta_account_id | tiktok_advertiser_id | unknown
motata_command: Command used or recommended for lookup
source_query: Query string or payload used for lookup
raw_id: Real ID from motata/API; blank/null if unresolved
raw_name: Real name from motata/API; blank/null if unresolved
raw_type: Platform raw field type
raw_path: Platform hierarchy/path if returned
country_scope: Applicable country/region
motata_payload_key: Later payload key for motata/API adapter
motata_payload_value: Later payload value; blank/null if unresolved
generic_field_id: Matching generic field ID
lookup_status: resolved | suggested | missing | failed
raw_response_ref: Compact raw response summary or artifact reference
```

Rules:

- Every motata field must reference one generic field through `generic_field_id`.
- `raw_id` must be empty/null unless returned by motata or provided by the user.
- `lookup_status: resolved` requires a real `raw_id` and payload value.
- `lookup_status: suggested` can be used for motata suggestion results that need user review.
- `lookup_status: missing` means no token/account/result was available, but the lookup plan is clear.
- `lookup_status: failed` means motata was attempted and returned an error.

## Campaign Structure

Meta:

```text
campaign:
  platform: meta
  campaign_name:
  objective:
  daily_budget:
  status: draft | paused
  adsets:
    - adset_name:
      daily_budget:
      countries:
      targeting_fields_generic: [generic field IDs or embedded objects]
      targeting_fields_motata: [motata field refs or embedded objects]
      ads:
        - ad_name:
          creative_angle:
          primary_text:
          headline:
          description:
          cta:
          landing_url:
          image_prompt_id:
```

TikTok:

```text
campaign:
  platform: tiktok
  campaign_name:
  objective:
  daily_budget:
  status: draft | paused
  adgroups:
    - adgroup_name:
      daily_budget:
      countries:
      targeting_fields_generic: [generic field IDs or embedded objects]
      targeting_fields_motata: [motata field refs or embedded objects]
      ads:
        - ad_name:
          creative_angle:
          ad_text:
          call_to_action:
          landing_url:
          image_prompt_id:
```

Do not call TikTok groups `adsets` in the export structure. Use `adgroups`.

## Validation Report

Include:

```text
channels_valid: true/false
budget_valid: true/false
ad_image_parity_valid: true/false
targeting_traceability_valid: true/false
missing_motata_lookups: list of generic_field_id + recommended command
risk_warnings: list
assumptions: list
```
