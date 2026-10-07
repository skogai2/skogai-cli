#!/usr/bin/env bash
# Walk through init, install and config in a scratch directory.
# Nothing outside the scratch directory is written.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skogai() { PYTHONPATH="$here/../src" python3 -m skogai "$@"; }

scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

echo "== a sample dash-skogai, as a local git repo"
cp -r "$here/dash" "$scratch/dash"
git -C "$scratch/dash" init -q -b main
git -C "$scratch/dash" add -A
git -C "$scratch/dash" -c user.name=demo -c user.email=demo@example.com commit -q -m "sample defaults"

echo "== a repo that uses it"
mkdir "$scratch/repo" && cd "$scratch/repo"
echo "-- dry run, shows the pin"; skogai init --source "$scratch/dash" --store .skogai
skogai init --source "$scratch/dash" --store .skogai --apply

echo "== install into a sandbox, never the real config"
export SKOGAI_CONFIG_EXAMPLE_DIR="$scratch/sandbox"
skogai install --store .skogai --apply
ls -l "$scratch/sandbox/bin/"

echo "== layered config, with the repo overlay and a machine file"
cp "$here/repo/config.local.json" .skogai/config.local.json
export SKOGAI_CONFIG_JSON_FILE="$here/machine/config.json"
skogai config get env --source --store .skogai
skogai config get base.sha --layer repo --store .skogai

echo "== done"
