"""Tests for the build scripts and the site they assemble."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import build_index
from build_colophon import format_message
from build_sitemap import NAMESPACE, build_sitemap
from common import BASE_URL, extract_meta_description, tool_files
from gather_links import extract_urls
from publish_tools import inject_footer, inject_telemetry


def test_extract_urls_trims_punctuation_and_duplicates():
    message = (
        "Built in https://claude.ai/share/abc. See (https://example.com/x),\n"
        "again https://claude.ai/share/abc"
    )
    assert extract_urls(message) == ["https://claude.ai/share/abc", "https://example.com/x"]


def test_extract_meta_description_handles_attribute_order():
    assert extract_meta_description('<meta content="Hi &amp; bye" name="description">') == "Hi & bye"
    assert extract_meta_description("<title>No meta</title>") == ""


def test_format_message_links_urls_and_issue_numbers():
    html = format_message("Fix <b> (#12)\nhttps://example.com/a#3.")
    assert "&lt;b&gt;" in html
    assert '<a href="https://github.com/mwarkentin/tools/issues/12">#12</a>' in html
    # The #3 inside the URL stays part of the URL, and the full stop stays outside it.
    assert '<a href="https://example.com/a#3">https://example.com/a#3</a>.' in html


def test_format_message_reflows_wrapped_lines():
    message = (
        "Add a tool that does\nsomething useful.\n\n"
        "- first item that\n  wraps\n- second item\n\n"
        "Co-Authored-By: Someone\nClaude-Session: https://claude.ai/code/x"
    )
    assert format_message(message).split("<br>\n") == [
        "Add a tool that does something useful.",
        "",
        "- first item that wraps",
        "- second item",
        "",
        "Co-Authored-By: Someone",
        'Claude-Session: <a href="https://claude.ai/code/x">https://claude.ai/code/x</a>',
    ]


def test_inject_footer_goes_before_last_body_tag_once():
    page = "<body><pre></body></pre>\n</BODY>\n</html>"
    injected = inject_footer(page, "abc")
    assert injected.endswith('<script type="module" src="/footer.js?v=abc"></script>\n</BODY>\n</html>')
    assert inject_footer(injected, "abc") == injected
    assert inject_footer("<p>no body tag", "abc").endswith("/footer.js?v=abc\"></script>\n")


def test_inject_telemetry_goes_before_head_end_once():
    page = "<html><HEAD><title>t</title></HEAD><body></head></body>"
    injected = inject_telemetry(page, "run();\n", "tools@abc")
    assert injected == (
        '<html><HEAD><title>t</title><script data-telemetry data-release="tools@abc">\nrun();\n</script>\n'
        "</HEAD><body></head></body>"
    )
    assert inject_telemetry(injected, "run();", "tools@abc") == injected
    no_head = inject_telemetry("<p>no head", "run();", "")
    assert no_head == '<p>no head\n<script data-telemetry data-release="">\nrun();\n</script>\n'


def test_tools_are_published_with_telemetry(site_dir):
    for filename in tool_files():
        text = (site_dir / filename).read_text("utf-8")
        head, _ = text.split("</head>", 1)
        assert '<script data-telemetry data-release="tools@' in head
        assert "const SENTRY_DSN" in head


def test_build_index_fills_recent_section(monkeypatch):
    monkeypatch.setattr(build_index, "RECENT_LIMIT", 1)
    readme = "# Tools\n\n<!-- recently starts -->\n<!-- recently stops -->\n\n## All\n"
    tools = [
        {"slug": "old", "filename": "old.html", "title": "Old", "url": "/old",
         "created": "2026-01-01T10:00:00-05:00", "updated": "2026-03-01T10:00:00-05:00"},
        {"slug": "new", "filename": "new.html", "title": "New", "url": "/new",
         "created": "2026-02-01T10:00:00-05:00", "updated": "2026-02-01T10:00:00-05:00"},
    ]
    page = build_index.build_index(readme, tools)
    assert page.index("Recently added") < page.index("Recently updated") < page.index("<h2>All</h2>")
    added, updated = page.split("Recently updated")
    assert '<a href="/new">New</a>' in added
    assert '<a class="muted" href="/colophon#new.html">Feb 1, 2026</a>' in added
    assert '<a href="/old">Old</a>' in updated


def test_build_sitemap_lists_tools_and_generated_pages():
    tools = [
        {"url": "/b-tool", "updated": "2026-10-01T09:00:00-04:00"},
        {"url": "/a-tool", "updated": "2026-10-20T09:00:00-04:00"},
    ]
    root = ET.fromstring(build_sitemap(tools))
    entries = {
        url.findtext(f"{{{NAMESPACE}}}loc"): url.findtext(f"{{{NAMESPACE}}}lastmod")
        for url in root
    }
    assert list(entries) == [
        f"{BASE_URL}/",
        f"{BASE_URL}/a-tool",
        f"{BASE_URL}/b-tool",
        f"{BASE_URL}/colophon",
    ]
    assert entries[f"{BASE_URL}/"] == "2026-10-20"
    assert entries[f"{BASE_URL}/b-tool"] == "2026-10-01"


def test_site_contains_only_publishable_files(site_dir):
    published = {path.relative_to(site_dir).as_posix() for path in site_dir.rglob("*") if path.is_file()}
    expected = {*tool_files(), "index.html", "colophon.html", "footer.js", "tools.json", "sitemap.xml", "robots.txt"}
    assert expected <= published
    leftovers = {name for name in published - expected if not name.startswith("python/")}
    assert leftovers == set(), "unexpected files would be deployed"


def test_every_tool_gets_footer_and_colophon_entry(site_dir):
    colophon = (site_dir / "colophon.html").read_text("utf-8")
    for filename in tool_files():
        assert 'src="/footer.js?v=' in (site_dir / filename).read_text("utf-8")
        assert f'id="{filename}"' in colophon
