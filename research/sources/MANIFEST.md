# Source manifest

Snapshots taken 2026-10-22. The live page remains authoritative.

| Snapshot | Upstream | Commit | Files | Local path |
| --- | --- | --- | --- | --- |
| DuckDB 2.0 manual | [duckdb/duckdb-web](https://github.com/duckdb/duckdb-web) | `37408677c0753c0b3607f8b77540df7f3096be95` | 461 | `sources/duckdb-2.0/` |
| DuckLake stable manual | [duckdb/ducklake-web](https://github.com/duckdb/ducklake-web) | `1b74f10e93a3905e247c12f30b8882ca683db8f4` | 76 | `sources/ducklake-stable/` |

Recreate the snapshots with `python3 scripts/fetch-docs.py`. The script reads the pinned commits above and downloads the Markdown only. The snapshots are excluded from git because they are bulk upstream content; the notes that cite them are tracked.

Each local path mirrors its URL path. `sources/duckdb-2.0/clients/cli/agent_mode.md` is `https://duckdb.org/docs/2.0/clients/cli/agent_mode.html`. `sources/ducklake-stable/duckdb/usage/connecting.md` is `https://ducklake.select/docs/stable/duckdb/usage/connecting.html`.

Both repositories are MIT licensed, copyright 2018-2025 Stichting DuckDB Foundation. The snapshot is a reference copy for research. It is not a second manual and is not shipped as skill content.

Pages read live because they are not in the snapshots:

- `https://duckdb.org/2026/10/21/announcing-duckdb-200.html`
- `https://duckdb.org/2026/08/17/duckdb-20-highlights.html`
- `https://duckdb.org/release_calendar.html`
- `https://github.com/duckdb/duckdb/releases/tag/v2.0.0`
- `https://ducklake.select/2026/10/21/ducklake-11/`
- `https://docs.overturemaps.org/release-calendar/`
- `https://docs.overturemaps.org/getting-data/duckdb/`
- `https://stac.overturemaps.org/catalog.json`
