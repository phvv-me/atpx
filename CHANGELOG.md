# Changelog

All notable changes to atpx are documented here.

The format follows Keep a Changelog, and releases are cut from the version in `pyproject.toml`.

## 0.0.7 - 2026-08-31

### Fixed

- A node whose front matter spells its name as `null` no longer mints a slug
  from the text `None` and lands under it in the index; the slug comes from the
  folder when the spelling is missing, and a spelling that is present but null
  is refused with the file named.

## 0.0.6 - 2026-08-29

### Added

- `undecided` is the fifth settled word on the lifecycle ladder: the verdict of
  a run that finished clean and whose registered comparison could not separate
  the outcomes. It settles a node like the rest of the settled statuses, so it
  leaves the frontier, tallies under its own key in `atpx status`, and can be
  declared in `[vocabulary]`; and it is free of any evidence gate, since no
  artifact witnesses a separation that did not happen. Without it a program
  reading an inconclusive trial has to spend `abandoned`, which says the attack
  was dropped, or `known`, which says the record already holds the answer, and
  both claim something the run never showed.

### Fixed

- `atpx index` refuses to write a regeneration that found no nodes at all over
  an index that carries rows, naming the blueprint roots it searched. 0.0.4 read
  a list-valued `blueprints` setting back as the text of a list, matched no
  directory, and rewrote a 63-row index with an empty table; the roots are wrong
  in that state rather than the workspace being empty, and nothing is written.
- A ledger's lock file no longer outlives its last holder. The index and the
  evidence stream take the same `Guard`, which removes the `.lock` pathname as
  the last holder lets go and sweeps away a leftover from a killed session on
  the next run that takes the lock, so a workspace stops accumulating zero-byte
  `INDEX.md.lock` files nobody can tell from live ones. The lock itself lives on
  the inode and the kernel drops it when its process dies, so such a leftover
  never blocked anything; `filelock>=3.32` is now the floor, since the sweep
  needs a lock that drops one won on an already-unlinked inode and retries.

## 0.0.5 - 2026-08-29

### Added

- `[workspace] blueprints` accepts a list of roots, `["math", "experiments"]`,
  read as one graph rather than as two workspaces, which is what a program
  needs once its claims of record move between trees. A bare string still
  names one root. Roots are searched in declaration order, the first is where
  a fresh blueprint lands, and a slug an existing root already holds is always
  reached there, so no verb opens a second copy of a node.
- `superseded_by` is a typed frontmatter relation. A node carrying it is an
  ALIAS whose claim of record lives at the pointer, a slug or a
  `<root>/<slug>` path: `atpx status`, `atpx graph`, the completeness and
  claim lints and the generated index all read the node of record and count
  the claim exactly once, a wikilink to the superseded slug resolves to the
  node of record so a dependency written before a migration still lands where
  it meant to, and `atpx note` on a stub is refused naming the canonical.
  The pointer is linted like any other relation, so a supersession pointing at
  nothing is a dangling link, and `doctor` reports the alias table under
  `superseded_nodes` without failing on it.
- `## Ledger` is accepted wherever `## Evidence` is, one reader with two
  aliases, so a node that calls its readings a ledger takes a note exactly
  like one that calls them evidence.
- `INDEX.json` carries the blueprints root each node came from beside its
  slug, state and claim, so a downstream renderer can take it as its roster.
- A `[vocabulary]` table declares the settled words a workspace is willing to
  settle on, each with the letter and terminal markup a progress line prints
  and the stance it takes on the prediction behind it, `confirms`, `refutes`,
  or a defaulted `neither`. atpx owns the declaration because atpx owns the
  lifecycle, and `atpx settle` refuses a settled status the table leaves out.
  A trial harness reads the same table out of the same manifest to print its
  progress line and validate the settled word a receipt stores, so the two
  vocabularies cannot drift; neither side imports the other.
- A `[universe]` table declares `root`, `evidence`, `axes`, `probed` and
  `samples`, where a workspace's trials live and what scopes their coverage.
  Schema only: atpx never executes a trial, and a hermetic executor reads the
  same declaration without either side importing the other.
- `judgments/<node>.ndjson` records counsel standing as data beside the prose,
  one appended line per ruling carrying `referee`, `date`, `ruling` (FATAL,
  GAP, MINOR or NONE), the `claim` attacked, the `prose` file it summarizes
  and the ladder `rung`. `atpx rule` appends one, with the same verb for a
  model lane and a human referee, and `doctor`'s `unjudged_sketches` reads it
  instead of regexing prose, falling back to the frontmatter pointers for a
  node that has none. So an external review becomes evidence in the graph
  while the reasoning stays prose.
- `Stream` factors the append-only NDJSON discipline the evidence ledger and
  the ruling ledger share: one record per line, an append that never rewrites,
  a lock a caller can widen, and a read that warns past what it cannot decode.

### Changed

- The evidence ledger is append-only NDJSON at `evidence/<hostname>.ndjson`,
  one certificate per line, written by opening the file for append and never
  by rewriting it. A killed process, a full disk, or one torn record now costs
  exactly the record it was writing. A record that does not decode is skipped
  with a `TornLedger` warning naming its file and line rather than raised, so
  one bad record can no longer make a whole host's ledger read as absent to
  `newest`, to a settle gate, or to `doctor`. The pre-stream format, one
  whole-file JSON array at `evidence/<hostname>.json`, is read transparently
  beside the stream and never rewritten, so history stays byte for byte what
  was recorded. Records split on the newline alone, never on `str.splitlines`,
  which also breaks at NEL and the paragraph separators that JSON does not
  escape and that would otherwise tear a certificate in half.
