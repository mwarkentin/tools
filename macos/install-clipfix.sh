#!/usr/bin/env bash
# Builds clipfix and runs it as a LaunchAgent, so it starts at login.
# Needs swiftc, from Xcode or its command line tools.
#
#   bash install-clipfix.sh             install, or rebuild after editing clipfix.swift
#   bash install-clipfix.sh uninstall   stop it and remove it
#
# Or straight from the site, which downloads clipfix.swift too:
#   curl -fsSL https://tools.michaelwarkentin.com/macos/install-clipfix.sh | bash
#   curl -fsSL https://tools.michaelwarkentin.com/macos/install-clipfix.sh | bash -s uninstall
set -euo pipefail

label="local.clipfix"
source_url="https://tools.michaelwarkentin.com/macos/clipfix.swift"
src="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/clipfix.swift"
bin="$HOME/.local/bin/clipfix"
plist="$HOME/Library/LaunchAgents/$label.plist"
logfile="$HOME/Library/Logs/clipfix.log"
domain="gui/$(id -u)"

if [[ "${1:-}" == "uninstall" ]]; then
  launchctl bootout "$domain/$label" 2>/dev/null || true
  rm -f "$plist" "$bin"
  echo "clipfix removed"
  exit 0
fi

if [[ ! -f "$src" ]]; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  src="$tmp/clipfix.swift"
  echo "Downloading $source_url"
  curl -fsSL "$source_url" -o "$src"
fi

mkdir -p "$(dirname "$bin")" "$(dirname "$plist")" "$(dirname "$logfile")"
swiftc -O -swift-version 5 "$src" -o "$bin"

cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key><array><string>$bin</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardErrorPath</key><string>$logfile</string>
</dict>
</plist>
EOF

if launchctl print "$domain/$label" >/dev/null 2>&1; then
  launchctl kickstart -k "$domain/$label"   # already loaded: restart on the new build
else
  launchctl bootstrap "$domain" "$plist"
fi

echo "clipfix is running. Log: $logfile"
