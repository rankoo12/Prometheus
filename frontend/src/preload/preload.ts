import { contextBridge, ipcRenderer } from "electron";
import type { ProbeResult } from "../shared/contracts";

// The only surface the renderer sees. contextIsolation keeps this minimal + safe.
contextBridge.exposeInMainWorld("prometheus", {
  pickClip: (): Promise<string | null> => ipcRenderer.invoke("pick-clip"),
  probe: (clipPath: string): Promise<ProbeResult> =>
    ipcRenderer.invoke("probe", clipPath),
});
