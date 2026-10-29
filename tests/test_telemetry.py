"""What telemetry.js sends to Sentry: nothing off the production site, and
nothing typed into a tool on it.

These tests serve the built site at https://tools.michaelwarkentin.com with
Playwright's page.route, give telemetry.js a test DSN and catch every envelope
the Sentry SDK sends. The SDK itself comes from browser.sentry-cdn.com, so the
browser checks its integrity hash.
"""

from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page, Route

from common import BASE_URL

DSN = "https://public@sentry.test/1"
SECRET = "hunter2-do-not-send"
DSN_LINE = re.compile(r"const SENTRY_DSN = '[^']*';")


def with_test_dsn(text: str) -> str:
    assert DSN_LINE.search(text), "telemetry.js should set SENTRY_DSN"
    return DSN_LINE.sub(f"const SENTRY_DSN = '{DSN}';", text)


class FakeSentry:
    """Answers the SDK's POSTs and keeps each envelope's items."""

    def __init__(self):
        self.bodies: list[str] = []

    def handle(self, route: Route) -> None:
        self.bodies.append(route.request.post_data or "")
        route.fulfill(status=200, json={}, headers={"Access-Control-Allow-Origin": "*"})

    def items(self, kind: str) -> list[dict]:
        found = []
        for body in self.bodies:
            lines = body.splitlines()[1:]
            for header, payload in zip(lines[::2], lines[1::2]):
                if json.loads(header).get("type") == kind:
                    found.append(json.loads(payload))
        return found

    def wait_for(self, page: Page, kind: str, count: int = 1) -> list[dict]:
        for _ in range(200):
            if len(self.items(kind)) >= count:
                return self.items(kind)
            page.wait_for_timeout(100)
        pytest.fail(f"expected {count} {kind} item(s), got {self.items(kind)}")


@pytest.fixture
def sentry(page: Page) -> FakeSentry:
    fake = FakeSentry()
    page.route("https://sentry.test/**", fake.handle)
    return fake


@pytest.fixture
def production(page: Page, site_dir: Path) -> str:
    """Serve the built site as the production host, with the test DSN."""

    def handle(route: Route) -> None:
        path = urlparse(route.request.url).path.strip("/") or "index.html"
        file = next((f for f in (site_dir / path, site_dir / f"{path}.html") if f.is_file()), None)
        if file is None:
            route.fulfill(status=404)
            return
        content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        body = file.read_bytes()
        if file.suffix == ".html":
            body = with_test_dsn(body.decode("utf-8")).encode("utf-8")
        route.fulfill(status=200, body=body, content_type=content_type)

    page.route(f"{BASE_URL}/**", handle)
    return BASE_URL


def test_telemetry_does_nothing_on_other_hosts(page: Page, site_url, errors):
    def handle(route: Route) -> None:
        response = route.fetch()
        route.fulfill(response=response, body=with_test_dsn(response.text()))

    page.route(f"{site_url}/k8s-quantity", handle)
    requested: list[str] = []
    page.on("request", lambda request: requested.append(request.url))
    page.goto(f"{site_url}/k8s-quantity", wait_until="networkidle")

    assert [url for url in requested if "sentry" in url] == []
    assert errors == []


def test_errors_reach_sentry_without_anything_typed(page: Page, production, sentry):
    page.goto(f"{production}/log-prettifier?q={SECRET}#{SECRET}")
    page.fill("#input", f'{{"level":"error","msg":"{SECRET}"}}')
    page.wait_for_function("window.Sentry?.getClient()")
    page.route("https://api.test/**", lambda route: route.fulfill(status=200, body="{}"))

    # Three ways input ends up in an error: an engine message that quotes it,
    # a rejection with it as the reason, and a message built from it in the
    # tool's own code (render() calls history.replaceState on every edit).
    # The console line and the request would be breadcrumbs.
    page.add_script_tag(content="""
      console.log('typed', document.querySelector('#input').value);
      fetch('https://api.test/?q=' + document.querySelector('#filter').value).catch(() => {});
      setTimeout(() => JSON.parse(document.querySelector('#filter').value));
      setTimeout(() => Promise.reject({ input: document.querySelector('#input').value }));
      history.replaceState = () => { throw new Error('Bad line: ' + document.querySelector('#input').value); };
    """)
    page.fill("#input", f'{{"level":"warn","msg":"{SECRET} again"}}')
    events = sentry.wait_for(page, "event", count=3)

    assert SECRET not in "".join(sentry.bodies)
    assert "{{auto}}" not in "".join(sentry.bodies)
    assert sorted(e["exception"]["values"][0]["type"] for e in events) == [
        "Error", "SyntaxError", "UnhandledRejection",
    ]
    for event in events:
        assert event["request"]["url"] == f"{production}/log-prettifier"
        assert event["release"].startswith("tools@")
        assert event["sdk"]["settings"]["infer_ip"] == "never"
        assert "user" not in event and "breadcrumbs" not in event
    thrown = next(e for e in events if e["exception"]["values"][0]["type"] == "Error")
    frames = thrown["exception"]["values"][0]["stacktrace"]["frames"]
    assert any(f["function"].endswith("render") and f["filename"] == f"{production}/log-prettifier" for f in frames)
    assert sentry.items("replay_event") == []


def test_errors_before_the_sdk_loads_are_sent_once_it_does(page: Page, production, sentry):
    held: list[Route] = []
    page.route("https://browser.sentry-cdn.com/**", lambda route: held.append(route))
    page.add_init_script("addEventListener('DOMContentLoaded', () => { throw new Error('early'); })")
    page.goto(f"{production}/k8s-quantity", wait_until="domcontentloaded")
    while not held:
        page.wait_for_timeout(50)
    assert sentry.bodies == []

    held[0].continue_()
    [event] = sentry.wait_for(page, "event")
    assert event["exception"]["values"][0]["type"] == "Error"
    assert event["exception"]["values"][0]["mechanism"]["handled"] is False