- A claim output too large for a certificate is now written whole to
  `evidence/outputs/<digest>.txt` and the certificate keeps whole lines from
  each end around a marker naming that file, beside an `elided` record with
  the character count, the digest, and the path. Elision lands only on a line
  boundary, so a stored output is either the entire text or an explicit
  pointer to it and never a JSON document cut through the middle. `Capture`
  replaces the `payload` function and covers the ordinary run, the rigor
  lanes, and the Lean audit alike.
- `atpx index` writes and `doctor` reads the INDEX pair under the same file
  lock the evidence store beside them already took, so two sessions
  regenerating at once, or one checking currency while the other writes, can
  no longer leave one artifact from each generation and turn a cosmetic race
  into a red workspace.

## 0.0.4 - 2026-08-25

### Added

- The node frontmatter contract. `node.md` frontmatter now parses into a typed
  `Frontmatter` model in the graph layer, with `depends` (the slugs a statement
  leans on), `serves` (the papers or experiments a node feeds), `seeds` (the
  seed bases allocated to the node), and `judgments` (the ruling files a
  sketched status rests on), each read from bracketed or bare comma lists. The
  parse is backfill-tolerant: a missing block or a malformed field lands in
  `problems` for `doctor` to report and never crashes a reader. A node's
  `kind` now derives a `Category`, and `probe-pool` directories are exempt
  from the claim lints while `convention` nodes are held to them.
- `atpx index` regenerates two artifacts from node state alone: the INDEX
  markdown with a generated node table, and a blueprint-shaped graph JSON
  beside it (nodes with slug, state, and one-line claim; edges from
  `depends`). Hand-authored prose is never deleted; the first generation over
  a hand-written index moves its whole body under a clearly marked manual
  section, which every later regeneration preserves verbatim.
- `doctor` grew completeness verdicts, all gating the exit code: frontmatter
  that does not parse, a claim node without a statement of record or an
  explicit refutation condition, a sketched node whose linked judgment is
  missing or names no attacking rung, a statement that drifted from its
  judgment snapshot (the check the backfill ran by hand), and an index a
  regeneration would change. Certificates with no pre-registration design
  file beside them report as untidiness without failing the gate.
- `atpx note <slug> <text>`, the append-only evidence verb. One dated UTC
  bullet lands at the end of the `## Evidence` section, and a node without
  that section is refused rather than restructured, so nothing above the
  evidence heading can ever be touched.
- `atpx design <slug>` scaffolds an AsPredicted-shaped pre-registration file
  in the node directory (hypothesis, observable, conditions, decision rule,
  seed base, cost estimate, exploratory declaration). The seed base is
  allocated fresh from the workspace-wide frontmatter registry and recorded
  in the node's `seeds` list in the same call.
- Judgments record the attacking rung first-class. `Referral` carries `rung`
  and `boss`, and every draft judgment the refuter writes names its strongest
  attacking rung and the lane that fought it, the line the sketch gate's
  doctor check reads.

## 0.0.3 - 2026-08-25

### Added

- `atpx.support.clock`, the one UTC clock every stamp reads. Certificate
  timestamps, judgment snapshots and background submission records now render
  as ISO 8601 UTC with an explicit `Z` suffix, submission log and record
  filenames carry the same `Z`-suffixed compact stamp, and journal lines,
  scaffolded nodes and draft judgment filenames date themselves from the same
  clock. No stamp in the package reads local time anymore.
- The counsel defense gate grew teeth. A defense probe now counts only when
  its `case=<name>` lines re-measure every quantity the attack's output
  named and when no `except` handler in its source can reach `sys.exit`
  with a status that could be zero, so a probe that measures beside the
  attack or that launders its own failure into an exit 0 is refused with
  the exact violation. The hollow defense the units-convention round
  accepted is the regression test.
- `--project <path>` on every CLI invocation, pinning one run to a named
  workspace (its root or any directory inside it). The answer to a monorepo
  task runner that changes into the repository root before running anything,
  where the upward walk would otherwise always land on the top workspace.
- `lab`, the verb for a claim whose verification is an experiment rather than
  a script. The command prints one `{"trial_receipt": {...}}` JSON line per
  trial, carrying its content-addressed `run_id`, its outcome, the `producer`
  that stamped it, and every declared gate's verdict; the gate demands at
  least one line and every trial through its gates, stamps rigor `lab`, and
  keeps the receipts in the certificate's witness list. The key names the
  shape rather than a framework, so any experiment harness that prints it is
  audited the same way. Re-verification is the same verb with no command,
  replaying what the manifest recorded. Rigor `lab` is evidence with an
  identity, not a proof, and `settle validated` keeps refusing it.
- `[workspace] runner`, a command prefix every claim, background check, and
  Lean build runs behind (`uv run --`, say). Empty by default, so a plain
  checkout runs claims on the interpreter already around atpx.
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

### Fixed

- The release gate is green again. The OpenRouter call site types its
  messages, response format and extra body against the openai 2.54 client,
  a manifest ladder rung validates through pydantic instead of unpacking an
  untyped table, the mkdocs hook imports its config type only for type
  checking, and the docs tests resolve `docs.hooks` from the repository
  root under `uv run pytest` as well.

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

## 0.0.2 - 2026-06-16

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
