# AI Creative MCP branch

This branch routes `standard-product-image`, `product-detail-page-pipeline`, `script-to-storyboard-video` and `product-to-ugc-video` through AI Creative MCP. It does not call NewAPI, OpenAI image endpoints or Gemini generation endpoints. `open-tiktok-script` separately uses the SpotMax `describe_video` HTTP API; see its own README for local-test versus production authentication. The remaining skills keep their original backends.

## Connection selection

Prefer the AI Creative MCP tools already available to the calling agent. Discover the platform's tool namespace (normally `aicreative`; hosts may expose an alias) and use `list_models`, `get_model_parameters`, `upload_media`, `submit_generation_task` and `get_generation_task` through that same connection. Do not switch account/environment merely to find a particular tool prefix. A successful `list_models` confirms that model discovery works on that connection; generation still uses its actual server permissions and the credit confirmation below.

**Platform tools and the bundled Python CLI are independent transports.** If platform tools work, a missing CLI URL, Token or `~/.codex/config.toml` is not an authorization failure and is not a reason to stop. Use the tools directly; do not extract a connector Token, request it again, demand that Runtime inject it into scripts, or run CLI `check` as a prerequisite. A real permission error from a platform tool should be reported as that tool's error.

### Standalone CLI setup (optional)

Use the CLI when platform tools are unavailable or a configured local workflow is preferred. Python 3.11+ and Pillow are required; video assembly also uses ffmpeg/ffprobe. Each skill bundles its runtime and can be installed individually. The CLI cannot inherit an opaque platform connector session.

The CLI can read an HTTP server named `aicreative` from `~/.codex/config.toml`, without printing its Token. The configured endpoint selects Beta or production. `AICREATIVE_MCP_SERVER` selects another server name; `AICREATIVE_CODEX_CONFIG` selects another TOML file. Alternatively, configure through your existing secret manager or environment:

- `AICREATIVE_MCP_URL`: the full MCP endpoint.
- `AICREATIVE_MCP_TOKEN`: the authorized Token, with or without the `Bearer ` prefix.
- `AICREATIVE_MCP_PARENT_ORIGIN`: optional `X-Embed-Parent-Origin` required by your deployment.
- `AICREATIVE_IMAGE_MODEL_ID`: image `modelConfigId`; tested Beta default `2102` (Seedream 4.5).
- `AICREATIVE_VIDEO_MODEL_ID`: video `modelConfigId`; storyboard default `1103` (Seedance 2.0), character-led UGC default `1108` (Wan 2.7).

An explicit endpoint override does not inherit credentials from a different endpoint. Legacy gateway credentials are not consulted. These commands diagnose only the local CLI:

```bash
python3 scripts/aicreative_mcp.py check
python3 scripts/aicreative_mcp.py models --type IMAGE
python3 scripts/aicreative_mcp.py models --type VIDEO
```

For either transport, select model IDs available to the connected account and read current parameter definitions. Check prompt length, reference count/dimensions, frames, duration, ratio, resolution and audio support. Set the declared default `resolutionKey` explicitly if omitted; the tested server requires it. Native requests must also set `count`, the intended aspect ratio and `publicVisibilityKey: "OFF"` explicitly unless the user requests public results; do not inherit a server default of `ON`. Do not assume Beta defaults exist on another deployment.

## Credit approval gate

The gate is **disclose the batch's estimated credits, then obtain the user's agreement before submission**. It does not require a particular transport or a special approval file. Compute `xx = sum(current model minPoints × new output count)` and say **“大约需要消耗 xx 积分”**, followed by “按模型起步积分估算，实际扣费可能随参数变化”. This is not an exact quote or spending cap. Use `minPoints` returned by `list_models` or `get_model_parameters`; if absent/invalid, fetch the missing price before submission. A returned zero is only a starting estimate, not a promise of free generation.

Show the batch contents, models, counts and relevant parameters with the estimate. Wait for an actual affirmative user reply; connection authorization or historical unlimited-spend permission alone does not approve this estimate. One reply can cover both creative approval and credits when both were presented together. An existing agreement to this same batch remains valid after a connection repair or a switch of transport; do not ask twice.

| Flow | Estimate scope |
| --- | --- |
| Standard product image | Requested new images |
| Detail page | All selected pages, alongside their content review |
| Storyboard | All new storyboard sheets |
| Storyboard video | New video segments, after storyboard review |
| UGC | New character reference, keyframes and video segments; exclude existing/skipped outputs |

### Native MCP workflow (preferred)

1. Reuse prepared prompts and assets. Call `list_models` / `get_model_parameters` through the connected platform tools; no CLI configuration check is needed. Preserve the user's requested model when available.
2. Resolve references through that same connection. Reuse returned asset IDs or call `upload_media` with an authorized, accessible media URL. Local byte uploads are not exposed; see the reference section below. Do not treat an unresolved local reference as an account authorization error.
3. Disclose the estimate for all new jobs in the current stage and obtain agreement. Conversation history is sufficient evidence; note the estimate, scope and actual reply in the existing project log. **Neither a CLI receipt nor `approve-credits` is required.** Never invent a user reply.
4. Call the platform's `submit_generation_task` directly for each approved job, using the tool's current schema. This is the supported native path, not a bypass. Before each call, persist its request and unique `clientRequestId` in the project log; afterwards record `taskId`. Do not start new jobs beyond the approved scope.
5. Query `get_generation_task` for accepted jobs, preserve result asset IDs and URLs, download outputs when needed and update the project's manifests. During `PROCESSING`, an item error can be historical; use the aggregate status. Report incomplete results without silently regenerating them.

