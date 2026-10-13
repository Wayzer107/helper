# captcha-solver plugin

Claude integrations for a self-hosted
[captcha-solver](https://github.com/waguriagentic/captcha-solver) service:

| Path | For | Contains |
|---|---|---|
| `plugins/captcha-solver/` | Claude Code | MCP server (`solve_captcha`, `solver_status`), `solver-api` reference skill, `/captcha-solver:status` |
| `skills/captcha-in-browser/` | Any Claude agent with a browser tool | Standalone skill: when and how to solve a captcha met during browser automation |
| `mcpb/` | Claude Desktop | MCPB bundle manifest (`./build.sh` packs it) |

Supported challenge types: Turnstile, reCAPTCHA (v2/v3/invisible, Enterprise), hCaptcha,
Cloudflare interstitial, AWS WAF, DataDome, PerimeterX, Akamai, Aliyun, Arkose, BotGuard.

You need a running solver and its API token.

## Claude Code plugin

```text
/plugin marketplace add Wayzer107/captcha-solver-plugin
/plugin install captcha-solver@captcha-solver
```

When the plugin is enabled, Claude Code asks for:

- **Solver URL**: the base URL of your solver API.
- **API token**: the solver's Bearer token. It is stored in the OS secure store.
- **Host header override**: only when the URL is a local address and the service uses host isolation.

Change them later in `/plugin` → captcha-solver → **Configure options**. Check
the connection with `/captcha-solver:status`.

## Standalone skill

```bash
git clone https://github.com/Wayzer107/captcha-solver-plugin
cp -r captcha-solver-plugin/skills/captcha-in-browser ~/.claude/skills/
```

The skill expects the `solve_captcha` tool, so install the plugin or the MCPB
bundle too. For claude.ai or the API, `./build.sh` produces
`dist/captcha-in-browser.zip` to upload.

## Claude Desktop bundle

```bash
./build.sh
```

Then double-click `dist/captcha-solver.mcpb`. Building needs Node (`npx`).

## Requirements

`python3` 3.9 or newer. The MCP server uses only the standard library.
