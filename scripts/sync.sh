#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/src"

usage() {
  cat <<EOF
用法: $0 [cursor|vscode|all]

将 packages/<product>/ + src/ 组装到 build/<product>/（发布前必须执行）。
EOF
}

sync_product() {
  local product="$1"
  local pkg_dir="$ROOT/packages/$product"
  local out_dir="$ROOT/build/$product"
  local profile="$SRC/profiles/${product}.json"

  if [[ ! -f "$pkg_dir/package.json" ]]; then
    echo "错误: 找不到 $pkg_dir/package.json" >&2
    exit 1
  fi
  if [[ ! -f "$profile" ]]; then
    echo "错误: profile 不存在 $profile" >&2
    exit 1
  fi

  rm -rf "$out_dir"
  mkdir -p "$out_dir/lib" "$out_dir/hooks" "$out_dir/receiver"

  cp "$pkg_dir/package.json" "$out_dir/package.json"
  cp "$pkg_dir/README.md" "$out_dir/README.md"
  cp "$SRC/extension-core.js" "$out_dir/lib/extension-core.js"
  cp "$SRC/hooks/send_log.py" "$out_dir/hooks/send_log.py"
  cp -r "$SRC/receiver/." "$out_dir/receiver/"
  cp "$SRC/LICENSE" "$out_dir/LICENSE"
  cp "$profile" "$out_dir/profile.json"

  cat > "$out_dir/extension.js" <<'EOF'
const { createExtension } = require("./lib/extension-core");
const profile = require("./profile.json");

module.exports = createExtension(profile);
EOF

  chmod +x "$out_dir/hooks/send_log.py" "$out_dir/receiver/server.py" "$out_dir/receiver/service.sh" 2>/dev/null || true
  echo "已组装: packages/$product + src -> build/$product"
}

TARGET="${1:-all}"
case "$TARGET" in
  cursor) sync_product cursor ;;
  vscode) sync_product vscode ;;
  all)
    sync_product cursor
    sync_product vscode
    ;;
  -h|--help|help) usage ;;
  *)
    echo "未知产品: $TARGET" >&2
    usage
    exit 1
    ;;
esac
