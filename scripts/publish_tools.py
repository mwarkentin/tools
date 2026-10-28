#!/usr/bin/env python3
"""Copy everything publishable into the site directory.

Each tool is copied with a <script> tag for footer.js added before its last
</body>. footer.js, tools.json and python/*.py are copied as they are.
Anything not listed here (scripts, tests, Markdown) never reaches the site.

Usage: publish_tools.py [SITE_DIR]
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

from common import ROOT, tool_files

FOOTER = "footer.js"


def footer_tag(version: str) -> str:
    return f'<script type="module" src="/{FOOTER}?v={version}"></script>'


def inject_footer(text: str, version: str) -> str:
    """Add the footer script before the last </body>, or at the end."""
    if f'src="/{FOOTER}' in text:
        return text
    tag = footer_tag(version)
    index = text.lower().rfind("</body>")
    if index == -1:
        return f"{text.rstrip()}\n{tag}\n"
    return f"{text[:index]}{tag}\n{text[index:]}"


def publish(site_dir: Path, root: Path = ROOT) -> list[str]:
    site_dir.mkdir(parents=True, exist_ok=True)
    footer = root / FOOTER
    # Changes to footer.js get a new URL, so browsers don't keep a stale copy.
    version = hashlib.sha256(footer.read_bytes()).hexdigest()[:8]
    shutil.copy2(footer, site_dir / FOOTER)

    published = tool_files(root)
    for filename in published:
        text = (root / filename).read_text("utf-8")
        (site_dir / filename).write_text(inject_footer(text, version), "utf-8")

    tools_json = root / "tools.json"
    if tools_json.exists():
        shutil.copy2(tools_json, site_dir / "tools.json")

    scripts = sorted((root / "python").glob("*.py"))
    if scripts:
        (site_dir / "python").mkdir(exist_ok=True)
        for script in scripts:
            shutil.copy2(script, site_dir / "python" / script.name)

    return published


def main() -> None:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    published = publish(site_dir)
    print(f"Published {len(published)} tools to {site_dir}")


if __name__ == "__main__":
    main()
