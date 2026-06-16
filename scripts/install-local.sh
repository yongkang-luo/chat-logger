#!/usr/bin/env bash
# 在本地电脑安装扩展（Cursor 或 VS Code）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<EOF
用法: $0 <cursor|vscode> [extensions目标目录]

示例:
  $0 cursor
  $0 vscode ~/.vscode/extensions
EOF
}

PRODUCT="${1:-}"
TARGET="${2:-}"

if [[ -z "$PRODUCT" ]]; then
  usage
  exit 1
fi

PKG_JSON="$ROOT/packages/$PRODUCT/package.json"
BUILD_DIR="$ROOT/build/$PRODUCT"
VERSION="$(node -p "require('$PKG_JSON').version")"
NAME="$(node -p "require('$PKG_JSON').name")"

bash "$ROOT/scripts/sync.sh" "$PRODUCT"

if [[ -z "$TARGET" ]]; then
  if [[ "$PRODUCT" == "cursor" && -d "$HOME/.cursor/extensions" ]]; then
    TARGET="$HOME/.cursor/extensions/${NAME}-${VERSION}"
  elif [[ -d "$HOME/.vscode/extensions" ]]; then
    TARGET="$HOME/.vscode/extensions/${NAME}-${VERSION}"
  else
    echo "未找到 extensions 目录，请手动指定目标路径" >&2
    exit 1
  fi
fi

mkdir -p "$TARGET"
rsync -a --delete "$BUILD_DIR/" "$TARGET/"

chmod +x "$TARGET/hooks/send_log.py" "$TARGET/receiver/server.py" 2>/dev/null || true

echo "已安装到: $TARGET"
echo "请重启 IDE，在 Settings 中配置并开启扩展。"
