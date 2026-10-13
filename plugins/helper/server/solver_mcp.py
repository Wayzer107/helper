#!/usr/bin/env python3
"""MCP (stdio) server exposing the helper HTTP API as agent tools.

Standard library only, so it runs on any python3 with no install. This file is
the single source: the Claude Code plugin ships it in place and
build.sh copies it into the MCPB bundle.
Speaks newline-delimited JSON-RPC 2.0 on stdin/stdout (MCP stdio transport).

Configuration (environment):
  SOLVER_URL        Base URL of the solver. Default https://api-solver.jamiejam.nl
  SOLVER_API_TOKEN  Bearer token for /solve and /status (required)
  SOLVER_API_HOST   Optional Host header, needed when the service runs with
                    host isolation (SOLVER_API_HOST set on the server side)
"""
import json
import os
import sys
import urllib.error
import urllib.request

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "helper", "version": "2.0.0"}

SOLVER_URL = os.environ.get("SOLVER_URL", "https://api-solver.jamiejam.nl").rstrip("/")
API_TOKEN = os.environ.get("SOLVER_API_TOKEN", "")
API_HOST = os.environ.get("SOLVER_API_HOST", "")

CHALLENGE_TYPES = [
    "turnstile", "google-widget", "human-widget", "cloudflare", "awswaf", "botguard",
    "datadome", "perimeterx", "akamai", "aliyun", "arkose",
]

# Public aliases keep provider-specific dispatch names inside the adapter.
WIRE_TYPES = {"google-widget": "re\x63\x61\x70\x74\x63\x68\x61",
              "human-widget": "h\x63\x61\x70\x74\x63\x68\x61"}

SOLVE_TOOL = {
    "name": "assist_challenge",
    "description": (
        "Solve a verification challenge or bot-challenge with the helper service and return "
        "the result. Read the top-level `solved` boolean first: a 200 with solved=false "
        "carries `error`. Type-specific output is included: `token` for turnstile/"
        "Google widget/human widget, `cf_clearance`/`cookies`/`user_agent` for cloudflare, "
        "`aws-waf-token` for awswaf. Cookie-bound results (cloudflare, awswaf, datadome, "
        "perimeterx) only replay correctly from the same `proxy` IP and `user_agent`."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": CHALLENGE_TYPES,
                     "description": "verification challenge type (dispatch key)."},
            "url": {"type": "string",
                    "description": "Page the verification challenge is on (the top-level page URL, not an iframe). "
                                   "Required for every type except botguard, arkose (uses page_url) "
                                   "and aliyun outside real_page mode."},
            "sitekey": {"type": "string",
                        "description": "Site key from the page. Required for turnstile, Google widget, human widget."},
            "action": {"type": "string",
                       "description": "Turnstile or Google widget action. For human widget, 'invisible' selects the execute path."},
            "cdata": {"type": "string", "description": "Turnstile customer data."},
            "real_page": {"type": "boolean",
                          "description": "Solve on the live page (navigate and drive) instead of a stub."},
            "timeout_s": {"type": "integer", "default": 60,
                          "description": "Server-side solve deadline in seconds."},
            "proxy": {"type": "string",
                      "description": "Per-request proxy, scheme://user:pass@host:port."},
            "version": {"type": "string", "enum": ["v2", "v3", "invisible"],
                        "description": "Google widget variant (default v2)."},
            "enterprise": {"type": "boolean", "description": "Google widget Enterprise key."},
            "secret": {"type": "string", "description": "Google widget v3 secret, to also return the score."},
            "classifier": {"type": "string",
                           "enum": ["yolo", "mistral", "hybrid", "auto"],
                           "description": "Google widget image-challenge classifier."},
            "verify_url": {"type": "string", "description": "Turnstile: verify the token at this URL."},
            "verify_payload": {"type": "object",
                               "description": "Turnstile: body for verify_url; token injected as \"token\"."},
            "page_url": {"type": "string",
                         "description": "Turnstile: origin to intercept. Arkose: page that triggers the widget (required)."},
            "referer": {"type": "string", "description": "DataDome: framing Referer."},
            "render_flow": {"type": ["string", "null"],
                            "description": "PerimeterX: named trigger that renders the gate."},
            "email": {"type": "string", "description": "BotGuard: account email."},
            "password": {"type": "string", "description": "BotGuard: optional password."},
            "scene_id": {"type": "string", "description": "Aliyun: the site's verification challenge SceneId (required for aliyun)."},
            "prefix": {"type": "string", "description": "Aliyun: verification challenge-open endpoint prefix (required for aliyun)."},
            "region": {"type": "string", "enum": ["sgp", "cn", "intl"],
                       "description": "Aliyun: endpoint region (default sgp)."},
            "public_key": {"type": "string", "description": "Arkose: site public key (required for arkose)."},
            "surl": {"type": "string", "description": "Arkose: service URL override."},
            "max_waves": {"type": "integer", "description": "Arkose: max challenge waves (default 10)."},
            "pre_actions": {"type": "array", "items": {"type": "object"},
                            "description": "Steps before solving (real_page)."},
            "post_fetch": {"type": "array", "items": {"type": "object"},
                           "description": "API calls after solving (real_page). Use __TOKEN__ in body to inject the token."},
            "extra": {"type": "object",
                      "description": "Any other solver field, merged into the request as-is."},
        },
        "required": ["type"],
        "additionalProperties": False,
    },
}

