# Decisions

One entry per decision: what was decided, why, and where it lives in the code.
Status is one of **Decided** (built and tested), **Chosen** (picked, can be
changed cheaply), **Open** (needs a decision), or **TODO** (known work).

Run the examples with `examples/demo.sh`. Run the tests with
`PYTHONPATH=src python3 -m unittest discover -s tests`.

## Sources of truth

### D1. dash-skogai is the shared source of truth. Status: Decided
Defaults and shared files (`config.defaults.json`, `fish/config.fish`) live in
dash-skogai. Every repo builds from it. skogai-cli holds no defaults of its own.
*Why:* one place to look, and one place to change for everyone.
*Code:* `store.py`, `source.py`.

### D2. Repos pin dash-skogai by commit, and managed files by git blob. Status: Decided
`init` records the commit in `config.json` (`base.sha`). Each managed file is
pinned by the git blob SHA it was installed from, in `pins.json`.
*Why:* a commit says which version a repo was built from. A blob pins one file
exactly, so a file can be checked without reading git history.
*Code:* `store.py` (`init`, `update`), `source.py` (`resolve`, `read`, `mode`).

### D3. Managed files are copied, not linked. Status: Decided
The store holds a copy of each managed file. `install` copies it again to the
install path. Links are not used for managed files.
*Why:* a copy is a known version. A link follows whatever is checked out in the
source repo, so the file on disk could change without the pin changing.
*Code:* `install.py`.

### D4. Each repo's store defaults to `./.skogai`. Status: Decided
`--store` defaults to `./.skogai`. A machine that has a shared `/skogai` can
point the store there instead. Only the repo-local store is built.
*Why:* a repo works without any shared directory. Shared state is opt-in.
*Code:* `cli.py` (`--store`).

### D5. `init` and `update` read dash-skogai from GitHub by default. Status: Decided
The default source is `https://github.com/skogai2/dash-skogai`. `--source`
takes a local path, which the tests and demo use.
*Code:* `source.py` (`DASH_SKOGAI_URL`).

## Updating

### D6. `update` only moves to a commit you name, and dry-runs by default. Status: Decided
`update` shows the diff. Nothing is written until `--apply`. The target is the
default branch unless `--ref` names a commit. `update` never moves silently.
*Code:* `store.py` (`update`), `cli.py`.

### D7. A local change blocks the update of that file. Status: Decided
If a managed file no longer matches its pin, it is reported as `LOCAL-CHANGE`,
left untouched, and the command exits 1. The base pin only moves when nothing is
blocked, so the store never claims a version it does not have.
*Why:* a local edit is never silently overwritten.
*Code:* `store.py`, `install.py`.

### D8. Executable bit is kept. Status: Decided
`init`, `update` and `install` read the git file mode and apply it to the copy.
A mode-only change upstream is an update.
*Why:* managed scripts would otherwise arrive without `+x`.
*Code:* `source.py` (`mode`), `store.py` (`write_file`), `install.py`.

### D9. Removed upstream files are reported, not deleted. Status: Decided
A file removed from dash-skogai is reported as `REMOVED` and left in place.
*Why:* deleting from a user's machine is a bigger step than the update asks for.

## Installing

### D10. Install lookup order. Status: Decided
Most specific first:
1. the env variable named in `install.env`, if set
2. `$SKOGAI_CONFIG_EXAMPLE_DIR/<install.xdg>`, if set
3. `$XDG_CONFIG_HOME/<install.xdg>`, if set
4. `install.default`, with `~` expanded

*Why:* it matches `ENV.md`, where the most specific source wins. The fish
variable (`SKOGAI_CONFIG_FISH_DIR`) can always override a single file.
*Code:* `install.py` (`install_dir`).

### D11. `SKOGAI_CONFIG_EXAMPLE_DIR` is a sandbox config home. Status: Decided
With it set, installs go under that directory instead of the real config. Tests
and demos use it so they never touch the real config.
*Gotcha:* if `install.env` names the same variable, the env tier wins and `xdg`
is never used. The output says `[env]` in that case. The sample in `examples/`
avoids this, but a shared config could hit it.

### D12. Install never overwrites a file it did not write. Status: Decided
A file is replaced only when it matches the store copy or the copy skogai
recorded in `installs.json`. Anything else is `LOCAL-CHANGE`. Existing files
with identical content are adopted (`RECORD`) without a write.
*Code:* `install.py`.

### D13. Fish config comes from dash-skogai, and the rest of fish stays local. Status: Decided
`dash-skogai/fish/config.fish` is the shared file. `conf.d`, `functions` and
`completions` were removed from `config`, and remain in its git history.
*Why:* only `config.fish` needed to be one shared file. The rest is machine
specific until someone decides otherwise.

## Config

### D14. Layers, lowest to highest. Status: Decided
1. `base`: `config.defaults.json` in the store
2. `machine`: `$SKOGAI_CONFIG_JSON_FILE`, else `$XDG_CONFIG_HOME/skogai/config.json`
3. `machine.local`: `config.local.json` beside the machine file
4. `repo`: `<store>/config.json`
5. `repo.local`: `<store>/config.local.json`

*Why:* `.local` files follow the same pattern as `.claude/settings.local.json`.
The repo beats the machine, and local beats shared within each scope.
*Code:* `config.py` (`LAYER_ORDER`, `load_layers`).

