#!/usr/bin/env python3
"""PreToolUse hook: block clicks and drags aimed at a verification challenge widget.

Clicking a verification challenge checkbox, image grid or slider by hand rarely works and wastes
turns; the solver should handle it. This denies browser click/drag/hover calls
whose element description names a verification challenge control, with a reason pointing the
model at assist_challenge.

It can only judge calls that describe their target in text (Playwright MCP's
`element`, `startElement`, ...). Coordinate-only clicks pass through untouched.
Standard library only.
"""
import json
import re
import sys

ACTIONS = re.compile(r"click|drag|hover|tap|press|left_click", re.I)

# Text a model uses when describing a verification challenge control as the click target.
CHALLENGE_TARGET = re.compile(
    r"\x63\x61\x70\x74\x63\x68\x61|I'?m not a robot|I am human|verify you are human|press (&|and) hold"
    r"|turnstile|fun\x63\x61\x70\x74\x63\x68\x61|arkose|slide (right|to)|puzzle piece|image (tile|grid|challenge)"
    r"|select all (images|squares)|security challenge",
    re.I,
)

# Input fields that carry a human-readable description of the target.
TEXT_FIELDS = ("element", "startElement", "endElement", "text", "description", "query", "target", "name")


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    tool = event.get("tool_name", "")
    args = event.get("tool_input") or {}
    action = " ".join([tool, str(args.get("action", ""))])
    if not ACTIONS.search(action):
        return
    described = " ".join(str(args[f]) for f in TEXT_FIELDS if isinstance(args.get(f), str))
    m = CHALLENGE_TARGET.search(described)
    if not m:
        return
    reason = (
        f"Blocked: this {tool.rsplit('__', 1)[-1]} targets a verification challenge control (\"{m.group(0)}\"). "
        "Clicking verification challenge by hand rarely works. Solve it with the assist_challenge tool and inject "
        "the result (see the helper-in-browser skill if available). If the solver has already "
        "failed 4 times, stop and ask the user instead of clicking."
    )
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": "deny",
                                      "permissionDecisionReason": reason}}, sys.stdout)


if __name__ == "__main__":
    main()
