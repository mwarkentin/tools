#!/usr/bin/env python3
"""Collect git history and metadata for every tool.

Writes two files to the repo root (both gitignored):

- gathered_links.json: each tool's commits and the URLs in their messages,
  read by build_colophon.py
- tools.json: one summary per tool, read by build_index.py and
  build_sitemap.py and published with the site

Adapted from gather_links.py in https://github.com/simonw/tools by Simon
Willison, licensed under the Apache License 2.0 (see LICENSE). Changed:
descriptions fall back to the tool's <meta name="description">, and
trailing punctuation is trimmed from URLs.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from common import ROOT, extract_meta_description, extract_title, tool_files

URL_PATTERN = re.compile(r"https?://\S+")
URL_TRAILING_PUNCTUATION = ".,;:!?)]}>\"'"


def get_commits(filename: str, root: Path = ROOT) -> list[dict]:
    """Commits that touched a file, newest first."""
    result = subprocess.run(
        # %x1f separates fields and %x00 separates commits; neither appears in messages.
        ["git", "log", "--format=%H%x1f%aI%x1f%B%x00", "--", filename],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    commits = []
    for record in result.stdout.split("\0"):
        record = record.strip("\n")
        if not record:
            continue
        commit_hash, date, message = record.split("\x1f", 2)
        commits.append({"hash": commit_hash, "date": date, "message": message.strip()})
    return commits


def extract_urls(text: str) -> list[str]:
    """URLs in a commit message, in order, without duplicates."""
    urls = []
    for match in URL_PATTERN.findall(text):
        url = match.rstrip(URL_TRAILING_PUNCTUATION)
        if url not in urls:
            urls.append(url)
    return urls


def extract_docs_description(docs_path: Path) -> str:
    """First paragraph of a tool's .docs.md file, if it has one."""
    if not docs_path.exists():
        return ""
    content = docs_path.read_text("utf-8").split("<!--", 1)[0].strip()
    paragraph = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            continue
        if not line:
            if paragraph:
                break
            continue
        paragraph.append(line)
    return " ".join(paragraph)


def gather(root: Path = ROOT) -> tuple[dict, list[dict]]:
    pages = {}
    tools = []
    for filename in tool_files(root):
        path = root / filename
        commits = get_commits(filename, root)
        urls = extract_urls("\n".join(commit["message"] for commit in commits))
        pages[filename] = {"commits": commits, "urls": urls}

        text = path.read_text("utf-8", errors="replace")
        slug = path.stem
        tools.append(
            {
                "filename": filename,
                "slug": slug,
                "title": extract_title(text, slug),
                "description": extract_docs_description(path.with_suffix(".docs.md"))
                or extract_meta_description(text),
                "url": f"/{slug}",
                "created": commits[-1]["date"] if commits else None,
                "updated": commits[0]["date"] if commits else None,
            }
        )
    tools.sort(key=lambda tool: tool["title"].lower())
    return {"pages": pages}, tools


def main() -> None:
    links, tools = gather()
    (ROOT / "gathered_links.json").write_text(json.dumps(links, indent=2), "utf-8")
    (ROOT / "tools.json").write_text(
        json.dumps(tools, indent=2, ensure_ascii=False), "utf-8"
    )
    print(f"Gathered history for {len(tools)} tools")


if __name__ == "__main__":
    main()
