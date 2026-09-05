# API

This page is the stable public API map for atpx. For what the fields and
gates mean, see [Concepts](concepts.md); for a walkthrough, see
[Guide](guide.md) and [Workflow](workflow.md).

## Public Surface

```python
import atpx

ws = atpx.workspace()  # ATPX_ROOT when set, else discovered from the cwd
ws = atpx.workspace("research/thoughtlens")  # or any directory inside that workspace
```

Every verb below is a `Workspace` method and an `atpx` CLI command. The verbs
marked async are `async def`, awaited directly in async code; the CLI runs
them on its own event loop through cyclopts, and synchronous scripts block on
them through the `ws.sync` facade (`ws.sync.run(...)`, `ws.sync.check(...)`,
`ws.sync.verify(...)`, `ws.sync.recall(...)`, `ws.sync.lean(...)`, `ws.sync.lab(...)`).

| verb | mode | what it returns |
|---|---|---|
| `run(slug, claim, *argv, seed=None, timeout=None)` | async | capture-first: any command as a claim, stamped, persisted, auto-registered |
| `check(slug, claim, seed=None, background=False)` | async | one blueprint claim run, persisted; `background=True` detaches it |
| `checks(slug)` | sync | background submissions, pending or landed (plain list, read only) |
| `verify(slug=None)` | async | the freshness sweep, fresh, failed, or skipped per claim plus stale flags |
| `lab(slug, claim, *argv, seed=None, timeout=None)` | async | a study run gated on its printed trial receipts, rigor `lab` |
| `brief(slug)` | sync | the full agent context bundle for one node (markdown, read only) |
| `judge_brief(slug)` | sync | what changed since the last refuter judgment (markdown, read only) |
| `status()` | sync | nodes grouped by status (plain dict, read only) |
| `graph()` | sync | the dependency frontier (plain list, read only) |
| `doctor()` | sync | what needs repair here and in every nested workspace, as one certificate that exits nonzero on a breakage |
| `settle(slug, status, message="", judgment=None, counterexample=None, lean=None)` | sync | one evidence-gated status move, returning the journal line |
| `lean(slug, target=None, timeout=3600)` | async | a Lean build ingested as an audited certificate |
| `fit(data, target, slug=None, seed=0, niterations=40, unary=None, binary=None, tail=None, driver=None, features=None)` | sync | the PySR Pareto front with holdout scores, honest when dormant |
| `recall(query, sources=None)` | async | federated search hits per source |
| `log(slug, who, tag, message)` | sync | one appended journal line, validated to round-trip |
| `note(slug, text, tag="note")` | sync | one dated evidence bullet appended below `## Evidence`, nothing above it ever touched |
| `design(slug)` | sync | a scaffolded `design-<date>.md` pre-registration with a fresh seed base recorded in the node frontmatter |
| `adopt(slug, source)` | sync | a markdown note copied into `blueprints/<slug>/node.md`, source untouched |
| `index()` | sync | the regenerated index note and the graph JSON beside it, hand-written prose preserved under the manual section |

Under the facade, each verb delegates to one service module: `running`
(capture-first execution and the freshness sweep), `settlement` (the evidence
gates as a registry, one class per gated status), `leaning` (the Lean build
audit), `discovery` (the fit lane behind a `SymbolicRegressor` seam),
`recalling` (the federated search fan-out), and `doctoring` (the lint).

The supporting types are `atpx.Certificate`, `atpx.Blueprint`, `atpx.Claim`,
`atpx.EvidenceStore`, `atpx.NodeStore`, `atpx.Node`, `atpx.Status`,
`atpx.Frontmatter`, `atpx.Category`, `atpx.Capability`, `atpx.Engine`, and
the errors `atpx.SettleError` and `atpx.SearchError`. The refuter's probe library lives in `atpx.adversarial`
as `seed_sensitivity`, `boundary_ties`, `precision_tilt`, and `rederive`.
Every self-reference derives from `atpx.NAME` and `atpx.CONFIG`, so renaming
the package folder renames the tool, its CLI, its manifest files, and its
`ATPX_ROOT` override variable.

On the command line, arguments are plain shell tokens, so a multi-word query
is just `atpx recall "Leech lattice"`, and command names keep their
underscores (`judge_brief`). Certificates print as JSON, markdown verbs print
their text as-is. List-valued fit flags accept repeats or comma-joined tokens
(`--unary exp,log`, `--binary "+,-,*"`), and a bare `-` needs the equals form
(`--binary=-`).

```sh
atpx --help
```
