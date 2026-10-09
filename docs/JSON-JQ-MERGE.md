# JSON merge via jq

Plain JSON, merged with jq's object-multiplication operator (`*`). The other
candidate to compare against `docs/GIT-CONFIG-FORMAT.md`.

## Structure
- Data is just JSON: objects, arrays, strings, numbers, booleans, null
- No sections/subsections - nesting is ordinary JSON object nesting
- Dotted key form (e.g. `base.sha`) is a path into nested objects, a
  convention the tool reading the JSON applies - same as `config.py`'s
  current `_leaves()`, not something JSON itself has

## Merge semantics (jq's `*` operator)
- Two objects: keys merge, recursing into nested objects
- Object key vs. a non-object (array, scalar, string, number): the
  right-hand value wins outright, no merge
- Arrays: replaced whole, never concatenated or merged - this is exactly
  `docs/DECISIONS.md` D15 ("Objects merge, arrays and scalars are replaced
  whole"), not an approximation of it
- Order matters: `reduce .[] as $item ({}; . * $item)` folds left to right,
  so the last layer in the list wins - the same rule as `config.py`'s
  `LAYER_ORDER`

## Provenance (which layer set a value)
- Not a jq builtin - `*` returns only the merged result, not which input
  contributed each leaf
- Doable by hand: walk each layer's `paths` separately, and for each leaf
  path remember the last layer that defined it - the same shape as
  `config.py`'s `sources()`, just as a jq filter instead of Python
- This is the one place jq doesn't make `--source` free; git config's
  `--show-origin` does better here (see `docs/GIT-CONFIG-FORMAT.md`)

## Secrets
- No builtin either. `any(paths; last | test("(?i)(TOKEN|KEY|PASSWORD|SECRET)$"))`
  reproduces `config.py`'s `SECRET_KEY` check as a one-line filter

## Limits
- jq is a pure filter: no filesystem writes, no subprocess, no network.
  Writing a merged layer back out is a plain `jq ... > file.json` from the
  shell, nothing jq-specific
- No schema validation, same as today
- Requires the `jq` binary

## Verify
```
echo '[{"a":{"x":1,"arr":[1,2]}}, {"a":{"y":2,"arr":[9]}}]' \
  | jq 'reduce .[] as $item ({}; . * $item)'
```
Expect: `{"a":{"x":1,"arr":[9],"y":2}}` - `x` and `y` are both kept (object
merge), `arr` is fully replaced by the second layer's array, not merged
(D15). Note: no `-s`/slurp here - the input is already one JSON array of
layers, not several JSON documents to combine into one.
