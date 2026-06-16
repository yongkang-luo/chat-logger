#!/usr/bin/env python3
"""通用 Chat Logger Hook：根据 product.json 将对话事件 POST 到配置的服务。"""

import datetime
import json
import os
import sys
import urllib.error
import urllib.request

HOOK_SCRIPT_NAME = "send_log.py"


def _paths():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    product_path = os.path.join(script_dir, "product.json")
    log_path = os.path.join(script_dir, "send.log")
    return config_path, product_path, log_path


def _log(log_path, message):
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("[{0}] {1}\n".format(ts, message))
    except OSError:
        pass


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return default


def _read_hook_input():
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_input": raw}


def _maybe_attach_transcript(data, product, config):
    if not product.get("attachTranscriptOnStop", False):
        return data
    if not config.get("includeTranscriptOnStop", True):
        return data
    transcript_path = data.get("transcript_path")
    if not transcript_path or not os.path.isfile(transcript_path):
        return data
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        max_len = 500000
        if len(content) > max_len:
            content = content[:max_len] + "\n...[truncated]"
        data = dict(data)
        data["transcript"] = content
        return data
    except OSError as exc:
        data = dict(data)
        data["transcript_error"] = str(exc)
        return data


def _should_skip(event, product, config):
    skip_map = product.get("skipWhenConfigFalse") or {}
    config_key = skip_map.get(event)
    if not config_key:
        return False
    return not config.get(config_key, False)


def _build_payload(marker, event, hook_input):
    return {
        "source": marker,
        "event": event,
        "timestamp": datetime.datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        "hook_event_name": hook_input.get("hook_event_name", event),
        "data": hook_input,
    }


def _post_payload(config, payload, log_path):
    host = str(config.get("serverHost", "127.0.0.1")).strip()
    port = int(config.get("serverPort", 8080))
    endpoint = str(config.get("endpoint", "/api/chat-log")).strip()
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    url = "http://{0}:{1}{2}".format(host, port, endpoint)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        _log(log_path, "POST {0} -> HTTP {1}".format(url, resp.status))


def _hook_output(event, product):
    continue_events = product.get("continueEvents") or []
    if event in continue_events:
        print(json.dumps({"continue": True}, ensure_ascii=False))


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    config_path, product_path, log_path = _paths()
    hook_input = _read_hook_input()
    config = _load_json(config_path, {"enabled": False})
    product = _load_json(product_path, {"managedMarker": "chat-logger"})

    if _should_skip(event, product, config):
        _hook_output(event, product)
        return 0

    if event == "Stop":
        hook_input = _maybe_attach_transcript(hook_input, product, config)

    marker = product.get("managedMarker", "chat-logger")
    if config.get("enabled", False):
        try:
            _post_payload(config, _build_payload(marker, event, hook_input), log_path)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            _log(log_path, "send failed ({0}): {1}".format(event, exc))

    _hook_output(event, product)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
