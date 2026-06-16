#!/usr/bin/env python3
"""通用 Chat Logger Hook：根据 product.json 将对话事件 POST 到配置的服务。"""

import datetime
import json
import os
import sqlite3
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
        max_len = int(config.get("maxTranscriptChars") or 0)
        if max_len > 0 and len(content) > max_len:
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
    default = config_key == "includeThinking"
    return not config.get(config_key, default)


def _state_vscdb_path(ide_id):
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        app_name = "Cursor" if ide_id == "cursor" else "Code"
        base = os.path.join(home, "Library", "Application Support", app_name)
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
        app_name = "Cursor" if ide_id == "cursor" else "Code"
        base = os.path.join(appdata, app_name)
    else:
        app_name = "Cursor" if ide_id == "cursor" else "Code"
        base = os.path.join(home, ".config", app_name)
    return os.path.join(base, "User", "globalStorage", "state.vscdb")


_CURSOR_DB_KEYS = {
    "cursorAuth/cachedEmail": "email",
    "cursorAuth/stripeMembershipType": "membership_type",
}


def _read_ide_user_from_vscdb(ide_id):
    db_path = _state_vscdb_path(ide_id)
    if not os.path.isfile(db_path):
        return {}

    key_map = _CURSOR_DB_KEYS if ide_id == "cursor" else {}
    if not key_map:
        return {}

    tags = {}
    try:
        conn = sqlite3.connect("file:{0}?mode=ro".format(db_path), uri=True)
        try:
            for db_key, tag_key in key_map.items():
                row = conn.execute(
                    "SELECT value FROM ItemTable WHERE key = ?",
                    (db_key,),
                ).fetchone()
                if row and row[0]:
                    tags[tag_key] = row[0]
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        pass
    return tags


def _merge_tag(tags, key, value):
    if value is None:
        return
    text = str(value).strip()
    if text:
        tags[key] = text


def _get_ide_user_tags(hook_input, config, product):
    """采集 Cursor / VS Code 登录用户标识，作为 tags 附带上报。"""
    tags = {}
    ide_id = str(product.get("ideId") or "cursor")

    _merge_tag(tags, "email", hook_input.get("user_email"))

    if hook_input.get("cursor_version"):
        tags["ide"] = "cursor"
        tags["ide_version"] = hook_input["cursor_version"]
    elif hook_input.get("vscode_version"):
        tags["ide"] = "vscode"
        tags["ide_version"] = hook_input["vscode_version"]

    ide_user = config.get("ideUser") or {}
    if isinstance(ide_user, dict):
        for key in ("email", "ide", "ide_version", "membership_type", "auth_provider", "account_id"):
            if key not in tags:
                _merge_tag(tags, key, ide_user.get(key))

    if "email" not in tags or "membership_type" not in tags:
        for key, value in _read_ide_user_from_vscdb(ide_id).items():
            if key not in tags:
                tags[key] = value

    if "ide" not in tags:
        tags["ide"] = ide_id

    session_id = hook_input.get("session_id") or hook_input.get("sessionId")
    _merge_tag(tags, "session_id", session_id)

    workspace_roots = hook_input.get("workspace_roots")
    if isinstance(workspace_roots, list) and workspace_roots:
        _merge_tag(tags, "workspace", workspace_roots[0])

    return tags


def _build_payload(marker, event, hook_input, config, product):
    return {
        "source": marker,
        "event": event,
        "timestamp": datetime.datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        "hook_event_name": hook_input.get("hook_event_name", event),
        "tags": _get_ide_user_tags(hook_input, config, product),
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
    timeout = int(config.get("postTimeoutSeconds") or 30)
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
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
            _post_payload(config, _build_payload(marker, event, hook_input, config, product), log_path)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            _log(log_path, "send failed ({0}): {1}".format(event, exc))

    _hook_output(event, product)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
