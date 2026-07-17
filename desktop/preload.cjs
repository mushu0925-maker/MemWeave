const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopShell", {
  serviceStatus: () => ipcRenderer.invoke("desktop-service-status"),
  startVoiceSetup: () => ipcRenderer.invoke("desktop-start-voice-setup"),
  closeClient: () => ipcRenderer.send("desktop-close"),
});
