import { app, BrowserWindow, ipcMain, dialog } from "electron";
import * as path from "node:path";
import { PythonBridge } from "./python-bridge";

// dist/main/main.js -> the repo root is three levels up (frontend/dist/main).
const PROJECT_ROOT = path.resolve(__dirname, "..", "..", "..");

const bridge = new PythonBridge(PROJECT_ROOT);

function createWindow(): void {
  const win = new BrowserWindow({
    width: 720,
    height: 560,
    webPreferences: {
      preload: path.join(__dirname, "..", "preload", "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  win.loadFile(path.join(__dirname, "..", "renderer", "index.html"));
}

// IPC seam: renderer -> main -> PythonBridge. The renderer never touches the child.
ipcMain.handle("pick-clip", async (): Promise<string | null> => {
  const result = await dialog.showOpenDialog({
    title: "Pick a Rocket League clip",
    properties: ["openFile"],
    filters: [{ name: "Video", extensions: ["mp4", "mov", "mkv", "webm", "avi"] }],
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle("probe", (_event, clipPath: string) => bridge.probe(clipPath));

app.whenReady().then(() => {
  bridge.start();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  bridge.stop();
  if (process.platform !== "darwin") app.quit();
});

app.on("quit", () => bridge.stop());
