# Git config format rules

INI-like, with git-specific rules.

## Structure
- Sections: `[section]` or `[section "subsection"]`
- Section name: case-insensitive
- Subsection (quoted): case-sensitive, may contain dots and spaces
- Variables: `name = value`
- Variable names: start with a letter, only alphanumerics and `-`, case-insensitive
- Comments: start with `#` or `;`

## Values
- Double-quote to preserve whitespace
- Escapes: `\n` `\t` `\"` `\\`
- Trailing `\` continues the line
- Bare `name` with no `=` means true
- Repeated key makes it multi-valued: single read returns the last, `--get-all` returns all
- Everything is stored as a string; types are applied at read time via `--type=bool|int|path`
- Bool accepts: true/yes/on/1 (and false/no/off/0)
- Int accepts suffixes: k, m, g

## Includes
- `[include] path = ...`
- `[includeIf "gitdir:..."]` for conditional includes
- Relative include paths resolve relative to the including file

## Dotted key form
- `section.key`
- `section.subsection.key`

## Limits
- No nesting beyond section.subsection.key
- No real arrays (multi-valued keys only)
- No schema validation
- Requires the git binary to read and write via `git config`

## Verify
```
printf '[a "B.c"]\n\tk = v # note\n\tflag\n' > /tmp/t.conf && git config -f /tmp/t.conf --list
```
Expect: `a.B.c.k=v` and `a.B.c.flag`

## Notes for skogai

Checked against the layered-config shape this project actually needs
(`base -> machine -> machine.local -> repo -> repo.local`, last layer wins,
`--source` reports which layer set a value):

- **Layering maps almost for free.** `[include] path = ...` splices another
  file's contents in place; a same-named key set again later wins. Chain
  the five layers as includes and `--get` already resolves to the right
  value with no merge code to write.
- **Includes are opt-in, easy to get silently wrong.** `git config -f <file>
  ...` does NOT expand `[include]`/`[includeIf]` unless `--includes` is also
  passed. Drop that flag from a script and it silently reads only the top
  file, not the layered result - no error, just the wrong answer.
- **`--show-origin` is `--source` for free.** With `--includes` on, `git
  config -f top --includes --show-origin --get-all key` lists every layer's
  value together with the file it came from, in layer order. This is the
  one piece `config.py`'s `sources()` had to build by hand that git already
  does natively.
- **No arrays of objects - a real gap.** `config.defaults.json`'s `files`
  list is an array of objects (`source`/`store`/`install` per managed
  file). Git config's "no real arrays, multi-valued keys only" limit means
  that shape doesn't translate; each managed file would need its own
  subsection (`[file "fish/config.fish"]`) instead of a list entry, which is
  a real format change, not a syntax swap.
- **No secret detection.** `config.py`'s `SECRET_KEY` refusal has no git-config
  equivalent; it needs its own check regardless of which format wins.

## Verify (layering + provenance)
```
d=$(mktemp -d)
printf '[a]\n\tk = from-base\n\tonly-base = x\n' > "$d/base.conf"
printf '[include]\n\tpath = %s/base.conf\n[a]\n\tk = from-top\n' "$d" > "$d/top.conf"
git config -f "$d/top.conf" --includes --get-all a.k
git config -f "$d/top.conf" --includes --show-origin --get-all a.k
```
Expect: `a.k` lists `from-base` then `from-top` (plain `--get` would return
just `from-top`, last wins), and `--show-origin` names `base.conf` and
`top.conf` as the respective origins.

## `hasconfig:` conditional includes - works, but the relative path lies

`[includeIf "hasconfig:remote.*.url:<glob>"]` (git >= 2.36) fires when a
repo's remote URL matches a glob - e.g. auto-loading config for any repo
under a given GitHub org. The condition itself works correctly. The
`path =` on that same stanza does not do what it looks like it does:

- **In a repo's own `.git/config`:** a relative path resolves against the
  directory of the *including file*, i.e. `.git/`, not the worktree root.
  `path = .skogai/config/gitconfig` silently resolves to
  `<repo>/.git/.skogai/config/gitconfig` - almost never what was written
  (`<repo>/.skogai/config/gitconfig`). No error either way; it just quietly
  finds nothing. Needs `../.skogai/config/gitconfig` or an absolute path.
- **In the global `~/.gitconfig`** (the natural home for a `hasconfig:`
  conditional - "apply this whenever I'm in a repo matching this remote"):
  a relative path resolves against `$HOME`, always. Verified with two
  repos, both matching the same glob, same relative path in the global
  config - both loaded the identical `$HOME/.skogai/config/gitconfig`, not
  their own per-repo files. There is no variable for "the repo that
  matched" - `path` is a static string regardless of what the condition
  matched against.
- **Consequence:** `hasconfig:` can give you one shared file applied to
  every repo matching a remote pattern (fine for a machine-wide policy),
  but it cannot discover and load *that specific repo's own* file with
  zero per-repo setup. Getting a genuinely per-repo file still needs
  something to write a repo-relative (or absolute) include line into that
  repo's own `.git/config` once - the same shape of work `skogai
  link`/`skogai init` already do, not something `includeIf` replaces.

### Verify
```
# condition fires correctly (real remote, real glob)
d=$(mktemp -d) && git init -q "$d" && git -C "$d" remote add origin https://github.com/skogai2/skogai-cli
mkdir -p "$d/.skogai/config" && printf '[marker]\n\thit = yes\n' > "$d/.skogai/config/gitconfig"
printf '[includeIf "hasconfig:remote.*.url:https://github.com/skogai2/**"]\n\tpath = %s/.skogai/config/gitconfig\n' "$d" >> "$d/.git/config"
git -C "$d" config --get marker.hit   # => yes, with the absolute path

# same stanza, relative path, inside .git/config: silently empty
printf '[includeIf "hasconfig:remote.*.url:https://github.com/skogai2/**"]\n\tpath = .skogai/config/gitconfig\n' >> "$d/.git/config"
git -C "$d" config --get-all marker.hit   # second line contributes nothing
```
