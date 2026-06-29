"""stdio JSON-RPC 2.0 server (spec §5.1).

Framing: newline-delimited JSON (one compact object per line) over stdin/stdout.
Discipline: stdout carries ONLY RPC responses. All logging goes to stderr, or the
stream is corrupted. Run with:  python -m backend.api.rpc
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any, TextIO

from backend.api.commands import REGISTRY

log = logging.getLogger("prometheus.rpc")

# JSON-RPC 2.0 standard error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "result": result, "id": req_id}


def _error(req_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "error": err, "id": req_id}


def dispatch(request: dict[str, Any]) -> dict[str, Any]:
    """Route one parsed JSON-RPC request to its handler and build the response."""
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    handler = REGISTRY.get(method)
    if handler is None:
        return _error(req_id, METHOD_NOT_FOUND, f"Method not found: {method!r}")

    try:
        if isinstance(params, dict):
            result = handler(**params)
        elif isinstance(params, list):
            result = handler(*params)
        else:
            return _error(req_id, INVALID_PARAMS, "params must be an object or array")
        return _result(req_id, result)
    except TypeError as exc:  # bad argument names/arity
        return _error(req_id, INVALID_PARAMS, str(exc))
    except Exception as exc:  # noqa: BLE001 - boundary: every failure becomes a response
        log.exception("handler %r failed", method)
        return _error(req_id, INTERNAL_ERROR, str(exc))


def serve(stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    log.info("prometheus rpc ready (%d commands)", len(REGISTRY))
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _error(None, PARSE_ERROR, f"Parse error: {exc}")
        else:
            response = dispatch(request)
        stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        stdout.flush()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,  # never stdout — that channel is reserved for RPC
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    serve()


if __name__ == "__main__":
    main()
