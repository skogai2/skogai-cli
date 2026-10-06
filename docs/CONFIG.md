# Config model

Status: agreed in conversation (2026-10-06 and 2026-10-07). Not implemented.
Open points are at the bottom. Env variable rules are in [ENV.md](ENV.md).

## Roles

- **dash-skogai** is the shared state and the source of truth. It holds the
  defaults (`config.defaults.json`) and the shared files, such as
  `fish/config.fish`. Every repo builds from it.
- **skogai-cli** knows how to fetch a named commit of dash-skogai, how to
  resolve config layers, and how to link or copy files. It does not hold
  defaults of its own.
- **A repo** (`.skogai/`) records which dash-skogai commit it was built from,
  and keeps a local overlay.

## Pins

- `init` fetches dash-skogai at one commit and records that SHA in the repo.
  A fetch needs the network, so `init` is not expected to work offline.
- The repo keeps a copy of `config.defaults.json` from that commit. That copy
  is the base snapshot, so the repo can be read without the network later.
- Every managed file is recorded with its git blob SHA at the pinned commit.
  A blob SHA pins one file exactly.

## Layers

Lowest to highest. Later layers win, object keys merge, and arrays are replaced.

1. base: `config.defaults.json` at the pinned dash-skogai commit
2. machine: `$XDG_CONFIG_HOME/skogai/config.json`, then `config.local.json`
3. repo: `./.skogai/config.json`, then `config.local.json`

The `.local.json` files are gitignored, the same as `.claude/settings.local.json`.
`--source` reports which layer set each value.

## Where a file is installed

A managed file (for example `fish/config.fish`) has a source in dash-skogai
and an install path. The install path is looked up in this order, most specific
first, as in ENV.md:

1. `SKOGAI_CONFIG_FISH_DIR`, if set
2. the XDG base directory, if set
3. the hardcoded default

For fish, step 2 resolves to `$XDG_CONFIG_HOME/fish`, not
`$XDG_CONFIG_HOME/skogai/fish`, because fish reads its own path. So fish needs
an explicit default. The generic `skogai/` subdirectory rule in
`skogai path` does not fit it.

## Updating

`skogai update` moves a repo to exactly one commit, the one the user names. It
never moves to a moving "latest" silently.

- A managed file whose local blob matches the recorded blob is replaced with
  the blob at the target commit.
- A managed file whose local blob differs from the recorded blob is reported as
  `LOCAL-CHANGE`. It is not touched, and the command exits non-zero.
- Before anything is written, the diff is shown.

## Decided

- **Install-path order** follows ENV.md: the `SKOGAI_*_DIR` override first, then
  `XDG_CONFIG_HOME`, then the hardcoded default.
- **Source for `init`** is always the GitHub URL, `https://github.com/skogai2/dash-skogai`.
- **Installed files are copies**, not symlinks. The default location is
  `./.skogai/`, for both the global and the local scope. On a machine that has a
  shared `/skogai`, the global path points there instead.
- **Fish config** is `dash-skogai/fish/config.fish`. Only that file is shared.
  The rest of `config/fish/` (`conf.d`, `functions`, `completions`) stays in
  `config` for now.

## Open points

None left for the design. Implementation (`init`, `update`, and installing
`fish/config.fish`) is not built yet.
