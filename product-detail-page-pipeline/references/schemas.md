# Output Schemas

## Product profile

```json
{
  "visible_facts": [{"fact": "", "confidence": "high|medium|low", "source": ""}],
  "supplied_facts": [{"fact": "", "source": ""}],
  "selling_points": [{"point": "", "priority": 1, "evidence_level": "", "evidence": "", "visually_provable": true}],
  "constraints": {"must_show": [], "must_not_distort": [], "sensitive_claims": []},
  "discarded_claims": [{"claim": "", "reason": ""}],
  "assumptions": []
}
```

## Buyer concerns

```json
{"concerns": [{"id": "C1", "buyer_question": "", "selling_point": "", "evidence": "", "proof_type": "", "priority": 1, "risk_if_unproven": ""}]}
```

## Screen plan

```json
{"screens": [{"screen_id": 1, "role": "", "buyer_question": "", "message": "", "headline": "", "subheadline": "", "layout": "", "visual_evidence": [], "success_criterion": ""}]}
```

## Prompt pack

```json
{
  "shared_visual_dna_block": "",
  "platform_constraints": "",
  "screens": [{
    "screen_id": 1,
    "role": "",
    "final_prompt_en": "",
    "negative_prompt": "",
    "text_to_render": {
      "language": "",
      "verbatim": true,
      "kicker": "",
      "headline": "",
      "subheadline": "",
      "badges": [],
      "placement": "",
      "typography": "",
      "max_lines": {"headline": 2, "subheadline": 2}
    },
    "buyer_logic": {"buyer_question": "", "visual_evidence_to_show": [], "claim_to_avoid_overstating": []},
    "backend_params": {"aspect_ratio": "", "size": "", "reference_images": []},
    "assembly_plan": {"order": 1, "crop_after_generation": true, "stitch_into_long_page": true, "notes": "Preserve the original; crop only the assembly derivative when the backend canvas differs from the target ratio."}
  }]
}
```

## Generation review

```json
{
  "status": "awaiting_user_confirmation",
  "generation_started": false,
  "prompt_pack_sha256": "",
  "page_count": 0,
  "pages": [{"screen_id": 1, "order": 1, "role": "", "buyer_question": "", "visual_content": "", "customer_copy": {}, "copy_layout": {}, "evidence_to_show": [], "claims_to_avoid": [], "aspect_ratio": "", "render_size": "", "reference_images": []}]
}
```

## Generation approval

Create only after explicit user approval. Bind it to the reviewed Prompt Pack hash.

```json
{"approved": true, "approval_scope": "all_pages_in_prompt_pack|selected_pages", "approved_screen_ids": ["1"], "confirmation": "开始生图", "prompt_pack_sha256": "", "review_sha256": "", "page_count": 0}
```
