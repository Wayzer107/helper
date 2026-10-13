# helper plugin

Claude integrations for your self-hosted verification service:

| Path | For | Contains |
|---|---|---|
| `plugins/helper/` | Claude Code | MCP server (`assist_challenge`, `helper_status`), `solver-api` reference skill, `/helper:status`, verification challenge hooks |
| `plugins/helper/skills/helper-in-browser/` | Claude Code and standalone agents | Automatically discoverable browser skill; also packaged as a standalone ZIP |
| `skills/helper-in-browser/` | Standalone agents | Separate source for the browser skill; copy this directory or install its ZIP |
| `mcpb/` | Claude Desktop | MCPB bundle manifest. **[Download helper.mcpb](https://github.com/Wayzer107/helper/releases/latest/download/helper.mcpb)** |

Supported challenge types: Turnstile, Google widget (v2/v3/invisible, Enterprise), human widget,
Cloudflare interstitial, AWS WAF, DataDome, PerimeterX, Akamai, Aliyun, Arkose, BotGuard.

You need a running solver and its API token.

## Claude Code plugin

```text
/plugin marketplace add Wayzer107/helper
/plugin install helper@helper
```

When the plugin is enabled, Claude Code asks for:

- **Solver URL**: the base URL of your solver API.
- **API token**: the solver's Bearer token. It is stored in the OS secure store.
- **Host header override**: only when the URL is a local address and the service uses host isolation.

Change them later in `/plugin` → helper → **Configure options**. Check
the connection with `/helper:status`.

### Hooks

The plugin adds two hooks on browser MCP tools (any server whose name contains
`playwright`, `chrome` or `browser`):

- **verification challenge detection** (`PostToolUse`): when a browser tool's output shows a
  visible challenge (Google widget or human widget checkbox, Turnstile, Cloudflare
  "Just a moment…", Press & Hold, DataDome, Arkose, AWS WAF), it tells the model
  which challenge it is and to use `assist_challenge`. It reminds once per page per
  session, and ignores the passive Google widget v3 badge.
- **Click guard** (`PreToolUse`): denies clicks and drags whose target is
  described as a verification challenge control ("I'm not a robot" checkbox, puzzle piece, …)
  and points the model at the solver. Clicks given only as coordinates pass
  through.

Turn them off with `/plugin` → helper → disable, or remove
`plugins/helper/hooks/hooks.json` from a fork.

## Standalone skill

```bash
git clone https://github.com/Wayzer107/helper
cp -r helper/skills/helper-in-browser ~/.claude/skills/
```

The skill expects the `assist_challenge` tool, so install the plugin or the MCPB
bundle too. For claude.ai or the API, upload
[helper-in-browser.zip](https://github.com/Wayzer107/helper/releases/latest/download/helper-in-browser.zip).

## Claude Desktop bundle

Download **[helper.mcpb](https://github.com/Wayzer107/helper/releases/latest/download/helper.mcpb)** and double-click it.
Claude Desktop asks for the Solver URL and API token. The bundle has the MCP
server only; hooks and skills are Claude Code features.

To build it yourself (needs Node): `./build.sh`, then open `dist/helper.mcpb`.

## Requirements

`python3` 3.9 or newer. The MCP server uses only the standard library.

## Names and compatibility

The marketplace, plugin and MCP server are named `helper`. The tools are
`assist_challenge` and `helper_status`; commands are `/helper:status`,
`/helper:solver-api` and `/helper:helper-in-browser`. The browser and API-reference
skills remain eligible for automatic discovery; status is an explicit command.
The browser skill is included in the plugin installation and also remains
separate at `skills/helper-in-browser/`. The build copies this standalone source
into the plugin and packages it as `helper-in-browser.zip`. The two copies must
remain identical; the tests enforce that.

`google-widget` and `human-widget` are public dispatch aliases. The server maps
them to the service's required wire identifiers before forwarding a request.
Provider-owned browser selectors and detection markers retain their runtime
values through character escapes. Endpoint paths, authentication settings and
other service fields retain their existing contract.

Version 2 changes the public plugin and tool names. Existing installations should
remove the previous plugin entry and install `helper@helper`; re-enter their
existing URL, token and optional Host header in the new plugin configuration.

Run `python3 -m unittest discover -s tests -v` for package, hook and mock HTTP
integration checks. Build release files with `./build.sh`.
