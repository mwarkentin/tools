#!/usr/bin/env python3
"""Copy everything publishable into the site directory.

Each tool is copied with telemetry.js inlined before its </head>, unless it
opts out, and a <script> tag for footer.js added before its last </body>.
footer.js, tools.json and python/*.py are copied as they are. Anything not
listed here (scripts, tests, Markdown, telemetry.js itself) never reaches
the site.

Usage: publish_tools.py [SITE_DIR]
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

from common import ROOT, tool_files

FOOTER = "footer.js"
TELEMETRY = "telemetry.js"
# A tool opts out of telemetry, and gets no trace of it, with <body data-no-telemetry>.
NO_TELEMETRY = re.compile(r"<body\b[^>]*\sdata-no-telemetry\b", re.IGNORECASE)


def current_release(root: Path = ROOT) -> str:
    """The release Sentry files errors under: tools@ and the commit being built."""
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    return f"tools@{result.stdout.strip()}" if result.returncode == 0 else ""


def inject_telemetry(text: str, script: str, release: str) -> str:
    """Inline the telemetry script before </head>, or at the end, once.

    It's inline rather than a file so it runs before the tool's own code
    without holding up the page for another request. A tool that opts out
    is left as it is.
    """
    if "<script data-telemetry" in text or NO_TELEMETRY.search(text):
        return text
    tag = f'<script data-telemetry data-release="{release}">\n{script.strip()}\n</script>\n'
    index = text.lower().find("</head>")
    if index == -1:
        return f"{text.rstrip()}\n{tag}"
    return f"{text[:index]}{tag}{text[index:]}"


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

    telemetry = (root / TELEMETRY).read_text("utf-8")
    release = current_release(root)

    published = tool_files(root)
    for filename in published:
        text = (root / filename).read_text("utf-8")
        text = inject_telemetry(text, telemetry, release)
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
