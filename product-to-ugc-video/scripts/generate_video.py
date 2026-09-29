#!/usr/bin/env python3
"""Resumable AI Creative MCP video generation with explicit reference roles."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
from aicreative_mcp import MCPError, generate, model_default


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    prompts = p.add_mutually_exclusive_group(required=True)
    prompts.add_argument('--prompt')
    prompts.add_argument('--prompt-file')
    p.add_argument('--model', default=model_default('video'), help='Numeric modelConfigId')
    p.add_argument('--mcp-url', '--base-url', dest='mcp_url')
    p.add_argument('--image', action='append', default=[], help='General reference image (not a frame anchor)')
    p.add_argument('--first-frame')
    p.add_argument('--last-frame')
    p.add_argument('--duration', type=int, default=5)
    p.add_argument('--ratio', default='9:16')
    p.add_argument('--resolution', default='720P')
    p.add_argument('--generate-audio', action=argparse.BooleanOptionalAction, default=False)
    p.add_argument('--visibility', choices=['ON', 'OFF'], default='OFF')
    p.add_argument('--output', required=True)
    p.add_argument('--save-json')
    p.add_argument('--credit-review', help='Approved batch credit review; default creates a per-task review')
    p.add_argument('--poll-interval', type=float, default=8)
    p.add_argument('--max-polls', type=int, default=120)
    p.add_argument('--download-timeout', type=float, default=240)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args(argv)
    prompt = Path(args.prompt_file).read_text() if args.prompt_file else args.prompt
    if Path(args.output).suffix.lower() != '.mp4':
        raise MCPError('Video output must use .mp4')
    parameters = {'count': 1, 'duration': args.duration, 'aspectRatioKey': args.ratio,
                  'resolutionKey': args.resolution.upper(), 'generateAudioKey': 'ON' if args.generate_audio else 'OFF',
                  'publicVisibilityKey': args.visibility}
    for path in generate(kind='VIDEO', model=args.model, prompt=prompt, parameters=parameters,
                         references=args.image, first_frame=args.first_frame, last_frame=args.last_frame,
                         output=args.output, journal=args.save_json, url=args.mcp_url,
                         timeout=args.download_timeout, poll_interval=args.poll_interval,
                         max_polls=args.max_polls, dry_run=args.dry_run, credit_review=args.credit_review):
        print(f'saved={path}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (MCPError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
