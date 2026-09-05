<div align="center">

<!-- [![atpx banner](https://raw.githubusercontent.com/phvv-me/atpx/main/docs/assets/banner.png)](https://phvv.me/atpx) -->

[![CI](https://github.com/phvv-me/atpx/actions/workflows/ci.yml/badge.svg)](https://github.com/phvv-me/atpx/actions/workflows/ci.yml)
[![Publish](https://github.com/phvv-me/atpx/actions/workflows/publish.yml/badge.svg)](https://github.com/phvv-me/atpx/actions/workflows/publish.yml)
[![PyPI](https://img.shields.io/pypi/v/atpx)](https://pypi.org/project/atpx/)
[![Python](https://img.shields.io/pypi/pyversions/atpx)](https://pypi.org/project/atpx/)
[![Docs](https://img.shields.io/badge/docs-phvv.me%2Fatpx-111111)](https://phvv.me/atpx)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](https://github.com/phvv-me/atpx/actions/workflows/ci.yml)

</div>

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
   at `evidence/<hostname>.ndjson`, one certificate per line, and each blueprint's
   `node.md` carries the node's statement, status, and journal. The directory name
   is the node's name.

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
table pointing at the blueprints directory. Discovery walks up from the cwd.
`--project <path>` pins one invocation to a named workspace, its root or any
directory inside it, which is what a monorepo needs when its task runner
changes into the repository root before running anything. `ATPX_ROOT` pins
every invocation the same way through the environment, and an explicit `root`
argument in Python still wins over both. Describing the tool never opens a
workspace, so `atpx --help` answers from anywhere.

Claim commands run behind the launcher the workspace declares, so a node
manifest holds the bare command and one line in `atpx.toml` decides which
environment it lands in:

```toml
[workspace]
blueprints = "research/math"
runner = "uv run --"   # your environment tool; empty by default: run the command as written
```

Command templates use shell-style quoting on every host. ATPX expands `{dir}`
inside each parsed argument, so workspace paths containing spaces stay one
argument on Windows, macOS, and Linux. Executables are found through the host's
normal `PATH` rules, including `PATHEXT` on Windows.

`blueprints` takes a list as readily as a string, `["math", "experiments"]`,
and the roots are read as one graph, which is what a program needs once its
claims of record move between trees. A node carrying `superseded_by` is an
alias whose claim of record lives at the pointer, so a claim that moved is
counted once, at its current home. The
[configuration reference](https://phvv.me/atpx/config/) documents every table,
including the `[vocabulary]` and `[universe]` data contracts a trial harness
reads without importing atpx.

```sh
atpx run <slug> <claim> <command...>   # run anything: stamp, persist, auto-register
atpx ball <slug> <claim> -- <command...>   # run, gate on verified ball enclosures, rigor "ball"
atpx smt <slug> <claim> -- <command...>    # run, gate on unsat solver proofs, rigor "smt"
atpx hunt <slug> <claim> -- <command...>   # property-based counterexample search, exit 0 = found
atpx lab <slug> <claim> -- <command...>    # run a study, gate on its trial receipts, rigor "lab"
atpx open <slug> --kind theorem            # scaffold node.md, probes/, specs/claim-spec.md
atpx check <slug> <claim>      # re-run a registered claim, stamp + persist a certificate
atpx check <slug> <claim> --background   # detach it, the child persists the certificate
atpx checks <slug>             # background submissions, pending or landed
atpx verify [<slug>]           # freshness sweep, re-run runnable claims, flag stale evidence
atpx brief <slug>              # the full agent context bundle for one node, as markdown
atpx judge_brief <slug>        # what changed since the last refuter judgment
atpx status                    # nodes grouped by status, malformed under `invalid`
atpx graph                     # unsettled nodes whose dependencies are all settled
atpx doctor                    # what needs repair, reported and never mutated
atpx settle <slug> <status>    # move a node's status, gated on evidence artifacts
atpx lean <slug> [<target>]    # ingest a Lean build as evidence, auditing sorries and axioms
atpx fit <data.csv> <target>   # PySR symbolic regression, certifying the Pareto front
atpx recall "<query>"          # federated search, one certificate of hits per source
atpx log <slug> <who> <tag> "message"     # append one plain journal line
atpx rule <slug> <referee> <ruling>       # record one FATAL/GAP/MINOR/NONE judgment as data
atpx adopt <slug> --source <path>         # copy a markdown note into node.md
atpx index --write             # regenerate the results index note
```

`run` is capture-first. A new slug gets a blueprint directory and manifest, a
new claim gets its command registered on first use, and the certificate always
lands in the evidence ledger. The manifest is a record the tool maintains, not
a form the agent fills. The command is a leading-hyphen var-positional, so
`atpx run demo probe python -c "print(1)"` passes `-c` through verbatim. Put
`--seed` and `--timeout` before the command tokens, and separate a command that
itself takes those flags with `--`.

Workspace text files are UTF-8 on every host. Relative paths written into
certificates and diagnostics use `/`, so the durable record is independent of
the operating system that produced it.

Arguments are plain shell tokens under cyclopts, so a multi-word query needs
only ordinary quoting, `atpx recall "Leech lattice"`, never the doubled
quoting the old fire CLI required. Options follow their verb's signature
(`--seed 7`, `--background`, `--sources oeis`), and `atpx --help` lists every
verb with its parameters.

The verbs split into three surfaces:

| Surface | Verbs | One line |
|---|---|---|
| court | `settle`, `status`, `graph`, `doctor`, `brief`, `judge_brief`, `log`, `rule`, `index`, `open` | the mathematician's bench: reads the state, scaffolds nodes, and moves statuses behind evidence gates |
| engine | `run`, `ball`, `smt`, `hunt`, `check`, `verify`, `lean`, `fit`, `recall`, `adopt` | capture-first execution and the rigor gates, every run stamped into the evidence ledgers |
| counsel | `prove`, `refute` | the model lanes, cheap probes for the affirmative and hostile attack episodes for the negative |

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
await ws.recall("196560, 16773120")  # the Leech theta series turns up OEIS A008408

# synchronous scripts and one-liners block on them through the sync facade
ws.sync.recall("196560, 16773120")
ws.status()  # the local readers stay plain sync
```

## Recall

`recall` fans one query out to every engine with the `search` capability and
returns a single certificate listing the hits per source. Four sources
enroll: OEIS by sequence values or words, loogle for mathlib declarations,
arXiv full-field phrase search, and the zbMATH Open REST API. All are keyless
and carry short timeouts. Knowledge recall against AIZK happens at the agent
level through its own tools; atpx keeps only the mathematical sources.

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

`judge_brief <slug>` keeps re-judgment rounds cheap. Settling a node to
`sketched` snapshots the full node text into the blueprint's
`judgments/` directory (a verbatim snapshot rather than a hash or git, since it
needs no repository around the node file and always yields a real diff). The verb
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

`status` and `graph` are tolerant readers. A node whose status field is
malformed or missing lands in the `invalid` bucket instead of crashing the
read, and `doctor` is the matching lint: invalid statuses, stray evidence
files, blueprint directories without a manifest, blueprints with evidence or a
manifest but no `node.md`, and wikilinks pointing at slugs with no blueprint
directory. It reports and never mutates.

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

## Rigor classes

Every certificate carries a `rigor` field grading its evidence class, plain
strings the readers tolerate beyond this vocabulary:

| rigor | meaning | stamped by |
|---|---|---|
| `sampled` | ordinary numerical probe, finite cases | `run`, `check`, `verify`, `hunt`, `fit` |
| `exact` | exact arithmetic over rationals or integers | agents stamping exact-arithmetic probes |
| `ball` | interval enclosure, true for the whole ball | the `ball` verb's stdout gate |
| `smt` | solver proof, the claim's negation unsat | the `smt` verb's stdout gate |
| `lean` | kernel-checked build | the `lean` verb |

`ball` runs a command exactly like `run` and then audits the full output: the
probe prints one `ball_certificate` JSON line per `atpx.rigor.ball_witness`
call (an arb enclosure entirely inside the tolerance interval around an exact
target), and the gate demands at least one line with every one verified.
`smt` audits `smt_certificate` lines the same way, demanding every `result`
be `unsat` for the claim's NEGATION; a `sat` result fails the gate and the
probe keeps the model in its output, since a model is a counterexample, still
valuable, never a validation. A gated-out run keeps rigor `sampled` and a
forced nonzero exit.

`hunt` is the free counterexample search, hypothesis-style property probes in
the refuter convention: exit 0 means a counterexample was FOUND and shrunk
(the probe prints the falsifying example), nonzero means the property
survived the budget. Run `hunt` BEFORE summoning counsel refutation, it costs
nothing and kills a false claim without a single model call.

## Counsel discipline

Lessons the 2026-08-14 protocol rounds paid for; follow them and the loop
stays cheap and honest.

**The statement lives in `node.md`, complete and inline.** The refuter reads
the node file; a statement of record deferred to an external note starves
every attack into guessing (observed verbatim: "full statement, model
definitions, and target bounds are external to the provided snippet"). A
starved round produces strawmen and its survival is worth nothing.

**Pin the scope or lose to inversions.** Every mechanically demonstrating
attack that failed semantic review did so by moving the goalposts, and each
pattern recurs: quantifier inversion (refuting "all transforms commute" when
the claim characterizes WHICH commute), direction inversion (applying a
contraction factor as amplification), model swap (stochastic rounding against
a deterministic-RNE claim), expectation-versus-realization (per-trial spread
read as bias of a mean), and invented targets (a guessed bound "refuted" by
Monte Carlo noise at one sigma). State quantifier domains, the noise model,
and the expectation scope in the node, and these attacks die at review.

**The mechanical verdict is a candidate, never a ruling.** A gate-clean
exit 0 is where semantic review STARTS. Review rules the round in the
judgment file, the judgment settles the node, and a genuine finding often
lands as GAP, a statement repair, rather than FATAL (a round-2 attack pair
exposed a criterion clause that was false under one reading of its symbol
and vacuous under the other; the mathematics survived, the phrasing did not).

**Attackers earn diversity, the prover earns thrift.** The prover's output is
mechanically gated and repairable, so the cheap lane is fine; attack quality
bounds the value of every "survived n rounds", so the attacker roster is
where families and stronger snapshots belong. The `[models]` table's one
`ladder` list serves both roles, bosses in `refute` and player generations
in campaign loops, with `prover` as the defense rung override.

**The roster is a cost ladder of boss battles.** `refute` walks the
attackers in order, cheapest first, and each rung is a bout: the boss
swings attack probes, and every demonstrated attack summons the prover
lane to answer with a defense probe, a precondition audit or a faithful
re-measurement, machine-gated like every other move, so no side ever
argues in prose. A rebutted boss gets the defense output and must produce
a new attack within its `rounds` budget; an attack the defense cannot
rebut ends the climb as the FATAL candidate. Strawman demonstrations die
mechanically inside the bout instead of waiting for review, a claim a
cheap boss breaks never pays for the dear rungs, and the dear rungs only
ever attack survivors, exactly the claims worth their price. Order the
roster by real per-episode cost, opening with the prover's own model as the
free screen, and rank promotional sticker prices where their true cost sits.
Frontier families whose harness the agent already carries (a Claude subagent,
codex headless) belong above the API rungs as plan-billed referees rather
than on the metered key. Capability tiers beat family variety at the top: in the
2026-08-14 panel, nine cheap-roster rounds yielded two statement-level GAPs
while a single top-tier referee found the one structural GAP that four
other lanes missed, so reserve the strongest referee for load-bearing
survivors and let review, not the mechanical verdict, end the climb.

## Settling

Status moves are gated on evidence artifacts rather than claimed roles, down
this ladder:

| status | gate |
|---|---|
| `open`, `in_progress` | free |
| `sketched` | `--judgment <path>`, the recorded refuter ruling |
| `validated` | `--certificate <claim>`, a persisted certificate with rigor `ball`, `smt`, or `exact` and exit 0 |
| `refuted` | `--counterexample <claim>`, a persisted counterexample certificate |
| `verified` | `--lean <claim>`, a clean Lean build certificate |
| `undecided` | free, the verdict of a clean run whose registered comparison could not separate the outcomes |
| `abandoned`, `known` | free, `known` marking a literature collision, true but already in the record |

```sh
atpx settle <slug> sketched --judgment <path>          # the recorded refuter ruling
atpx settle <slug> validated --certificate <claim>     # a persisted ball/smt/exact certificate
atpx settle <slug> refuted --counterexample <claim>    # a persisted counterexample certificate
atpx settle <slug> verified --lean <claim>             # a clean Lean build certificate
```

`sketched` demands the judgment file the refuter recorded, `validated` a
rigorous machine certificate (interval, solver, or exact arithmetic) short of
a kernel-checked proof, `refuted` a counterexample certificate persisted in
the node's blueprint ledgers, and `verified` a persisted Lean certificate
that built cleanly with zero sorries and an empty `flagged` list. `atpx lean <slug>` produces that certificate by
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
assert sweep.stable, sweep.outcomes  # a nonzero spread is a refutation lead

ties = boundary_ties([[2, 0], [1, 1]])  # exact dyadic midpoints v/2, decoder tie bait
batches = precision_tilt(ties, [2**-20, 2**-30, 2**-40])  # verdicts must survive tilts

verdict = rederive(basis_a, basis_b)  # exact unimodular change-of-basis check
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
concurrently through `httpx.AsyncClient`, `run`, `check`, and `lean` execute their commands
as asyncio subprocesses, and `verify` re-runs claims with at most four in
flight. The purely local or CPU-bound verbs (`status`, `graph`, `brief`,
`doctor`, `settle`, `fit`, ...) stay plain sync.

File-backed writes are serialized by native locks. Their adjacent `.lock` paths are
cleanup markers rather than ownership records: ATPX sweeps them after use, including
the release-before-delete path Windows requires for an open lock handle.
A new append also terminates any partial tail left by a killed writer before writing its
own record, so the damaged record cannot make the next certificate unreadable.

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
