#!/usr/bin/env bash
# Example: install a repo's config as listed in links.txt next to this file.
# The logic lives in skogai-cli (`skogai link`); this only chooses the manifest.
#
#   ./link.sh          create missing links (same as "link")
#   ./link.sh check    report only, change nothing
#
# Exits non-zero if anything is not in the expected state.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
exec skogai link "${1:-link}" --manifest links.txt
