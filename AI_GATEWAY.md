# AI Gateway Configuration

Configure any NewAPI-compatible model gateway once and reuse it across supported skills.

## Configure

From a cloned repository:

```bash
python3 shared/ai-gateway/configure_ai_gateway.py
```

From an individually installed supported skill:

```bash
python3 scripts/configure_ai_gateway.py
```

The command securely prompts for the token and writes:

```text
~/.config/ai-gateway/config.env
```

The token is not printed, and the file is written with owner-only permissions.

## Variables

```env
AI_GATEWAY_BASE_URL=https://your-gateway.example.com
AI_GATEWAY_API_KEY=your-model-api-token
AI_TEXT_MODEL=your-text-model
AI_VISION_MODEL=your-vision-model
AI_IMAGE_MODEL=your-image-model
AI_IMAGE_SUPPORTED_SIZES=1024x1024,1024x1536,1536x1024
AI_VIDEO_MODEL=your-video-model
```

Only the base URL and API key are always required. Configure model IDs for the capabilities used by the installed skill.

The base URL may use HTTP or HTTPS. HTTPS uses the system's default certificate verification; the bundled clients do not add a global certificate-bypass option.

## Supported skills

- `product-creative-scraper`: vision model through `/v1/chat/completions`
- `open-tiktok-script`: vision/video understanding through `/v1beta/models/{model}:generateContent`
- `script-to-storyboard-video`: image generation plus asynchronous video generation
- `product-to-ugc-video`: text planning, image generation, and asynchronous video generation
- `product-detail-page-pipeline`: per-screen image generation with approval-gated local assembly

Gateway implementations vary. A gateway that exposes only chat models cannot provide image or video generation merely because it accepts NewAPI-style authentication.

## Precedence and compatibility

Values are resolved in this order:

1. shell environment
2. skill-local `.env`
3. `~/.config/ai-gateway/config.env`
4. script defaults

Existing `GEMINI_*`, `OPENAI_*`, `NEWAPI_*`, `UGC_*`, `AD_STORYBOARD_*`, `IMAGE_API_*`, and `VIDEO_API_*` variables remain fallback aliases during migration.

To inspect status without revealing the token:

```bash
python3 shared/ai-gateway/configure_ai_gateway.py --check
```

For an individually installed skill, use `python3 scripts/configure_ai_gateway.py --check` from that skill directory.
