#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<EOF
用法: $0 [cursor|vscode|all]

发布到 Open VSX（会先 package，再 ovsx publish）。

环境变量:
  OVSX_PAT   Open VSX Personal Access Token（必填）

示例:
  export OVSX_PAT=xxxx
  $0 all
EOF
}

publish_product() {
  local product="$1"
  local pkg_json="$ROOT/packages/$product/package.json"
  local name version vsix publisher

  if [[ -z "${OVSX_PAT:-}" ]]; then
    echo "错误: 请设置环境变量 OVSX_PAT" >&2
    exit 1
  fi

  bash "$ROOT/scripts/package.sh" "$product"

  name="$(node -p "require('$pkg_json').name")"
  version="$(node -p "require('$pkg_json').version")"
  publisher="$(node -p "require('$pkg_json').publisher")"
  vsix="$ROOT/dist/${name}-${version}.vsix"

  if [[ ! -f "$vsix" ]]; then
    echo "错误: 找不到 $vsix" >&2
    exit 1
  fi

  echo "发布 $publisher.$name@${version} ..."
  npx --prefix "$ROOT" ovsx publish "$vsix" -p "$OVSX_PAT"
  echo "完成: https://open-vsx.org/extension/${publisher}/${name}"
}

TARGET="${1:-all}"
case "$TARGET" in
  cursor) publish_product cursor ;;
  vscode) publish_product vscode ;;
  all)
    publish_product cursor
    publish_product vscode
    ;;
  -h|--help|help) usage ;;
  *)
    echo "未知产品: $TARGET" >&2
    usage
    exit 1
    ;;
esac
