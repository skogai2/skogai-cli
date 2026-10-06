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
```

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
tests/test_env.py          python3 -m unittest discover -s tests
```

## Status

- Done: `path`, `env --explain`, `env check`.
- Open, from docs/ENV-HANDOVER.md, and not decided by the CLI:
  - The canonical skogai home name. `ROOT_VARS` in `areas.py` is a leaning
    (`SKOGAI_DIR`), so change it there once decided.
  - The fixed area list. Areas outside it are reported as warnings.
  - Whether `fish/config.fish` `set -gx` lines move to atuin or mise. The
    CLI reports mismatches; it does not rewrite config.
- Deferred: `skogai link`, and migration tooling beyond `check`.
