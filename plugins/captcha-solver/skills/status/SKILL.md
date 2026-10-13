---
name: status
description: Check that the captcha-solver service is reachable and show its running tasks.
disable-model-invocation: true
---

Call the `solver_status` tool from the captcha-solver MCP server and report:

- whether the solver is reachable (HTTP status),
- each captcha type and whether it is `online`,
- any tasks under `current`.

If the call fails, say which part failed:

- **Cannot reach solver**: the Solver URL setting is wrong or the service or tunnel is down.
- **HTTP 401**: the API token setting is wrong.
- **HTTP 421**: the request reached a local address without the right Host header. Set *Host header override*.

Point the user to `/plugin` → captcha-solver → **Configure options** to fix the settings.
