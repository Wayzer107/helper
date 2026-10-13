---
name: helper-in-browser
description: Use when browser automation is blocked by human verification, an "I'm not a robot" checkbox, an image grid or slider, a Turnstile widget, a Cloudflare "Just a moment" page, an AWS WAF gate or a "Press & Hold" prompt. Supports Google and human widgets, DataDome, PerimeterX, Arkose and Aliyun. Explains how to identify the challenge and use helper's assist_challenge tool.
---

# Getting past verification challenges during browser automation

You have an `assist_challenge` tool (helper plugin or MCPB bundle). It solves
the challenge in its own anti-detect browser and returns a token or cookies. Your
job is to identify the challenge, request the right solve, and hand the result
back to the page you are driving.

For the per-type field reference, load the `helper:solver-api` skill if it
is available.

## When to use it

Use it when a verification challenge **blocks a step of the task the user asked for**: a login,
a form submit, a page you need to read.

Don't use it:

- **In a retry loop.** One solve, at most 4 retries (see *Failure handling*).

Clicking a verification challenge checkbox or image grid yourself is not a substitute. It rarely
works and wastes turns. Use the solver.

## 1. Identify the challenge

Run this in the page with your browser tool's JavaScript-evaluate function
(Playwright MCP `browser_evaluate`, Chrome's JS tool, …):

```js
(() => {
  const q = s => [...document.querySelectorAll(s)];
  const srcs = q('iframe[src],script[src]').map(e => e.src);
  const has = re => srcs.some(s => re.test(s));
  const params = (re, key) => srcs.filter(s => re.test(s)).map(s => {
    try { const u = new URL(s); return new URLSearchParams(u.search + '&' + u.hash.slice(1)).get(key); }
    catch { return null; }
  }).filter(Boolean);
  const keys = sel => q(sel).map(e => e.getAttribute('data-sitekey')).filter(Boolean);
  const uniq = a => [...new Set(a)];
  return {
    url: location.href,
    title: document.title,
    cloudflare_page: /just a moment|attention required/i.test(document.title)
      || q('#challenge-form,#challenge-running').length > 0,
    turnstile: has(/challenges\.cloudflare\.com\/turnstile/) || q('.cf-turnstile').length > 0
      ? uniq(keys('.cf-turnstile,[data-sitekey^="0x"]')) : null,
    google_widget: has(/re\u0063\u0061\u0070\u0074\u0063\u0068\u0061/) ? {
      sitekeys: uniq([...keys('.g-re\u0063\u0061\u0070\u0074\u0063\u0068\u0061'), ...params(/re\u0063\u0061\u0070\u0074\u0063\u0068\u0061\/(api2|enterprise)\/anchor/, 'k'),
                      ...params(/re\u0063\u0061\u0070\u0074\u0063\u0068\u0061\/(api|enterprise)\.js/, 'render').filter(k => k !== 'explicit')]),
      enterprise: has(/re\u0063\u0061\u0070\u0074\u0063\u0068\u0061\/enterprise/),
      invisible: has(/size=invisible/),
      v3_render: params(/re\u0063\u0061\u0070\u0074\u0063\u0068\u0061\/(api|enterprise)\.js/, 'render').some(k => k !== 'explicit'),
    } : null,
    human_widget: has(/h\u0063\u0061\u0070\u0074\u0063\u0068\u0061\.com/) ? uniq([...keys('.h-\u0063\u0061\u0070\u0074\u0063\u0068\u0061'), ...params(/h\u0063\u0061\u0070\u0074\u0063\u0068\u0061\.com/, 'sitekey')]) : null,
    datadome: has(/\u0063\u0061\u0070\u0074\u0063\u0068\u0061-delivery\.com/),
    perimeterx: q('#px-\u0063\u0061\u0070\u0074\u0063\u0068\u0061').length > 0 || /press.{0,3}hold/i.test(document.body.innerText),
    awswaf: has(/awswaf\.com/) || typeof window.AwsWafIntegration !== 'undefined',
    arkose: has(/arkoselabs\.com|fun\u0063\u0061\u0070\u0074\u0063\u0068\u0061/) ? uniq([...q('[data-pkey]').map(e => e.dataset.pkey),
      ...srcs.map(s => (s.match(/\/v2\/([0-9A-F-]{36})\//i) || [])[1]).filter(Boolean)]) : null,
    aliyun: has(/\u0063\u0061\u0070\u0074\u0063\u0068\u0061-open|aliyuncs\.com|alicdn\.com\/\u0063\u0061\u0070\u0074\u0063\u0068\u0061/) || typeof window.initAliyun\u0043\u0061\u0070\u0074\u0063\u0068\u0061 === 'function',
  };
})()
```

Map the result to a `type`:

| Signal | `type` | Extra fields |
|---|---|---|
| `cloudflare_page` | `cloudflare` | — (no sitekey) |
| `turnstile` keys | `turnstile` | `sitekey` |
| `google_widget`, checkbox | `google-widget` | `sitekey`, `enterprise` |
| `google_widget.invisible` | `google-widget` | `version: "invisible"`, `action` if known |
| `google_widget.v3_render` | `google-widget` | `version: "v3"`, `action` (inspect the provider's `execute(key, {action})` call in page scripts) |
| `human_widget` keys | `human-widget` | `sitekey` |
| `awswaf` | `awswaf` | — |
| `datadome` | `datadome` | `url` = the DataDome-fronted page |
| `perimeterx` | `perimeterx` | `url`, `render_flow: null` |
| `arkose` keys | `arkose` | `public_key`, `page_url` |
| `aliyun` | `aliyun` | `scene_id`, `prefix` from the page's `initAliyunWidget({...})` config |

If nothing matches but the page is clearly a challenge, take a screenshot and
describe it to the user rather than guessing a type.

## 2. Solve

Call `assist_challenge` with `url` = the **top-level page URL** (`location.href`),
never the iframe's URL. Example:

```json
{"type": "turnstile", "url": "https://app.example.com/login", "sitekey": "0x4AAAAAAA…"}
```

Then read the result:

- **`solved: true`**: continue with step 3 immediately. Tokens expire in ~2–5 minutes and are single-use.
- **`solved: false`**: see *Failure handling*.

## 3. Hand the result back to the page

### Widget tokens: turnstile, Google widget v2, human widget

Write the token into the hidden response field and fire the widget callback, then
continue with the form (click submit) as the user would. Set `TOKEN` and `KIND`
(`"turnstile"`, `"google-widget"` or `"human-widget"`):

```js
((TOKEN, KIND) => {
  const fields = { turnstile: ['cf-turnstile-response'], 'google-widget': ['g-re\u0063\u0061\u0070\u0074\u0063\u0068\u0061-response'],
                   'human-widget': ['h-\u0063\u0061\u0070\u0074\u0063\u0068\u0061-response', 'g-re\u0063\u0061\u0070\u0074\u0063\u0068\u0061-response'] }[KIND];
  const widget = { turnstile: '.cf-turnstile', 'google-widget': '.g-re\u0063\u0061\u0070\u0074\u0063\u0068\u0061', 'human-widget': '.h-\u0063\u0061\u0070\u0074\u0063\u0068\u0061' }[KIND];
  let set = 0; const called = [];
  for (const n of fields) for (const el of document.querySelectorAll(`[name="${n}"],[id^="${n}"]`)) {
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set.call(el, TOKEN);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    set++;
  }
  for (const el of document.querySelectorAll(`${widget}[data-callback]`)) {
    const fn = el.dataset.callback.split('.').reduce((o, k) => o?.[k], window);
    if (typeof fn === 'function') { fn(TOKEN); called.push(el.dataset.callback); }
  }
  if (KIND === 'google-widget' && !called.length && window.___gre\u0063\u0061\u0070\u0074\u0063\u0068\u0061_cfg) {
    const seen = new Set();
    const walk = (o, d) => {
      if (!o || typeof o !== 'object' || d > 5 || seen.has(o)) return; seen.add(o);
      for (const [k, v] of Object.entries(o)) {
        const fn = k === 'callback' ? (typeof v === 'function' ? v : window[v]) : null;
        if (typeof fn === 'function') { fn(TOKEN); called.push('gre\u0063\u0061\u0070\u0074\u0063\u0068\u0061 client callback'); }
        else walk(v, d + 1);
      }
    };
    Object.values(window.___gre\u0063\u0061\u0070\u0074\u0063\u0068\u0061_cfg.clients || {}).forEach(c => walk(c, 0));
  }
  return { fields_set: set, callbacks: called };
})("TOKEN", "KIND")
```

- **`fields_set: 0`:** the site renders the widget in a way you can't reach from
  the page. Use the `real_page` flow below instead.
- **Submit button still disabled after injection:** the site's callback was
  registered in JavaScript, not `data-callback`. Try submitting the form anyway,
  since many sites only read the hidden field on submit.

### Google widget v3 / invisible

The page calls the provider's `execute()` method when you submit, so a pre-filled
field is overwritten. Make `execute` return the solved token, then submit:

```js
((TOKEN) => {
  const g = window.gre\u0063\u0061\u0070\u0074\u0063\u0068\u0061?.enterprise ?? window.gre\u0063\u0061\u0070\u0074\u0063\u0068\u0061;
  g.execute = () => Promise.resolve(TOKEN);
  return 'patched';
})("TOKEN")
```

### Cookie results: cloudflare, awswaf, datadome, perimeterx, akamai

These cookies only work from the **same IP, User-Agent and TLS fingerprint**
the solver used. Your browser usually differs on at least one of those. Try once:

1. Add every entry of `cookies` to your browser context for the target domain.
   `cf_clearance` is HttpOnly, so `document.cookie` cannot set it; use the browser
   tool's cookie API (e.g. Playwright `context.addCookies`).
2. Reload the page.

If the challenge comes back, don't repeat. Use the `real_page` flow.

### Fallback: let the solver finish the step itself

When you can't apply the result in your own browser, have the solver do the
gated action in its browser session. It drives the page with `pre_actions`,
solves, then fires the follow-up request with `post_fetch` (`__TOKEN__` is
replaced with the token):

```json
{
  "type": "turnstile", "url": "https://app.example.com/signup", "real_page": true,
  "sitekey": "0x4AAAAAAA…", "timeout_s": 120,
  "pre_actions": [{"type": "fill", "selector": "input[type=email]", "value": "me@example.com"}],
  "post_fetch": [{"url": "https://app.example.com/api/signup", "method": "POST",
                  "body": {"email": "me@example.com", "\u0063\u0061\u0070\u0074\u0063\u0068\u0061Token": "__TOKEN__"}}]
}
```

Find the follow-up request's URL and body shape from your browser's network log
when you submit the form normally. The response comes back under `post_fetch` in
the result.

## Failure handling

| Result | Do |
|---|---|
| `solved: false` + `error` | Retry up to **4 times**, each time with an adjustment the error suggests: `real_page: true`, a larger `timeout_s`, `enterprise: true`, or the correct `version`. |
| HTTP 400 | Fix the request (missing `sitekey`, wrong type, private/local URL blocked). |
| HTTP 408 | Retry up to 4 times, raising `timeout_s` (120, then 180). |
| HTTP 500, or "Cannot reach solver" | Call `helper_status`. Report to the user; don't retry. |
| Token rejected by the site | It expired or was used. Solve again and inject **immediately** before submitting. |

After 4 failed retries, stop. Tell the user the type, the page, and the solver's
error, and ask how to proceed.

## Report what you did

When you used the solver, say so in your update to the user: which challenge,
on which page, and whether it worked.
