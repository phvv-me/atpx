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
2. **CLI.** `atpx <verb>` exposes the same methods through fire.
3. **Filesystem.** Blueprint directories hold per-host append-only evidence ledgers
   at `evidence/<hostname>.json`, and vault zettels carry node status.

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
table pointing at the blueprints directory and the zettel vault.

```sh
atpx check <slug> <claim>      # run a blueprint claim, stamp + persist a certificate
atpx check <slug> <claim> --background   # detach it, the child persists the certificate
atpx checks <slug>             # background submissions, pending or landed
atpx verify [<slug>]           # freshness sweep, re-run cheap claims, flag stale evidence
atpx brief <slug>              # the full agent context bundle for one node, as markdown
atpx judge_brief <slug>        # what changed since the last refuter judgment
atpx status                    # nodes grouped by zettel status
atpx graph                     # open nodes whose dependencies are all settled
atpx recall '"<query>"'        # federated search, one certificate of hits per source
atpx connect <slug>            # OEIS lookups for integer runs in the node's evidence
atpx strategies                # close-rates by strategy tag over the append-only logs
atpx lean_candidates           # sketched nodes ranked for formalization
atpx log <zettel> <role> <tag> "message" --status sketched   # role-gated journal
atpx index --write             # regenerate the results index note
atpx compute <engine> <operation> <payload>                  # one typed engine op
atpx prove "<goal>"            # try ATP engines in order, certify who closed it
atpx cross_check <operation> <payload>   # same probe on independent engines
```

Status transitions are enforced in code, not prose. Only a refuter sets
`sketched` or `refuted` and only the formalizer sets `verified`.

```python
import atpx

ws = atpx.workspace()
certificate = ws.check("voronoi-e8-codec", "bijectivity-m1")
ws.cross_check("evaluate", "exp(pi*sqrt(163))")   # sympy vs mpmath, certified agreement
ws.recall("196560, 16773120")   # the Leech theta series turns up OEIS A008408
```

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

## Recall

`recall` fans one query out to every engine with the `search` capability and
returns a single certificate listing the hits per source. A source that is
unavailable or fails at run time becomes an entry under `errors` and the
certificate exits nonzero, so a partial recall is never mistaken for a complete
one. The network engines carry short timeouts and no API keys; loogle expects a
Lean identifier or pattern such as `Real.sqrt _ * _` and reports plain-English
queries as errors.

## Loop mechanics

These verbs exist because loop bookkeeping, not mathematics, is what slows an
agentic prove-and-refute cycle down.

`brief <slug>` assembles the whole opening context in one command, the node
text, its dependency statuses from the wikilink walk, the per-host evidence
summary with stale flags against the current git revision, the last refuter
judgment verbatim, and the blueprint file list, all as markdown on stdout.

`judge_brief <slug>` keeps re-judgment rounds cheap. Every refuter log line on
a node with a blueprint snapshots the full node text into the blueprint's
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

`strategies` aggregates the `[who/strategy date]` journal lines across all
nodes into close-rates per strategy tag, and `lean_candidates` ranks sketched
nodes by backlink count over statement length. Both are v1 tables built on
documented heuristics, no learning and no scoring model.

`connect <slug>` extracts integer runs from the node's persisted certificate
payloads and queries each through the OEIS search engine via `recall`, ambient
conjecture generation under the same certificate discipline.

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

## Free threading

The parallel surfaces (`recall` sources, `cross_check` engines, the `verify`
sweep) run on `ThreadPoolExecutor`, they are I/O and subprocess bound. Standard
CPython 3.14 is the supported runtime; free-threaded 3.14t is currently
**blocked by one dependency** and is not required for anything.

The table below was measured on `cpython-3.14.3+freethreaded` (macOS arm64,
uv-managed, 2026-06).

| dependency | free-threaded wheel | imports under `PYTHON_GIL=0` |
| ------------- | ------------------- | ---------------------------- |
| pydantic-core | yes | yes, GIL stays off |
| z3-solver | yes | yes, GIL stays off |
| python-flint | yes (0.8.0) | yes, GIL stays off |
| cvc5 | **no** (through 1.3.4, `cp38`-`cp314` only) | n/a |
| sympy, mpmath, httpx, fire, plumbum, patos | yes | yes |

`uv pip install atpx` on 3.14t therefore fails to resolve because of cvc5.
With cvc5 stubbed out for the experiment, 130 of the 132 tests pass under
`PYTHON_GIL=0` (the two that exercise the real cvc5 solver cannot run), so the
package itself is free-threading clean and the status flips to supported the
moment cvc5 ships a `cp314t` wheel.

## Engines

Engines self-register through a typed registry and stamp their name and version
into every certificate. Each declares one capability.

| engine  | capability  | availability                                  |
| ------- | ----------- | --------------------------------------------- |
| sympy   | evaluate    | always (hard dependency)                       |
| mpmath  | evaluate    | always (hard dependency)                       |
| flint   | factor      | always (hard dependency, python-flint)         |
| pari    | factor      | linux only, and only when cypari2 is installed |
| z3      | solve-smt   | always (hard dependency, z3-solver)            |
| cvc5    | solve-smt   | always (hard dependency)                       |
| eprover | prove-tptp  | only when the `eprover` binary is on PATH      |
| vampire | prove-tptp  | only when the `vampire` binary is on PATH      |
| vault   | search      | only when the `chefe` binary is on PATH        |
| oeis    | search      | always, network EAFP at run time               |
| loogle  | search      | always, network EAFP at run time               |
| arxiv   | search      | always, network EAFP at run time               |
| zbmath  | search      | always, network EAFP at run time               |

cypari2 is not a dependency because its wheel only installs cleanly on linux
x86-64, so the pari engine reports unavailable everywhere else. The two
first-order provers are subprocess engines and never Python dependencies.

The vault engine searches the Zettelkasten through `qmd search` inside the
chefe env, the no-LLM BM25 surface, so recall never waits on a model download.
The four web sources are keyless: OEIS by sequence values or words, loogle for
mathlib declarations, arXiv full-field phrase search, and the zbMATH Open REST
API, which answers without a key.

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
