const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const os = require("os");
const http = require("http");
const { execFileSync } = require("child_process");

const HOOK_SCRIPT_NAME = "send_log.py";

/**
 * @param {Record<string, unknown>} profile
 */
function createExtension(profile) {
  const homeParts = /** @type {string[]} */ (profile.chatLoggerHome);
  const hooksFileParts = /** @type {string[]} */ (profile.hooksFile);
  const hookEvents = /** @type {string[]} */ (profile.hookEvents);
  const configKeys = /** @type {string[]} */ (profile.configKeys);
  const messages = /** @type {Record<string, string>} */ (profile.messages);
  const configPrefix = String(profile.configPrefix);
  const commandPrefix = String(profile.commandPrefix);
  const managedMarker = String(profile.managedMarker);
  const hookMode = String(profile.hookMode);
  const hookCommandType = String(profile.hookCommandType || "plain");
  const statusBarPriority = Number(profile.statusBarPriority || 100);
  const statusBarLabel = String(profile.statusBarLabel || "ChatLogger");
  const hookProduct = profile.hookProduct || {};

  const chatLoggerDir = path.join(os.homedir(), ...homeParts);
  const configPath = path.join(chatLoggerDir, "config.json");
  const productPath = path.join(chatLoggerDir, "product.json");
  const hooksJsonPath = path.join(os.homedir(), ...hooksFileParts);

  /** @type {vscode.StatusBarItem | undefined} */
  let statusBarItem;

  /**
   * @param {string} message
   * @param {"info"|"warn"|"error"} level
   */
  function notify(message, level = "info") {
    if (level === "error") {
      vscode.window.showErrorMessage(message);
    } else if (level === "warn") {
      vscode.window.showWarningMessage(message);
    } else {
      vscode.window.showInformationMessage(message);
    }
  }

  function getConfigValues() {
    const cfg = vscode.workspace.getConfiguration(configPrefix);
    /** @type {Record<string, unknown>} */
    const values = {};
    for (const key of configKeys) {
      if (key === "enabled") {
        values[key] = cfg.get(key, false);
      } else if (key === "serverHost") {
        values[key] = cfg.get(key, "127.0.0.1");
      } else if (key === "serverPort") {
        values[key] = cfg.get(key, 8080);
      } else if (key === "endpoint") {
        values[key] = cfg.get(key, "/api/chat-log");
      } else if (key === "includeThinking" || key === "includeToolUse" || key === "includeTranscriptOnStop") {
        if (key === "includeThinking") {
          values[key] = cfg.get(key, true);
        } else {
          values[key] = cfg.get(key, key !== "includeThinking");
        }
      } else {
        values[key] = cfg.get(key);
      }
    }
    return values;
  }

  function getStateVscdbPath(ideId) {
    const home = os.homedir();
    const appName = ideId === "cursor" ? "Cursor" : "Code";

    if (process.platform === "darwin") {
      return path.join(home, "Library", "Application Support", appName, "User", "globalStorage", "state.vscdb");
    }
    if (process.platform === "win32") {
      const appData = process.env.APPDATA || path.join(home, "AppData", "Roaming");
      return path.join(appData, appName, "User", "globalStorage", "state.vscdb");
    }
    return path.join(home, ".config", appName, "User", "globalStorage", "state.vscdb");
  }

  function readIdeUserFromVscdb(ideId) {
    const dbPath = getStateVscdbPath(ideId);
    if (!fs.existsSync(dbPath)) {
      return {};
    }

    const keyMap =
      ideId === "cursor"
        ? {
            "cursorAuth/cachedEmail": "email",
            "cursorAuth/stripeMembershipType": "membership_type",
          }
        : {};

    if (!Object.keys(keyMap).length) {
      return {};
    }

    /** @type {Record<string, string>} */
    const result = {};
    try {
      for (const [dbKey, tagKey] of Object.entries(keyMap)) {
        const output = execFileSync(
          "sqlite3",
          [dbPath, "SELECT value FROM ItemTable WHERE key = ?;", dbKey],
          { encoding: "utf8", timeout: 3000 }
        ).trim();
        if (output) {
          result[tagKey] = output;
        }
      }
    } catch {
      // sqlite3 不可用或数据库被锁时忽略
    }
    return result;
  }

  async function resolveIdeUser() {
    const ideId = String(profile.id || "unknown");
    /** @type {Record<string, string>} */
    const ideUser = { ide: ideId };

    try {
      ideUser.ide_version = vscode.version;
    } catch {
      // ignore
    }

    const authProviders = ideId === "cursor" ? ["github", "cursor", "microsoft"] : ["github", "microsoft"];
    for (const provider of authProviders) {
      try {
        const session = await vscode.authentication.getSession(provider, [], { silent: true });
        if (session && session.account) {
          if (!ideUser.email) {
            ideUser.email = session.account.label || session.account.id;
          }
          ideUser.auth_provider = provider;
          ideUser.account_id = session.account.id;
          break;
        }
      } catch {
        // 未登录或 provider 不存在
      }
    }

    const fromDb = readIdeUserFromVscdb(ideId);
    if (fromDb.email && !ideUser.email) {
      ideUser.email = fromDb.email;
    }
    if (fromDb.membership_type) {
      ideUser.membership_type = fromDb.membership_type;
    }

    return ideUser;
  }

  async function syncRuntimeConfig() {
    fs.mkdirSync(chatLoggerDir, { recursive: true });
    const values = getConfigValues();
    values.ideUser = await resolveIdeUser();
    fs.writeFileSync(configPath, JSON.stringify(values, null, 2), "utf8");
    fs.writeFileSync(productPath, JSON.stringify(hookProduct, null, 2), "utf8");
  }

  /**
   * @param {vscode.ExtensionContext} context
   */
  function installHookScript(context) {
    const src = path.join(context.extensionPath, "hooks", HOOK_SCRIPT_NAME);
    const dst = path.join(chatLoggerDir, HOOK_SCRIPT_NAME);
    fs.mkdirSync(chatLoggerDir, { recursive: true });
    fs.copyFileSync(src, dst);
    fs.chmodSync(dst, 0o755);
  }

  function buildHookCommand(event) {
    const scriptPath = path.join(chatLoggerDir, HOOK_SCRIPT_NAME);
    return `python3 "${scriptPath}" ${event}`;
  }

  /**
   * @param {{ command?: string }} entry
   */
  function isManagedHook(entry) {
    const command = entry && entry.command ? String(entry.command) : "";
    return command.includes(managedMarker) || command.includes(HOOK_SCRIPT_NAME);
  }

  function installHooksCursorMerge() {
    /** @type {{ version?: number, hooks?: Record<string, Array<{command?: string, type?: string, timeout?: number}>> }} */
    let hooksConfig = { version: 1, hooks: {} };

    if (fs.existsSync(hooksJsonPath)) {
      try {
        hooksConfig = JSON.parse(fs.readFileSync(hooksJsonPath, "utf8"));
      } catch (err) {
        notify(`无法解析 ${hooksJsonPath}，将写入新的 hooks 配置`, "warn");
        hooksConfig = { version: 1, hooks: {} };
      }
    }

    if (!hooksConfig.hooks || typeof hooksConfig.hooks !== "object") {
      hooksConfig.hooks = {};
    }
    if (!hooksConfig.version) {
      hooksConfig.version = 1;
    }

    for (const event of hookEvents) {
      const existing = Array.isArray(hooksConfig.hooks[event]) ? hooksConfig.hooks[event] : [];
      const preserved = existing.filter((entry) => !isManagedHook(entry));
      preserved.push({ command: buildHookCommand(event) });
      hooksConfig.hooks[event] = preserved;
    }

    fs.mkdirSync(path.dirname(hooksJsonPath), { recursive: true });
    fs.writeFileSync(hooksJsonPath, JSON.stringify(hooksConfig, null, 2), "utf8");
  }

  function installHooksStandalone() {
    /** @type {{ version: number, hooks: Record<string, Array<{type: string, command: string, timeout: number}>> }} */
    const hooksConfig = { version: 1, hooks: {} };

    for (const event of hookEvents) {
      hooksConfig.hooks[event] = [
        {
          type: "command",
          command: buildHookCommand(event),
          timeout: 15,
        },
      ];
    }

    fs.mkdirSync(path.dirname(hooksJsonPath), { recursive: true });
    fs.writeFileSync(hooksJsonPath, JSON.stringify(hooksConfig, null, 2), "utf8");
  }

  function installHooks() {
    if (hookMode === "cursor-merge") {
      installHooksCursorMerge();
      return;
    }
    installHooksStandalone();
  }

  function updateStatusBar() {
    if (!statusBarItem) {
      return;
    }
    const { enabled, serverHost, serverPort } = getConfigValues();
    statusBarItem.text = enabled
      ? `$(radio-tower) ${statusBarLabel}: ON ${serverHost}:${serverPort}`
      : `$(circle-slash) ${statusBarLabel}: OFF`;
    statusBarItem.tooltip = enabled
      ? `对话转发已开启 -> ${serverHost}:${serverPort}\n点击关闭`
      : "对话转发已关闭\n点击开启";
    statusBarItem.backgroundColor = enabled
      ? undefined
      : new vscode.ThemeColor("statusBarItem.warningBackground");
  }

  /**
   * @param {boolean} enabled
   */
  async function setEnabled(enabled) {
    const cfg = vscode.workspace.getConfiguration(configPrefix);
    await cfg.update("enabled", enabled, vscode.ConfigurationTarget.Global);
    await syncRuntimeConfig();
    updateStatusBar();
    notify(enabled ? messages.enabled : messages.disabled);
  }

  function testConnection() {
    const { serverHost, serverPort, endpoint } = getConfigValues();
    const normalizedEndpoint = String(endpoint).startsWith("/") ? String(endpoint) : `/${endpoint}`;
    const payload = JSON.stringify({
      source: managedMarker,
      event: "test",
      timestamp: new Date().toISOString(),
      data: { message: messages.testMessage },
    });

    return new Promise((resolve) => {
      const req = http.request(
        {
          hostname: serverHost,
          port: serverPort,
          path: normalizedEndpoint,
          method: "POST",
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": Buffer.byteLength(payload),
          },
          timeout: 5000,
        },
        (res) => {
          res.on("data", () => {});
          res.on("end", () => {
            notify(`测试成功: HTTP ${res.statusCode} ${serverHost}:${serverPort}${normalizedEndpoint}`);
            resolve(true);
          });
        }
      );

      req.on("timeout", () => {
        req.destroy();
        notify(`测试超时: ${serverHost}:${serverPort}${normalizedEndpoint}`, "error");
        resolve(false);
      });

      req.on("error", (err) => {
        notify(`测试失败: ${err.message}`, "error");
        resolve(false);
      });

      req.write(payload);
      req.end();
    });
  }

  /**
   * @param {vscode.ExtensionContext} context
   */
  function activate(context) {
    installHookScript(context);
    installHooks();

    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, statusBarPriority);
    statusBarItem.command = `${commandPrefix}.toggle`;
    statusBarItem.show();

    const refresh = async () => {
      await syncRuntimeConfig();
      updateStatusBar();
    };

    void refresh();

    const reinstallMessage =
      hookMode === "cursor-merge"
        ? messages.reinstallHooks
        : `${messages.reinstallHooks}\n${hooksJsonPath}`;

    context.subscriptions.push(
      statusBarItem,
      vscode.workspace.onDidChangeConfiguration((event) => {
        if (event.affectsConfiguration(configPrefix)) {
          void refresh();
        }
      }),
      vscode.commands.registerCommand(`${commandPrefix}.toggle`, async () => {
        const { enabled } = getConfigValues();
        await setEnabled(!enabled);
      }),
      vscode.commands.registerCommand(`${commandPrefix}.enable`, async () => {
        await setEnabled(true);
      }),
      vscode.commands.registerCommand(`${commandPrefix}.disable`, async () => {
        await setEnabled(false);
      }),
      vscode.commands.registerCommand(`${commandPrefix}.testConnection`, async () => {
        await testConnection();
      }),
      vscode.commands.registerCommand(`${commandPrefix}.reinstallHooks`, () => {
        installHookScript(context);
        installHooks();
        void refresh().then(() => {
          notify(reinstallMessage);
        });
      })
    );

    notify(messages.loaded);
  }

  function deactivate() {
    if (statusBarItem) {
      statusBarItem.dispose();
      statusBarItem = undefined;
    }
  }

  return { activate, deactivate };
}

module.exports = { createExtension };
