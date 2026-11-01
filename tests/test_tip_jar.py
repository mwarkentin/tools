"""The tip jar link: hidden until TIP_URL is set, then tagged with its source."""

from __future__ import annotations

import re

import build_colophon
import build_index
import common
from playwright.sync_api import Page, expect

from common import ROOT, render_page, tip_link

FAKE_TIP_URL = "https://buy.stripe.com/test_tipjar"
FOOTER_TIP_URL = re.compile(r"^const TIP_URL = '(.*)';$", re.MULTILINE)


def footer_source() -> str:
    return (ROOT / "footer.js").read_text("utf-8")


def test_footer_and_build_share_one_tip_url():
    match = FOOTER_TIP_URL.search(footer_source())
    assert match, "footer.js needs a `const TIP_URL = '...';` line"
    assert match.group(1) == common.TIP_URL, "TIP_URL differs between footer.js and scripts/common.py"


def test_tip_link_tags_the_source(monkeypatch):
    monkeypatch.setattr(common, "TIP_URL", FAKE_TIP_URL)
    assert tip_link("tools-home") == f"{FAKE_TIP_URL}?client_reference_id=tools-home"
    # Stripe drops a reference with anything but letters, digits, - and _.
    assert tip_link("tools-a.b c") == f"{FAKE_TIP_URL}?client_reference_id=tools-a_b_c"
    monkeypatch.setattr(common, "TIP_URL", f"{FAKE_TIP_URL}?prefilled_promo_code=x")
    assert tip_link("tools").endswith("?prefilled_promo_code=x&client_reference_id=tools")


def test_header_has_no_tip_link_without_url():
    assert "Tip jar" not in render_page("Title", "<p>body</p>")


def test_home_and_colophon_link_the_tip_jar_once_url_is_set(monkeypatch):
    monkeypatch.setattr(common, "TIP_URL", FAKE_TIP_URL)
    home = build_index.build_index("# Tools\n", [])
    colophon = build_colophon.build_colophon({}, [])
    assert f'<a href="{FAKE_TIP_URL}?client_reference_id=tools-home">Tip jar</a></nav>' in home
    assert f'<a href="{FAKE_TIP_URL}?client_reference_id=tools-colophon">Tip jar</a></nav>' in colophon


def test_footer_has_no_tip_link_without_url(page: Page, site_url):
    page.goto(f"{site_url}/k8s-quantity")
    footer = page.locator("footer[data-tools-footer]")
    expect(footer).to_be_visible()
    expect(footer.get_by_role("link", name="Tip jar")).to_have_count(0)


def test_footer_tip_link_names_the_tool(page: Page, site_url, errors):
    patched = FOOTER_TIP_URL.sub(f"const TIP_URL = '{FAKE_TIP_URL}';", footer_source())
    page.route(
        "**/footer.js*",
        lambda route: route.fulfill(body=patched, content_type="text/javascript"),
    )
    page.set_viewport_size({"width": 375, "height": 740})
    page.goto(f"{site_url}/k8s-quantity")

    link = page.locator("footer[data-tools-footer]").get_by_role("link", name="Tip jar")
    expect(link).to_have_attribute("href", f"{FAKE_TIP_URL}?client_reference_id=tools-k8s-quantity")
    assert page.evaluate("document.documentElement.scrollWidth") <= 375
    assert errors == []
