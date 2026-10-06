# Handover: environment variables and directories (for skogai-cli)

Read this before building or changing anything env-related in the
`skogai` CLI. The rules themselves live in [ENV.md](ENV.md); this file
records the reasoning, the trade-offs we already discussed, and what is
still undecided. ENV.md is still a proposal, so treat its rules as the
current intent, not settled law.

## Why this exists

- Paths and settings are currently resolved inconsistently: the same
  concept is set under several names (`XDG_SKOGAI_DIR`,
  `XDG_SKOGAI_CONFIG_DIR`, `SKOGAI_SKOGAI_DIR`, `SKOGAI_CONFIG_DIR`), and
  they point at different paths.
- Values are filed in the wrong place. Plaintext secrets once ended up in
  the atuin var list and the whole list had to be wiped (2026-09-30, see
  [atuin.md](atuin.md)).
- `fish/config.fish` sets globals directly with `set -gx`, which bypasses
  every rule above.

The CLI is meant to make the rules enforceable in one place, instead of
relying on each script and person to follow them.

## The rules the CLI should enforce

1. **Resolution order, most specific first:** explicit argument
   (`--root`, `--manifest`), then `SKOGAI_<THING>_DIR`, then the XDG base
   directory, then a hardcoded default under `$HOME`.
2. **One helper owns resolution.** Scripts ask the CLI for a path
   (`skogai path config fish`) rather than re-implementing the chain.
3. **Naming.** Skogai variables use `SKOGAI_`. XDG variables keep their
   standard names. Directory variables end in `_DIR`. Area segments come
   from a fixed list that is changed deliberately, not per tool.
4. **Where values live:**

   | Kind of value                           | Home                                   |
   |-----------------------------------------|----------------------------------------|
   | Tool versions, per-project env          | `mise.toml`                            |
   | Global non-secret env, aliases          | atuin dotfiles (syncs to all machines) |
   | Machine-local values                    | shell rc, commented as machine-local   |
   | Secrets                                 | a secret manager, never atuin, mise, or the repo |

5. **Scripts locate their own source** from their path, not from an env
   var. Env vars a script reads are listed at the top of the script with
   their defaults.
6. **Repo config is installed, not referenced.** `links.txt` + `link.sh`
   install versioned config. No hardcoded repo paths in config files.

## What the CLI should do first (small scope on purpose)

- `skogai path <area> [<component>...]`: print the resolved path, no
  trailing slash, for scripts to consume.
- `skogai env --explain`: print each relevant variable and which tier of
  the resolution order supplied it.
- `skogai env check`: report overlapping names pointing at different
  paths, names that break the naming rules, and secret-looking names
  (`*_TOKEN`, `*_KEY`, `*_PASSWORD`, `*_SECRET`) in the atuin var list.

Deferred until the above has been used for a while: `skogai link`
(replacing `link.sh`, verifying installed links still point into the
repo), and any migration tooling beyond `check`.

Known design pitfall: the CLI itself becomes a dependency. Scripts that
call it must degrade to plain XDG defaults if it is missing or broken.
Keep the CLI's own surface small so the fallback stays simple.

## Decisions still open (the CLI cannot make these)

These come from ENV.md's open questions. My leanings are recorded, but
none of them is agreed.

1. **Canonical skogai home name.** Leaning: a single root variable with
   no area segment (e.g. `SKOGAI_DIR`), since the root is what areas hang
   off, not an area itself. Then update `CLAUDE.md`, which currently uses
   `XDG_SKOGAI_DIR`, and ENV.md itself says not to invent `XDG_SKOGAI_*`
   names. Using `SKOGAI_SKOGAI_DIR` follows the rule literally but reads
   badly. **Must be settled first**: the CLI and the migration both
   depend on it.
2. **Global vars: atuin vs mise.** Leaning: atuin for shell-wide values,
   mise for tool-related ones. Blocked on fact-checking item A below.
3. **`XDG_*` overrides in `links.txt`.** Leaning: keep literal `~/...`
   paths for now.
4. **When to add `SKOGAI_*_DIR` at all.** Leaning: only for directories
   skogai scripts need to locate. If a tool already finds its directory
   through XDG (e.g. fish), do not duplicate it.
5. **Install path vs repo path** for linked config directories. Leaning:
   the install path, since that is what the tool reads. Mitigation: the
   CLI's `check` verifies that installed links still resolve into the
   repo, so drift is detected rather than silent.

## Facts to verify before relying on them

These were discussed but not verified:

- **A. Atuin dotfile vars outside interactive shells.** The assumption is
  that they are loaded only through shell init, so cron, systemd units and
  non-interactive scripts will not see them. Check this against the
  current atuin setup before deciding item 2.
- **B. Live environment inventory.** Run `env | grep -E 'XDG_SKOGAI|SKOGAI'`
  and record what each name points at. Do not assume the four overlapping
  names listed in ENV.md are still the full set.
- **C. Where each current `set -gx` in `fish/config.fish` should go**
  (atuin, mise, or rc). Not yet classified.

## Constraints

- Secrets never go into atuin, mise, `links.txt`, or the repo. The CLI's
  `check` should refuse to report them as healthy, not just warn.
- Do not touch `~/dot`, which is off-limits (see the agent-homes
  architecture memory).
- Migration is a separate, reviewed step. The CLI should report
  mismatches; it should not rewrite `config.fish` or atuin vars
  automatically.
- Nothing in this handover has been implemented. Whether a `skogai` CLI
  already exists has not been checked; check first.

## Suggested order of work

1. Verify facts A and B.
2. Decide open question 1 and update `CLAUDE.md` and ENV.md to match.
3. Build `skogai path` and `skogai env --explain`, with the script fallback.
4. Build `skogai env check`.
5. Classify `config.fish` (item C) and migrate in reviewed steps.
6. Only then consider `skogai link`.
