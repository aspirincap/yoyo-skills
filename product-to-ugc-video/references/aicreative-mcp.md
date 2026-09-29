# AI Creative MCP branch

This branch routes `standard-product-image`, `product-detail-page-pipeline`, `script-to-storyboard-video` and `product-to-ugc-video` through AI Creative MCP. It does not call NewAPI, OpenAI image endpoints or Gemini generation endpoints. The other skills keep their original backends.

## Setup

Use Python 3.11+ and Pillow (`python3 -m pip install Pillow`). Video assembly also uses ffmpeg/ffprobe. Each of the four skills bundles its own runtime, so it can be installed individually.

If Codex already has an HTTP MCP server named `aicreative`, the runtime reads its URL and authentication from `~/.codex/config.toml`. It does not copy or print the Token. The configured URL determines the environment (Beta or production). `AICREATIVE_MCP_SERVER` selects another server name; `AICREATIVE_CODEX_CONFIG` selects another TOML file.

Outside Codex, configure these environment variables through your secret manager or shell environment:

- `AICREATIVE_MCP_URL`: the full MCP endpoint, e.g. `https://aicreative-api-beta.creatiads.com/api/mcp`.
- `AICREATIVE_MCP_TOKEN`: the authorized Token, with or without the `Bearer ` prefix.
- `AICREATIVE_MCP_PARENT_ORIGIN`: optional `X-Embed-Parent-Origin` required by your deployment.
- `AICREATIVE_IMAGE_MODEL_ID`: numeric image `modelConfigId`; Beta default `2102` (Seedream 4.5).
- `AICREATIVE_VIDEO_MODEL_ID`: numeric video `modelConfigId`; storyboard/direct video default `1103` (Seedance 2.0), character-led UGC default `1108` (Wan 2.7, person references + both frame anchors, native audio ON required).

An explicit endpoint override does not inherit credentials from a different Codex endpoint. `AI_GATEWAY_*` and legacy gateway credentials are not consulted by these four skills.

From an installed skill directory, check connectivity and discover current model capabilities:

```bash
python3 scripts/aicreative_mcp.py check
python3 scripts/aicreative_mcp.py models --type IMAGE
python3 scripts/aicreative_mcp.py models --type VIDEO
```

The defaults reflect the tested Beta account; use model IDs available to your account. The runtime reads `get_model_parameters` before new submissions and checks prompt length, image count/known dimensions/pixel count, frame requirements, duration and parameter enums. Omitted image resolution is filled from the model's declared default and persisted in the task journal, because the tested server rejects an omitted `resolutionKey`.

## Local references: bind once, reuse by content

MCP `upload_media` imports an accessible HTTPS URL. It does **not** upload local bytes, accept base64 or expose a local upload endpoint. Do not invent an endpoint or silently publish local files to an unrelated hosting service.

For a local source image already present in AI Creative, bind the file to its matching asset in your account:

```bash
python3 scripts/aicreative_mcp.py bind --file /absolute/path/product.png --asset-id 123
```

Alternatively, import a matching, service-accessible source URL and bind it:

```bash
python3 scripts/aicreative_mcp.py bind \
  --file /absolute/path/product.png \
  --source-url https://your-approved-media-host.example/product.png
```

The file and remote asset must contain the same reference image. If only a local file exists, obtain a matching asset ID or use your approved media hosting/upload process first. This requirement is exposed as an actionable error before generation submission.

Bindings are cached by file SHA-256 under `~/.cache/aicreative-mcp/`, scoped to the MCP endpoint and credential fingerprint. Copies of the same file reuse the binding. Generated images are automatically bound to their returned asset IDs, so subsequent storyboards/keyframes need no new upload. `AICREATIVE_CACHE_DIR` overrides the cache root. A changed credential uses a new scope by default. For same-account token rotation, set a stable `AICREATIVE_ACCOUNT_SCOPE` label before the first run; keep that label for that account only. The journal and bindings can then survive token renewal. Without a stable label, keep the original credential for recovery or rebind in the new scope.

The low-level image CLI also accepts HTTPS URLs or `asset:123` directly as `--image`; orchestrators that validate/copy local inputs still use bound local files.

## Image and video commands

```bash
python3 scripts/image_tool.py edit \
  --model 2102 --image /absolute/path/product.png \
  --prompt 'Faithful product photograph on a white background; preserve the original structure.' \
  --size 1024x1024 --output outputs/product.png --save-json outputs/product.json
```

`--size` is a **canvas aspect-ratio hint**, not an exact output dimension. `--resolution 2K`/`4K` requests a model-supported tier. Actual dimensions come from the output file. PNG/JPEG/WebP delivery files are encoded correctly; the exact downloaded source is retained beside them as `*.original`.

Video-enabled skills also bundle:

```bash
python3 scripts/generate_video.py \
  --model 1103 --prompt-file prompts/clip.txt \
  --first-frame /absolute/path/start.png --last-frame /absolute/path/end.png \
  --duration 5 --ratio 9:16 --resolution 720P --no-generate-audio \
  --output outputs/clip.mp4 --save-json outputs/clip.json
```

Use `--image` for general references, or `--first-frame`/`--last-frame` for anchors. Never mix the two modes. Public visibility defaults to `OFF`; the direct CLIs accept `--visibility ON` when requested. Image references and native generated audio are supported according to model configuration; voice cloning, TTS and audio-reference input are not provided by this adapter.

`--dry-run` makes no network calls and does not require credentials or bindings. It shows unresolved references explicitly; live validation still happens before a real submission.

## Recovery and output contracts

- The response JSON is a resumable task journal: request, `clientRequestId`, `taskId`, model configuration, observations and downloaded assets. Credentials are excluded.
- Repeat the **same command with the same output and journal** to resume. An accepted submission whose response was lost is replayed with the same persisted ID. A polling timeout does not submit a second task.
- Changed inputs, model, output or credential scope cannot reuse the old journal. For intentional regeneration use a new output/journal (or a new project).
- A per-journal lock prevents concurrent duplicate submissions. Transient query/transport failures have bounded retries. `upload_media` is not automatically retried because it is not declared idempotent.
- During aggregate `PROCESSING`, a transient item `FAILED` does not terminate polling. Aggregate `SUCCESS` with valid results is accepted even if historical item errors remain; raw errors stay in the journal for diagnosis.
- Partial results are downloaded and preserved but the command exits unsuccessfully if requested results are incomplete. Existing task IDs are kept for inspection.
- Images print `saved=/absolute/path` for the existing orchestrators. Original media and project/assembly manifests remain available.
- MCP currently has no equivalent controls for masks, transparent backgrounds, seeds or arbitrary provider metadata. Unsupported options fail explicitly. Put semantic exclusions in the prompt; this is not a dedicated negative-prompt parameter.

UGC planning is performed by the calling agent and supplied with `--plan-file`, or by the explicit local `--heuristic-plan`. No text API is called. Existing storyboard confirmation and detail-page approval/hash validation remain in place.
