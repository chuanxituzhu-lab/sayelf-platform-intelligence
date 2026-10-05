# Public Release Review

Review date: 2026-10-05

Destination: `chuanxituzhu-lab/sayelf-platform-intelligence` (public GitHub repository)
Release target: `v0.9.1`
Scope: source code, synthetic tests, public-facing bilingual documentation, the user-supplied logo explicitly requested for this public repository, and the repository's existing MIT license.

Every file included in this commit is classified **Public**. The per-file inventory below is the complete release set. Source modules contain application logic and configured public official-source URLs; tests contain synthetic fixtures. The public-facing README states the current evidence and platform-review limits.

Machine-specific filesystem defaults for the legacy-radar reference were removed; its optional web action now requires an explicit `SAYELF_ALGO_RADAR_PATH`. No local database, official-page body snapshot, private review, internal build decision, operational report, screenshot, Agent Ops inbox, credential, or local filesystem path is included. `.gitignore` excludes runtime state and common local-only files from future commits.

## Included files — Public

- `.gitignore`
- `LICENSE` (existing repository MIT license)
- `README.md`
- `PUBLIC-RELEASE-REVIEW.md`
- `platform_intelligence/__init__.py`
- `platform_intelligence/adapters.py`
- `platform_intelligence/briefs.py`
- `platform_intelligence/catalog.py`
- `platform_intelligence/cli.py`
- `platform_intelligence/contracts.py`
- `platform_intelligence/engine.py`
- `platform_intelligence/integration.py`
- `platform_intelligence/legacy_radar.py`
- `platform_intelligence/static/brief.js`
- `platform_intelligence/static/logo.png` (user-supplied brand image, explicitly requested for this public repository)
- `platform_intelligence/store.py`
- `platform_intelligence/web.py`
- `tests/test_acquisition.py`
- `tests/test_briefs.py`
- `tests/test_core.py`
- `tests/test_legacy_radar.py`
- `tests/test_multiplatform.py`
- `tests/test_web.py`

## Excluded local/internal files

The source project's `data/`, `reports/`, `reviews/`, `scripts/`, generated package archives, launch wrapper, release manifest, build decision, shared internal contracts, GitHub research artifacts, and local screenshots are excluded. The release repository will contain only the files enumerated above and its pre-existing license.
