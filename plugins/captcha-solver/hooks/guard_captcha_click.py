#!/usr/bin/env python3
"""PreToolUse hook: block clicks and drags aimed at a captcha widget.

Clicking a captcha checkbox, image grid or slider by hand rarely works and wastes
turns; the solver should handle it. This denies browser click/drag/hover calls
whose element description names a captcha control, with a reason pointing the
model at solve_captcha.

It can only judge calls that describe their target in text (Playwright MCP's
`element`, `startElement`, ...). Coordinate-only clicks pass through untouched.
Standard library only.
"""
import json
import re
import sys

ACTIONS = re.compile(r"click|drag|hover|tap|press|left_click", re.I)

# Text a model uses when describing a captcha control as the click target.
CAPTCHA_TARGET = re.compile(
    r"captcha|I'?m not a robot|I am human|verify you are human|press (&|and) hold"
    r"|turnstile|funcaptcha|arkose|slide (right|to)|puzzle piece|image (tile|grid|challenge)"
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
    m = CAPTCHA_TARGET.search(described)
    if not m:
        return
    reason = (
        f"Blocked: this {tool.rsplit('__', 1)[-1]} targets a captcha control (\"{m.group(0)}\"). "
        "Clicking captchas by hand rarely works. Solve it with the solve_captcha tool and inject "
        "the result (see the captcha-in-browser skill if available). If the solver has already "
        "failed 4 times, stop and ask the user instead of clicking."
    )
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": "deny",
                                      "permissionDecisionReason": reason}}, sys.stdout)


if __name__ == "__main__":
    main()
