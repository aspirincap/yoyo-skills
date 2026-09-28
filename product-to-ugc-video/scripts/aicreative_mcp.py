#!/usr/bin/env python3
"""AI Creative Streamable HTTP client, asset bindings and resumable generation.

No NewAPI fallback. Requires Python 3.11+; image outputs also require Pillow.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import uuid


class MCPError(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def model_default(kind):
    return os.getenv(f"AICREATIVE_{kind.upper()}_MODEL_ID", "2102" if kind == "image" else "1103")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".mcp-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def https_url(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise MCPError("URL must use HTTPS without embedded credentials")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise MCPError("MCP endpoint redirects are disabled; configure the final endpoint")


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        https_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def load_config(url=None):
    # Explicit endpoint overrides never inherit credentials from another endpoint.
    config_path = Path(os.getenv("AICREATIVE_CODEX_CONFIG", str(Path.home()/".codex/config.toml")))
    server_name = os.getenv("AICREATIVE_MCP_SERVER", "aicreative-beta")
    server = {}
    if config_path.exists():
        server = tomllib.loads(config_path.read_text()).get("mcp_servers", {}).get(server_name, {})
    endpoint = url or os.getenv("AICREATIVE_MCP_URL") or server.get("url")
    if not endpoint:
        raise MCPError("Configure AICREATIVE_MCP_URL + AICREATIVE_MCP_TOKEN, or a Codex aicreative-beta HTTP server")
    https_url(endpoint)
    headers = {}
    if endpoint == server.get("url"):
        allowed = {"authorization", "x-embed-parent-origin", "language"}
        headers.update({k: v for k, v in server.get("http_headers", {}).items() if k.lower() in allowed})
        for key, variable in server.get("env_http_headers", {}).items():
            if key.lower() in allowed and os.getenv(variable):
                headers[key] = os.environ[variable]
        variable = server.get("bearer_token_env_var")
        if variable and os.getenv(variable):
            headers["Authorization"] = "Bearer " + os.environ[variable]
    headers = {k.lower(): v for k, v in headers.items()}
    if os.getenv("AICREATIVE_MCP_TOKEN"):
        headers["authorization"] = "Bearer " + os.environ["AICREATIVE_MCP_TOKEN"].removeprefix("Bearer ")
    if os.getenv("AICREATIVE_MCP_PARENT_ORIGIN"):
        headers["x-embed-parent-origin"] = os.environ["AICREATIVE_MCP_PARENT_ORIGIN"]
    headers.setdefault("language", "zh")
    if not headers.get("authorization"):
        raise MCPError("AI Creative MCP authentication is missing; gateway credentials are not used")
    return endpoint, headers


class Client:
    def __init__(self, url=None, timeout=60):
        self.url, self.headers = load_config(url)
        self.timeout = timeout
        self.sequence = 0
        self.protocol = "2025-03-26"
        self.session = None
        self.ready = False
        identity = os.getenv("AICREATIVE_ACCOUNT_SCOPE") or self.headers["authorization"]
        self.scope = hashlib.sha256((self.url + "\n" + identity).encode()).hexdigest()[:24]
        self.opener = urllib.request.build_opener(NoRedirect())

    def redact(self, text):
        for value in self.headers.values():
            if len(value) > 12:
                text = text.replace(value, "[REDACTED]").replace(value.removeprefix("Bearer "), "[REDACTED]")
        return text

    def rpc(self, method, params=None, notification=False):
        self.sequence += 1
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        if not notification:
            payload["id"] = self.sequence
        headers = {**self.headers, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.ready:
            headers["MCP-Protocol-Version"] = self.protocol
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, json.dumps(payload).encode(), headers, method="POST")
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read().decode()
                self.session = response.headers.get("Mcp-Session-Id", self.session)
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            raise MCPError(f"MCP HTTP {exc.code}", exc.code in {408, 429, 500, 502, 503, 504}) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise MCPError("MCP transport error: " + self.redact(str(exc)), True) from None
        if notification:
            return None
        try:
            if "text/event-stream" in content_type:
                messages = []
                for event in raw.replace("\r\n", "\n").split("\n\n"):
                    data = "\n".join(line[5:].lstrip() for line in event.splitlines() if line.startswith("data:"))
                    if data and data != "[DONE]":
                        messages.append(json.loads(data))
                matches = [m for m in messages if m.get("id") == payload["id"]]
                result = matches[-1] if matches else {}
            else:
                result = json.loads(raw)
        except (ValueError, TypeError):
            raise MCPError("MCP returned an invalid JSON response", True) from None
        if result.get("id") != payload["id"]:
            raise MCPError("MCP response id missing or mismatched", True)
        if "error" in result:
            err = result["error"]
            raise MCPError(self.redact(f"MCP {err.get('code')}: {err.get('message')}"), err.get("code") == -32001)
        return result["result"]

    def initialize(self):
        if self.ready:
            return
        info = self.rpc("initialize", {"protocolVersion": self.protocol, "capabilities": {}, "clientInfo": {"name": "yoyo-aicreative", "version": "1.0"}})
        self.protocol = info.get("protocolVersion", self.protocol)
        self.ready = True
        self.rpc("notifications/initialized", notification=True)

    def call(self, name, arguments):
        # Generation retries always reuse the caller's persisted clientRequestId.
        attempts = 3 if name in {"list_models", "get_model_parameters", "get_generation_task", "submit_generation_task"} else 1
        for attempt in range(attempts):
            try:
                self.initialize()
                value = self.rpc("tools/call", {"name": name, "arguments": arguments})
                data = value.get("structuredContent")
                if data is None:
                    texts = [c["text"] for c in value.get("content", []) if c.get("type") == "text"]
                    data = json.loads("\n".join(texts))
                if value.get("isError"):
                    raise MCPError(self.redact(f"{name}: {json.dumps(data, ensure_ascii=False)}"), data.get("code") in {429, 502, 503, 504})
                return data
            except MCPError as exc:
                if not exc.retryable or attempt == attempts - 1:
                    raise
                time.sleep(2 ** attempt)


class Assets:
    def __init__(self, client):
        self.client = client
        self.root = Path(os.getenv("AICREATIVE_CACHE_DIR", str(Path.home()/".cache/aicreative-mcp"))) / client.scope

    def path(self, key):
        return self.root / (hashlib.sha256(key.encode()).hexdigest() + ".json")

    def bind(self, file, asset):
        record = dict(asset)
        try:
            from PIL import Image
            with Image.open(file) as image:
                record['metadata'] = {"width": image.width, "height": image.height}
        except (ImportError, OSError):
            pass
        record["fileSizeBytes"] = Path(file).stat().st_size
        atomic_json(self.path("sha256:"+digest(file)), record)

    def resolve(self, reference):
        if reference.startswith("asset:"):
            asset_id = int(reference.split(":", 1)[1])
            if asset_id <= 0:
                raise MCPError("assetId must be positive")
            return {"assetId": asset_id}
        is_url = reference.startswith(("https://", "http://"))
        key = reference if is_url else "sha256:"+digest(Path(reference).expanduser())
        path = self.path(key)
        if path.exists():
            return json.loads(path.read_text())
        if not is_url:
            raise MCPError(f"Local reference is not bound: {reference}. Run aicreative_mcp.py bind --file FILE --asset-id ID, or --source-url HTTPS_URL. MCP has no local-file upload endpoint.")
        https_url(reference)
        value = self.client.call("upload_media", {"sourceUrl": reference, "assetType": "IMAGE", "assetName": "yoyo-reference-"+uuid.uuid4().hex[:12]})["asset"]
        atomic_json(path, value)
        return value


def ratio_for_size(size):
    try:
        w, h = map(int, size.lower().split("x"))
        if w <= 0 or h <= 0:
            raise ValueError()
        divisor = math.gcd(w, h)
        return f"{w//divisor}:{h//divisor}"
    except ValueError:
        raise MCPError("size must contain two positive dimensions, e.g. 1024x1536") from None


def enum_values(spec):
    values = spec.get("values", [])
    if isinstance(values, dict):
        return set(values)
    return {v["value"] for v in values if isinstance(v, dict) and "value" in v}


def validate(request, model, assets):
    inputs = model["inputSettings"]
    text_spec = inputs.get("text", {})
    length = len(request["prompt"])
    if length < text_spec.get("minCount", 1) or length > text_spec.get("maxCount", 10000):
        raise MCPError(f"prompt length {length} exceeds model text bounds (Unicode code points)")
    if model.get("modelType", "").upper() != request["generationType"]:
        raise MCPError("modelConfigId does not match generationType")
    refs = request.get("imageAssets", [])
    spec = inputs.get("image", {})
    if refs and (not spec.get("visibility") or len(refs) > spec.get("maxCount", 0)):
        raise MCPError("imageAssets exceeds the model reference-image limit")
    frame = request.get("frame", {})
    if frame:
        spec = inputs.get("frame", {})
        if not spec.get("visibility") or not frame.get("firstFrame"):
            raise MCPError("frame requires a supported firstFrame")
        if frame.get("lastFrame") and spec.get("type") != "FIRST_LAST":
            raise MCPError("selected model does not support lastFrame")
        if refs and "image" in spec.get("forbiddenInputs", []):
            raise MCPError("frame cannot be combined with imageAssets")
    media_spec = inputs.get("frame" if frame else "image", {})
    for asset in assets:
        dimensions = asset.get("metadata") or {}
        for axis in ["Width", "Height"]:
            value = dimensions.get(axis.lower())
            if value is not None and not media_spec.get("min"+axis, 0) <= value <= media_spec.get("max"+axis, float("inf")):
                raise MCPError("reference image dimensions violate model constraints")
        if asset.get("fileSizeBytes", 0) > media_spec.get("maxSizeMb", float("inf"))*1024*1024:
            raise MCPError("reference file exceeds model size limit")
    names = {"count": "count", "duration": "duration", "resolutionKey": "resolution", "aspectRatioKey": "aspectRatio", "generateAudioKey": "generateAudio", "qualityKey": "quality"}
    for key, value in request["parameters"].items():
        if key == "publicVisibilityKey":
            spec = (model.get("businessSettings") or {}).get("publicVisibility", {})
        else:
            spec = model["outputSettings"].get(names.get(key, key), {})
        # visibility describes the product UI, not whether a bounded API field is accepted.
        values = enum_values(spec)
        supported = spec.get("maxCount", 0) > 0 if key in {"count", "duration"} else bool(values)
        if not supported:
            raise MCPError(f"parameter {key} is not supported by this model")
        if values and value not in values:
            raise MCPError(f"unsupported {key}: {value}; allowed: {sorted(values)}")
        if key in {"count", "duration"} and not spec.get("minCount", 0) <= value <= spec.get("maxCount", float("inf")):
            raise MCPError(f"{key} is outside model bounds")


@contextmanager
def job_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as f:
        if os.name == "nt":
            import msvcrt
            f.write(b"0"); f.flush(); f.seek(0)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise MCPError("This generation output is already in use") from None
        else:
            import fcntl
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise MCPError("This generation output is already in use") from None
        try:
            yield
        finally:
            if os.name == "nt":
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


def download_result(asset, destination, generation_type, timeout):
    https_url(asset["url"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    original = destination.with_name(destination.name + ".original")
    temp = original.with_name(original.name + ".part")
    try:
        # Do not forward the MCP credential to media storage.
        with urllib.request.build_opener(HTTPSRedirect()).open(asset["url"], timeout=timeout) as response, temp.open("wb") as f:
            shutil.copyfileobj(response, f)
        if not temp.stat().st_size:
            raise MCPError("Result download was empty")
        os.replace(temp, original)
        if generation_type == "IMAGE":
            from PIL import Image
            with Image.open(original) as im:
                im.load()
                fmt = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}.get(destination.suffix.lower())
                if not fmt:
                    raise MCPError("Image output must use .png, .jpg, .jpeg or .webp")
                if im.format == fmt:
                    shutil.copyfile(original, destination)
                else:
                    (im.convert("RGB") if fmt == "JPEG" else im).save(destination, format=fmt)
        else:
            shutil.copyfile(original, destination)
    finally:
        temp.unlink(missing_ok=True)
    return {"path": str(destination.resolve()), "original": str(original.resolve()), "sha256": digest(destination), "asset": asset}


def generate(*, kind, model, prompt, parameters, references, first_frame=None, last_frame=None,
             output, journal=None, url=None, timeout=60, poll_interval=5, max_polls=120,
             dry_run=False, client=None):
    if not prompt.strip() or poll_interval < 0 or max_polls < 1:
        raise MCPError("Nonempty prompt and valid polling limits are required")
    if last_frame and not first_frame:
        raise MCPError("lastFrame requires firstFrame")
    if first_frame and references:
        raise MCPError("Use frame anchors or reference images, not both")
    request = {"generationType": kind, "modelConfigId": int(model), "prompt": prompt, "parameters": parameters}
    if dry_run:
        print(json.dumps({"provider": "aicreative-mcp", "tool": "submit_generation_task", "argumentsBeforeAssetResolution": request,
                          "referenceInputs": references, "firstFrameInput": first_frame, "lastFrameInput": last_frame,
                          "note": "Offline only: resolve assets and validate live model configuration before submission"}, ensure_ascii=False, indent=2))
        return []
    if kind == "IMAGE":
        try:
            from PIL import Image  # Verify the local encoder before submitting paid work.
        except ImportError:
            raise MCPError("Pillow is required for image output; install the skill requirements first") from None
    output = Path(output).resolve()
    journal = Path(journal).resolve() if journal else output.with_suffix(output.suffix+".mcp.json")
    if output == journal:
        raise MCPError("Output and journal paths must differ")
    client = client or Client(url, min(timeout, 60))
    assets = Assets(client)
    with job_lock(journal.with_suffix(journal.suffix+".lock")):
        records = [assets.resolve(ref) for ref in references]
        if records:
            request["imageAssets"] = [{k: a[k] for k in ["assetId", "url"] if k in a} for a in records]
        if first_frame:
            anchors = {"firstFrame": assets.resolve(first_frame)}
            if last_frame:
                anchors["lastFrame"] = assets.resolve(last_frame)
            records = list(anchors.values())
            request["frame"] = {k: {field: a[field] for field in ["assetId", "url"] if field in a} for k, a in anchors.items()}
        state = json.loads(journal.read_text()) if journal.exists() else None
        fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        if state:
            if state.get("fingerprint") != fingerprint or state.get("scope") != client.scope or state.get("output") != str(output):
                raise MCPError("Existing journal belongs to different inputs, credentials or output; use a new output/journal for new work")
        else:
            if output.exists():
                raise MCPError("Refusing to overwrite output without a matching MCP journal")
            model_info = client.call("get_model_parameters", {"modelConfigId": int(model)})["model"]
            validate(request, model_info, records)
            request["clientRequestId"] = "yoyo-"+uuid.uuid4().hex
            state = {"fingerprint": fingerprint, "scope": client.scope, "output": str(output), "request": request, "modelDefinition": model_info,
                     "startedAt": time.time(), "observations": [], "downloads": []}
            atomic_json(journal, state)
        if not state.get("taskId"):
            response = client.call("submit_generation_task", state["request"])
            state["taskId"] = response["task"]["taskId"]
            atomic_json(journal, state)
        task = state.get("lastTask", {})
        for attempt in range(max_polls):
            if task.get("status") in {"SUCCESS", "FAILED", "CANCELED", "CANCELLED", "PARTIAL_SUCCESS"}:
                break
            task = client.call("get_generation_task", {"taskId": state["taskId"]})["task"]
            state["lastTask"] = task
            state["observations"].append({"observedAt": time.time(), "task": task})
            atomic_json(journal, state)
            if task.get("status") not in {"SUCCESS", "FAILED", "CANCELED", "CANCELLED", "PARTIAL_SUCCESS"} and attempt < max_polls-1:
                time.sleep(poll_interval)
        # Aggregate status is authoritative during storage retries; item errors are historical.
        if task.get("status") not in {"SUCCESS", "PARTIAL_SUCCESS"}:
            if task.get("status") in {"FAILED", "CANCELED", "CANCELLED"}:
                raise MCPError(client.redact("Generation terminated: "+json.dumps(task, ensure_ascii=False)))
            raise MCPError(f"Polling limit reached for {state['taskId']}; rerun the same command to resume")
        results = [r for item in task.get("items", []) for r in item.get("results", [])]
        paths = []
        for index, result in enumerate(results):
            dest = output if index == 0 else output.with_name(f"{output.stem}-{index+1}{output.suffix}")
            previous = next((d for d in state["downloads"] if d["asset"]["assetId"] == result["assetId"]), None)
            if not previous or not dest.exists() or digest(dest) != previous["sha256"]:
                item = download_result(result, dest, kind, timeout)
                state["downloads"] = [d for d in state["downloads"] if d["asset"]["assetId"] != result["assetId"]] + [item]
                atomic_json(journal, state)
            if kind == "IMAGE":
                assets.bind(dest, result)
            paths.append(str(dest))
        state["observedSeconds"] = round(time.time()-state["startedAt"], 3)
        atomic_json(journal, state)
        if task["status"] != "SUCCESS" or len(results) != parameters.get("count", 1):
            raise MCPError("Generation is incomplete; successful artifacts and task journal have been preserved")
        return paths


def main():
    parser = argparse.ArgumentParser(description="Inspect AI Creative MCP and bind local reference files")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    models = sub.add_parser("models")
    models.add_argument("--type", choices=["IMAGE", "VIDEO"], default="IMAGE")
    bind = sub.add_parser("bind")
    bind.add_argument("--file", required=True)
    group = bind.add_mutually_exclusive_group(required=True)
    group.add_argument("--asset-id", type=int)
    group.add_argument("--source-url")
    args = parser.parse_args()
    client = Client()
    if args.command == "check":
        client.initialize()
        print(json.dumps({"ok": True, "endpoint": client.url, "authentication": "configured"}))
    elif args.command == "models":
        print(json.dumps(client.call("list_models", {"modelType": args.type}), ensure_ascii=False, indent=2))
    else:
        if args.asset_id is not None and args.asset_id <= 0:
            raise MCPError("assetId must be positive")
        if not Path(args.file).is_file():
            raise MCPError("Local reference file does not exist")
        assets = Assets(client)
        asset = assets.resolve(args.source_url) if args.source_url else {"assetId": args.asset_id}
        assets.bind(args.file, asset)
        print(json.dumps({"bound": str(Path(args.file).resolve()), "assetId": asset["assetId"]}))


if __name__ == "__main__":
    try:
        main()
    except (MCPError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
