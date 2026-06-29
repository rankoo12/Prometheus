import { spawn, ChildProcessWithoutNullStreams } from "node:child_process";
import * as path from "node:path";
import * as readline from "node:readline";
import type { JsonRpcResponse, ProbeResult } from "../shared/contracts";

interface Pending {
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
}

/**
 * Owns the Python backend child process and the stdio JSON-RPC transport
 * (spec §5.1): newline-delimited JSON, responses correlated to requests by id.
 * Only the Electron main process talks to this; the renderer reaches it via IPC.
 */
export class PythonBridge {
  private child: ChildProcessWithoutNullStreams | null = null;
  private readonly pending = new Map<number, Pending>();
  private nextId = 1;

  constructor(private readonly projectRoot: string) {}

  start(): void {
    if (this.child) return;

    const pythonPath =
      process.env.PROMETHEUS_PYTHON ??
      path.join(this.projectRoot, ".venv", "Scripts", "python.exe");

    this.child = spawn(pythonPath, ["-m", "backend.api.rpc"], {
      cwd: this.projectRoot,
      stdio: ["pipe", "pipe", "pipe"],
    }) as ChildProcessWithoutNullStreams;

    // One JSON-RPC response per line on stdout.
    const rl = readline.createInterface({ input: this.child.stdout });
    rl.on("line", (line) => this.onLine(line));

    // Backend logs/diagnostics arrive on stderr — surface them in the main console.
    this.child.stderr.on("data", (chunk: Buffer) => {
      process.stderr.write(`[python] ${chunk.toString()}`);
    });

    this.child.on("exit", (code) => {
      const err = new Error(`Python backend exited (code ${code})`);
      for (const { reject } of this.pending.values()) reject(err);
      this.pending.clear();
      this.child = null;
    });
  }

  stop(): void {
    this.child?.kill();
    this.child = null;
  }

  probe(clipPath: string): Promise<ProbeResult> {
    return this.call<ProbeResult>("probe", { clip_path: clipPath });
  }

  private call<T>(method: string, params: unknown): Promise<T> {
    if (!this.child) this.start();
    const id = this.nextId++;
    const request = { jsonrpc: "2.0" as const, id, method, params };
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject });
      this.child!.stdin.write(JSON.stringify(request) + "\n");
    });
  }

  private onLine(line: string): void {
    const trimmed = line.trim();
    if (!trimmed) return;

    let response: JsonRpcResponse;
    try {
      response = JSON.parse(trimmed) as JsonRpcResponse;
    } catch {
      process.stderr.write(`[bridge] non-JSON line from backend: ${trimmed}\n`);
      return;
    }

    if (response.id == null) return;
    const pending = this.pending.get(response.id);
    if (!pending) return;
    this.pending.delete(response.id);

    if (response.error) {
      pending.reject(new Error(response.error.message));
    } else {
      pending.resolve(response.result);
    }
  }
}
