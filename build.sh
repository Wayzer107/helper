#!/usr/bin/env bash
# Build the distributable integrations from their single sources.
#
#   plugins/helper/server/solver_mcp.py  (MCP server, source)
#     -> mcpb/server/solver_mcp.py  (generated copy)
#     -> dist/helper.mcpb   (Claude Desktop bundle)
#   skills/helper-in-browser/ -> plugin skill copy and standalone ZIP
#
# The Claude Code plugin needs no build: this repo is its marketplace.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

SERVER=plugins/helper/server/solver_mcp.py
mkdir -p mcpb/server dist
cp "$SERVER" mcpb/server/solver_mcp.py
cp skills/helper-in-browser/SKILL.md plugins/helper/skills/helper-in-browser/SKILL.md

MCPB=(npx -y @anthropic-ai/mcpb)
command -v mise >/dev/null 2>&1 && MCPB=(mise exec node@22 -- "${MCPB[@]}")
"${MCPB[@]}" validate mcpb/manifest.json
"${MCPB[@]}" pack mcpb dist/helper.mcpb

rm -f dist/helper-in-browser.zip
(cd skills && python3 -m zipfile -c ../dist/helper-in-browser.zip helper-in-browser/)
echo "built: $(ls dist)"