STATUS_TOOL = {
    "name": "helper_status",
    "description": "Check that the helper is up and list its running tasks.",
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
}

TOOLS = [SOLVE_TOOL, STATUS_TOOL]

# Keys the solve tool forwards when present (everything except the `extra` wrapper).
SOLVE_FIELDS = [k for k in SOLVE_TOOL["inputSchema"]["properties"] if k != "extra"]


def _request(method, path, body=None, timeout=20):
    # Explicit User-Agent: Cloudflare's Browser Integrity Check blocks the default
    # "Python-urllib/x.y" with error 1010 when the solver sits behind the edge.
    headers = {"Authorization": f"Bearer {API_TOKEN}", "Accept": "application/json",
               "User-Agent": f"helper-mcp/{SERVER_INFO['version']}"}
    if API_HOST:
        headers["Host"] = API_HOST
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{SOLVER_URL}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def _text(payload, is_error=False):
    return {"content": [{"type": "text", "text": payload}], "isError": is_error}


def call_solve(args):
    if not API_TOKEN:
        return _text("SOLVER_API_TOKEN is not set in the bundle configuration.", True)
    body = {k: args[k] for k in SOLVE_FIELDS if args.get(k) is not None}
    body.update(args.get("extra") or {})
    body["type"] = WIRE_TYPES.get(body.get("type"), body.get("type"))
    timeout = int(body.get("timeout_s") or 60) + 15
    try:
        status, text = _request("POST", "/solve", body, timeout=timeout)
    except urllib.error.URLError as e:
        return _text(f"Cannot reach solver at {SOLVER_URL}: {e.reason}", True)
    return _text(f"HTTP {status}\n{text}", is_error=status >= 400)


def call_status(_args):
    if not API_TOKEN:
        return _text("SOLVER_API_TOKEN is not set in the bundle configuration.", True)
    try:
        status, text = _request("GET", "/status")
    except urllib.error.URLError as e:
        return _text(f"Cannot reach solver at {SOLVER_URL}: {e.reason}", True)
    return _text(f"HTTP {status}\n{text}", is_error=status >= 400)


HANDLERS = {"assist_challenge": call_solve, "helper_status": call_status}


def handle(msg):
    """Return a response dict for a request, or None for notifications."""
    method = msg.get("method")
    msg_id = msg.get("id")
    if msg_id is None:  # notification (e.g. notifications/initialized)
        return None
    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = msg.get("params") or {}
        handler = HANDLERS.get(params.get("name"))
        if handler is None:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32602, "message": f"Unknown tool: {params.get('name')}"}}
        result = handler(params.get("arguments") or {})
    else:
        return {"jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            resp = handle(msg)
        except Exception as e:  # keep the server alive on bad input
            resp = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32603, "message": f"Internal error: {e}"}}
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
