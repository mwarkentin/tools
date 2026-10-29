# AGENTS.md

This repo is the source of [tools.michaelwarkentin.com](https://tools.michaelwarkentin.com):
small single-file HTML tools, published by GitHub Pages on every push to `main`.

## Layout

- `*.html` at the top level: one file per tool. The filename is the URL:
  `foo.html` is served at `/foo`.
- `README.md`: the tool list. The build turns it into `index.html`.
- `footer.js`: shared footer the build adds to every tool.
- `telemetry.js`: error reporting through Sentry, which the build inlines
  into every tool's `<head>`. See Security.
- `python/`: single-file Python scripts, published at `/python/<name>.py`.
- `build.sh` and `scripts/`: assemble the site in `_site/` (never committed).
  The build also generates `index.html`, `colophon.html`, `sitemap.xml` and
  `tools.json`, so don't create those by hand.
- `tests/`: pytest with Playwright.

## Rules for every tool

- One `.html` file with inline `<style>` and vanilla JavaScript in
  `<script type="module">`. No React, no JSX, no npm, no build step.
- Load libraries from `cdn.jsdelivr.net` or `cdnjs.cloudflare.com`, pinned
  to an exact version (`croner@10.0.1`, never `croner@10` or `croner`).
  Prefer a package's own ESM file; for a UMD-only package, use a classic
  `<script src>` and read its global from the module. The one other host is
  `browser.sentry-cdn.com`, for `telemetry.js` only.
- Phone first: usable at 375px wide with no sideways scrolling. Inputs,
  textareas and selects use `font-size: 16px` or larger so iOS doesn't zoom.
  Put a Copy button beside any output meant to be pasted elsewhere.
- Keep shareable state in the URL (query string or `#fragment`), updated
  with `history.replaceState` as it changes, so results can be bookmarked.
  Keep drafts and API keys in `localStorage`, never in the source. Prefix
  `localStorage` keys with the tool's name, because all tools share one origin.
- The `<head>` has a `<title>`,
  `<meta name="viewport" content="width=device-width, initial-scale=1">` and
  a one-sentence `<meta name="description" content="...">`. The index and
  colophon show that description.
- System font stack, two-space indentation, and dark mode support
  (`color-scheme: light dark` plus `prefers-color-scheme`).
- Small enough to rewrite from scratch: a few hundred lines.
- Don't make `<body>` a flex or grid container; wrap the tool in `<main>`
  so the footer lands below it. A tool can opt out of the footer with
  `<body data-hide-footer>`, and out of all telemetry with
  `<body data-no-telemetry>` (see Security).

## Adding or changing a tool

1. Look at the existing tools first and reuse their patterns: copy buttons,
   URL state, light and dark colours.
2. Create `foo.html` following the rules above.
3. Link it from `README.md` under the right heading:
   `- [Title](https://tools.michaelwarkentin.com/foo): what it does`.
4. Add `tests/test_foo.py` that drives the tool the way a person would:
   type input, check output. `tests/test_tools.py` already smoke-tests
   every tool.
5. Run `uv run pytest` and make sure it passes.
6. In the commit message, say what changed and include the URL of the chat
   or agent session that produced it. The colophon publishes those links.

## Commands

```sh
uv run playwright install chromium   # once
uv run pytest                        # builds the site into a temp dir, then tests it
uv run ./build.sh && python3 -m http.server -d _site 8000   # preview the real site
```

The smoke tests load every tool at 375px wide and fail on console errors,
uncaught exceptions, failed requests, sideways scrolling, text inputs under
16px or a missing footer. They also check the `<head>` metadata, CDN version
pins and the README link.

In a Claude Code on the web sandbox, the default network policy can block
`cdn.jsdelivr.net`, `cdnjs.cloudflare.com` and `browser.sentry-cdn.com`
(which `tests/test_telemetry.py` loads). A test failing with
`Failed: https://cdn.jsdelivr.net/...` means the sandbox can't reach the CDN,
not that the tool is broken. Ask for those hosts to be allowed. CI has full
network access.

## Security

- Every tool runs on the same origin, so any tool can read every other
  tool's `localStorage`, API keys included. Only add code that has been
  read; never host someone else's HTML here.
- This repo is public. Keep secrets, internal hostnames, project names and
  other work specifics out of tools, tests and commit messages.
- `telemetry.js` reports errors to Sentry, but tools hold pasted and typed
  text in the page, the URL and `localStorage`, so it sends only an error's
  type and stack trace, the page's path, the browser and the release. No
  error messages (they can quote input), query strings, fragments,
  breadcrumbs, IP addresses or session replays. Keep it that way, and don't
  call Sentry from a tool. `telemetry.js` does nothing until `SENTRY_DSN` is
  set, and only runs on tools.michaelwarkentin.com. A tool whose input could
  be sensitive opts out with `<body data-no-telemetry>`, and the build then
  leaves `telemetry.js` off its page entirely, so nothing on it records
  anything. Log Prettifier does, because people paste logs into it. Anything
  added to `telemetry.js` later, such as page-view counts, must keep that
  true. `tests/test_telemetry.py`
  types a marker string into a tool, makes it fail several ways and fails if
  the marker reaches Sentry. The SDK is pinned with an integrity hash; to
  update it, change the URL and the hash
  (`curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A`).

## APIs that work from the browser

These send CORS headers, so a tool can call them with `fetch()`:

- GitHub: `api.github.com` (60 unauthenticated requests an hour) and
  `raw.githubusercontent.com`
- Gists: `api.github.com/gists/<id>`
- PyPI: `pypi.org/pypi/<package>/json`
- Bluesky: `public.api.bsky.app/xrpc/...`
- iNaturalist: `api.inaturalist.org/v1/...`
- OSV.dev: `api.osv.dev/v1/query`
- Wikipedia: `en.wikipedia.org/w/api.php?origin=*&...` and
  `en.wikipedia.org/api/rest_v1/...`

An API without CORS needs a server-side proxy such as a Cloudflare Worker.
Ask before adding one.

## Python scripts

Each script in `python/` is a single file that runs with `uv run`, from a
checkout or straight from its URL
(`uv run https://tools.michaelwarkentin.com/python/foo.py`). Start every
file with an inline script metadata block, and use click for command-line
options and httpx for HTTP:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click",
#     "httpx",
# ]
# ///
```
