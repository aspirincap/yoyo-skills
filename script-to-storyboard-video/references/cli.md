# CLI reference

Read [aicreative-mcp.md](aicreative-mcp.md) for configuration and local-reference bindings. The commands use numeric modelConfigId values, not gateway model names.

## Storyboard stage

```bash
python3 scripts/aicreative_mcp.py check
python3 scripts/aicreative_mcp.py bind --file /absolute/path/product.png --asset-id 123
python3 scripts/script_to_storyboard_video.py storyboard \
  --script-file /absolute/path/script.txt \
  --product-image /absolute/path/product.png \
  --duration 30 --project-dir /absolute/path/project
```

- Repeat `--product-image` for multiple bound local references.
- `--product-notes` adds product identity and claim constraints.
- `--segment-duration` is the maximum segment duration, default 15 seconds. Splits are balanced to keep default-model clips between 4 and 15 seconds.
- `--storyboard-count` explicitly chooses the number of valid segments.
- `--storyboard-frames` defaults to 6 panels.
- `--storyboard-size 2048x1152` is a ratio hint; exact pixels follow the model tier.
- `--image-model 2102` selects the MCP image model; `--dry-run` is offline.
- Reuse `--project-dir` with unchanged inputs to recover the original tasks. Use a new project for revisions.

## Video stage

After storyboard approval:

```bash
python3 scripts/script_to_storyboard_video.py video \
  --project-dir /absolute/path/project --confirmed --parallel 2
```

`--video-model` defaults to `AICREATIVE_VIDEO_MODEL_ID` or 1103. `--ratio` defaults to 9:16, `--resolution` to 720P. Audio defaults to ON; use `--no-generate-audio` for silent output. The storyboard is passed as a general reference image. The MCP has no explicit watermark toggle.

`--poll-interval`, `--max-polls` and `--parallel` control waiting and concurrency. A polling timeout preserves task IDs; repeat the same command to resume without resubmitting completed tasks. Check actual dimensions, duration and audio with ffprobe before delivery.
