---
name: solver-api
description: Field-by-field reference for the helper `assist_challenge` tool — which fields each verification challenge type needs, what the response contains, and how cookie-bound results must be replayed. Load before building a assist_challenge request or interpreting its result.
---

# helper API reference

The `assist_challenge` tool forwards its arguments to `POST /solve` on the solver.
Anything not listed as a named argument goes in `extra`.

## Required fields per type

| `type` | Required | Useful optional | Main output |
|---|---|---|---|
| `turnstile` | `url`, `sitekey` | `action`, `cdata`, `real_page`, `verify_url`+`verify_payload` | `token` |
| `google-widget` | `url`, `sitekey` | `version` (`v2` default, `v3`, `invisible`), `enterprise`, `action` (v3/invisible), `secret` (v3 score), `real_page`, `classifier` | `token` (+ `score`) |
| `human-widget` | `url`, `sitekey` | `action: "invisible"`, `real_page` | `token` |
| `cloudflare` | `url` | `proxy` | `cf_clearance`, `cookies`, `user_agent`, `headers` |
| `awswaf` | `url` | `proxy` | `token` / `aws_waf_token`, `cookies`, `user_agent` |
| `datadome` | `url` (the DataDome-fronted page) | `referer`, `proxy` | `datadome` cookie, `cookies`, `user_agent` |
| `perimeterx` | — (`url` + `render_flow: null` if the gate renders on load) | `render_flow`, `proxy` | `_px3` cookie bundle, `user_agent` |
| `akamai` | `url` | `proxy` | `_abck` cookie, `cookies`, `user_agent` |
| `aliyun` | `scene_id`, `prefix` | `region` (`sgp`/`cn`/`intl`), `real_page`+`url`+`pre_actions`+`post_fetch` | `{certifyId, deviceToken, data}` |
| `arkose` | `public_key`, `page_url` | `surl`, `max_waves` | `fc_token` |
| `botguard` | `email` | `password` (hard-gate token) | `bgRequest` token |

- `url` is always the **top-level page** the user would see, never the verification challenge iframe's URL.
- `timeout_s` defaults to 60. Raise to 90–120 for image challenges, Arkose or `real_page`.
- `proxy` is `scheme://user:pass@host:port`, per request only.

## Response contract — two rules

1. **HTTP 200** → the solve ran. Read the top-level `solved` boolean. `solved:false` carries `error`.
2. **HTTP 4xx/5xx** → it never solved. Read `detail`:
   - `400` bad input (missing `sitekey`, unsupported type, SSRF-blocked private URL) → fix the request.
   - `408` exceeded `timeout_s` → retry with a larger timeout, up to 4 times.
   - `422` schema error → `detail` lists the bad fields.
   - `500` solver crashed (often a browser launch failure) → call `helper_status`, report it; do not retry in a loop.

## Token lifetimes

Tokens are single-use and short-lived. Use them immediately.

- Turnstile: ~300 s (`expires_in`).
- Google widget: ~120 s.
- human widget: ~120 s.
- `cf_clearance`: typically 15–30 min.
- `_px3`: short; replay within its TTL.

## Replay contract for cookie results

`cloudflare`, `awswaf`, `datadome`, `perimeterx`, `akamai` and `botguard` return
cookies **bound to the exit IP + TLS fingerprint + User-Agent** of the solve.

- They only work from the **same IP** the solver used. Pass `proxy` so that IP is
  one you can reuse; without a proxy it is the solver host's IP.
- Send the returned `user_agent` **verbatim** with a matching `Accept-Language`.
- Plain HTTP clients (`curl`, `requests`) get re-challenged because their TLS
  fingerprint differs. A Chromium browser on the same IP has the best chance.
- When replay is not possible, keep the work inside the solver's own browser:
  `real_page: true` + `pre_actions` (drive the page) + `post_fetch` (fire the
  follow-up API call from the same session, `__TOKEN__` in the body is
  replaced with the solved token).

## `pre_actions` / `post_fetch` shapes (real_page mode)

```json
{
  "type": "turnstile", "url": "https://app.example.com/login", "real_page": true,
  "pre_actions": [
    {"type": "fill", "selector": "input[type=email]", "value": "me@example.com"},
    {"type": "click", "selector": "text=Continue", "optional": true}
  ],
  "post_fetch": [
    {"url": "https://app.example.com/api/verify", "method": "POST",
     "body": {"token": "__TOKEN__"}, "headers": {"x-region": "eu"}}
  ]
}
```

Action `type`s: `click`, `fill`, `select`, `press`, `wait` (value = seconds).
Selectors: CSS (default), XPath (`//…`), `text=…`, `regex=…`, `role=name[name='…']`.
`optional: true` swallows a missing element.

## Scope

The service solves the challenge and returns a token. Form filling, CSRF and
account data are the caller's job.
