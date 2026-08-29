# Configuration reference

Everything a workspace declares lives in one `atpx.toml` at its root. Four
tables, and three of them are data contracts a second tool reads without
either tool naming the other.

## `[workspace]`

| Key | Type | Default | What it says |
| --- | --- | --- | --- |
| `blueprints` | string or list of strings | `"research/math"` | the blueprint roots, read as one graph |
| `index` | string | `<first root>/INDEX.md` | where the generated index note lands, root-relative |
| `runner` | string | `""` | the command prefix every claim, background check and Lean build runs behind |
| `lean` | string | `"lean-build"` | the declared task name that runs the Lean build |

```toml
[workspace]
blueprints = ["math", "experiments"]
index = "math/INDEX.md"
runner = "mainboard run --"
```

`blueprints` takes a list as readily as a string. Roots resolve in declaration
order, the first is where `atpx open` and a capture-first `atpx run` put a new
blueprint, and a slug an existing root already holds is always reached there.
A node carrying `superseded_by` is an alias whose claim of record lives at the
pointer, so a claim that moved between roots is counted once, at its current
home. See [the guide](guide.md#several-blueprint-roots).

## `[models]`

The counsel lanes. `prover` names the model that writes probes, and `ladder`
is the attack roster the refuter climbs, cheapest rung first. A rung is a bare
model id or a table carrying `model`, `max_tokens` and `timeout`.

```toml
[models]
prover = "deepseek/deepseek-v4-flash-0731"
ladder = [
  "deepseek/deepseek-v4-flash-0731",
  { model = "z-ai/glm-5.2", max_tokens = 96000, timeout = 900 },
]
```

## `[vocabulary]`, the settled words

**A data contract.** atpx owns the lifecycle, so atpx owns the declaration.
One sub-table per word, keyed by the word itself, which must be a settled
status on the ladder (`sketched`, `validated`, `refuted`, `verified`,
`undecided`, `abandoned`, `known`). Declaration order is report order.

| Key | Type | Default | What it says |
| --- | --- | --- | --- |
| `letter` | string | the word's initial | the character a progress line prints |
| `markup` | table of booleans | `{}` | the terminal markup the word prints under, exactly the mapping pytest's own `pytest_report_teststatus` takes |
| `stance` | `"confirms"`, `"refutes"`, `"neither"` | `"neither"` | what settling on this word does to the prediction behind it |

```toml
[vocabulary]
validated = { letter = "V", markup = { green = true }, stance = "confirms" }
refuted   = { letter = "R", markup = { red = true }, stance = "refutes" }
known     = {}
```

`stance` defaults to `neither` on purpose. A vocabulary of only confirmations
and refutations forces every reading into one of the two, and a program whose
subject is numeric noise then rounds an inconclusive separation into a
decisive word; a workspace that never thinks about stance is never recorded as
having claimed anything.

**Who reads it.** `atpx settle` refuses a settled status the table leaves out,
naming what is declared, so a word nobody declared can never quietly reach a
receipt column nobody reads. A trial harness reads the same table out of the
same manifest to print its progress line and to validate the settled word a
receipt stores. The declaration is the joint: atpx imports no harness and a
harness imports no atpx. An undeclared table narrows nothing.

## `[universe]`, the trial layout

**A data contract, schema only.** atpx declares where a workspace's trials
live because the workspace manifest is where a project says what shape it is.
atpx never executes a trial; a hermetic executor reads this table and neither
side imports the other, so a new executor is a new reader of a declaration
that already exists.

| Key | Type | Default | What it says |
| --- | --- | --- | --- |
| `root` | string | required | the directory holding the nodes, one directory per claim |
| `evidence` | string | `"evidence/receipts"` | the per-node path the receipt partitions sit under |
| `axes` | list of strings | `[]` | the coverage coordinates, each one a receipt column asked of every lane |
| `probed` | list of strings | `[]` | the distributions whose version every receipt records |
| `samples` | integer | `1` | how many passing receipts one cell owes before a lane is complete there |

```toml
[universe]
root = "experiments"
axes = ["card", "model"]
probed = ["torch", "numpy", "python-flint"]
samples = 1
```

An axis is resolved from a trial's own parameters when it names one and from
the run's probed provenance otherwise, so `model` comes off a parametrize grid
and `card` off the machine without either being special-cased. A flat universe
names the root itself and stores one dataset, which is the same rule with one
node rather than a special case. `samples` above one suits a program whose
subject is variance, where a re-run accumulates toward the target instead of
replaying it.

## `[claims]`, in a blueprint manifest

Not a workspace table. Every blueprint directory carries its own `atpx.toml`
holding only `[claims]`, one entry per claim, a bare command string or a table
with `command` and an optional `requires`. `{dir}` expands to the blueprint
directory's full path, and it is the only spelling that survives moving the
node.

```toml
[claims]
octave-exact = "python {dir}/probes/octave_exact.py"
tile-bias = { command = "python {dir}/probes/tile_bias.py", requires = "cuda" }
```

## Judgment rulings

Not a manifest table, a file: `judgments/<node>.ndjson` inside a blueprint
directory, one appended JSON record per ruling.

| Field | Type | What it says |
| --- | --- | --- |
| `referee` | string | the model lane id or the human name that ruled |
| `date` | string | the ISO date the ruling was made |
| `ruling` | `FATAL`, `GAP`, `MINOR`, `NONE` | how badly it cut |
| `claim` | string | what was attacked, the node itself or a numbered claim inside it |
| `prose` | string | the review file this record summarizes, node-directory-relative |
| `rung` | string | the ladder position that attacked, empty for a referee outside the ladder |

```jsonl
{"referee":"referee-theory","date":"2026-08-28","ruling":"FATAL","claim":"the locking core","prose":"judgments/referee-theory-2026-08-28.md","rung":"3"}
```

`atpx rule <slug> <referee> <ruling>` appends one, with the same verb for a
model lane and for a human referee, which is what lets an external review
count as evidence in the graph instead of a file only a person opens. The
reasoning stays prose in whatever `--prose` names; what lands here is the
standing `doctor` reads when it asks whether a sketched node was ever actually
attacked. A node with a recorded ruling answers that question directly, and a
node with none falls back to the frontmatter `judgments` pointers and a regex
over the prose behind them.
