#!/usr/bin/env python3
"""本地测试接收服务：接收 Cursor Chat Logger 转发的对话日志。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class ChatLogHandler(BaseHTTPRequestHandler):
    log_dir: Path

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")

        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        event = payload.get("event", "unknown")
        out_file = self.log_dir / f"{ts}_{event}.json"
        out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"[{datetime.now().isoformat(timespec='seconds')}] {event} -> {out_file.name}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "saved": out_file.name}, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
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
    print(f"接收服务已启动: http://{args.host}:{args.port}/api/chat-log")
    print(f"日志目录: {log_dir.resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
