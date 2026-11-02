"""What analytics.js sends to Counterscale: one page view per page, with its
path and the referring site's origin, nothing typed into a tool, nothing
from tools that opt out and nothing off the production site.

These tests serve the built site at https://tools.michaelwarkentin.com with
Playwright's page.route, point analytics.js at a fake Counterscale and keep
every request it gets. The tracker itself comes from jsDelivr, so the browser
checks its integrity hash. Sentry is switched off, so only analytics runs.
"""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import pytest
from playwright.sync_api import Page, Route

from common import BASE_URL

COUNTERSCALE = "https://counterscale.test"
TRACKER = "https://cdn.jsdelivr.net/npm/@counterscale/tracker@*/**"
URL_LINE = re.compile(r"const COUNTERSCALE_URL = '[^']*';")
DSN_LINE = re.compile(r"const SENTRY_DSN = '[^']*';")
CORS = {"Access-Control-Allow-Origin": "*"}
GIF = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


def with_counterscale(text: str, url: str) -> str:
    """Point analytics.js, on pages that have it, at url, and switch Sentry off."""
    return DSN_LINE.sub("const SENTRY_DSN = '';", URL_LINE.sub(f"const COUNTERSCALE_URL = '{url}';", text))


class FakeCounterscale:
    """Answers the tracker's two requests, /cache and /collect, and keeps them."""

    def __init__(self):
        self.requests: list[str] = []

    def handle(self, route: Route) -> None:
        url = route.request.url
        self.requests.append(url)
        if urlparse(url).path == "/cache":
            route.fulfill(status=200, json={"ht": 1}, headers=CORS)
        else:
            route.fulfill(status=200, body=GIF, content_type="image/gif", headers=CORS)

    def page_views(self) -> list[dict]:
        return [
            dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
            for url in self.requests
            if urlparse(url).path == "/collect"
        ]

    def wait_for(self, page: Page, count: int = 1) -> list[dict]:
        for _ in range(100):
            if len(self.page_views()) >= count:
                page.wait_for_timeout(300)  # time for any extra page view to show up
                return self.page_views()
            page.wait_for_timeout(100)
        pytest.fail(f"expected {count} page view(s), got {self.page_views()}")


@pytest.fixture
def counterscale(page: Page) -> FakeCounterscale:
    fake = FakeCounterscale()
    page.route(f"{COUNTERSCALE}/**", fake.handle)
    return fake


def serve_as_production(page: Page, site_dir: Path, counterscale_url: str) -> str:
    """Serve the built site as the production host, with analytics pointed at counterscale_url."""

    def handle(route: Route) -> None:
        path = urlparse(route.request.url).path.strip("/") or "index.html"
        file = next((f for f in (site_dir / path, site_dir / f"{path}.html") if f.is_file()), None)
        if file is None:
            route.fulfill(status=404)
            return
        body = file.read_bytes()
        if file.suffix == ".html":
            body = with_counterscale(body.decode("utf-8"), counterscale_url).encode("utf-8")
        route.fulfill(status=200, body=body, content_type=mimetypes.guess_type(file.name)[0])

    page.route(f"{BASE_URL}/**", handle)
    return BASE_URL


@pytest.fixture
def production(page: Page, site_dir: Path) -> str:
    return serve_as_production(page, site_dir, COUNTERSCALE)


SECRET = "hunter2-do-not-send"


def test_a_tool_sends_its_path_and_nothing_typed(page: Page, production, counterscale, errors):
    # Tools keep their input in the query string, and the tracker would
    # otherwise read ?source= and utm_ parameters from it.
    page.goto(
        f"{production}/k8s-quantity?q={SECRET}&source={SECRET}&utm_source={SECRET}#{SECRET}",
        referer=f"https://news.example/item?id={SECRET}",
    )
    counterscale.wait_for(page)
    page.fill("#input", f"{SECRET} again")  # the tool calls history.replaceState on every edit
    page.wait_for_timeout(500)

    assert counterscale.page_views() == [
        {"sid": "tools", "h": BASE_URL, "p": "/k8s-quantity", "r": "https://news.example", "ht": "1"}
    ]
    assert not [url for url in counterscale.requests if SECRET in url]
    assert errors == []


def test_home_page_and_colophon_count_and_moves_within_the_site_have_no_referrer(
    page: Page, production, counterscale, errors
):
    # Unlike a tool, the home page leaves its query string as it is, so the
    # tracker would see these if analytics.js didn't keep them from it.
    page.goto(f"{production}/?source={SECRET}&utm_source={SECRET}#{SECRET}")
    counterscale.wait_for(page, 1)  # the tracker loads after the page, so don't click away first
    page.click('main a[href$="/cron-explainer"]')
    page.wait_for_url(f"{production}/cron-explainer")
    counterscale.wait_for(page, 2)
    page.goto(f"{production}/colophon")
    views = counterscale.wait_for(page, 3)

    assert views[0] == {"sid": "tools", "h": BASE_URL, "p": "/", "r": "", "ht": "1"}
    assert [(view["p"], view["r"]) for view in views] == [("/", ""), ("/cron-explainer", ""), ("/colophon", "")]
    assert not [url for url in counterscale.requests if SECRET in url]
    assert errors == []


def test_log_prettifier_counts_nothing(page: Page, production, counterscale):
    requested: list[str] = []
    page.on("request", lambda request: requested.append(request.url))
    page.goto(f"{production}/log-prettifier?q={SECRET}", wait_until="networkidle")
    page.fill("#input", f'{{"level":"error","msg":"{SECRET}"}}')
    page.wait_for_timeout(1000)

    assert page.locator("script[data-analytics]").count() == 0
    assert [url for url in requested if not url.startswith(f"{production}/")] == []
    assert counterscale.requests == []


def test_nothing_loads_until_counterscale_url_is_set(page: Page, site_dir, counterscale):
    production = serve_as_production(page, site_dir, "")
    requested: list[str] = []
    page.on("request", lambda request: requested.append(request.url))
    page.goto(f"{production}/cron-explainer", wait_until="networkidle")

    assert [url for url in requested if "counterscale" in url] == []


def test_nothing_loads_on_other_hosts(page: Page, site_url, counterscale):
    def handle(route: Route) -> None:
        response = route.fetch()
        route.fulfill(response=response, body=with_counterscale(response.text(), COUNTERSCALE))

    page.route(f"{site_url}/k8s-quantity", handle)
    requested: list[str] = []
    page.on("request", lambda request: requested.append(request.url))
    page.goto(f"{site_url}/k8s-quantity", wait_until="networkidle")

    assert [url for url in requested if "counterscale" in url] == []


def test_a_tampered_tracker_never_runs(page: Page, production, counterscale):
    page.route(TRACKER, lambda route: route.fulfill(
        body="window.tampered = true; export const init = () => {}, trackPageview = () => {};",
        content_type="text/javascript",
        headers=CORS,
    ))
    page.goto(f"{production}/k8s-quantity", wait_until="networkidle")
    page.wait_for_timeout(300)

    assert page.evaluate("window.tampered") is None
    assert counterscale.requests == []


def test_a_blocked_tracker_leaves_the_tool_alone(page: Page, production, counterscale):
    uncaught: list[str] = []
    page.on("pageerror", lambda exc: uncaught.append(str(exc)))
    page.route(TRACKER, lambda route: route.abort("blockedbyclient"))
    page.goto(f"{production}/k8s-quantity", wait_until="networkidle")
    page.fill("#input", "128Mi")
    page.wait_for_timeout(300)

    assert uncaught == []
    assert counterscale.requests == []
    assert page.locator("#input").input_value() == "128Mi"
