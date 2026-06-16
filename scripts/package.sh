#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<EOF
用法: $0 [cursor|vscode|all]

打包 .vsix（会先 sync 到 build/，再 vsce package）。
EOF
}

package_product() {
  local product="$1"
  local dir="$ROOT/build/$product"
  local name version vsix

  bash "$ROOT/scripts/sync.sh" "$product"

  cd "$dir"
  npx --prefix "$ROOT" vsce package --no-dependencies --allow-missing-repository

  name="$(node -p "require('./package.json').name")"
  version="$(node -p "require('./package.json').version")"
  vsix="${name}-${version}.vsix"

  mkdir -p "$ROOT/dist"
  cp -f "$vsix" "$ROOT/dist/$vsix"
  echo "已打包: $ROOT/dist/$vsix"
}

TARGET="${1:-all}"
case "$TARGET" in
  cursor) package_product cursor ;;
  vscode) package_product vscode ;;
  all)
    package_product cursor
    package_product vscode
    ;;
  -h|--help|help) usage ;;
  *)
    echo "未知产品: $TARGET" >&2
    usage
    exit 1
    ;;
esac
