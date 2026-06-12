# Changelog

All notable changes to atpx are documented here.

The format follows Keep a Changelog, and releases are cut from the version in `pyproject.toml`.

## Unreleased

### Added

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

- Renamed the package from prova to atpx (Automatic Theorem Prover
  Accelerated). The name genericity work means the rename is one folder move,
  the CLI is now `atpx`, the workspace marker and blueprint manifests are
  `atpx.toml`, and new certificates stamp `atpx` as the engine. Historical
  evidence ledger entries stamped by `prova` stay untouched.
- `recall` sources, `cross_check` engines, and the `verify` sweep run
  concurrently on `ThreadPoolExecutor`; free-threaded CPython 3.14t was
  evaluated and documented in the README (installable except for cvc5, which
  ships no `cp314t` wheel; standard 3.14 stays the default).
