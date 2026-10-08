# Glossary

Terms that get mixed up across skogai docs and conversation. Definitions here
should match CONFIG.md, ENV.md and DECISIONS.md; if one of those changes, fix
the mismatch rather than keeping two answers.

## dash and dot

Both are file-safe names for paths that can't be used as-is in an identifier
(a path starting with `/` or `.`).

- **dash-skogai** is `/skogai`. The dash stands for the leading `/`: a
  root-level directory, not inside anyone's home. It holds shared,
  system-wide state — `config.defaults.json`, `fish/config.fish` — and
  "every repo builds from it" (CONFIG.md). On a machine without a
  provisioned `/skogai`, `skogai-cli` fetches the same content from
  `https://github.com/skogai2/dash-skogai` instead (D5 in DECISIONS.md).
- **dot-skogai** is `.skogai`. The dot stands for the leading `.`: a hidden,
  per-project directory. It's the store a single repo keeps — pinned to one
  dash-skogai commit, holding its own overlay (D4). `./.skogai` is the
  default; `--store` can point it elsewhere.

Rule of thumb: dash-skogai is the one source everyone reads from. dot-skogai
is the local, repo-scoped copy that reads from it. "Updating dash-skogai"
changes the shared default; "updating a repo's .skogai" moves that one repo
to a new pin of it (`skogai update`).

## machine, local, global, repo

These describe *where a value is read from*, not what kind of value it is.
They answer different questions, so don't assume they line up:

- **repo** — scoped to the directory you're standing in. Comes from that
  repo's `.skogai/` store (`./.skogai/config.json`). Checked in; everyone who
  clones the repo gets it.
- **machine** — scoped to this machine, not to any one repo. Comes from
  `$XDG_CONFIG_HOME/skogai/config.json` (or `$SKOGAI_CONFIG_JSON_FILE`).
  Applies across every repo on this box unless a repo layer overrides it.
- **local** — not a scope of its own; a modifier on the two above. Each
  scope has a `.local.json` sibling (`config.local.json`) that is gitignored
  and never shared (D19). "Repo-local" and "machine-local" are both valid;
  plain "local" is ambiguous — say which scope.
- **global** — not a config layer at all. It means a value that syncs to
  every machine, outside the layered config system entirely: atuin dotfiles
  vars/aliases (ENV.md). If it's in the `skogai config` layer stack, it's
  "machine" or "repo", never "global" — reserve "global" for the atuin-synced
  stuff.

Full layer order, lowest to highest (D14, CONFIG.md):

```
base            config.defaults.json, pinned from dash-skogai
machine         $XDG_CONFIG_HOME/skogai/config.json
machine.local   config.local.json next to the machine file
repo            ./.skogai/config.json
repo.local      ./.skogai/config.local.json
```

Later layers win; `config get --source` names which layer a value actually
came from when it's not obvious.

## store

**The store** is the `.skogai/` directory itself — one repo's dot-skogai.
`--store` (default `./.skogai`) names it explicitly; D4 is the decision that
every repo gets one by default, with a shared `/skogai` as an opt-in
alternative.

What lives in the store (CONFIG.md, D2, D25):

- `config.defaults.json` — the base snapshot, copied from the pinned
  dash-skogai commit.
- `config.json` / `config.local.json` — the repo's own config layers.
- `pins.json` — the git blob SHA each managed file was installed from.
- `installs.json` — where each managed file was actually written on this
  machine. Gitignored (D19); it holds machine paths, not shared ones.

"Store path" (in `store: "..."` on a managed entry) means a file's location
*inside* the store, as opposed to its **source** (where it comes from) or its
**install path** (where it ends up outside the store).

## source

**Overloaded** — three distinct meanings, all live in this codebase, and
conversation tends to flatten them into one word:

1. On a managed entry in `config.defaults.json`, `source` is that entry's
   path *in dash-skogai* — its identity (D25). This is what gets fetched into
   the store.
2. `skogai init --source` / `--ref` name *where dash-skogai itself comes
   from*: a GitHub URL by default, or a local path for tests (D5). This
   answers "which dash-skogai," not "which file."
3. `skogai config get --source` names *which config layer* a merged value
   came from (base/machine/repo/…) — nothing to do with dash-skogai at all
   (D16).

When "source" is ambiguous in conversation, ask which of the three is meant
before writing it down.

## pin, blob, and managed file

- **Managed file** — one entry in `config.defaults.json`: a file dash-skogai
  distributes and skogai-cli knows how to fetch, store, and optionally
  install. It has a required `source` (§source, sense 1) and an optional
  `store` path (D25).
- **Blob (SHA)** — git's hash of a file's exact byte content, independent of
  which commit it showed up in. Two files with the same content have the
  same blob SHA even in unrelated commits.
- **Pin** — a recorded version that `update` won't move past unless asked.
  Two kinds exist, at two levels: the whole store is pinned to a dash-skogai
  *commit* (`base.sha` in `config.json`); each managed file is additionally
  pinned to the *blob* it was installed from (`pins.json`). The commit pin
  says "which dash-skogai"; the blob pin says "which exact bytes of this one
  file" (D2).

## area and tier

Both describe resolution order, for different things — don't swap them:

- **Area** — the fixed category word in an env var name,
  `SKOGAI_<AREA>[_<COMPONENT>...]_DIR` (e.g. `CONFIG`, `DATA`, `STATE`,
  `CACHE`, `CLAUDE`). Areas come from a deliberately-maintained fixed list,
  not invented per tool; anything outside it is a warning in `env check`
  (D21, D23).
- **Tier** — the precedence order used to resolve *one* directory or
  setting: explicit arg → app-specific `SKOGAI_*_DIR` → XDG base dir →
  hardcoded default (ENV.md, D10). `env --explain` reports which tier
  resolved each area.

"Layer" (config) and "tier" (env/install) are both orderings of "most
specific wins," but they're separate mechanisms with separate code
(`config.py` vs `env/resolve.py`, `install.py`) — a value can be in the
`repo` config layer and still resolve its install path through the `XDG`
tier.

## LOCAL-CHANGE

The status `update` or `install` reports for a managed file whose on-disk
content no longer matches its recorded pin/blob. The file is left untouched
and the command exits non-zero (D7, D12) — a local edit is never silently
overwritten. It's the thing that makes a dry run worth reading before
`--apply`.
