# captcha-solver plugin

Claude integrations for a self-hosted
[captcha-solver](https://github.com/waguriagentic/captcha-solver) service:

| Path | For | Contains |
|---|---|---|
| `plugins/captcha-solver/` | Claude Code | MCP server (`solve_captcha`, `solver_status`), `solver-api` reference skill, `/captcha-solver:status`, captcha hooks |
| `skills/captcha-in-browser/` | Any Claude agent with a browser tool | Standalone skill: when and how to solve a captcha met during browser automation |
| `mcpb/` | Claude Desktop | MCPB bundle manifest. **[Download captcha-solver.mcpb](https://github.com/Wayzer107/captcha-solver-plugin/releases/latest/download/captcha-solver.mcpb)** |

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

### Hooks

The plugin adds two hooks on browser MCP tools (any server whose name contains
`playwright`, `chrome` or `browser`):

- **Captcha detection** (`PostToolUse`): when a browser tool's output shows a
  visible challenge (reCAPTCHA or hCaptcha checkbox, Turnstile, Cloudflare
  "Just a moment…", Press & Hold, DataDome, Arkose, AWS WAF), it tells the model
  which challenge it is and to use `solve_captcha`. It reminds once per page per
  session, and ignores the passive reCAPTCHA v3 badge.
- **Click guard** (`PreToolUse`): denies clicks and drags whose target is
  described as a captcha control ("I'm not a robot" checkbox, puzzle piece, …)
  and points the model at the solver. Clicks given only as coordinates pass
  through.

Turn them off with `/plugin` → captcha-solver → disable, or remove
`plugins/captcha-solver/hooks/hooks.json` from a fork.

## Standalone skill

```bash
git clone https://github.com/Wayzer107/captcha-solver-plugin
cp -r captcha-solver-plugin/skills/captcha-in-browser ~/.claude/skills/
```

The skill expects the `solve_captcha` tool, so install the plugin or the MCPB
bundle too. For claude.ai or the API, upload
[captcha-in-browser.zip](https://github.com/Wayzer107/captcha-solver-plugin/releases/latest/download/captcha-in-browser.zip).

## Claude Desktop bundle

Download **[captcha-solver.mcpb](https://github.com/Wayzer107/captcha-solver-plugin/releases/latest/download/captcha-solver.mcpb)** and double-click it.
Claude Desktop asks for the Solver URL and API token. The bundle has the MCP
server only; hooks and skills are Claude Code features.

To build it yourself (needs Node): `./build.sh`, then open `dist/captcha-solver.mcpb`.

## Requirements

`python3` 3.9 or newer. The MCP server uses only the standard library.
