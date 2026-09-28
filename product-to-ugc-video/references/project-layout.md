# Project Layout

Each run creates a project folder under `outputs/product_to_ugc/<project-slug>` unless `--project-dir` overrides it.

## Top-Level Files

- `project.json`: run metadata and high-level planner details

## Folders

- `inputs/`
  - copied product image
  - optional copied character reference image
  - `description.txt`
- `planning/`
  - `plan.json`
  - `plan_summary.md`
  - agent-supplied or heuristic plan; no text API request
- `character_reference/`
  - generated stable character reference image
  - `responses/` with MCP task journals
- `prompts/frames/`
  - one prompt text file per continuous keyframe
- `prompts/character_reference.prompt.txt`
  - prompt for generating the stable character reference
- `prompts/segments/`
  - one video-model prompt text file and one voiceover text file per segment
- `continuous_frames/`
  - generated keyframe images
  - `responses/` with MCP task journals
- `video_segments/`
  - generated mp4 segment files
  - `responses/` with MCP task journals
- `manifests/`
  - `assembly_manifest.json` for adjacent-frame segment stitching
  - `merge_manifest.json` for final concat metadata
- `logs/`
  - `command_log.json`
- `merged/`
  - optional merged final video if ffmpeg is available

## Assembly Manifest

The Phase 2 script writes `manifests/assembly_manifest.json` with:

- segment ids
- source clip paths
- source frame paths
- duration
- voiceover text
- suggested tail trim per segment

This manifest is designed for a later stitching phase with ffmpeg or another editor.

Generated media retain exact downloaded `*.original` files. Image delivery files use their declared encoding. Task journals preserve clientRequestId/taskId for recovery.
