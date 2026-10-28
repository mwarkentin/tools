from urllib.parse import quote

from playwright.sync_api import Page, expect

# Wednesday at noon UTC, a few days before Toronto leaves daylight saving time.
NOW = "2026-10-28T12:00:00Z"


def open_tool(page: Page, site_url: str, query: str = "") -> None:
    page.clock.set_fixed_time(NOW)
    page.goto(f"{site_url}/cron-explainer{query}")


def test_lists_next_runs_in_toronto_time_across_dst(page: Page, site_url, errors):
    open_tool(page, site_url, "?cron=" + quote("0 9 * * 1-5") + "&tz=UTC&show=America/Toronto")

    expect(page.locator("#description")).to_have_text("At 09:00 AM, Monday through Friday (UTC)")
    runs = page.locator("#runs li .when")
    expect(runs).to_have_count(10)
    expect(runs.nth(0)).to_have_text("Thu, Oct 29, 2026, 5:00 AM EDT")
    expect(runs.nth(2)).to_have_text("Mon, Nov 2, 2026, 4:00 AM EST")
    expect(page.locator("#runs li .detail").nth(0)).to_have_text("in 21 hours · Thu, 9:00 AM UTC")
    assert errors == []


def test_typing_updates_results_and_url(page: Page, site_url):
    open_tool(page, site_url)
    page.fill("#cron", "*/15 * * * *")

    expect(page.locator("#description")).to_have_text("Every 15 minutes (UTC)")
    expect(page.locator("#runs li .when").nth(0)).to_have_text("Wed, Oct 28, 2026, 8:15 AM EDT")
    assert "cron=*%2F15+*+*+*+*" in page.url


def test_cron_tz_prefix_overrides_schedule_zone(page: Page, site_url):
    open_tool(page, site_url, "?cron=" + quote("CRON_TZ=Europe/London 30 2 * * 0"))

    expect(page.locator("#source-tz")).to_be_disabled()
    expect(page.locator("#description")).to_contain_text("(Europe/London)")
    # London is back on GMT from October 25; Toronto stays on EDT until November 1.
    expect(page.locator("#runs li .when").nth(0)).to_have_text("Sat, Oct 31, 2026, 10:30 PM EDT")


def test_invalid_expression_shows_error(page: Page, site_url, errors):
    open_tool(page, site_url)
    page.fill("#cron", "every day at nine")

    expect(page.locator("#error")).not_to_be_empty()
    expect(page.locator("#runs li")).to_have_count(0)
    assert errors == []


def test_copy_button_copies_runs(page: Page, site_url):
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    open_tool(page, site_url, "?cron=" + quote("0 0 1 * *") + "&tz=UTC&show=UTC")
    page.click("#copy")

    expect(page.locator("#copy")).to_have_text("Copied")
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied.splitlines()[0] == "0 0 1 * *"
    assert "Sun, Nov 1, 2026, 12:00 AM UTC" in copied
