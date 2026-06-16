#!/usr/bin/env python3
"""本地测试接收服务：接收 Cursor Chat Logger 转发的对话日志。"""

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn

CN_TZ = timezone(timedelta(hours=8))
_UNSAFE_SEGMENT_RE = re.compile(r"[^\w.\-+@]+")


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def _safe_segment(value, default="unknown", max_len=120):
    text = str(value or "").strip()
    if not text:
        return default
    if "/" in text or "\\" in text:
        text = text.replace("\\", "/").rstrip("/").split("/")[-1] or default
    text = _UNSAFE_SEGMENT_RE.sub("_", text).strip("._")
    if not text:
        return default
    return text[:max_len]


def _resolve_tags(payload):
    tags = payload.get("tags") or {}
    data = payload.get("data") or {}

    email = tags.get("email") or data.get("user_email") or "unknown"
    ide = tags.get("ide") or "unknown"
    workspace = tags.get("workspace")
    if not workspace:
        roots = data.get("workspace_roots") or []
        workspace = roots[0] if roots else data.get("cwd") or "unknown"
    session_id = (
        tags.get("session_id")
        or data.get("session_id")
        or data.get("sessionId")
        or "unknown"
    )
    return email, ide, workspace, session_id


def _normalize_tz_for_strptime(text):
    text = str(text).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+0000"
    match = re.match(r"^(.*)([+-]\d{2}):(\d{2})$", text)
    if match:
        text = "{0}{1}{2}".format(match.group(1), match.group(2), match.group(3))
    return text


def _parse_timestamp(payload):
    ts_str = payload.get("timestamp") if isinstance(payload, dict) else None
    if ts_str:
        text = str(ts_str).strip()
        normalized = _normalize_tz_for_strptime(text)
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
        ):
            try:
                dt = datetime.strptime(normalized, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(CN_TZ)
            except ValueError:
                continue
        if hasattr(datetime, "fromisoformat"):
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(CN_TZ)
            except (TypeError, ValueError):
                pass
    return datetime.now(CN_TZ)


def _format_beijing_timestamp(dt):
    dt = dt.astimezone(CN_TZ)
    return "{0}.{1}+08:00".format(
        dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "{0:03d}".format(dt.microsecond // 1000),
    )


def _normalize_payload_timestamp(payload):
    if not isinstance(payload, dict):
        return payload
    payload["timestamp"] = _format_beijing_timestamp(_parse_timestamp(payload))
    return payload


def _build_output_path(log_dir, payload):
    email, ide, workspace, session_id = _resolve_tags(payload)
    dt = _parse_timestamp(payload)
    event = _safe_segment(payload.get("event", "unknown"), default="unknown", max_len=80)

    day_dir = dt.strftime("%Y-%m-%d")
    filename = "{0}_{1}.json".format(dt.strftime("%H%M%S_%f"), event)

    return (
        log_dir
        / _safe_segment(email, default="unknown")
        / _safe_segment(ide, default="unknown")
        / _safe_segment(workspace, default="unknown")
        / _safe_segment(session_id, default="unknown")
        / day_dir
        / filename
    )


class ChatLogHandler(BaseHTTPRequestHandler):
    log_dir = None

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")

        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}

        if isinstance(payload, dict):
            _normalize_payload_timestamp(payload)

        out_file = _build_output_path(self.log_dir, payload)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        saved = str(out_file.relative_to(self.log_dir))
        print("[{0}] {1} -> {2}".format(datetime.now(CN_TZ).isoformat(timespec="seconds"), payload.get("event", "unknown"), saved))

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "saved": saved}, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):  # noqa: A003
        return


def main():
    parser = argparse.ArgumentParser(description="Cursor Chat Logger 测试接收服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8080, help="监听端口")
    parser.add_argument(
        "--output-dir",
        default="./chat_logs",
        help="日志保存目录",
    )
    args = parser.parse_args()

    log_dir = Path(args.output_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    ChatLogHandler.log_dir = log_dir
    server = ThreadingHTTPServer((args.host, args.port), ChatLogHandler)
    print("接收服务已启动: http://{0}:{1}/api/chat-log".format(args.host, args.port))
    print("日志目录: {0}".format(log_dir.resolve()))
    print("目录结构: {{email}}/{{ide}}/{{workspace}}/{{session_id}}/{{YYYY-MM-DD}}/{{HHMMSS}}_{{event}}.json")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
