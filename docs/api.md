# API

This page is the stable public API map for atpx.

## Public Surface

```python
import atpx

ws = atpx.workspace()          # discover the workspace root from the cwd
```

Every verb below is a `Workspace` method and an `atpx` CLI command, and every
one returns an `atpx.Certificate`, never a naked result. The verbs marked
async are `async def`, awaited directly in async code; the CLI runs them on
its own event loop through cyclopts, and synchronous scripts block on them
through the `ws.sync` facade (`ws.sync.check(...)`, `ws.sync.verify(...)`,
`ws.sync.recall(...)`, `ws.sync.connect(...)`).

| verb | mode | what it certifies |
|---|---|---|
| `check(slug, claim, background=False)` | async | one blueprint claim run, persisted to the evidence ledger; `background=True` detaches it |
| `checks(slug)` | sync | background submissions, pending or landed (plain list, read only) |
| `verify(slug=None)` | async | the freshness sweep, fresh, failed, or skipped per claim plus stale flags |
| `brief(slug)` | sync | the full agent context bundle for one node (markdown, read only) |
| `judge_brief(slug)` | sync | what changed since the last refuter judgment (markdown, read only) |
| `status()` | sync | nodes grouped by zettel status (plain dict, read only) |
| `graph()` | sync | the dependency frontier (plain list, read only) |
| `recall(query, sources=None)` | async | federated search hits per source |
| `connect(slug)` | async | OEIS matches for integer runs in the node's evidence |
| `strategies()` | sync | close-rates by strategy tag (markdown table, read only) |
| `lean_candidates()` | sync | sketched nodes ranked for formalization (markdown table, read only) |
| `log(zettel, role, tag, message, status=None)` | sync | one role-gated journal line |
| `index(write=False)` | sync | the regenerated results index note |
| `compute(engine, operation, payload)` | sync | one typed engine operation |
| `prove(goal, syntax=None)` | sync | which ATP engine closed the goal |
| `cross_check(operation, payload, engines=None)` | sync | agreement of independent engines |

The supporting types are `atpx.Certificate`, `atpx.Blueprint`, `atpx.Claim`,
`atpx.EvidenceStore`, `atpx.Vault`, `atpx.Zettel`, `atpx.Role`,
`atpx.Status`, `atpx.Capability`, `atpx.Engine`, and the errors
`atpx.RoleError` and `atpx.SearchError`. The refuter's probe library lives in
`atpx.adversarial` as `seed_sensitivity`, `boundary_ties`, `precision_tilt`,
and `rederive`. Every self-reference derives from `atpx.NAME` and
`atpx.CONFIG`, so renaming the package folder renames the tool, its CLI, and
its manifest files.

On the command line, arguments are plain shell tokens, so a multi-word query
is just `atpx recall "Leech lattice"`, and command names keep their
underscores (`cross_check`, `judge_brief`, `lean_candidates`). Certificates
print as JSON, markdown verbs print their text as-is.

```sh
atpx --help
```
