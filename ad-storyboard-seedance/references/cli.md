# CLI Reference

## Env Setup

```bash
cd /path/to/ad-storyboard-seedance
cp .env.example .env
```

Fill `AD_STORYBOARD_BASE_URL` and at least one API key in `.env`. The scripts also accept shell exports and explicit `--base-url`.

## Storyboard Stage

```bash
python3 scripts/ad_storyboard_pipeline.py storyboard \
  --script-file /absolute/path/script.txt \
  --product-image /absolute/path/product.png \
  --duration 30 \
  --project-name my-ad \
  --api-key-env OPENAI_API_KEY,NEWAPI_API_KEY
```

Useful flags:

- `--product-image`: repeat for multiple product references
- `--product-notes`: stricter product identity/compliance notes
- `--segment-duration`: default `15`, max `15`
- `--storyboard-count`: override automatic `ceil(duration / segment_duration)`
- `--storyboard-frames`: default `6`
- `--storyboard-size`: default `2048x1152`
- `--dry-run`: print image request without spending generation

## Video Stage

```bash
python3 scripts/ad_storyboard_pipeline.py video \
  --project-dir /absolute/path/project \
  --confirmed \
  --api-key-env OPENAI_API_KEY,NEWAPI_API_KEY \
  --parallel 2
```

Useful flags:

- `--confirmed`: required for real video generation
- `--video-model`: defaults to `AD_STORYBOARD_VIDEO_MODEL`; set it to the model ID supported by your provider
- `--ratio`: default `9:16`
- `--width`: default `720`
- `--height`: default `1280`
- `--generate-audio` / `--no-generate-audio`
- `--parallel`: number of segments to generate concurrently
- `--dry-run`: inspect video payloads without submitting
