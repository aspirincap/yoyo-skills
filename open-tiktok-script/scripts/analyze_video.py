#!/usr/bin/env python3
"""Analyze a local video or media URL using the SpotMax describe_video API."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib import error, parse, request
import uuid

DEFAULT_BASE_URL = 'https://agentapi.spotmaxtech.com'
ENDPOINT_PATH = '/api/v1/describe_video'
SKILL_DIR = Path(__file__).resolve().parents[1]
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
TOKEN_FIELDS = ('cache_token', 'input_token', 'output_token', 'thought_token', 'tool_input_token', 'total_token')
LEGACY_FLAGS = {'--model', '-m', '--resolution', '-r', '--media-resolution', '--fps', '--auth-mode',
                '--api-key-env', '--max-inline-mb', '--inline-limit-mb', '--allow-large-inline'}
TOPICS = ('前2秒钩子分析', 'Creator人设与信任来源', '分镜结构', '节奏与留存',
          'TikTok-native表达', '转化设计', '西方语境安全检查', '可复制要素')


class AnalysisError(RuntimeError):
    pass


def settings():
    values = {}
    path = SKILL_DIR / '.env'
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.removeprefix('export ').split('=', 1)
            if key.strip().startswith('VIDEO_ANALYSIS_'):
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                values[key.strip()] = value
    values.update({k: v for k, v in os.environ.items() if k.startswith('VIDEO_ANALYSIS_')})
    return values


def parse_args(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    unsupported = [item.split('=', 1)[0] for item in argv if item.split('=', 1)[0] in LEGACY_FLAGS]
    if unsupported:
        raise AnalysisError('describe_video does not expose these legacy Gemini controls: ' + ', '.join(unsupported))
    cfg = settings()
    p = argparse.ArgumentParser(description=__doc__)
    media = p.add_mutually_exclusive_group(required=True)
    media.add_argument('--video', '-v', help='Local video file; TikTok share pages must be downloaded first')
    media.add_argument('--video-url', help='HTTPS media URL accessible by the service, not a TikTok share page')
    prompts = p.add_mutually_exclusive_group(required=True)
    prompts.add_argument('--prompt', '-p')
    prompts.add_argument('--prompt-file')
    p.add_argument('--output', '-o', help='Markdown result; written only after a valid analysis')
    p.add_argument('--response-json', help='Raw response; defaults to <output>.response.json')
    p.add_argument('--metadata-json', help='Run metadata; defaults to <output>.run.json')
    p.add_argument('--raw-response', action='store_true', help='Output raw JSON instead of Markdown after validation')
    p.add_argument('--base-url', default=cfg.get('VIDEO_ANALYSIS_BASE_URL') or DEFAULT_BASE_URL)
    p.add_argument('--environment', choices=['local', 'production'], default=cfg.get('VIDEO_ANALYSIS_ENV') or 'production')
    p.add_argument('--profile', choices=['general', 'tiktok'], default='general', help='tiktok requires all eight analysis sections')
    p.add_argument('--mime-type', help='Local upload MIME type, e.g. video/mp4')
    start = p.add_mutually_exclusive_group()
    start.add_argument('--start', type=float, help='Local clip start in seconds')
    start.add_argument('--start-offset', help='Local clip start, e.g. 2.5s')
    end = p.add_mutually_exclusive_group()
    end.add_argument('--end', type=float, help='Local clip end in seconds')
    end.add_argument('--end-offset', help='Local clip end, e.g. 8s')
    p.add_argument('--timeout', type=float, default=300, help='HTTP socket timeout; requests are not automatically retried')
    p.add_argument('--dry-run', action='store_true', help='Offline request preview; no key, upload or ffmpeg execution')
    args = p.parse_args(argv)
    if args.environment not in {'local', 'production'} or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise AnalysisError('Invalid environment or timeout')
    return args


def endpoint(base_url):
    u = parse.urlsplit(base_url)
    local = u.scheme == 'http' and u.hostname in {'localhost', '127.0.0.1', '::1'}
    if (u.scheme != 'https' and not local) or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise AnalysisError('Base URL must be HTTPS without credentials/query; HTTP is allowed only on loopback for tests')
    if u.path.rstrip('/') == ENDPOINT_PATH:
        return base_url.rstrip('/')
    return base_url.rstrip('/') + ENDPOINT_PATH


def media_url(value):
    u = parse.urlsplit(value)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.fragment:
        raise AnalysisError('video_url must be an HTTPS media URL without embedded credentials')
    if u.hostname == 'tiktok.com' or u.hostname.endswith('.tiktok.com'):
        raise AnalysisError('Download the TikTok share page first, then use --video with the local file')
    return value


def local_media_path(value):
    path = Path(value).expanduser().resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise AnalysisError('Local video is missing, empty or not a regular file')
    return path


def auth_headers(environment, cfg):
    if environment == 'production':
        return {}  # Never forward a leftover local-test credential in production.
    if environment != 'local':
        raise AnalysisError('Unknown environment')
    key = cfg.get('VIDEO_ANALYSIS_API_KEY', '').strip()
    if not key or key.lower().startswith(('replace_', 'your_', 'placeholder')) or '\n' in key or '\r' in key:
        raise AnalysisError('Local testing requires VIDEO_ANALYSIS_API_KEY; production omits X-API-Key')
    return {'X-API-Key': key}


def scrub(value, secret):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if k.lower() in {'x-api-key', 'authorization'} else scrub(v, secret) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, secret) for v in value]
    return value.replace(secret, '[REDACTED]') if secret and isinstance(value, str) else value


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def atomic_text(path, text):
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.analysis-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text if text.endswith('\n') else text + '\n')
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def save_json(path, data):
    if path:
        atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2))


class Multipart:
    def __init__(self, prompt, *, url=None, file=None, mime=None):
        self.boundary = 'yoyo-' + uuid.uuid4().hex
        self.file = file
        self.prefix = self.field('user_request', prompt)
        if url:
            self.prefix += self.field('video_url', url)
        if file:
            mime = mime or mimetypes.guess_type(file.name)[0] or 'video/mp4'
            if not re.fullmatch(r'video/[A-Za-z0-9.+-]+', mime):
                raise AnalysisError('A valid video/* MIME type is required')
            suffix = file.suffix if re.fullmatch(r'\.[A-Za-z0-9]{1,8}', file.suffix) else '.mp4'
            self.prefix += (f'--{self.boundary}\r\nContent-Disposition: form-data; name="video_file"; '
                            f'filename="video{suffix}"\r\nContent-Type: {mime}\r\n\r\n').encode()
        self.suffix = ('\r\n' if file else '').encode() + f'--{self.boundary}--\r\n'.encode()
        self.length = len(self.prefix) + (file.stat().st_size if file else 0) + len(self.suffix)

    def field(self, key, value):
        return f'--{self.boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()

    def __iter__(self):
        yield self.prefix
        if self.file:
            with self.file.open('rb') as f:
                yield from iter(lambda: f.read(1024 * 1024), b'')
        yield self.suffix


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AnalysisError('API redirect refused; configure the final endpoint. No analysis was retried.')


def post_multipart(url, body, headers, timeout):
    headers = {**headers, 'Content-Type': 'multipart/form-data; boundary=' + body.boundary,
               'Content-Length': str(body.length), 'Accept': 'application/json'}
    req = request.Request(url, data=body, headers=headers, method='POST')
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise AnalysisError('API response exceeds the 8 MiB local response limit')
            return response.status, response.headers, raw
    except error.HTTPError as exc:
        return exc.code, exc.headers, exc.read(MAX_RESPONSE_BYTES)
    except (error.URLError, TimeoutError, ConnectionError) as exc:
        raise AnalysisError(f'Analysis transport failed ({type(exc).__name__}); completion is unknown. No automatic retry.') from None


def extract_text(response, profile='general'):
    if not isinstance(response, dict) or response.get('error') or response.get('success') is False:
        raise AnalysisError('API returned a business error or unexpected response shape')
    if 'code' in response and response['code'] not in (0, 200, '0', '200'):
        raise AnalysisError('API returned a non-success business code')
    text = response.get('result')
    if not isinstance(text, str) or not text.strip():
        raise AnalysisError('API result must contain nonempty analysis text')
    if re.search(r'[ \t]{256,}', text):
        raise AnalysisError('Analysis contains abnormal whitespace; raw response preserved, result not accepted')
    if profile == 'tiktok':
        missing = [topic for i, topic in enumerate(TOPICS, 1)
                   if not re.search(r'^#{1,6}\s+' + str(i) + r'[.、．)）]\s*' + re.escape(topic), text, re.M)]
        if missing:
            raise AnalysisError('Incomplete eight-dimension analysis: ' + ', '.join(missing))
    return text.strip()


def seconds(value):
    if value is None:
        return None
    try:
        number = float(str(value).removesuffix('s'))
    except ValueError:
        raise AnalysisError('Clip offsets must be seconds, e.g. 2.5 or 2.5s') from None
    if not math.isfinite(number) or number < 0:
        raise AnalysisError('Clip offsets must be finite nonnegative seconds')
    return number


@contextmanager
def prepared_video(path, start, end):
    if start is None and end is None:
        yield path
        return
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise AnalysisError('Local clipping requires ffmpeg and ffprobe')
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)],
                           text=True, capture_output=True, timeout=60)
    try:
        duration = float(json.loads(probe.stdout)['format']['duration'])
    except (ValueError, KeyError):
        raise AnalysisError('Cannot determine source video duration for clipping') from None
    begin, finish = start or 0, end if end is not None else duration
    if not math.isfinite(duration) or not 0 <= begin < finish <= duration:
        raise AnalysisError('Clip must satisfy 0 <= start < end <= source duration')
    with tempfile.TemporaryDirectory(prefix='yoyo-video-clip-') as tmp:
        clipped = Path(tmp) / 'clip.mp4'
        done = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-ss', str(begin),
                               '-i', str(path), '-t', str(finish-begin), '-map', '0:v:0', '-map', '0:a?',
                               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-c:a', 'aac',
                               '-movflags', '+faststart', str(clipped)], capture_output=True, timeout=300)
        if done.returncode or not clipped.is_file() or not clipped.stat().st_size:
            raise AnalysisError('Local video clipping failed before upload')
        yield clipped


def main(argv=None):
    clock_start = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    args = parse_args(argv)
    cfg = settings()
    secret = cfg.get('VIDEO_ANALYSIS_API_KEY', '').strip()
    target = endpoint(args.base_url)
    prompt = Path(args.prompt_file).expanduser().read_text(encoding='utf-8') if args.prompt_file else args.prompt
    if not prompt.strip():
        raise AnalysisError('A nonempty user_request is required')
    path = local_media_path(args.video) if args.video else None
    url = media_url(args.video_url) if args.video_url else None
    start = seconds(args.start_offset if args.start_offset is not None else args.start)
    end = seconds(args.end_offset if args.end_offset is not None else args.end)
    if (start is not None or end is not None) and not path:
        raise AnalysisError('Clip offsets require a local --video; they cannot be sent to describe_video')
    if end is not None and end <= (start or 0):
        raise AnalysisError('Clip end must be greater than start')
    response_path = args.response_json or (str(args.output)+'.response.json' if args.output else None)
    metadata_path = args.metadata_json or (str(args.output)+'.run.json' if args.output else None)
    outputs = [Path(p).expanduser().resolve() for p in (args.output, response_path, metadata_path) if p]
    if len(outputs) != len(set(outputs)) or any(p == path or (args.prompt_file and p == Path(args.prompt_file).expanduser().resolve()) for p in outputs):
        raise AnalysisError('Output, response, metadata, source and prompt paths must not overlap')
    source = {'type': 'file', 'name': path.name, 'bytes': path.stat().st_size, 'sha256': sha256(path)} if path else {
        'type': 'url', 'url': parse.urlunsplit(parse.urlsplit(url)._replace(query=''))}
    metadata = {'endpoint': target, 'environment': args.environment, 'profile': args.profile, 'source': source,
                'promptSha256': hashlib.sha256(prompt.encode()).hexdigest(), 'promptCharacters': len(prompt),
                'clip': {'startSeconds': start, 'endSeconds': end, 'timestampsRelativeToClip': start is not None or end is not None}}
    if args.dry_run:
        print(json.dumps({**metadata, 'method': 'POST', 'fields': ['user_request', 'video_file' if path else 'video_url'],
                          'sendsTestKey': args.environment == 'local', 'offline': True}, ensure_ascii=False, indent=2))
        return 0
    headers = auth_headers(args.environment, cfg)
    metadata['startedAt'] = started_at
    metadata['status'] = 'failed'
    try:
        with prepared_video(path, start, end) as upload:
            mime = 'video/mp4' if upload and upload != path else args.mime_type
            body = Multipart(prompt, url=url, file=upload, mime=mime)
            metadata['multipartBytes'] = body.length
            network_start = time.monotonic()
            status, response_headers, raw = post_multipart(target, body, headers, args.timeout)
            metadata['requestSeconds'] = round(time.monotonic()-network_start, 3)
            metadata['httpStatus'] = status
            metadata['responseContentType'] = response_headers.get('Content-Type', '')
            if response_headers.get('X-Request-Id'):
                metadata['requestId'] = response_headers['X-Request-Id']
            try:
                response = scrub(json.loads(raw), secret)
            except (ValueError, UnicodeDecodeError):
                save_json(response_path, {'httpStatus': status, 'unparsedBody': scrub(raw.decode(errors='replace'), secret)})
                raise AnalysisError(f'HTTP {status}: response is not valid JSON; analysis not accepted') from None
            save_json(response_path, response)
            if status != 200:
                raise AnalysisError(f'HTTP {status}: analysis failed; raw response preserved. No automatic retry.')
            metadata['usage'] = {k: response[k] for k in TOKEN_FIELDS if isinstance(response, dict) and k in response}
            text = extract_text(response, args.profile)
            output = json.dumps(response, ensure_ascii=False, indent=2) if args.raw_response else text
            if args.output:
                atomic_text(args.output, output)
                print(f'Result saved to: {Path(args.output).expanduser().resolve()}', file=sys.stderr)
            else:
                print(output)
            metadata['status'] = 'success'
    except (AnalysisError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        metadata['error'] = scrub(str(exc), secret)
        raise
    finally:
        metadata['finishedAt'] = datetime.now(timezone.utc).isoformat()
        metadata['elapsedSeconds'] = round(time.monotonic()-clock_start, 3)
        save_json(metadata_path, scrub(metadata, secret))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AnalysisError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(scrub(str(exc), settings().get('VIDEO_ANALYSIS_API_KEY', '').strip()), file=sys.stderr)
        raise SystemExit(1)
