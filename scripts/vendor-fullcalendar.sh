#!/bin/sh
# Copy the FullCalendar browser build into the static vendor directory.
#
# v7 ships a split build rather than v6's single self-contained bundle:
#   - all/global.js            core + plugins (embeds the Temporal polyfill)
#   - themes/classic/global.js theme plugin, self-registers on load
#   - skeleton.css + the theme's theme.css/palette.css  (no longer auto-injected)
#   - locales/<lang>/global.js  (v6 used locales/<lang>.global.js)
#
# Kept in one place so the Docker build and the Copilot setup workflow cannot
# drift apart. app/static/vendor is gitignored, so this must run wherever the
# app is built or served from a source checkout.
set -eu

src="node_modules/fullcalendar"
target="${1:-app/static/vendor/fullcalendar}"

if [ ! -d "$src" ]; then
    echo "error: $src not found — run 'npm ci' first" >&2
    exit 1
fi

# Start clean so files from a previous version never linger.
rm -rf "$target"
mkdir -p "$target"

cp "$src/all/global.js" "$target/all.global.js"
cp "$src/themes/classic/global.js" "$target/classic.global.js"
cp "$src/skeleton.css" "$target/"
cp "$src/themes/classic/theme.css" "$target/"
cp "$src/themes/classic/palette.css" "$target/"
cp -r "$src/locales" "$target/"

echo "FullCalendar assets copied to $target"
