# VS Code Chat Logger

Forward VS Code Copilot Agent chat logs to your self-hosted HTTP server.

## Features

- Capture user prompts via `UserPromptSubmit` Copilot Hook
- Capture session transcript on `Stop` (includes agent replies when available)
- Optional `PostToolUse` tool-call logging
- Configurable IP:Port endpoint with enable/disable toggle
- Disabled by default

## Requirements

- **Visual Studio Code** 1.96+ with **GitHub Copilot** and **Agent Hooks** (Preview)
- **Python 3** on the local machine (for hook scripts)
- Copilot hooks must be enabled (check enterprise policy if hooks do not fire)

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `vscodeChatLogger.enabled` | `false` | Enable log forwarding |
| `vscodeChatLogger.serverHost` | `127.0.0.1` | Receiver server IP |
| `vscodeChatLogger.serverPort` | `8080` | Receiver server port |
| `vscodeChatLogger.endpoint` | `/api/chat-log` | HTTP POST path |
| `vscodeChatLogger.includeToolUse` | `true` | Forward PostToolUse events |
| `vscodeChatLogger.includeTranscriptOnStop` | `true` | Attach session transcript on Stop |

## Privacy

Logs are sent only to the server you configure. No data is sent to third parties. The extension is **off by default**.

## Receiver API

```
POST http://<host>:<port>/api/chat-log
Content-Type: application/json
```

## Commands

- `VS Code Chat Logger: Enable` / `Disable` / `Toggle`
- `VS Code Chat Logger: Test Connection`
- `VS Code Chat Logger: Reinstall Hooks`
