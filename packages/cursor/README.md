# Cursor Chat Logger

Forward Cursor LLM chat logs to your self-hosted HTTP server.

## Features

- Capture user prompts, agent responses, and session events via Cursor Hooks
- Send logs to a configurable IP:Port endpoint
- Enable/disable toggle from settings or status bar
- Disabled by default

## Requirements

- **Cursor IDE** with Hooks support (not VS Code)
- **Python 3** on the local machine (for hook scripts)

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `cursorChatLogger.enabled` | `false` | Enable log forwarding |
| `cursorChatLogger.serverHost` | `127.0.0.1` | Receiver server IP |
| `cursorChatLogger.serverPort` | `8080` | Receiver server port |
| `cursorChatLogger.endpoint` | `/api/chat-log` | HTTP POST path |
| `cursorChatLogger.includeThinking` | `false` | Include agent thinking blocks |

## Privacy

Logs are sent only to the server you configure. No data is sent to third parties. The extension is **off by default**.

## Receiver API

```
POST http://<host>:<port>/api/chat-log
Content-Type: application/json
```

## Commands

- `Cursor Chat Logger: Enable` / `Disable` / `Toggle`
- `Cursor Chat Logger: Test Connection`
- `Cursor Chat Logger: Reinstall Hooks`