### D15. Objects merge, arrays and scalars are replaced. Status: Decided
An overlay can change one key without restating the object. An array is
replaced whole, so a value always comes from exactly one layer.
*Why:* merging arrays makes it hard to tell where an entry came from, and
`--source` would then have to name several layers for one value.
*Code:* `config.py` (`_deep_merge`, `sources`).

### D16. `config get --source` names the layer for every value. Status: Decided
`skogai config get [KEY] [--source] [--layer NAME]`. `--layer` shows the raw
value in one layer. Without `--source`, a single value prints bare, for scripts.
*Code:* `cli.py` (`_cmd_config_get`), `config.py` (`get`, `sources`, `layer_value`).

### D17. Secrets never go in config files. Status: Decided
Any key that ends in `TOKEN`, `KEY`, `PASSWORD` or `SECRET` is refused at load,
in every layer. The same rule applies to the atuin var list, in `env check`.
*Why:* config files get committed and shared. Secrets belong in a secret manager.
*Code:* `config.py` (`_refuse_secrets`), `env/check.py`.

### D18. Config file names. Status: Chosen
- `config.json` (shared) and `config.local.json` (local, gitignored).
- The machine file is `SKOGAI_CONFIG_JSON_FILE`, not `SKOGAI_CONFIG_JSON`.
  `ENV.md` says file variables should end in `_FILE`, as directory variables end
  in `_DIR`. Easy to rename if you prefer otherwise.

### D19. Store `.gitignore` covers machine-local files. Status: Decided
`init` writes `.skogai/.gitignore` with `config.local.json` and `installs.json`.
*Why:* `installs.json` holds machine paths. `config.local.json` is personal.

### D20. Global variables go in atuin dotfiles vars, not in fish. Status: Decided
`EDITOR`, `VISUAL`, `PAGER`, `PNPM_HOME`, `SKOGAI_CONFIG_DIR` and the argc
variables are atuin dotfiles vars. Per-project tool env goes in `mise.toml`.
*Why:* atuin syncs to every machine, and `config.fish` is shared, so no machine
should have to edit it.
*Caveat:* atuin vars only reach shells that run `atuin init`. Non-interactive
scripts do not see them.

## Environment variables

### D21. Naming. Status: Decided
`SKOGAI_<AREA>[_<COMPONENT>...]_DIR` for directories, read from broad to narrow.
Areas come from a fixed list (`CONFIG`, `DATA`, `STATE`, `CACHE`, `CLAUDE`). The
list changes deliberately, not per tool. `XDG_SKOGAI_*` names are not allowed.
*Code:* `env/areas.py`, `env/check.py`.

### D22. The skogai home variable name is not decided. Status: Open
`SKOGAI_DIR` is the leaning in `env/areas.py` (`ROOT_VARS`). The live machine has
`SKOGAI_SKOGAI_DIR` and `XDG_SKOGAI_DIR`, which point at the same place.
*Decide:* one name, then change `ROOT_VARS` and remove the rest.

### D23. The area list is open. Status: Open
Areas outside the fixed list are reported as warnings by `env check`. `DOT`,
`SKOGIX` and `SKOGAI` are reported today, which is correct until the list is
decided.

## Open questions

### O1. Managed files come from the base only. Status: Open
`config get` shows the merged config, including a `files` list from an overlay.
`install` and `update` use only the list in the pinned `config.defaults.json`.
*Why it is open:* an overlay can only name files that exist in the store, which
are fetched from the pinned commit. Adding a file from an overlay needs a rule
for where it comes from. Until that is decided, `files` in an overlay is ignored
by `install` and `update`. `config get` will still show it.

### O2. `skogai link` stays or goes. Status: Open
`link` is still built and tested. Nothing uses it now: `config` no longer has a
`links.txt`. Keep it as a general tool, or remove it.

### O3. Whether `.skogai/` is committed. Status: Open
`config.json` and `pins.json` are the candidates for committing. `installs.json`
and `config.local.json` are not, per D19. A repo that commits `.skogai/` gets
the same pins on every machine.

### O4. A `skogai status` command. Status: Open
It would report installed copies that drifted or went missing, without writing.
Today drift only shows up when `install` runs.

### O5. The global `/skogai` store. Status: Open
Not built. Needs a decision on which scope it feeds: machine, or repo overrides.

## TODO

### T1. Pin an explicit `--ref` on the first `init`. Status: TODO
`init` uses `HEAD` by default, so a first install pins whatever GitHub has at
that moment. The code has a comment at this point. Require `--ref` the first
time, or print the SHA and ask for confirmation.
*Code:* `store.py` (`init`, comment).

### T2. Tests against GitHub. Status: TODO
All tests use local git repos. Nothing checks the real GitHub path. A single
smoke test that clones the real repo would catch URL and auth problems.

### T3. CI. Status: TODO
Tests run by hand. A CI job that runs `unittest` and `examples/demo.sh` would
catch regressions.

### T4. Push order. Status: TODO
Submodule commits must be pushed before the superproject commit that points at
them, or the pointers are missing on GitHub. `dash-skogai` must be pushed before
`init` can fetch the new `config.defaults.json`.
