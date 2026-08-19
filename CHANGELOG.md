# Changelog

All notable changes to atpx are documented here.

The format follows Keep a Changelog, and releases are cut from the version in `pyproject.toml`.

## Unreleased

### Added

- `--project <path>` on every CLI invocation, pinning one run to a named
  workspace (its root or any directory inside it). The answer to a monorepo
  task runner that changes into the repository root before running anything,
  where the upward walk would otherwise always land on the top workspace.
- `lab`, the verb for a claim whose verification is an experiment rather than
  a script. The command prints one `{"mainboard_receipt": {...}}` JSON line
  per trial, carrying its content-addressed `run_id`, its outcome, and every
  declared gate's verdict; the gate demands at least one line and every trial
  through its gates, stamps rigor `lab`, and keeps the receipts in the
  certificate's witness list. Re-verification is the same verb with no
  command, replaying what the manifest recorded. Rigor `lab` is evidence with
  an identity, not a proof, and `settle validated` keeps refusing it.
- `[workspace] runner`, a command prefix every claim, background check, and
  Lean build runs behind (`mainboard run --`, say). Empty by default, so a
  plain checkout runs claims on the interpreter already around atpx.
- `doctor` gains three evidence lints: `failing_claims` (newest certificate
  exited nonzero), `unevidenced_claims` (declared but never certified), and
  `stale_claims` (evidence stamped before the last commit that changed the
  node it supports).
- `ATPX_ROOT` environment override for workspace discovery: when set, every
  invocation pins to that root instead of walking up from the cwd, so verbs
  fired from anywhere in a monorepo cannot silently target the wrong vault.
  An explicit root argument still wins.
- `fit` gains `--features` (restrict the fit to named columns, recorded in
  the certificate), comma-joined operator menus (`--unary exp,log`,
  `--binary "+,-,*"`) alongside repeated flags, and cwd-first data path
  resolution (root-relative second).

### Changed

- `doctor` returns a certificate instead of a plain report, and covers the
  resolved workspace plus every workspace nested inside it in one pass. The
  payload is `{"breakages": [...], "workspaces": {"<path>": {...}}}` and the
  exit is nonzero when any finding contradicts what a workspace asserts;
  untidiness the capture-first posture tolerates still reports and never
  gates.
- A verb's failing certificate now sets the process exit code, so `doctor`,
  `verify`, `ball`, `smt`, and `lab` gate a pipeline without anyone parsing
  their JSON. `hunt` keeps its documented inversion.
- Opening a workspace touches no filesystem until a verb needs it, so
  `atpx --help` answers from a directory holding no workspace at all.
- `{dir}` in a claim command expands to the node directory's full path rather
  than a workspace-relative one, since the declared launcher decides which
  directory a claim actually runs from.
- The default runner is a plain subprocess behind the declared launcher,
  replacing the hardcoded `chefe run` shell-out.

- Internal restructure: `workspace.py` is now a thin facade over service
  modules, `running` (capture-first execution, freshness sweep),
  `settlement` (evidence gates as a patos registry, one class per gated
  status), `leaning` (Lean build audit), `discovery` (fit lane behind a
  `SymbolicRegressor` seam with holdout policy objects), `recalling`
  (federated search fan-out), and `doctoring` (the lint). The CLI verb
  surface is unchanged.
- Blueprint manifests are serialized by a real minimal TOML emitter that
  round-trips through `tomllib` (quoted keys, escaped control characters,
  inline tables), and rewriting a manifest preserves top-level keys it does
  not manage.
- `verify` staleness is judged per host: a claim only counts stale when no
  host's newest certificate matches the current revision, so cross-host
  clock skew cannot shadow fresh local evidence.
- Journal writes (`log`, `settle`) validate against the log parser before
  touching the file, stamp the UTC date (the certificate clock), and a
  message-less settle now lands as a line the parser reads back.
- `settle verified` refuses certificates without a Lean audit shape, and a
  malformed `claims` manifest value fails as a clean domain error.
- Claim payload parsing reads indented JSON and takes the last complete
  value on a line with several concatenated values (interleaved writers).
- `recall` and `verify` fan out under `asyncio.TaskGroup`, so a fault or
  ctrl-c cancels and awaits sibling requests instead of abandoning them.
- Slugs and claims are validated as single path segments at registration.

- Initial public project scaffolding.
- Stage 2 recall: the `recall` verb and CLI federate one query across `search`
  engines (vault via qmd, OEIS, loogle, arXiv, zbMATH Open) into a single
  certificate listing hits per source, with failed sources recorded under
  `errors` and a nonzero exit status.
