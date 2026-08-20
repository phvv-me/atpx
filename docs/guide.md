# Guide

## Install

```sh
pip install atpx
```

For a persistent CLI, install it as a tool rather than into a project
environment:

```sh
uv tool install atpx   # or: pipx install atpx
```

## Finding the workspace

A workspace root is any directory whose `atpx.toml` declares a `[workspace]`
table pointing at the blueprints directory. Discovery walks up from the
current directory, so any subdirectory of a project resolves to the same
root.

In a monorepo the walk is not enough on its own, because the task runner that
provides the environment usually changes into the repository root before
running anything, and every verb would then resolve to whatever workspace
sits there. Two things fix that. `--project <path>` pins one invocation to a
named workspace, its root or any directory inside it. And `doctor` needs no
pin at all, since it answers for the resolved workspace and every workspace
nested under it in one pass. `ATPX_ROOT` still pins every invocation through
the environment, and an explicit `root` argument in Python wins over both.

Describing the tool opens no workspace, so `atpx --help` and `atpx --version`
answer from any directory at all.

## Choosing how claims run

A claim command in a node's manifest is a bare command. Which environment it
lands in is one line in the workspace manifest, naming whatever environment
tool that workspace already uses:

```toml
[workspace]
blueprints = "research/math"
runner = "uv run --"
```

Every claim, background check, and Lean build then runs behind that prefix.
The default is empty, which runs the command exactly as written on whatever
interpreter is already active. `{dir}` in a claim command expands to the node
directory's full path, so a claim keeps working whatever directory the
launcher decides to run it from.

## Scaffolding a node

```sh
atpx open bijectivity-e8 --kind theorem
```

`open` writes `node.md` with the claim's frontmatter and section
skeleton, a `probes/` directory, and `specs/claim-spec.md` — the feasibility
checklist a claim should answer before anyone spends compute on it.

## Running a claim

```sh
atpx run bijectivity-e8 check-1 python probes/check.py
```

```text
{
  "claim": "bijectivity-e8/check-1",
  "result": {"ok": true, "cases": 4096},
  "engine": "atpx",
  "hostname": "gpu-node-3",
  "git_rev": "a1b2c3d",
  "exit_status": 0,
  "rigor": "sampled"
}
```

The command is a leading-hyphen var-positional, so flags after it pass
through verbatim — `atpx run demo probe python -c "print(1)"` works exactly
as typed. Put `--seed` and `--timeout` *before* the command tokens, and
separate a command that itself takes `--seed`-shaped flags with `--`.

Re-running a registered claim only needs its name:

```sh
atpx check bijectivity-e8 check-1
atpx check bijectivity-e8 check-1 --background   # detach it; checks bijectivity-e8 reports later
```

## Reading state back

```sh
atpx status    # nodes grouped by status; malformed ones under "invalid"
atpx graph     # unsettled nodes whose dependencies are all settled
atpx doctor    # what needs repair — reported, never mutated
```

`doctor` is the lint, and it returns a certificate rather than a bare
report: its payload is keyed by workspace path (`.` for the resolved one),
and it exits nonzero when a finding contradicts what a workspace itself
asserts. Those breakages are an invalid status, a wikilink pointing at
nothing, and a claim whose newest evidence failed, never ran, or was stamped
before the last commit that changed the node it supports. Stray files under
`evidence/`, a blueprint with no manifest, and a blueprint with no `node.md`
report as untidiness and never fail the gate, since capture-first work is
allowed to be messy.

So `atpx doctor` from the top of a monorepo is the one command that answers
whether every mathematical idea it holds is still settled, and its exit code
is usable directly in CI.

## Verifying a claim that is an experiment

When a claim's verification is a study rather than a script, `lab` runs it
and gates on what the study printed:

```sh
atpx lab scale-invariance sigma-sweep -- python probes/study.py
atpx lab scale-invariance sigma-sweep          # re-verify, replaying the registered command
```

The contract is one JSON line per trial, `{"trial_receipt": {...}}`, carrying
the trial's content-addressed `run_id`, its `outcome`, the `producer` that
stamped it, and every declared gate's verdict. It names the shape rather than
any one framework, so any harness that prints that line is audited here. The
gate demands at least one line and every trial through its gates, then stamps
rigor `lab` and keeps each receipt in the certificate's witness list, so the
evidence names the run that produced it.
A trial a gate withheld fails the gate here, since a withheld trial is not a
checked claim, and the violation line carries the study's own reason.

Rigor `lab` is evidence with an identity, not a proof: the `validated` settle
gate keeps refusing it exactly as it refuses `sampled`.

## Gating on rigor

`ball` and `smt` run a command exactly like `run`, then audit its stdout
against a tolerance or a solver verdict (see [Concepts](concepts.md)):

```sh
atpx ball bijectivity-e8 check-1 -- python probes/enclosure.py
atpx smt bijectivity-e8 check-1 -- python probes/encoding.py
```

A gated-out run keeps `rigor: sampled` and forces a nonzero exit, so it can
never feed the `validated` settle gate by accident.

## Settling

```sh
atpx settle bijectivity-e8 sketched --judgment specs/ruling.md
atpx settle bijectivity-e8 validated --certificate check-1
```

Every settle call returns the journal line it wrote, so a script can confirm
the move without a second read.

## Recall

```sh
atpx recall "Leech lattice"
```

`recall` fans one query out to every search-capable engine — OEIS, loogle,
arXiv, zbMATH — and returns one certificate listing hits per source.
An empty result is not a failure: zbMATH answers "nothing found" with a
plain 404, and loogle reports a query it cannot parse through its own
`error` field. Genuine transport failures still land under `errors` and the
certificate exits nonzero, so a partial recall is never mistaken for a
complete one.

## Next

[Workflow](workflow.md) covers the parts of atpx built specifically for an
agentic prove–refute loop: briefs, judgments, and the counsel lanes.
