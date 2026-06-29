// TypeScript mirror of the Electron<->Python JSON-RPC contract (spec §5.2).
// Phase 0 covers probe() only; detect/render/fetch_music get added as those land.

export interface ProbeResult {
  duration: number;
  width: number;
  height: number;
  fps: number;
}

// JSON-RPC 2.0 envelope (the stdio framing).
export interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number;
  method: string;
  params?: unknown;
}

export interface JsonRpcError {
  code: number;
  message: string;
  data?: unknown;
}

export interface JsonRpcResponse<T = unknown> {
  jsonrpc: "2.0";
  id: number | null;
  result?: T;
  error?: JsonRpcError;
}