- Blueprint claims accept a table form with `requires`; a claim whose
  requirement this host cannot meet (for example `requires = "cuda"`) is
  skipped gracefully and never enters the evidence ledger.
- Stage 3a loop mechanics: `brief` (the one-command agent context bundle),
  `judge_brief` (node diff and newer certificates since the last refuter
  judgment, backed by snapshots in the blueprint's `judgments/` dir),
  `check --background` plus `checks` (detached runs with pending/landed
  tracking under `checks/`), `verify` (freshness sweep flagging git-rev-stale
  certificates, nothing deleted), `strategies` (close-rates per strategy tag),
  `connect` (OEIS fingerprinting of integer runs in evidence payloads), and
  `lean_candidates` (backlinks-over-length formalization ranking).
- `atpx.adversarial`, the refuter's typed probe library: `seed_sensitivity`,
  `boundary_ties`, `precision_tilt`, and `rederive` (exact rational
  change-of-basis check through flint), all property-tested.
- Name genericity: `atpx.NAME` derives from `__name__` and `atpx.CONFIG`
  from it, so the manifest names, CLI name, evidence stamps, and detached
  child commands all rename with the package folder.

### Changed

- The CLI moved from fire to cyclopts and the I/O verbs went async-first.
  `check`, `verify`, `recall`, and `connect` are now `async def` on
  `Workspace` and compose on the caller's event loop (`asyncio.gather` over
  several recalls works); the purely local and CPU-bound verbs stay sync,
  with `cross_check` keeping its deliberate sequential loop. cyclopts owns
  the CLI event loop and runs sync and async verbs alike, command names keep
  their underscores (`cross_check`, `judge_brief`), certificates print as
  canonical JSON, markdown verbs print as-is, and a multi-word query needs
  only ordinary shell quoting (`atpx recall "Leech lattice"`, no more fire
  double quoting). Synchronous scripts block on the async verbs through the
  new `workspace().sync` facade, backed by the same `runtime.drive` that
  still refuses nested event loops with a clear error. fire left the
  dependencies, cyclopts entered.
- Renamed the package from prova to atpx (Automatic Theorem Prover
  Accelerated). The name genericity work means the rename is one folder move,
  the CLI is now `atpx`, the workspace marker and blueprint manifests are
  `atpx.toml`, and new certificates stamp `atpx` as the engine. Historical
  evidence ledger entries stamped by `prova` stay untouched.
- `recall` sources, `cross_check` engines, and the `verify` sweep run
  concurrently on `ThreadPoolExecutor`; free-threaded CPython 3.14t was
  evaluated and documented in the README (installable except for cvc5, which
  ships no `cp314t` wheel; standard 3.14 stays the default).
- The parallel surfaces dropped threads entirely. `recall` fans out with
  `asyncio.gather` over a new `SearchEngine` intermediate whose async `fetch`
  is the real implementation (`httpx.AsyncClient` for the web sources and an
  asyncio subprocess for the vault qmd call), `verify` re-runs claims through
  asyncio subprocesses bounded by a semaphore at four in flight, and
  `cross_check` probes its CPU-bound engines in a plain sequential loop. The
  public API and the fire CLI stay fully synchronous, every verb drives its
  async internals with `asyncio.run` and refuses to run inside an active
  event loop with a clear error. The `Engine` contract is unchanged for
  compute engines, and `ChefeRunner` now executes claim commands through
  `asyncio.create_subprocess_exec` instead of plumbum. The free-threading
  evaluation in the README is historical context now, the question is moot
  by design.

## 0.0.3 - 2026-06-16

### Fixed

- The CLI now turns a verb's own domain error into one clean `error:` line and
  a nonzero exit instead of dumping a Python traceback. An unknown engine, a
  missing slug, an unknown claim or node, a forbidden role transition, or a
  down search source each print the message the verb already wrote. A genuine
  programming fault still surfaces its full traceback, since `main` catches
  only the expected exception families.
- `prove` validates an explicit `--syntax` value against the known dialects and
  reports `unknown syntax 'x'; pass one of smtlib, tptp`, where it used to die
  on a raw `KeyError` from the internal closing-condition table.
- `Blueprint.load` reports `no blueprint 'slug' at <path>` for a missing
  blueprint directory instead of leaking a bare `FileNotFoundError` on the
  manifest path.
