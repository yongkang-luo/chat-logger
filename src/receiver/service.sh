#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="cursor-chat-logger"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_SRC="$ROOT/receiver/cursor-chat-logger.service"
UNIT_DST="/etc/systemd/system/${SERVICE_NAME}.service"

usage() {
  cat <<EOF
用法: $0 {install|start|stop|restart|status|uninstall}

  install   安装并启用 systemd 常驻服务
  start     启动服务
  stop      停止服务
  restart   重启服务
  status    查看状态
  uninstall 停用并移除 systemd 服务
EOF
}

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "请使用 root 权限运行: sudo $0 $*"
    exit 1
  fi
}

install_service() {
  require_root install
  mkdir -p /data/yongkangluo/chat_logs
  cp "$UNIT_SRC" "$UNIT_DST"
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
  systemctl status "$SERVICE_NAME" --no-pager
}

case "${1:-}" in
  install) install_service ;;
  start)
    require_root start
    systemctl start "$SERVICE_NAME"
    systemctl status "$SERVICE_NAME" --no-pager
    ;;
  stop)
    require_root stop
    systemctl stop "$SERVICE_NAME"
    ;;
  restart)
    require_root restart
    systemctl restart "$SERVICE_NAME"
    systemctl status "$SERVICE_NAME" --no-pager
    ;;
  status)
    systemctl status "$SERVICE_NAME" --no-pager || true
    ;;
  uninstall)
    require_root uninstall
    systemctl disable --now "$SERVICE_NAME" || true
    rm -f "$UNIT_DST"
    systemctl daemon-reload
    echo "已卸载 ${SERVICE_NAME}"
    ;;
  *)
    usage
    exit 1
    ;;
esac
