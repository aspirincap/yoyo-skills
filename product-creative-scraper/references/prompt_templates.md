# OCR/VLM Prompt Templates

## Image Analysis Prompt

Use this contract when analyzing each product/app image. The script in `scripts/analyze_assets.py` already embeds this prompt.

Return one strict JSON object:

```json
{
  "image_type": "main_image",
  "primary_selling_point": "large_display",
  "secondary_selling_point": "easy_operation",
  "style": "clean_white",
  "layout_type": "product_with_callouts",
  "scene_type": "studio_white",
  "benefit_expression_mode": "feature",
  "visual_subjects": ["product", "hand_usage"],
  "design_elements": ["overlay_text", "callout_line", "icon"],
  "text_on_image_raw": "Extra Large Display",
  "cn_copy_summary": "突出大屏显示和易读性",
  "confidence": 0.86
}
```

## Field Guidance

- `text_on_image_raw`: OCR text exactly as shown. Keep original language.
- `cn_copy_summary`: Chinese summary for operators and designers.
- `primary_selling_point`: concise snake_case label, not a sentence.
- `style`, `layout_type`, and `scene_type`: use stable labels so rows can be grouped.
- `confidence`: model confidence from 0 to 1.
