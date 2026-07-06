<div align="center">

<!-- [![atpx banner](https://raw.githubusercontent.com/phvv-me/atpx/main/docs/assets/banner.png)](https://phvv.me/atpx) -->

[![CI](https://github.com/phvv-me/atpx/actions/workflows/ci.yml/badge.svg)](https://github.com/phvv-me/atpx/actions/workflows/ci.yml)
[![Publish](https://github.com/phvv-me/atpx/actions/workflows/publish.yml/badge.svg)](https://github.com/phvv-me/atpx/actions/workflows/publish.yml)
[![PyPI](https://img.shields.io/pypi/v/atpx)](https://pypi.org/project/atpx/)
[![Python](https://img.shields.io/pypi/pyversions/atpx)](https://pypi.org/project/atpx/)
[![Docs](https://img.shields.io/badge/docs-phvv.me%2Fatpx-EAB308)](https://phvv.me/atpx)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](https://github.com/phvv-me/atpx/actions/workflows/ci.yml)

</div>

[🇧🇷](https://phvv.me/atpx/pt-BR/) [🇲🇽](https://phvv.me/atpx/es/) [🇯🇵](https://phvv.me/atpx/ja/) [🇨🇳](https://phvv.me/atpx/zh/)

Agentic mathematics workbench: every result is a certificate

atpx (Automatic Theorem Prover Accelerated, formerly published as prova) is the
ledger underneath an agentic math loop. Every operation returns a
`Certificate` stamping the claim, the result, the engine name and version, the
hostname, device, seed, git revision, timestamp, and exit status. There are no
naked results anywhere, no daemon, and no database, just three surfaces over one
filesystem state.

1. **Python API.** `atpx.workspace()` returns a `Workspace` whose methods are the verbs.
2. **CLI.** `atpx <verb>` exposes the same methods through cyclopts, which owns the
   event loop and runs the async verbs to completion.
3. **Filesystem.** Blueprint directories hold per-host append-only evidence ledgers
   at `evidence/<hostname>.json`, and vault zettels carry node status.

The posture is capture first, tolerate the mess, gate on evidence. `run` wraps
any command with zero ceremony, the readers never crash on malformed state,
`doctor` reports what needs repair, and the settling transitions demand
artifacts rather than trusting a claimed role.

## Install

```sh
pip install atpx
```
For a persistent CLI install:

```sh
uv tool install atpx   # or: pipx install atpx
```

## Use

A workspace root is any directory whose `atpx.toml` declares a `[workspace]`
table pointing at the blueprints directory and the zettel vault. Discovery
walks up from the cwd, and the `ATPX_ROOT` environment variable overrides the
walk, pinning every invocation to one workspace so a verb fired from anywhere
in a monorepo cannot silently target whatever vault sits above the cwd. An
explicit `root` argument still wins over the variable.

```sh
atpx run <slug> <claim> <command...>   # run anything: stamp, persist, auto-register
atpx check <slug> <claim>      # re-run a registered claim, stamp + persist a certificate
atpx check <slug> <claim> --background   # detach it, the child persists the certificate
atpx checks <slug>             # background submissions, pending or landed
atpx verify [<slug>]           # freshness sweep, re-run runnable claims, flag stale evidence
atpx brief <slug>              # the full agent context bundle for one node, as markdown
atpx judge_brief <slug>        # what changed since the last refuter judgment
atpx status                    # nodes grouped by zettel status, malformed under `invalid`
atpx graph                     # unsettled nodes whose dependencies are all settled
atpx doctor                    # what needs repair, reported and never mutated
atpx settle <zettel> <status>  # move a node's status, gated on evidence artifacts
atpx lean <slug> [<target>]    # ingest a Lean build as evidence, auditing sorries and axioms
atpx fit <data.csv> <target>   # PySR symbolic regression, certifying the Pareto front
atpx recall "<query>"          # federated search, one certificate of hits per source
atpx log <zettel> <who> <tag> "message"   # append one plain journal line
atpx index --write             # regenerate the results index note
```

`run` is capture-first. A new slug gets a blueprint directory and manifest, a
new claim gets its command registered on first use, and the certificate always
lands in the evidence ledger. The manifest is a record the tool maintains, not
a form the agent fills. The command is a leading-hyphen var-positional, so
`atpx run demo probe python -c "print(1)"` passes `-c` through verbatim. Put
`--seed` and `--timeout` before the command tokens, and separate a command that
itself takes those flags with `--`.

Arguments are plain shell tokens under cyclopts, so a multi-word query needs
only ordinary quoting, `atpx recall "Leech lattice"`, never the doubled
quoting the old fire CLI required. Options follow their verb's signature
(`--seed 7`, `--background`, `--sources oeis`), and `atpx --help` lists every
verb with its parameters.

A blueprint claim is either a bare command string or a table with `command` and
`requires`. A claim whose requirement this host cannot meet, `requires = "cuda"`
on a machine without an NVIDIA driver, is skipped gracefully: the certificate
says so and nothing enters the evidence ledger, since a skip is not a run.

```toml
[claims]
bijectivity-m1 = "python {dir}/checks.py bijectivity 1"

[claims.gaussian-ladder]
command = "python {dir}/checks.py claim3"
requires = "cuda"
```

```python
import atpx

ws = atpx.workspace()

# the I/O verbs are async, so they compose on one event loop
certificate = await ws.run("voronoi-e8-codec", "bijectivity-m1", "python", "checks.py")
await ws.recall("196560, 16773120")   # the Leech theta series turns up OEIS A008408

# synchronous scripts and one-liners block on them through the sync facade
ws.sync.recall("196560, 16773120")
ws.status()   # the local readers stay plain sync
```

## Recall

`recall` fans one query out to every engine with the `search` capability and
returns a single certificate listing the hits per source. Five sources enroll:
the vault (Zettelkasten search through `qmd` inside the chefe env, available
only when the `chefe` binary is on PATH), OEIS by sequence values or words,
loogle for mathlib declarations, arXiv full-field phrase search, and the
zbMATH Open REST API. The web sources are keyless and carry short timeouts.

An empty search is not a failure. zbMATH answers a no-result query with HTTP
404 and loogle reports a query it cannot parse ("Unknown identifier ...")
through its `error` field, since it only understands Lean identifiers and
patterns such as `Real.sqrt _ * _`. Both come back as zero hits. Genuine
transport failures, timeouts, connection errors, and 5xx still land under
`errors` and the certificate exits nonzero, so a partial recall is never
mistaken for a complete one.

## Loop mechanics

These verbs exist because loop bookkeeping, not mathematics, is what slows an
agentic prove-and-refute cycle down.

`brief <slug>` assembles the whole opening context in one command, the node
text, its dependency statuses from the wikilink walk, the per-host evidence
summary with stale flags against the current git revision, the last refuter
judgment verbatim, and the blueprint file list, all as markdown on stdout.

`judge_brief <slug>` keeps re-judgment rounds cheap. Settling a node with a
blueprint to `sketched` snapshots the full node text into the blueprint's
`judgments/` directory (a verbatim snapshot rather than a hash or git, since it
needs no repository around the vault and always yields a real diff). The verb
then prints the unified diff since that snapshot plus the claims whose
certificates landed after it.

`check <slug> <claim> --background` detaches the run in its own session with
stdout under the blueprint's `checks/` directory. The child stamps and persists
the certificate exactly as a foreground check does, and `checks <slug>` reports
each submission as pending or landed by reading the evidence ledgers. Remote
stays composition, lote runs this same CLI on another host.

`verify [<slug>]` is the freshness sweep. It re-runs every claim this host can
run (`requires`-gated claims it cannot meet are reported skipped), appends the
fresh certificates, and flags claims whose latest prior certificate carries a
git revision different from the tree now. Nothing is ever deleted.

`status` and `graph` are tolerant readers. A zettel whose status field is
malformed lands in the `invalid` bucket instead of crashing the read, and
`doctor` is the matching lint: invalid statuses, stray evidence files,
blueprint directories without a manifest, and nodes pointing at blueprints
that do not exist. It reports and never mutates.

`fit` is the symbolic-regression lane, PySR over a CSV artifact with a
held-out split, certifying the Pareto front of equations and the holdout
scores. The data path resolves cwd-first and then root-relative. The operator
menu opens with repeated flags (`--unary exp --unary log`) or comma-joined
tokens (`--unary exp,log`, `--binary "+,-,*"`), the comma form sidestepping
flag parsing of a bare `-`, which otherwise needs `--binary=-`; PySR defaults
hold when a menu is omitted, because a law the operators cannot express is
only ever matched by an opaque rational. `--features rate,noise` restricts the
fit to named columns when the CSV carries bookkeeping columns that would
pollute the search. A random holdout does not predict extrapolation, so
`--tail 0.1` holds out the fraction of rows with the largest values of the
driver column instead, `--driver` naming it and defaulting to the first
feature column. The certificate records the front, `holdout_r2` and
`holdout_nmse` (`null` when the holdout target is constant), the `holdout`
split (mode, fraction, driver), the `operators` menu, and the `features`
actually used. pysr is not a dependency; without it the verb returns an
honest nonzero certificate saying the lane is dormant.

## Settling

Status moves are gated on evidence artifacts rather than claimed roles. The
free statuses (`open`, `in_progress`, `abandoned`, `known`) need none, with
`known` marking a literature collision, a claim that is true but already in
the record, distinct from `refuted` and never a novelty.

```sh
atpx settle <zettel> sketched --judgment <path>          # the recorded refuter ruling
atpx settle <zettel> refuted --counterexample <claim>    # a persisted counterexample certificate
atpx settle <zettel> verified --lean <claim>             # a clean Lean build certificate
```

`sketched` demands the judgment file the refuter recorded, `refuted` a
counterexample certificate persisted in the node's blueprint ledgers, and
`verified` a persisted Lean certificate that built cleanly with zero sorries
and an empty `flagged` list. `atpx lean <slug>` produces that certificate by
running the workspace's lean task (`lean-build` by default), counting sorries
and scanning the output for the risky axiom markers `sorryAx`, `ofReduceBool`,
`ofNat.lit`, `Lean.trustCompiler` and `native_decide`, recorded as `flagged`
and forcing a nonzero exit when any appear; Lean interaction itself lives in
lean-lsp-mcp, this verb only turns a build into the evidence `settle verified`
demands.

`log` appends one plain journal line, `- [who/tag date] message`, to a node's
append-only log and never touches status. Status moves live in `settle`.

## Adversarial probes

`atpx.adversarial` is the refuter's typed toolkit, four reusable attack
probes that turn folklore into one-liners.

```python
from atpx.adversarial import boundary_ties, precision_tilt, rederive, seed_sensitivity

sweep = seed_sensitivity(lambda seed: run_check(seed), seeds=range(8))
assert sweep.stable, sweep.outcomes          # a nonzero spread is a refutation lead

ties = boundary_ties([[2, 0], [1, 1]])       # exact dyadic midpoints v/2, decoder tie bait
batches = precision_tilt(ties, [2**-20, 2**-30, 2**-40])   # verdicts must survive tilts

verdict = rederive(basis_a, basis_b)         # exact unimodular change-of-basis check
assert verdict.same_lattice, verdict.determinant
```

`boundary_ties` returns points exactly halfway between the origin and nearby
lattice vectors, exactly representable in binary floating point, so a decoder
must break the tie deterministically. `rederive` runs over exact rationals
through flint and reports integrality and the determinant of the basis-change
matrix.

## Concurrency

atpx has no threads. The verbs with real I/O underneath are `async def` and
compose on the caller's event loop. `recall` awaits every search source
concurrently (`httpx.AsyncClient` for the web sources and an asyncio
subprocess for the vault), `run`, `check`, and `lean` execute their commands
as asyncio subprocesses, and `verify` re-runs claims with at most four in
flight. The purely local or CPU-bound verbs (`status`, `graph`, `brief`,
`doctor`, `settle`, `fit`, ...) stay plain sync.

The CLI never exposes any of this, cyclopts owns the event loop and runs sync
and async verbs alike. In Python, async code awaits the verbs directly and
can fan them out with `asyncio.gather`; synchronous scripts use the
`workspace().sync` facade, which drives one verb to completion on a fresh
loop per call. Calling the facade from inside an already running loop fails
with a clear error instead of a nested-loop crash, await the verb directly
there.

## Documentation

Full documentation lives at [https://phvv.me/atpx](https://phvv.me/atpx).

For LLM-assisted use, start with [`llms.txt`](https://phvv.me/atpx/llms.txt).

## Development

The dev environment is managed by [uv](https://docs.astral.sh/uv/).

- Install: `uv sync --extra dev`
- Lint: `uv run ruff check . && uv run ruff format --check .`
- Typecheck: `uv run mypy src && uv run pyrefly check`
- Test: `uv run pytest -q`
- Docs: `uv run --extra docs mkdocs build -d site`
- Build: `uv build`
