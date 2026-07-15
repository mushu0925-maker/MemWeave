const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopShell", {
  serviceStatus: () => ipcRenderer.invoke("desktop-service-status"),
  closeClient: () => ipcRenderer.send("desktop-close"),
});
