# Versions

Frozen snapshots of each autoresearch run. Each folder captures:

- `meta.yaml` — structured metadata (asset, dates, counts, peak metrics, known limitations)
- `results.tsv` — journal snapshot at the moment the run was declared done
- `strategy.final.py` — the winning strategy file
- `retrospective.md` — full post-mortem + interpretation

The corresponding git state is preserved via a tag (e.g. `v0.1.0` → peak commit of that run). The original research branch is kept around too (e.g. `autoresearch/apr22`).

Versioning is loose — use semver spirit, not letter:
- **Major** (1.0, 2.0): significant harness / methodology change (new oracle, new loop architecture)
- **Minor** (0.2, 0.3): new asset, new timerange, new program.md, or otherwise distinct research question
- **Patch** (0.1.1, 0.1.2): minor reruns of the same setup (re-seed, small tweaks, reproducibility checks)

## Rules

**Archives are immutable.** Once a version folder is merged to master, do not
modify files inside `versions/<version>/`. If something in a past archive is
wrong or needs extension, write `versions/<version>/errata.md` or bump to a
patch version. The history is load-bearing — the whole point of this folder
is that we can read an archived retrospective a year from now and trust it
reflects what we thought at the time.

**Scaffold PRs and version-archive PRs are separate.** A PR that adds a new
`versions/<version>/` folder should touch nothing outside `versions/` (+
`.gitignore` if needed). A PR that changes `prepare.py`, `run.py`,
`config.json`, `program.md`, etc. should not touch `versions/`. This keeps
review surfaces distinct: scaffold PRs get real review, version PRs are
rubber-stamp.

## Index

| Version | Date | Asset | Experiments | Peak Sharpe | Headline |
|---|---|---|---|---|---|
| [0.1.0](0.1.0/) | 2026-04-22 | BTC/USDT + ETH/USDT @ 1h | 99 | 1.44 (true edge: 0.19) | Pattern validated; agent self-reversed Goodhart exploits |
