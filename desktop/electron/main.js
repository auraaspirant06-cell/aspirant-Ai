const {
  app,
  BrowserWindow,
  Menu,
  Notification,
  Tray,
  clipboard,
  globalShortcut,
  ipcMain,
  nativeImage,
} = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const WEB_URL = process.env.ASPIRANT_WEB_URL || "http://127.0.0.1:3000";
const API_URL = process.env.ASPIRANT_API_URL || "http://127.0.0.1:8000/api/v1";
const ICON_PATH = path.join(__dirname, "..", "assets", "app-icon-512.png");

let mainWindow = null;
let tray = null;
let backendChild = null;
let lastClipboard = "";
let clipboardWatcherId = null;

function isUrlReachable(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(900, () => {
      req.destroy();
      resolve(false);
    });
  });
}

function pushNotification(title, body) {
  if (Notification.isSupported()) {
    new Notification({ title, body, icon: ICON_PATH }).show();
  }
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("desktop:notification", {
      title,
      body,
      timestamp: new Date().toISOString(),
    });
  }
}

function startBackgroundService() {
  if (process.env.ASPIRANT_AUTOSTART_BACKEND !== "1" || backendChild) {
    return;
  }
  const repoRoot = path.resolve(__dirname, "..", "..");
  backendChild = spawn(
    "uv",
    ["run", "--directory", repoRoot, "python", "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    { windowsHide: true, stdio: "ignore" }
  );
}

function startClipboardMonitor() {
  if (clipboardWatcherId) return;
  lastClipboard = clipboard.readText();
  clipboardWatcherId = setInterval(() => {
    const current = clipboard.readText();
    if (current && current !== lastClipboard) {
      lastClipboard = current;
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("desktop:clipboard-changed", current.slice(0, 4000));
      }
    }
  }, 1500);
}

async function createMainWindow() {
  const icon = nativeImage.createFromPath(ICON_PATH);
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: "#05070E",
    title: "Aspirant AI — NOVA Desktop",
    icon,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  const reachable = await isUrlReachable(WEB_URL);
  if (reachable) {
    await mainWindow.loadURL(WEB_URL);
  } else {
    await mainWindow.loadFile(path.join(__dirname, "renderer.html"));
  }

  mainWindow.on("close", (event) => {
    if (!app.isQuiting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
}

function createTray() {
  const icon = nativeImage.createFromPath(ICON_PATH).resize({ width: 16, height: 16 });
  tray = new Tray(icon);
  tray.setToolTip("Aspirant AI — NOVA & MJ Active");
  const menu = Menu.buildFromTemplate([
    {
      label: "Open Aspirant AI Console",
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    {
      label: 'Trigger Voice ("Hey Nova")',
      accelerator: "CommandOrControl+Shift+N",
      click: () => {
        if (mainWindow) mainWindow.show();
        pushNotification("NOVA Listening", 'Wake phrase "Hey Nova" activated.');
      },
    },
    { type: "separator" },
    {
      label: "Quit Aspirant AI",
      click: () => {
        app.isQuiting = true;
        app.quit();
      },
    },
  ]);
  tray.setContextMenu(menu);
  tray.on("double-click", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

function registerHotkeys() {
  globalShortcut.register("CommandOrControl+Shift+N", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
      mainWindow.webContents.send("desktop:hotkey", { trigger: "hey-nova" });
    }
    pushNotification("NOVA Quick Summon", "Global hotkey triggered.");
  });
  globalShortcut.register("CommandOrControl+Shift+M", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.webContents.send("desktop:hotkey", { trigger: "mj-capture" });
    }
  });
}

ipcMain.handle("desktop:notify", (_evt, { title, body }) => {
  pushNotification(title, body);
  return { delivered: true };
});

ipcMain.handle("desktop:status", () => ({
  platform: process.platform,
  webUrl: WEB_URL,
  apiUrl: API_URL,
  hotkeys: ["Ctrl+Shift+N", "Ctrl+Shift+M"],
  backgroundBackendRunning: Boolean(backendChild),
}));

app.whenReady().then(async () => {
  startBackgroundService();
  await createMainWindow();
  createTray();
  registerHotkeys();
  startClipboardMonitor();
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
  if (clipboardWatcherId) clearInterval(clipboardWatcherId);
  if (backendChild && !backendChild.killed) {
    backendChild.kill();
  }
});
