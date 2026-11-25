"""clipfix: the macOS installer, run on Linux with swiftc and launchctl stubbed out.

CI can't build Swift against AppKit, so these check the installer's logic and
that the build publishes both files. Build clipfix.swift on a Mac before
committing changes to it.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
from pathlib import Path

import pytest

from common import ROOT

MACOS = ROOT / "macos"
INSTALLER = MACOS / "install-clipfix.sh"

SWIFTC = """#!/bin/sh
echo "swiftc $*" >> "$STUB_LOG"
while [ $# -gt 0 ]; do [ "$1" = "-o" ] && { shift; touch "$1"; }; shift; done
"""

# Pretends to be launchd: `print` succeeds only once something is bootstrapped.
LAUNCHCTL = """#!/bin/sh
echo "launchctl $*" >> "$STUB_LOG"
case "$1" in
  print) [ -f "$STUB_DIR/loaded" ] ;;
  bootstrap) touch "$STUB_DIR/loaded" ;;
  bootout) rm -f "$STUB_DIR/loaded" ;;
esac
"""

# Stands in for curl when the installer runs on its own, away from clipfix.swift.
CURL = """#!/bin/sh
echo "curl $*" >> "$STUB_LOG"
while [ $# -gt 0 ]; do [ "$1" = "-o" ] && { shift; echo "// downloaded" > "$1"; }; shift; done
"""


@pytest.fixture
def sandbox(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in (("swiftc", SWIFTC), ("launchctl", LAUNCHCTL), ("curl", CURL)):
        (stubs / name).write_text(body)
        (stubs / name).chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{stubs}:{os.environ['PATH']}",
        "STUB_DIR": str(tmp_path),
        "STUB_LOG": str(tmp_path / "calls.log"),
    }

    def run(script: Path = INSTALLER, *args: str) -> list[str]:
        subprocess.run(["bash", str(script), *args], env=env, check=True, capture_output=True)
        log = tmp_path / "calls.log"
        calls = log.read_text().splitlines() if log.exists() else []
        log.unlink(missing_ok=True)
        return calls

    run.home = home
    run.tmp = tmp_path
    return run


def test_installer_is_valid_bash():
    subprocess.run(["bash", "-n", str(INSTALLER)], check=True)


def test_install_builds_and_starts_agent(sandbox):
    calls = sandbox()
    binary = sandbox.home / ".local/bin/clipfix"
    assert f"swiftc -O -swift-version 5 {MACOS / 'clipfix.swift'} -o {binary}" in calls
    assert binary.exists()

    plist_path = sandbox.home / "Library/LaunchAgents/local.clipfix.plist"
    plist = plistlib.loads(plist_path.read_bytes())
    assert plist["Label"] == "local.clipfix"
    assert plist["ProgramArguments"] == [str(binary)]
    assert plist["RunAtLoad"] and plist["KeepAlive"]
    assert plist["StandardErrorPath"] == str(sandbox.home / "Library/Logs/clipfix.log")
    assert any(call.startswith("launchctl bootstrap gui/") for call in calls)


def test_reinstall_restarts_running_agent(sandbox):
    sandbox()
    calls = sandbox()
    assert any(call.startswith("launchctl kickstart -k gui/") for call in calls)
    assert not any(call.startswith("launchctl bootstrap") for call in calls)


def test_uninstall_removes_everything(sandbox):
    sandbox()
    calls = sandbox(INSTALLER, "uninstall")
    assert any(call.startswith("launchctl bootout gui/") for call in calls)
    assert not (sandbox.home / ".local/bin/clipfix").exists()
    assert not (sandbox.home / "Library/LaunchAgents/local.clipfix.plist").exists()


def test_installer_downloads_source_when_run_alone(sandbox):
    alone = sandbox.tmp / "alone" / "install-clipfix.sh"
    alone.parent.mkdir()
    shutil.copy2(INSTALLER, alone)
    calls = sandbox(alone)
    assert any(
        call.startswith("curl ") and "https://tools.michaelwarkentin.com/macos/clipfix.swift" in call
        for call in calls
    )
    assert any(call.startswith("swiftc ") for call in calls)


def test_build_publishes_clipfix(site_dir):
    for name in ("clipfix.swift", "install-clipfix.sh"):
        assert (site_dir / "macos" / name).read_bytes() == (MACOS / name).read_bytes()
