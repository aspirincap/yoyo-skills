#!/usr/bin/env python3
"""Image generation/reference editing through AI Creative MCP only."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from aicreative_mcp import MCPError, generate, model_default, ratio_for_size


def safe_extra(raw):
    if raw and json.loads(raw):
        raise SystemExit('MCP extra fields cannot override core request fields; use documented options')
    return {}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['generate', 'edit']:
        p = sub.add_parser(name)
        prompts = p.add_mutually_exclusive_group(required=True)
        prompts.add_argument('--prompt')
        prompts.add_argument('--prompt-file')
        p.add_argument('--model', default=model_default('image'), help='Numeric modelConfigId')
        p.add_argument('--mcp-url', '--base-url', dest='mcp_url')
        p.add_argument('--endpoint', choices=['mcp'], default='mcp')
        p.add_argument('--size', default='1024x1024', help='Aspect-ratio hint, not an exact pixel guarantee')
        p.add_argument('--ratio')
        p.add_argument('--resolution', help='Model resolutionKey; omitted uses model default')
        p.add_argument('--count', type=int, default=1)
        p.add_argument('--visibility', choices=['ON', 'OFF'], default='OFF')
        p.add_argument('--output', required=True)
        p.add_argument('--save-json')
        p.add_argument('--credit-review', help='Approved batch credit review; default creates a per-task review')
        p.add_argument('--timeout', type=float, default=120)
        p.add_argument('--poll-interval', type=float, default=5)
        p.add_argument('--max-polls', type=int, default=120)
        p.add_argument('--dry-run', action='store_true')
        p.add_argument('--extra')
        p.add_argument('--output-format', choices=['png', 'jpeg', 'webp'])
        if name == 'edit':
            p.add_argument('--image', required=True, action='append', help='Bound local file, HTTPS URL, or asset:ID')
    args = parser.parse_args(argv)
    safe_extra(args.extra)
    prompt = Path(args.prompt_file).read_text() if args.prompt_file else args.prompt
    if args.output_format:
        suffix = {'png': '.png', 'jpeg': '.jpg', 'webp': '.webp'}[args.output_format]
        if Path(args.output).suffix.lower() not in ({'.jpg', '.jpeg'} if suffix == '.jpg' else {suffix}):
            raise MCPError('--output-format must match the output filename; originals are preserved separately')
    parameters = {'count': args.count, 'aspectRatioKey': args.ratio or ratio_for_size(args.size), 'publicVisibilityKey': args.visibility}
    if args.resolution:
        parameters['resolutionKey'] = args.resolution.upper()
    for path in generate(kind='IMAGE', model=args.model, prompt=prompt, parameters=parameters,
                         references=getattr(args, 'image', []), output=args.output, journal=args.save_json,
                         url=args.mcp_url, timeout=args.timeout, poll_interval=args.poll_interval,
                         max_polls=args.max_polls, dry_run=args.dry_run, credit_review=args.credit_review):
        print(f'saved={path}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (MCPError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
