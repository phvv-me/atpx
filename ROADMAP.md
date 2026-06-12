# Roadmap

Where atpx is headed. This document tracks what works today and what
each milestone needs. It is a direction, not a contract, so order and scope can shift.

## Today (0.0.x)

- [x] Initial public scaffolding with CI, docs, and a version-driven release pipeline.
- [x] Stage 1, evidence and bookkeeping plus exact engines. The certificate
      contract, per-host append-only evidence ledgers, role-gated status
      transitions, the dependency frontier, index regeneration, and the engine
      registry with cross-engine certification.
- [x] Stage 2, recall. The `recall` verb federates one query across read-only
      `search` engines, vault (qmd BM25), OEIS, loogle, arXiv, and zbMATH Open,
      into a single certificate of hits per source with per-source error
      accounting. Blueprint claims grew an optional `requires` marker, so
      GPU-only evidence skips gracefully on hosts without CUDA, and every
      blueprint under the workspace now carries an `atpx.toml` claim map.
- [x] Stage 3a, loop mechanics. Everything ten prove-and-refute cycles showed
      was friction. `brief` bundles the full agent context in one command,
      `judge_brief` diffs the node and its evidence since the last refuter
      ruling, `check --background` detaches runs with `checks` tracking pending
      or landed, `verify` sweeps freshness and flags git-rev-stale
      certificates, `strategies` tabulates close-rates per strategy tag,
      `connect` fingerprints evidence numerics against the OEIS,
      `lean_candidates` ranks sketched nodes for formalization, and
      `atpx.adversarial` ships the refuter's reusable probes. Name genericity
      landed too, every self-reference derives from `NAME = __name__`, and the
      parallel surfaces moved to `ThreadPoolExecutor` with free-threaded 3.14t
      evaluated and documented in the README (blocked by cvc5 wheels only).

## Stage 3b, the Lean bridge

A scriptable `atpx lean` surface. Search, proof skeletons generated from a
zettel and its dependencies, statement back-translation recorded alongside every
build, and staleness hashing. Lean enters as one more engine whose closing
certificate is the only path to `verified`. Deeper connect follows on top,
invariant fingerprinting beyond integer runs and long-running program ledgers,
always new capabilities in the engine vocabulary, never edits to the
certificate contract.

## v0.1.0

Make atpx complete and trustworthy at its core.

- [ ] **Stable public surface.** Define and document the names users should import or call.
- [ ] **Tests at full coverage** across the supported platforms and Python versions.
- [ ] **Friendlier failures.** Clear messages when something is missing or misconfigured.
- [ ] **LLM-friendly docs.** Keep `llms.txt` and `llms-full.txt` building in CI and linked from the README.
- [ ] **Further i18n.** Keep every docs page in sync across the supported locales.

## v1.0.0

Freeze the surface and make atpx safe to depend on.

- [ ] **Stable API.** Semantic versioning with a written migration and deprecation policy.
- [ ] **Full tested parity** on every supported platform.
- [ ] **Compatibility guarantees.** A 1.x promise for the public API and CLI.
- [ ] **Complete reference docs** in every supported language.
