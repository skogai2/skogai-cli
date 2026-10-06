# skogai-cli

The `skogai` command: one place for skogai conventions. The first module is
**env**, which owns environment variables and directories.

The rules live in [docs/ENV.md](docs/ENV.md). The reasoning, trade-offs and
open decisions live in [docs/ENV-HANDOVER.md](docs/ENV-HANDOVER.md).

## Install

Stdlib only, no dependencies. Python 3.10+.

```bash
pip install -e .        # or: uv tool install -e .
```

Without installing, run it from `src/`:

```bash
PYTHONPATH=src python3 -m skogai env check
```

## Commands

```bash
skogai path                    # the skogai home
skogai path config fish        # e.g. ~/.config/skogai/fish, no trailing slash
skogai env --explain           # each variable, and which tier resolved each area
skogai env check               # naming, overlap and secret findings; exit 1 on error
skogai link [link|check]       # install repo config as listed in links.txt
skogai init                    # copy the shared defaults from dash-skogai into ./.skogai
skogai update [--apply]        # move ./.skogai to another dash-skogai commit (dry run by default)
skogai install [--apply]       # copy managed files from ./.skogai to their install paths (dry run by default)
```

`install` looks up each file's directory in order: the env variable named in
`install.env`, then `$SKOGAI_CONFIG_EXAMPLE_DIR/<install.xdg>` (a sandbox config
home, for tests and dry runs), then `$XDG_CONFIG_HOME/<install.xdg>`, then
`install.default`. It
copies the file and records what it wrote in `installs.json`. It never overwrites
a file that differs from both the store copy and its own record. That is
reported as `LOCAL-CHANGE` and the command exits 1.

`init` and `update` read dash-skogai from GitHub by default. `--source` takes a
local path for testing, and `--ref` picks a commit. A managed file is replaced
only if its local blob still matches the pin recorded at install. Otherwise it
is reported as `LOCAL-CHANGE`, left alone, and the command exits 1. See
docs/CONFIG.md.

`skogai link` reads `links.txt` in the current directory (or `--manifest PATH`).
Each line is `<repo path, relative to the manifest> <install path>`. It creates
missing links and never overwrites a real file. `check` only reports. A repo
gets a `link.sh` from `examples/link.sh`, which is a three-line wrapper.

Resolution order, most specific first (see docs/ENV.md):

1. `SKOGAI_<AREA>[_<COMPONENT>...]_DIR`
2. XDG base directory (`XDG_CONFIG_HOME` etc.), under `skogai/`
3. Hardcoded default under `$HOME`

Explicit `--root`-style arguments are not implemented yet. Add them when a
script needs one.

## Scripts that call the CLI

The CLI must not become a hard dependency. Scripts should fall back to plain
XDG defaults when it is missing:

```sh
dir=$(skogai path config fish 2>/dev/null) || dir="${XDG_CONFIG_HOME:-$HOME/.config}/skogai/fish"
```

## Layout

```
src/skogai/cli.py          argument parsing, one function per subcommand
src/skogai/env/areas.py    the fixed area list and root variable
src/skogai/env/resolve.py  resolution order
src/skogai/env/inventory.py  reads env and atuin var names (never values)
src/skogai/env/check.py    rule checks, returns findings
src/skogai/links.py        manifest parsing and link/check logic
src/skogai/source.py       read commits and files from a git URL (bare clone)
src/skogai/store.py        init and update of the .skogai store, with pins
src/skogai/install.py      install managed files to their install paths
examples/link.sh           the wrapper a repo copies next to its links.txt
tests/                     python3 -m unittest discover -s tests
```

## Status

- Done: `path`, `env --explain`, `env check`, `link`, `init`, `update`, `install`.
- Open, from docs/ENV-HANDOVER.md, and not decided by the CLI:
  - The canonical skogai home name. `ROOT_VARS` in `areas.py` is a leaning
    (`SKOGAI_DIR`), so change it there once decided.
  - The fixed area list. Areas outside it are reported as warnings.
  - Whether `fish/config.fish` `set -gx` lines move to atuin or mise. The
    CLI reports mismatches; it does not rewrite config.
- Not built yet: layered config lookup (`config get --source`) and the global `/skogai` store.
- Deferred: migration tooling beyond `check`.
