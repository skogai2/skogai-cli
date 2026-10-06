# Environment variables and directories

Proposed rules. Not yet implemented; the open questions at the bottom need
answers before this becomes the agreed scheme.

## Precedence

When a tool needs a directory or setting, resolve it in this order, most
specific first:

1. **Explicit argument** (`--root`, `--manifest`): wins for a single run.
   Used for tests and one-offs. Add only when a script actually needs it.
2. **App-specific variable** (`SKOGAI_<THING>_DIR`): overrides the default
   for one tool without affecting the others.
3. **XDG base directory** (`$XDG_CONFIG_HOME`, `$XDG_DATA_HOME`,
   `$XDG_STATE_HOME`, `$XDG_CACHE_HOME`; default `~/.config`, `~/.local/share`,
   `~/.local/state`, `~/.cache`). The standard location for app config, data,
   state and cache. Note the name is `XDG_CONFIG_HOME`, not `XDG_CONFIG_DIR`.
4. **Hardcoded default** under `$HOME`: only when nothing above is set.

Shell pattern for a config directory:

```bash
dir="${SKOGAI_FOO_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/skogai/foo}"
```

## Naming

- All skogai-owned variables use the `SKOGAI_` prefix. Don't invent
  `XDG_SKOGAI_*` names.
- XDG variables keep their standard names and are not renamed.
- Directory variables end in `_DIR`, and their value is an **absolute path
  ending in `/`** (e.g. `SKOGAI_CLAUDE_DIR=/home/skogix/claude/`). Absolute,
  so the value doesn't depend on the caller's working directory.
- Name structure is `SKOGAI_<AREA>[_<COMPONENT>...]_DIR`, read left to right
  from broad to specific: `SKOGAI_CONFIG_FISH_DIR` is the fish config
  directory inside the config area.
- `AREA` is taken from a fixed list (`CONFIG`, `DATA`, `STATE`, `CACHE`,
  `CLAUDE`, ...) so that `_` separators stay unambiguous. Add to the list
  deliberately, not per tool.
- One name per concept. Where two names must exist, one derives from the
  other rather than being set independently.

## Where values are set

| Kind of value                        | Where it lives                          |
|--------------------------------------|-----------------------------------------|
| Tool versions, per-project env       | `mise.toml` (`[env]` section) per project or globally |
| Global non-secret env vars, aliases  | `atuin dotfiles var` / `atuin dotfiles alias` (syncs to every machine) |
| Machine-local values that must not sync | Shell rc file, commented as machine-local |
| Secrets (API keys, passwords, tokens) | A secret manager. **Never** in atuin vars, mise, or the repo |

The atuin dotfiles var list has leaked plaintext secrets before (see
`atuin.md`). Treat it as config only.

## Repo-level rules

- Config that is versioned in this repo is referenced through `links.txt`
  and installed with `link.sh`. Don't hardcode repo paths in config files;
  use the install path.
- Scripts take their source location from their own path, not from an env
  var.
- Anything a script reads from the environment is listed at the top of the
  script with its default.

## Migration

Existing things that don't follow these rules yet:

- `fish/config.fish` sets `SKOGAI_CONFIG_DIR`, `ARGC_COMPLETIONS_ROOT`,
  `PNPM_HOME` and others directly with `set -gx`. Per the rules above,
  global non-secret values should move to atuin dotfiles vars, and
  project-scoped ones to mise.
- The live environment has overlapping names for the same concept:
  `XDG_SKOGAI_DIR`, `XDG_SKOGAI_CONFIG_DIR`, `SKOGAI_SKOGAI_DIR`,
  `SKOGAI_CONFIG_DIR`, all pointing at different paths. Pick one canonical
  name and derive the rest.

## Open questions

1. Which name is canonical for the skogai home: `XDG_SKOGAI_DIR` (as
   `CLAUDE.md` uses it) or `SKOGAI_SKOGAI_DIR`?
2. Should global env vars live in atuin dotfiles, or in mise's global
   config? Proposal above: atuin for shell-wide, mise for tool-related.
3. Do we allow `XDG_*` overrides in `links.txt` entries, or keep entries
   literal `~/...` paths?
4. Should a `SKOGAI_*_DIR` variable exist at all for a directory the tool
   already finds through XDG (e.g. fish)? Proposal: only for directories
   skogai scripts need to locate.
5. For a config directory that is linked from the repo, should
   `SKOGAI_CONFIG_FISH_DIR` point at the install path (`~/.config/fish/`) or
   the repo path (`.../fish/`)? Proposal: the install path, since that's what
   the tool reads.
