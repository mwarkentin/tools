#!/usr/bin/env python3
"""Build index.html from README.md, with recently added and updated tools.

The recent lists replace whatever sits between the
<!-- recently starts --> and <!-- recently stops --> markers in README.md.

Adapted from build_index.py in https://github.com/simonw/tools by Simon
Willison, licensed under the Apache License 2.0 (see LICENSE). Changed: shares
page chrome with the colophon, writes into the site directory, and leaves
out the settings panel and the by-month link.

Usage: build_index.py [SITE_DIR]
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import markdown

from common import ROOT, SITE_NAME, format_date, parse_date, render_page

START_MARKER = "<!-- recently starts -->"
END_MARKER = "<!-- recently stops -->"
RECENT_LIMIT = 8

EXTRA_CSS = """
.recent { display: flex; flex-wrap: wrap; gap: 0 2rem; }
.recent section { flex: 1 1 16rem; }
.recent ul { list-style: none; padding: 0; margin: 0; }
"""


def select_recent(tools: list[dict], key: str, exclude: frozenset[str] = frozenset()) -> list[dict]:
    dated = [
        (parse_date(tool.get(key)), tool)
        for tool in tools
        if tool["slug"] not in exclude and parse_date(tool.get(key))
    ]
    dated.sort(key=lambda item: item[0], reverse=True)
    return [{**tool, "when": when} for when, tool in dated[:RECENT_LIMIT]]


def render_recent(tools: list[dict]) -> str:
    added = select_recent(tools, "created")
    updated = select_recent(
        [tool for tool in tools if tool.get("updated") != tool.get("created")],
        "updated",
        exclude=frozenset(tool["slug"] for tool in added),
    )
    sections = []
    for heading, entries in (("Recently added", added), ("Recently updated", updated)):
        if not entries:
            continue
        items = "\n".join(
            f'<li><a href="{tool["url"]}">{html.escape(tool["title"])}</a>'
            f' <a class="muted" href="/colophon#{tool["filename"]}">{format_date(tool["when"])}</a></li>'
            for tool in entries
        )
        sections.append(f"<section><h2>{heading}</h2>\n<ul>\n{items}\n</ul></section>")
    if not sections:
        return ""
    return '<div class="recent">\n' + "\n".join(sections) + "\n</div>"


def build_index(readme: str, tools: list[dict]) -> str:
    body = markdown.markdown(readme, extensions=["extra"])
    start, end = body.find(START_MARKER), body.find(END_MARKER)
    if 0 <= start < end:
        body = (
            body[: start + len(START_MARKER)]
            + "\n"
            + render_recent(tools)
            + "\n"
            + body[end:]
        )
    return render_page(SITE_NAME, body, extra_css=EXTRA_CSS)


def main() -> None:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    readme = (ROOT / "README.md").read_text("utf-8")
    tools_json = ROOT / "tools.json"
    tools = json.loads(tools_json.read_text("utf-8")) if tools_json.exists() else []
    (site_dir / "index.html").write_text(build_index(readme, tools), "utf-8")
    print("Built index.html")


if __name__ == "__main__":
    main()
