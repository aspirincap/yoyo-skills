---
name: ad-campaign-workflow
description: Platform-independent Meta and TikTok advertising workflow planner. Use when a user asks to analyze a product URL or product brief and produce a paid-media plan, campaign/adset/ad or campaign/adgroup/ad structures, audience targeting, ad copy, image prompts, or a delivery-ready targeting package with both generic targeting fields and motata CLI/API-consumable targeting fields. Excludes Google by default and never creates live ads or spends budget unless another skill/tool is explicitly requested.
---

# Ad Campaign Workflow

## Overview

Use this skill to turn a product URL or product brief into a Meta/TikTok advertising preparation package. Keep the workflow platform-execution independent: produce strategy, structures, targeting fields, copy, image prompts, and validation reports, but do not create live ads or upload assets.

Always output targeting in two forms:

1. **Generic targeting fields** for strategy review, UI display, and cross-platform understanding.
2. **Motata targeting fields** for later motata CLI/API adapters, preserving command provenance and real platform IDs when available.

Google is out of scope. If the user asks for Google too, state that this skill only covers Meta and TikTok unless they explicitly request a separate Google workflow.

## Workflow

1. **Analyze the product**
   - Read the product URL, product brief, images, or user notes.
   - Extract product name, category, product type, selling points, proof points, use cases, audience hypotheses, risk flags, visual cues, and seed image candidates.
   - Generate targeting query seeds: category terms, pain-point terms, competitor terms, use-case terms, persona terms, and location terms.

2. **Resolve targeting fields through motata when possible**
   - Use read-only motata targeting commands for Meta and TikTok when account/token context is available.
   - Do not invent platform IDs. If motata cannot be called or returns no exact match, emit a motata field with `lookup_status: missing` or `failed` and include the suggested command/query.
   - Read `references/motata-targeting.md` for command selection and fallback behavior.

3. **Present recommendation before final structure**
   - Recommend countries, Meta/TikTok suitability, budget split, audience splits, and creative testing structure.
   - Ask the user to confirm channels, countries, total budget, channel budgets, adset/adgroup count, ads per group, and whether to generate image assets.
   - If the user says to decide automatically, use Meta 60% / TikTok 40% and label it as an assumption.

4. **Generate campaign structures**
   - Meta structure: campaign / adset / ad.
   - TikTok structure: campaign / adgroup / ad.
   - Each adset/adgroup must include `targeting_fields_generic[]` and `targeting_fields_motata[]` linked through `generic_field_id`.
   - Each ad must include angle, copy, CTA, landing URL, image prompt, and one image task.

5. **Validate before final answer**
   - No Google channels or fields.
   - No fabricated Meta/TikTok targeting IDs.
   - Each adset/adgroup has at least one location/region field.
   - Each motata field has `motata_command`, `source_query`, and `generic_field_id`.
   - Campaign budgets sum to total budget; adset/adgroup budgets sum to campaign budget.
   - Total ads equals total image prompts and image tasks.
   - High-risk categories include a manual review warning and avoid aggressive/unsupported claims.

## Final Output Sections

Include these sections when delivering the final package:

- `strategy_brief`: Product, audience, channel, country, and budget rationale.
- `targeting_fields_generic`: Generic targeting field bank.
- `targeting_fields_motata`: Motata-ready field bank with provenance.
- `campaign_structure`: Meta and/or TikTok campaign hierarchy.
- `creative_matrix`: Ad angles, copy, hooks, CTA, and audience mapping.
- `image_prompt_pack`: One image prompt/task per ad.
- `validation_report`: Checks passed, missing lookups, risk warnings, and assumptions.

For exact field contracts, read `references/output-contract.md`.

## Safety Rules

- Stay read-first when using motata.
- Never spend budget, publish ads, or switch delivery status.
- Treat motata fields as a preparation contract, not a live execution command.
- Mark all unresolved platform IDs explicitly; never substitute model guesses.
- Keep default campaign/ad/adgroup status as `draft` or `paused`.
