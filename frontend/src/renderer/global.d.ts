import type { ProbeResult } from "../shared/contracts";

// The API the preload exposes on window. Ambient so the (module-free) renderer
// script is typed without importing anything.
declare global {
  interface Window {
    prometheus: {
      pickClip(): Promise<string | null>;
      probe(clipPath: string): Promise<ProbeResult>;
    };
  }
}
