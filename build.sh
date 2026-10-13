#!/usr/bin/env bash
# Build the distributable integrations from their single sources.
#
#   plugins/captcha-solver/server/solver_mcp.py  (MCP server, source)
#     -> mcpb/server/solver_mcp.py  (generated copy)
#     -> dist/captcha-solver.mcpb   (Claude Desktop bundle)
#   skills/captcha-in-browser/      -> dist/captcha-in-browser.zip (standalone skill)
#
# The Claude Code plugin needs no build: this repo is its marketplace.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

SERVER=plugins/captcha-solver/server/solver_mcp.py
mkdir -p mcpb/server dist
cp "$SERVER" mcpb/server/solver_mcp.py

MCPB=(npx -y @anthropic-ai/mcpb)
command -v mise >/dev/null 2>&1 && MCPB=(mise exec node@22 -- "${MCPB[@]}")
"${MCPB[@]}" validate mcpb/manifest.json
"${MCPB[@]}" pack mcpb dist/captcha-solver.mcpb

rm -f dist/captcha-in-browser.zip
(cd skills && python3 -m zipfile -c ../dist/captcha-in-browser.zip captcha-in-browser/)
echo "built: $(ls dist)"