Keep the connection/transport label, model, actual parameters, prompt/reference identifiers, estimate, user reply, `clientRequestId`, `taskId`, result assets, status and elapsed time in ordinary project logs. Never store connector credentials. Native logs need not imitate CLI hash receipts. Use the same filenames/output structure expected by each skill; only mark a file or task complete when it actually exists/succeeds. Do not pass native task logs off as CLI resume journals or re-run a submitting CLI over them.

On a lost submission response, reuse the same `clientRequestId` on the same connection, with the same request, to recover the accepted task. If switching transports and the account/environment cannot be verified as the same, resolve the existing task first rather than blindly replaying it. Query/download retries do not require new credit approval. A fresh paid retry after failure is a new job and needs an estimate and agreement.

Adding paid jobs, changing model/count/charge-affecting parameters or increasing the estimate requires an updated disclosure and agreement. A transport switch, output-path cleanup or equivalent prompt wording within the same approved scope does not. Material creative/reference/public-visibility changes still follow the user's content requirements. Preserve storyboard review before video and detail-page review before image generation on both paths.

### CLI credit receipts (only for CLI execution)

Run the usual command to prepare a review JSON and readable `.md`. Without approval it prints the estimate, exits with `Credit approval required` and submits zero tasks. `--dry-run` remains offline. After the user agrees, record their existing reply and rerun the same command:

```bash
python3 scripts/aicreative_mcp.py approve-credits \
  --review /absolute/path/generation.credits.json \
  --confirmation '<actual affirmative user reply to the displayed estimate>'
```

Default files are `<journal>.credits.json` for direct image/video commands, `<output-dir>/generation.credits.json` for detail pages, `<project-dir>/storyboard.credits.json` / `video.credits.json` for storyboard stages, and `<project-dir>/generation.credits.json` for UGC. Batch wrappers pass `--credit-review` to their child tools. There is no self-approval or `--yes` generation flag.

CLI receipts bind exact jobs, account, prices and source contents to persisted request IDs to prevent duplicate submissions. Rebuild a stale receipt if necessary; re-record an already valid user reply only when the batch, cost and consent scope are unchanged. For a material change, get a new agreement. Keep journals/receipts for recovery. If this CLI is unconfigured but native tools work, continue with the native workflow above instead of trying to manufacture CLI credentials or hash receipts.

The CLI's detail-page creative approval and storyboard `--confirmed` checks remain. `--skip-backend-check` cannot skip its credit gate. Custom detail-page `--image-tool` paths remain restricted to non-executing `--dry-run`; native MCP is a separate supported agent workflow, not a custom executable override.

## Local references: bind once, reuse by content

MCP `upload_media` imports an accessible HTTPS URL. It does **not** upload local bytes, accept base64 or expose a local upload endpoint. Do not invent an endpoint or silently publish local files to an unrelated hosting service.

With native tools, use matching asset IDs directly; no CLI binding/cache is required. Import an existing accessible reference URL with `upload_media`, preserving the returned asset ID for later calls. For local-only files, use an already authorized upload/hosting route or request the missing accessible source, not another account login.

For the CLI path, bind a local source image to its matching asset in your account:

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

## CLI recovery and output contracts

- The response JSON is a resumable task journal: request, `clientRequestId`, `taskId`, model configuration, observations and downloaded assets. Credentials are excluded.
- Repeat the **same command with the same output and journal** to resume. An accepted submission whose response was lost is replayed with the same persisted ID. A polling timeout does not submit a second task.
- Changed inputs, model, output or credential scope cannot reuse the old journal. For intentional regeneration use a new output/journal (or a new project).
- A per-journal lock prevents concurrent duplicate submissions. Transient query/transport failures have bounded retries. `upload_media` is not automatically retried because it is not declared idempotent.
- During aggregate `PROCESSING`, a transient item `FAILED` does not terminate polling. Aggregate `SUCCESS` with valid results is accepted even if historical item errors remain; raw errors stay in the journal for diagnosis.
- Partial results are downloaded and preserved but the command exits unsuccessfully if requested results are incomplete. Existing task IDs are kept for inspection.
- Images print `saved=/absolute/path` for the existing orchestrators. Original media and project/assembly manifests remain available.
- MCP currently has no equivalent controls for masks, transparent backgrounds, seeds or arbitrary provider metadata. Unsupported options fail explicitly. Put semantic exclusions in the prompt; this is not a dedicated negative-prompt parameter.

UGC planning is performed by the calling agent and supplied with `--plan-file`, or by the explicit local `--heuristic-plan`. No text API is called. Existing storyboard confirmation and detail-page approval/hash validation remain in place.
