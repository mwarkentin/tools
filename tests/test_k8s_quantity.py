import re

import pytest
from playwright.sync_api import Locator, Page, expect


@pytest.fixture
def tool(page: Page, site_url):
    page.goto(f"{site_url}/k8s-quantity")
    return page


def conversion(scope: Page | Locator, suffix: str) -> Locator:
    """The value cell of a conversion table row, like "1.5Gi" in the Gi row."""
    rows = scope.locator("tr")
    label = rows.page.locator("td:first-child", has_text=re.compile(f"^{suffix}$"))
    return rows.filter(has=label).locator("td:last-child")


# Canonical forms match what k8s.io/apimachinery's Quantity.String() returns.
@pytest.mark.parametrize(
    "quantity, expected",
    [
        ("1.5Gi", "1536Mi"),
        ("2048Ki", "2Mi"),
        ("1Ki", "1Ki"),
        ("0.5Ki", "512"),
        ("0.5", "500m"),
        ("1000m", "1"),
        ("1.5k", "1500"),
        ("1000k", "1M"),
        ("1e3", "1e3"),
        ("0.1n", "1n"),
    ],
)
def test_canonical_form(tool: Page, quantity, expected):
    tool.fill("#input", quantity)
    expect(tool.locator(".canonical")).to_have_text(expected)


def test_totals_yaml_per_resource(tool: Page, errors):
    tool.fill(
        "#input",
        "resources:\n  requests:\n    cpu: 250m\n    memory: 512Mi\n"
        "- name: sidecar\n  image: nginx:1.27\n    cpu: 1.5\n    memory: 1Gi\n",
    )
    groups = tool.locator(".group")
    expect(groups.locator("h2")).to_have_text(["cpu", "memory"])
    expect(groups.nth(0).locator(".total")).to_have_text("1750m = 1.75 cores")
    expect(groups.nth(1).locator(".total")).to_have_text("1536Mi = 1,610,612,736 bytes")
    expect(conversion(groups.nth(1), "Gi")).to_have_text("1.5Gi")
    assert errors == []


def test_conversions_mark_inexact_values(tool: Page):
    tool.fill("#input", "128M")
    expect(conversion(tool, "Mi")).to_have_text("≈ 122.070313Mi")
    expect(conversion(tool, "k")).to_have_text("128,000k")


@pytest.mark.parametrize(
    "quantity, message",
    [
        ("512MB", "Drop the B: try 512M."),
        ("1K", "Use k (1000) or Ki (1024). There is no K."),
        ("512 Mi", "Remove the space before the suffix."),
    ],
)
def test_explains_common_mistakes(tool: Page, quantity, message):
    tool.fill("#input", quantity)
    expect(tool.locator(".items .error")).to_have_text(f"{quantity} {message}")


def test_state_round_trips_through_url(tool: Page, site_url):
    tool.fill("#input", "cpu: 100m\ncpu: 200m")
    assert "q=cpu%3A%20100m%0Acpu%3A%20200m" in tool.url
    tool.goto(tool.url)
    expect(tool.locator(".canonical")).to_have_text("300m")


def test_copy_button_copies_canonical_total(tool: Page):
    tool.context.grant_permissions(["clipboard-read", "clipboard-write"])
    tool.fill("#input", "256Mi\n256Mi")
    tool.click(".group button")
    expect(tool.locator(".group button")).to_have_text("Copied")
    assert tool.evaluate("navigator.clipboard.readText()") == "512Mi"
