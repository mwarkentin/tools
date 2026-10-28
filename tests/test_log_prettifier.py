import pytest
from playwright.sync_api import Page, expect


@pytest.fixture
def tool(page: Page, site_url):
    page.goto(f"{site_url}/log-prettifier")
    return page


def test_parses_json_logfmt_and_plain_lines(tool: Page, errors):
    tool.click("#example")

    entries = tool.locator(".entry")
    expect(entries).to_have_count(5)
    expect(tool.locator("#stats")).to_have_text("5 entries · 2 errors · 1 warning")
    # pino's numeric level 30 is info; extra JSON keys become fields.
    expect(entries.nth(0).locator(".level")).to_have_text("INFO")
    expect(entries.nth(0).locator(".fields")).to_have_text("method=GET path=/health status=200")
    expect(entries.nth(2)).to_have_class("entry warn")
    expect(entries.nth(2).locator(".message")).to_have_text("retrying upstream")
    # The Python traceback stays with the line that logged it.
    expect(entries.nth(3).locator(".extra")).to_contain_text("ValueError: bad payload")
    # ANSI colour codes are stripped.
    expect(entries.nth(4).locator(".message")).to_have_text("shutdown complete")
    assert errors == []


def test_filters_by_level_and_text(tool: Page):
    tool.click("#example")
    tool.select_option("#level", "error")
    expect(tool.locator(".entry")).to_have_count(2)
    expect(tool.locator("#stats")).to_contain_text("showing 2")
    assert "level=error" in tool.url

    tool.select_option("#level", "")
    tool.fill("#filter", "billing")
    expect(tool.locator(".entry")).to_have_count(1)


def test_copy_as_markdown(tool: Page):
    tool.context.grant_permissions(["clipboard-read", "clipboard-write"])
    tool.click("#example")
    tool.select_option("#level", "warn")
    tool.uncheck("#fields")
    tool.click("#copy-markdown")

    expect(tool.locator("#copy-markdown")).to_have_text("Copied")
    assert tool.evaluate("navigator.clipboard.readText()") == "\n".join(
        [
            "```text",
            "2026-10-27T14:02:11.482Z ERROR payment failed",
            "2026-10-27T14:02:12Z WARN  retrying upstream",
            "2026-10-27 14:02:13,004 ERROR worker: job crashed",
            "Traceback (most recent call last):",
            '  File "worker.py", line 42, in run',
            "    process(job)",
            "ValueError: bad payload",
            "```",
        ]
    )


def test_markdown_fence_outgrows_backticks_in_logs(tool: Page):
    tool.context.grant_permissions(["clipboard-read", "clipboard-write"])
    tool.fill("#input", "INFO wrote ```code``` to the log")
    tool.click("#copy-markdown")
    expect(tool.locator("#copy-markdown")).to_have_text("Copied")
    assert tool.evaluate("navigator.clipboard.readText()").startswith("````text\n")


def test_keeps_draft_after_reload(tool: Page):
    tool.fill("#input", "level=info msg=hello user=42")
    tool.reload()
    expect(tool.locator("#input")).to_have_value("level=info msg=hello user=42")
    expect(tool.locator(".entry .fields")).to_have_text("user=42")
