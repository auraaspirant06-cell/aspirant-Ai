const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("aspirantDesktop", {
  notify: (title, body) => ipcRenderer.invoke("desktop:notify", { title, body }),
  getStatus: () => ipcRenderer.invoke("desktop:status"),
  onHotkey: (callback) => {
    ipcRenderer.on("desktop:hotkey", (_event, payload) => callback(payload));
  },
  onClipboardChanged: (callback) => {
    ipcRenderer.on("desktop:clipboard-changed", (_event, text) => callback(text));
  },
  onNotification: (callback) => {
    ipcRenderer.on("desktop:notification", (_event, note) => callback(note));
  },
});
