# Motata Targeting Reference

Use motata only for read-only targeting lookup in this skill. Do not create campaigns, update budgets, or activate delivery.

## Meta Commands

Use these command groups:

```bash
motata meta targeting locations <query> --account-id <META_ACCOUNT_ID> --access-token <META_ACCESS_TOKEN> --json --limit <N>
motata meta targeting interests <query> --account-id <META_ACCOUNT_ID> --access-token <META_ACCESS_TOKEN> --json --limit <N>
motata meta targeting suggestions --interests <INTEREST_ID...> --account-id <META_ACCOUNT_ID> --access-token <META_ACCESS_TOKEN> --json --limit <N>
motata meta targeting behaviors --account-id <META_ACCOUNT_ID> --access-token <META_ACCESS_TOKEN> --json --limit <N>
motata meta targeting demographics --account-id <META_ACCOUNT_ID> --access-token <META_ACCESS_TOKEN> --json --limit <N>
motata meta targeting estimate --account-id <META_ACCOUNT_ID> --access-token <META_ACCESS_TOKEN> --json --targeting '<TARGETING_JSON>'
```

Recommended payload keys:

- `targeting.geo_locations` for locations.
- `targeting.interests` for interests.
- `targeting.behaviors` for behaviors.
- `targeting.demographics` or the platform-specific returned key for demographic fields.
- `targeting.age_min`, `targeting.age_max`, and `targeting.genders` for age/gender when applicable.

If token/account is missing, produce a `lookup_status: missing` motata field with the exact command that should be run once credentials are available.

## TikTok Commands

Use these command groups:

```bash
motata tiktok targeting regions --advertiser-id <TIKTOK_ADVERTISER_ID> --access-token <TIKTOK_ACCESS_TOKEN> --json
motata tiktok targeting list --advertiser-id <TIKTOK_ADVERTISER_ID> --access-token <TIKTOK_ACCESS_TOKEN> --json --location-id <LOCATION_ID> --scene <SCENE>
motata tiktok targeting search --advertiser-id <TIKTOK_ADVERTISER_ID> --access-token <TIKTOK_ACCESS_TOKEN> --json --payload-json '<PAYLOAD_JSON>'
motata tiktok targeting info --advertiser-id <TIKTOK_ADVERTISER_ID> --access-token <TIKTOK_ACCESS_TOKEN> --json --payload-json '<PAYLOAD_JSON>'
```

Recommended payload keys depend on returned raw type. Common adapter keys include:

- `targeting.location_ids` for regions.
- `targeting.interest_category_ids` for interest categories.
- `targeting.behavior_ids` for behavior fields.
- `targeting.age_groups`, `targeting.gender`, `targeting.languages`, and device-related keys when returned by list/info.

If exact TikTok payload keys are not present in the response, keep `motata_payload_key` as the best-known adapter path and include the raw response summary for adapter review.

## Query Seed Strategy

For each product, generate and try seeds in this order:

1. Product category terms.
2. Core use-case terms.
3. Audience/persona terms.
4. Pain-point terms.
5. Competitor or adjacent-category terms when provided or discoverable.
6. Broad category terms if exact queries return no usable fields.

## Fallback Behavior

When no token or account context is available:

- Still produce generic fields based on product strategy.
- Produce motata fields as lookup plans with `lookup_status: missing`.
- Keep `raw_id`, `raw_name`, and `motata_payload_value` empty/null unless supplied by the user.
- Add each unresolved lookup to `validation_report.missing_motata_lookups`.

When motata returns an error:

- Preserve the command and source query.
- Set `lookup_status: failed`.
- Summarize the error in `raw_response_ref`.
- Do not block the strategy output unless location/region fields cannot be determined.
