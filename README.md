# Chat Logger Monorepo

将 Cursor / VS Code 的 LLM 对话转发到自建 HTTP 服务。

## 目录结构

```
chat-logger/
├── packages/               # 产品元数据（仅 package.json + README）
│   ├── cursor/
│   └── vscode/
├── src/                    # 共用源码
│   ├── extension-core.js
│   ├── hooks/send_log.py
│   ├── profiles/
│   └── receiver/
├── build/                  # sync 组装输出（git 忽略）
├── dist/                   # .vsix 打包输出（git 忽略）
└── scripts/
```

## 开发流程

```bash
# 组装到 build/（改 src 或 packages 后执行）
npm run sync

# 打包
npm run package

# 发布 Open VSX
export OVSX_PAT=<token>
npm run publish:ovsx

# 本机安装（Mac）
npm run install:cursor
npm run install:vscode
```

## 修改指南

| 改什么 | 改哪里 |
|--------|--------|
| Hook / HTTP 逻辑 | `src/hooks/send_log.py` |
| 扩展行为 | `src/extension-core.js` |
| Cursor/VS Code 差异 | `src/profiles/*.json` |
| 版本、设置项、命令 | `packages/cursor/package.json` 或 `packages/vscode/package.json` |
| 市场页说明 | `packages/*/README.md` |

## 接收服务

```bash
python3 src/receiver/server.py --host 0.0.0.0 --port 8080 --output-dir ./chat_logs
bash src/receiver/service.sh install   # systemd 常驻
```
