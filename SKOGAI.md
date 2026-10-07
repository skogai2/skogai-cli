---
id: skogai-cli
---

The `skogai` command: one place for skogai conventions. Stdlib-only Python
3.10+, no dependencies. The first module is **env** (environment variables
and directories); `config`, `links`, and a `.skogai` store synced from
dash-skogai have followed.

Run it without installing: `PYTHONPATH=src python3 -m skogai env check`.
Tests: `python3 -m unittest discover -s tests`.

- @README.md — commands, resolution order, and the `src/skogai/*` layout
- @docs/ENV.md — the env/dir rules a cold agent needs to follow them
- @docs/ENV-HANDOVER.md — reasoning and open decisions behind env
- @docs/CONFIG.md — config layers, store init/update/install
- @docs/DECISIONS.md — what's settled vs. still open (read before changing
  `ROOT_VARS`, the area list, or install/update semantics)
- @examples/demo.sh — exercises the CLI against sample fixtures, touches
  nothing real
