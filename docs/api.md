# API

This page is the stable public API map for atpx.

## Public Surface

```python
import atpx

ws = atpx.workspace()          # discover the workspace root from the cwd
```

Every verb below is a `Workspace` method and an `atpx` CLI command, and every
one returns an `atpx.Certificate`, never a naked result.

| verb | what it certifies |
|---|---|
| `check(slug, claim, background=False)` | one blueprint claim run, persisted to the evidence ledger; `background=True` detaches it |
| `checks(slug)` | background submissions, pending or landed (plain list, read only) |
| `verify(slug=None)` | the freshness sweep, fresh, failed, or skipped per claim plus stale flags |
| `brief(slug)` | the full agent context bundle for one node (markdown, read only) |
| `judge_brief(slug)` | what changed since the last refuter judgment (markdown, read only) |
| `status()` | nodes grouped by zettel status (plain dict, read only) |
| `graph()` | the dependency frontier (plain list, read only) |
| `recall(query, sources=None)` | federated search hits per source |
| `connect(slug)` | OEIS matches for integer runs in the node's evidence |
| `strategies()` | close-rates by strategy tag (markdown table, read only) |
| `lean_candidates()` | sketched nodes ranked for formalization (markdown table, read only) |
| `log(zettel, role, tag, message, status=None)` | one role-gated journal line |
| `index(write=False)` | the regenerated results index note |
| `compute(engine, operation, payload)` | one typed engine operation |
| `prove(goal, syntax=None)` | which ATP engine closed the goal |
| `cross_check(operation, payload, engines=None)` | agreement of independent engines |

The supporting types are `atpx.Certificate`, `atpx.Blueprint`, `atpx.Claim`,
`atpx.EvidenceStore`, `atpx.Vault`, `atpx.Zettel`, `atpx.Role`,
`atpx.Status`, `atpx.Capability`, `atpx.Engine`, and the errors
`atpx.RoleError` and `atpx.SearchError`. The refuter's probe library lives in
`atpx.adversarial` as `seed_sensitivity`, `boundary_ties`, `precision_tilt`,
and `rederive`. Every self-reference derives from `atpx.NAME` and
`atpx.CONFIG`, so renaming the package folder renames the tool, its CLI, and
its manifest files.

```sh
atpx --help
```
