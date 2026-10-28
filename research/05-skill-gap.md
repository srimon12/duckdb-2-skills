# DuckDB skills gap analysis (upstream vs 2.0.0)

Date checked: 2026-10-22. Upstream tree: `duckdb-skills-upstream` (plugin README, nine `SKILL.md` files, spatial reference notes, `install-duckdb/eval.sh`). Local CLI used for probes: `v2.0.0 (Cyanoptera) d54cbbe3df`. Docs cited are `https://duckdb.org/docs/2.0/...` unless noted.

This is not a fork plan. No existing skill should be copied in as a file. Reuse only the ideas named below, and attribute them (see License).

## License

`duckdb-skills-upstream/LICENSE` is the **MIT License**. Copyright **2018-2025 Stichting DuckDB Foundation**. MIT requires the copyright notice and the permission notice in all copies or substantial portions of the software. A new repo that reuses structure or wording (state file, friendly-SQL list, ad-hoc sandbox settings, docs FTS query, Overture bbox-first procedure) must carry that notice, not just a link. See the README section at the end.

The upstream README is a Claude Code marketplace plugin (`/plugin marketplace add duckdb/duckdb-skills`, slash commands `/duckdb-skills:<name>`). It does not mention `convert-file`, `s3-explore`, or `spatial`, which are in the tree. `install-duckdb/eval.sh` only runs under `claude --print`. None of that packaging belongs in a Grok / Claude Code / Codex skill repo.

## 2.0 facts confirmed on duckdb.org

Release post: [Announcing DuckDB 2.0.0 LTS “Cinnamon Teal”](https://duckdb.org/2026/10/21/announcing-duckdb-200.html) (2026-10-21). Migration: [Migrating to DuckDB 2.0](https://duckdb.org/docs/2.0/operations_manual/migration.html). `https://duckdb.org/data/latest_stable_version.txt` returned `2.0.0` the same day.

| Fact | What the docs actually say | Why it hits the skills |
|---|---|---|
| Agent mode | Auto when a known agent env var is set, stdout is not a tty, **and no output-mode flag** (`-csv`, `-json`, …) was passed. Force with `-agent` / `-no-agent`. Markdown tables, truncation footer, JSON errors on stderr, cost estimate when a scan reads more than 1,000,000 rows. [Agent mode](https://duckdb.org/docs/2.0/clients/cli/agent_mode.html). | Every skill invokes `duckdb -csv` and/or `duckdb -c`. `-csv` **turns agent mode off**. |
| Storage | Files **created** by 2.0.0 use storage version 69 (`v2.0.0`). DuckDB **before 2.0 cannot read them**. 2.0 **can** read and write older files, and those files **keep** their old storage version. Opt out with `-storage-version`, `storage_compatibility_version`, or `ATTACH ... STORAGE_VERSION`. Move a file forward with `EXPORT DATABASE` / `IMPORT DATABASE` (or `COPY FROM DATABASE`). | `attach-db` opens or creates a file and never mentions this. A new empty file created by the skill is unreadable by 1.4/1.5. |
| Lambdas | `x -> x + 1` is disabled by default. Use `lambda x : x + 1`. Temporary bridge: `SET lambda_syntax = 'enable_single_arrow'`. Removed in 2.1. | Friendly-SQL blurb says “lambdas” with no syntax. Probed: the arrow form errors; the `lambda` form returns `[2, 3, 4]`. |
| PEG parser | Default. Designed to be compatible. Fallback is an extension, not a built-in: `INSTALL AND LOAD legacy_parser; SET enable_legacy_parser = true;`. | No skill mentions it. Do not set it preemptively. |
| Quack + `CONNECT` | `CALL quack_serve(token => ...)`, `ATTACH 'quack:host' AS qk (TOKEN ...)`, `CONNECT qk`, `DISCONNECT`. CLI: `duckdb -serve`, `duckdb -connect`. Server binds localhost unless a reverse proxy (or the testing-only `allow_other_hostname`) is used. `CONNECT` also targets Postgres and MySQL, with remote pushdown. | No skill. |
| `VARIANT` | First-class, shredded in storage and Parquet. `variant_type`, `variant_keys`, `variant_extract`, and the rest of `variant_*`. JSON is still text; cast with `::JSON::VARIANT`. | Readers still treat JSON as `read_json_auto` only. |
| Async I/O | Automatic for **Parquet**, **uncompressed, seekable UTF-8 CSV**, and **native DuckDB storage**. Not JSON. Knobs (`async_threads`, `read_ahead_depth`) are advanced. [I/O](https://duckdb.org/docs/2.0/data/io.html). | Remote Parquet advice never says the speedup is already on. |
| Triggers | `CREATE TRIGGER` with `BEFORE`/`AFTER`, row/statement, `REFERENCING OLD/NEW TABLE`, `DROP TRIGGER`. **Not yet:** `BEFORE ... FOR EACH ROW` and `UPDATE ... FOR EACH ROW`. | No skill. Too narrow and too limited to be its own skill. |
| DuckLake 1.1 | Shipped with 2.0. Extension still reads and writes **1.0 catalogs**. 1.1 spec features need a migration. DuckLake 1.1 **requires DuckDB 2.0.0+**. [What’s New in DuckLake 1.1](https://ducklake.select/2026/10/21/ducklake-11/), [DuckLake docs](https://ducklake.select/docs/stable/). | No skill. `attach-db` would treat a `.ducklake` path as a native file. |
| Extension repositories | `INSTALL name` and `INSTALL name FROM community` (or `core`) still work. `UPDATE EXTENSIONS` still works (probed). New `CREATE EXTENSION REPOSITORY` is **explicitly WIP** and “its syntax may change”. | `install-duckdb` teaches the stable `name@repo` form, which is fine, and does not warn about the WIP statement. |
| Other breaks the skills never mention | Integer `//` and `%` by zero now error (`TRY(...)` or `SET error_on_division_by_zero = false`). S3 **URL** parameters (`s3://bucket/key?s3_access_key_id=...`) are off by default; the query string is part of the key. `preserve_identifier_case` is now a string. ICU is no longer in the core build; time zones still work via the `icu` extension. Community extensions are **not built for `osx_amd64`**; 2.1 drops that platform. | Lakehouse and extensions skills must own the S3-key and community-platform notes. Do not scatter them. |

Local probes that matter below: a new database’s `duckdb_databases().tags` was `{storage_version=v2.0.0+}`. `storage_compatibility_version` defaulted to `latest`. CLI `-help` text says `-storage-version` default `'v0.10.0'`; that string is **not** what a new file used. Do not teach the help-text default.

## Verdicts

No skill is a straight keep. Each one is a Claude Code procedure (`allowed-tools: Bash`, `$0`, `/duckdb-skills:...`) written against the 1.x CLI. The replacement set further down is smaller on purpose.

### `attach-db` — rewrite

Becomes `session`. The job (attach a local database, remember it, show the schema) is still real. The file is unsafe on 2.0 because it creates and opens database files with no storage check.

Wrong or incomplete:

- No version gate and no storage warning. Step 1: “If yes, continue” when the file does not exist, and DuckDB then creates it. On 2.0 that file is storage version 69. Older clients get `Trying to read a database file with version number 69, but we can only read versions between 64 and 68.`
- `duckdb "$RESOLVED_PATH" -c "PRAGMA version;"` only prints the **library** version (`library_version`, `source_id`, `codename`). It does not show the file’s storage version. The file version is on `duckdb_databases().tags` (`storage_version=v2.0.0+` in the probe).
- Opening a 1.x file does **not** upgrade it. The skill never says that, so an agent may “fix” compatibility by rewriting the file.
- `ATTACH IF NOT EXISTS 'RESOLVED_PATH' AS my_data;` plus `USE my_data;` assumes a native DuckDB file. A DuckLake path, an Iceberg catalog, a SQLite file, or `quack:` does not belong in this statement. SQLite on 2.0 is `ATTACH ... (TYPE sqlite)` (extension name in `duckdb_extensions()` is `sqlite_scanner`; `INSTALL sqlite` still loads it).
- Last `USE` in an append-only file silently changes the default database every time another file is attached.
- Delegation is Claude-only: “delegate to `/duckdb-skills:install-duckdb`”.

Worth keeping: one `state.sql` per project, project dir vs `$HOME`, append-only, `duckdb -init`, gitignore prompt, `duckdb_tables()` plus `DESCRIBE` plus `count()` capped at 20 tables. `estimated_size` and `column_count` are still columns of `duckdb_tables()` (probed).

### `query` — rewrite

Still the skill agents will run most often. The friendly-SQL list and the ad-hoc sandbox settings are valid. The invocation and the lambda hint are not.

Wrong or incomplete:

- Every execution uses `-csv` (`duckdb -init ... -csv -c "<QUERY>"` and the ad-hoc heredoc). On 2.0 that disables agent mode, so the agent loses the truncation footer, the result hash, JSON errors, and the >1,000,000-row cost line. The skill then re-implements a weaker version of that (ask at >1M rows, warn at >10 GB, “if more than 100 rows, note the truncation”).
- `-safe` is **not** a substitute for the sandbox. Safe mode sets `enable_external_access = false` and blocks **all** external files, including the file the user just named ([Safe mode](https://duckdb.org/docs/2.0/clients/cli/safe_mode.html)). The SQL sandbox is still the right ad-hoc pattern.
- Friendly SQL, “lambdas”: `COLUMNS(*): apply expressions across columns; supports regex, EXCLUDE, REPLACE, lambdas`. It never says the syntax. An agent that emits `x -> x + 1` hits `Deprecated lambda arrow (->) detected` (probed). Python-style `lambda x : expr` works. List comprehensions still work: `[x*2 FOR x IN [1,2,3]]` returned `[2, 4, 6]`. `LIMIT 10%` still parses.
- `SET VARIABLE x = expr`: define SQL-level variables, reference with `getvariable('x')`. `getvariable` still works. 2.0’s idiom is also `$x` (probed: both returned 7). The line is incomplete, not false.
- `max(col, 3)` top-n still returned `[9, 5, 2]`. Prefix alias `SELECT x: 42` still works. Do not delete those lines; do not let another skill repeat them.
- Error path sends the agent to `/duckdb-skills:duckdb-docs` and never mentions the legacy parser. A PEG miss is `INSTALL AND LOAD legacy_parser; SET enable_legacy_parser = true;` for that session only.
- Natural-language-to-SQL stays, but the skill should not grow a dialect encyclopedia. 2.0 additions that belong as **one line each**, not new sections: `$variable`, `NEAREST` joins, data-modifying CTEs, nested schemas (`CREATE SCHEMA finance.reports`), `FETCH FIRST`. Triggers do **not** belong as a skill; a short “supported shape plus the two missing combinations” note belongs here so agents stop inventing `BEFORE UPDATE FOR EACH ROW`.

Worth keeping: friendly-SQL list (owner: this skill only), ad-hoc settings below, schema lookup via `duckdb_tables()` / `DESCRIBE`, heredoc for multi-line SQL, “don’t paste a million rows into the chat.”

Sandbox settings still exist (probed in `duckdb_settings()`):

```sql
SET allowed_paths=['FILE_PATH'];
SET enable_external_access=false;
SET allow_persistent_secrets=false;
SET lock_configuration=true;
```

### `read-file` — merge into `files`

Previewing a file is still a job. The `read_any` macro is the wrong long-term interface, and two branches are wrong on 2.0.

Wrong or incomplete:

- SQLite branch calls a function that is not there. After `LOAD sqlite` the functions are `sqlite_attach`, `sqlite_query`, `sqlite_scan` only (probed). This line fails:

  `sqlite_case AS (FROM sqlite_scan(file_name, (SELECT name FROM sqlite_master(file_name) LIMIT 1)))`

  Use `ATTACH 'file' AS s (TYPE sqlite)` and `SHOW TABLES`, then `sqlite_scan` only when the table name is known. `INSTALL sqlite_scanner` in the retry hint did install (the extension’s name is `sqlite_scanner`).

- GeoJSON is forced through JSON, not geometry:

  `WHEN file_name ILIKE '%.json' OR ... OR file_name ILIKE '%.geojson' OR file_name ILIKE '%.geojsonl' ... THEN 'json_case'`

  2.0 `read_json(..., geojson := true)` can produce `GEOMETRY`. `ST_Read` also reads GeoJSON. The macro does neither.

- Remote S3 always installs a credential chain, including public buckets:

  `| s3:// | LOAD httpfs; CREATE SECRET (TYPE S3, PROVIDER credential_chain); |`

  Probed with `LOAD httpfs` and no AWS profile: `Secret Validation Failure: no profile 'default' found`. `s3-explore` already says to skip the secret for public buckets. One owner should say that (the lakehouse skill). `read-file` must not.

- `read_json_auto` still exists (it is an alias of `read_json`). A CSV `read_any` call succeeded on 2.0 **without** loading avro, excel, or spatial, so unused branches are not bound. That does not make the macro a good 2.0 design: extension-backed branches fail only when selected, and the agent is told to retry with a manual `LOAD`.
- No `VARIANT`, no `read_duckdb` (the function exists in 2.0), no Iceberg/Delta/DuckLake. Those are other skills’ jobs. This skill should hand off, not grow.
- Async I/O is invisible. Parquet and uncompressed seekable UTF-8 CSV already read asynchronously. Do not tell the agent to `SET async_threads` on a preview.

Worth keeping: extension-by-suffix as a **short table** (not a giant macro), `DESCRIBE` + `count()` + `LIMIT 20`, “never `DESCRIBE` by downloading a Parquet file’s rows when `parquet_metadata` can answer”, and the refusal to treat source code as data.

### `convert-file` — merge into `files`

`COPY (FROM '<INPUT_PATH>') TO '<OUTPUT_PATH>' <FORMAT_CLAUSE>` is still the right tool. Probed: CSV, JSON `ARRAY true`, and default Parquet writes succeed. `FORMAT xlsx` correctly errors until `excel` is loaded, which the skill already says.

Still true on 2.0, so keep the idea and do not duplicate it elsewhere: `PARTITION_BY` is inside the `COPY` options and works for Parquet and CSV. The 2.0 docs example is `COPY orders TO 'orders' (FORMAT parquet, PARTITION_BY (year, month));`. The target is a **directory**. `CODEC 'zstd'` was not re-probed; do not invent codecs in the new skill, point at the docs skill.

Wrong or incomplete: same S3 `credential_chain` prepend as `read-file` (public buckets fail). Same Claude slash-command failures. No DuckLake / Iceberg / Delta write path, and it should not grow one — that is the lakehouse skill. Defaulting a missing output path to `.parquet` is a behavior choice, not a 2.0 bug; keep it only if the new skill says it out loud.

### `s3-explore` — merge into `lakehouse`

Listing a prefix without pulling `content`, and using `parquet_metadata` for row counts, is the right job. It is not a whole skill next to DuckLake, Iceberg, and Delta.

Wrong or incomplete:

- Stops at files. 2.0 lakehouse work is `ATTACH` of DuckLake, Iceberg REST, and Delta (`CREATE TABLE`, time travel, better `VARIANT`). A file glob is the wrong first move when the user has a catalog.
- Secrets are copied again, differently from `read-file` and from `spatial` (`PROVIDER config` vs `credential_chain`). R2 `TYPE r2` and `ACCOUNT_ID` are still documented; keep **one** table in the lakehouse skill.
- `SET` of `async_threads` is absent, which is fine, but the skill also never says async I/O is already on for Parquet. Agents will “optimize” by downloading the bucket.
- No warning that `?s3_access_key_id=` is now part of the object key.

Worth keeping: “directory → `read_blob` of `filename, size, last_modified` only; never `content`”; Parquet counts from `parquet_metadata`; public-bucket skip. `CREATE SECRET (TYPE S3, PROVIDER config, REGION 'us-west-2')` still succeeds with no keys (probed) and is the right **region pin**, not a credential.

### `install-duckdb` — rewrite, and split

Extension install is a real job. CLI install is a different job and currently contradicts the README (the README says this skill installs DuckDB; the body refuses to, and only upgrades the CLI under `--update` after a prompt).

Still true, keep in the **extensions** skill only:

- `name` → `INSTALL name;`
- `name@repo` → `INSTALL name FROM repo;` (`INSTALL sqlite` loaded `sqlite_scanner`)
- `UPDATE EXTENSIONS;` and `UPDATE EXTENSIONS (name, ...);` (probed: `httpfs`, `sqlite_scanner`, `fts` returned `NO_UPDATE_AVAILABLE`)
- `https://duckdb.org/data/latest_stable_version.txt` is live and currently says `2.0.0`. That HTTP check belongs to the **cli** skill, not here. One owner.

Wrong or incomplete:

- Does not say community extensions are unsigned-by-core and are no longer built for `osx_amd64`.
- Does not say `CREATE EXTENSION REPOSITORY` / `SET allow_extension_repositories = 'allowed'` is WIP. Agents that see the 2.0 blog post will try it. The extensions skill should refuse to invent that syntax and should send the user to the docs skill.
- `eval.sh` is a Claude Code eval, not a skill. Drop it.
- Installing `json` (the eval does) is a stale example: JSON facilities used above are in the core/json surface the CLI already has. Do not teach `INSTALL json` as a required step.

CLI install lines (`brew install duckdb`, `curl -fsSL https://install.duckdb.org | sh`, `winget install DuckDB.cli`) move to the cli skill. Do not auto-upgrade: a 2.0 CLI will write v2.0 files.

### `duckdb-docs` — rewrite

The hosted FTS index is worth keeping. The version filter is false, and the query as written does not run on 2.0.

Probed against `https://duckdb.org/data/docs-search.duckdb` (the URL still returns 200, schema columns match the skill):

| `version` | rows |
|---|---|
| `2.0` | 2695 |
| `blog` | 999 |
| `lts` | **0** |
| `current` | **0** |
| `stable` | **0** |

DuckLake index `https://ducklake.select/data/docs-search.duckdb` has **`stable` only** (198 rows, 0 `preview`). 36 chunks mention `1.1`. There is no `preview` version.

Wrong or incomplete:

- “By default, search **DuckDB docs** and filter to `version = 'lts'`.” That filter returns no rows. The index versions are `2.0` and `blog`.
- The version table in the same file says DuckDB versions are `` `lts`, `current`, `blog` ``. Same bug.
- Step 5 says if you want docs and blog, run one query with `` `version = 'stable'` ``. `stable` is the **DuckLake** label, not the DuckDB one. Inside this file the default, the table, and step 5 disagree with each other.
- The search SQL filters on the BM25 alias in the same SELECT:

  ```sql
  fts_main_docs_chunks.match_bm25(chunk_id, 'SEARCH_QUERY') AS score
  FROM docs_chunks
  WHERE score IS NOT NULL
    AND version = 'VERSION'
  ```

  On 2.0 that is `Binder Error: Alias "score" referenced - but the expression has side effects. This is not yet supported.` A subquery works (probed): score ~6.98 for `agent mode` on `/docs/2.0/clients/cli/agent_mode#activating-agent-mode`. Official FTS examples already use the subquery form. The `fts_main_docs_chunks` name is correct **when that file is the main database**, which the skill’s `duckdb "$CACHE" -readonly` invocation does.

- Result `url` values are paths (`/docs/2.0/...`, `/docs/stable/...`), not absolute URLs. Presenting `{url}` raw sends the user nowhere. Prefix `https://duckdb.org` or `https://ducklake.select`.
- Cache-for-two-days and `COPY FROM DATABASE` are fine. `INSTALL httpfs; INSTALL fts;` is fine (`fts` is not loaded until installed; probed).
- Defaulting “unsure” to “all versions” now mixes the 2.0 manual with the blog. Default to `version = '2.0'`. Add `blog` only when the user wants a post.

Worth keeping: remote index, local cache, BM25, “answer from the chunks, don’t recite the manual.”

### `spatial` — rewrite

The job is real. `references/functions.md` and `references/overture.md` are **reference tables** (function catalogs, schema tables, H3 resolutions) plus a few worked queries. They are not procedures. Do not ship them as a second manual. The new skill keeps one procedure and looks up function signatures through the docs skill.

`geometry_always_xy` still exists on the 2.0 spatial extension (setting the name without `LOAD spatial` returns “it exists in the spatial extension”). `ST_Distance_Spheroid` still takes `POINT_2D` in the spatial function list. Keep the cast `ST_Point(ST_X(geometry), ST_Y(geometry))::POINT_2D` and “longitude first” for CSV. Do not copy the rest of `functions.md`.

Wrong or incomplete:

- Overture release is hardcoded seven months stale, and Overture only keeps about two months of data in the public buckets. `references/overture.md`: “As of 2026-03-18, the latest release is `2026-03-18.0`.” The release calendar on 2026-10-22 lists **`2026-10-21.0`** as the current release and `2026-09-23.1` as the previous one ([release calendar](https://docs.overturemaps.org/release-calendar/)). Paths under `s3://overturemaps-us-west-2/release/2026-03-18.0/...` should be treated as gone.
- Places schema uses `categories.primary`. Overture removed `categories` in release `2026-09-23.0`. Current docs and the overtureR notes use `taxonomy.primary` (and `basic_category`). The worked query `AND categories.primary = 'coffee_shop'` is the wrong column.
- The file tells the agent to read the STAC catalog, then ignores that advice and pastes the March path into every example. 2.0-safe pattern, already used by Overture’s own docs:

  ```sql
  SET VARIABLE latest = (
      SELECT latest FROM 'https://stac.overturemaps.org/catalog.json'
  );
  ```

  Then `'s3://overturemaps-us-west-2/release/' || getvariable('latest') || '/theme=places/type=place/*'`. (`$latest` is the 2.0 spelling; either is fine. Do not document both in two skills.)

- Bbox-first is right. Overture’s own DuckDB examples filter **`bbox.xmin` / `bbox.ymin` with `BETWEEN`**, not `xmin > AND xmax <`, because the partition column for points is the min corner. The strict containment in the reference (`bbox.xmax < -73.97`) drops edge partitions. Keep “filter bbox before `ST_*`”; use the min-corner predicate.
- `INSTALL h3 FROM community` is still the right registry. It is an extensions-skill fact. Spatial should name `h3` and the community repo, not re-teach `INSTALL`.
- S3 region pin may stay as the config secret above, or `SET s3_region = 'us-west-2'` as in Overture’s current DuckDB page. Pick one in the lakehouse skill and call it. Do not also hardcode credentials.
- `COPY ... (FORMAT GDAL, DRIVER 'GeoJSON')` is still the documented export. One example is enough.

### `read-memories` — drop

It searches `$HOME/.claude/projects/*/*.jsonl` for Claude Code transcripts. Nothing in DuckDB 2.0 needs that. `read_ndjson(..., filename=true)` is a generic file feature the files skill already covers if someone points it at a JSONL file. Do not keep a skill whose trigger is “do you remember” and whose path is one vendor’s session log. `eval.sh`-style Claude coupling goes with it.

## Ideas worth keeping

These are the only upstream inventions worth adapting. Each has one owner in the new set.

1. **`state.sql`.** Append-only `ATTACH` / `USE` / `LOAD` init file, project-local `.duckdb-skills/state.sql` or `~/.duckdb-skills/<project-id>/state.sql`, restored with `duckdb -init`. Owner: `session`. Do not store raw Quack tokens or cloud secret keys in it; store `CREATE SECRET` names and `ATTACH` lines that reference them. Never `USE` on every append without asking.
2. **Friendly SQL list.** `FROM`-first, `GROUP BY ALL`, `EXCLUDE` / `REPLACE`, `UNION ALL BY NAME`, `LIMIT n%`, prefix aliases, `count()`, lateral aliases, `FILTER`, `PIVOT` / `UNPIVOT`, `DESCRIBE`, `SUMMARIZE`, `INSERT BY NAME`, ASOF and POSITIONAL joins. Owner: `query`. Update the lambda bullet to `lambda x : expr` and the variable bullet to `$x` (mention `getvariable` once). Add the four 2.0 one-liners listed under `query`. Do not paste this list into any other skill.
3. **Sandboxed ad-hoc mode.** `allowed_paths` + `enable_external_access = false` + `allow_persistent_secrets = false` + `lock_configuration = true`, and only for local files the user named. Owner: `query`, invoked by `files` when it previews. Not `-safe`.
4. **Docs FTS index.** `https://duckdb.org/data/docs-search.duckdb` and `https://ducklake.select/data/docs-search.duckdb`, local cache, BM25 **subquery**, version `2.0` or DuckLake `stable`. Owner: `docs`.
5. **Overture bbox-first.** Predicate on `bbox` before any `ST_*`, spheroid distance only on `POINT_2D`, longitude then latitude, release id from STAC not from a hardcoded date. Owner: `spatial`.

## What not to add

- **Triggers as a skill.** Reject. One short section in `query`: statement-level `AFTER` triggers with `REFERENCING OLD/NEW TABLE` work; `BEFORE ... FOR EACH ROW` and `UPDATE ... FOR EACH ROW` do not yet. Anything fancier goes to the docs skill. Agents do not “run triggers” as a daily job distinct from writing SQL.
- **A JSON skill beside `variant`.** JSON readers stay in `files`. Mutation functions (`json_set`, `json_insert`, `json_replace`, `json_remove`) are one line in `variant`: use them on JSON text; use `variant_extract` once the value is `VARIANT`.
- **A separate Iceberg skill and a separate Delta skill.** Same job as S3 and DuckLake: attach a table that lives outside a `.duckdb` file, don’t scan it blindly.
- **C API, Python, or JDBC skills.** Out of scope for a CLI skill pack unless a later repo wants a client skill. The C API v2 is explicitly not stable.
- **WIP `CREATE EXTENSION REPOSITORY` as a procedure.** Name it, say the syntax can change, stop.
- **Claude session search, slash commands, `allowed-tools`, `$0` argument wiring.** Portable frontmatter is `name` and `description` only.

## Curated set

Eleven skills. Shared facts have one owner. Other skills say “see `<owner>`” in one line and do not restate the fact.

| Skill | Job an agent actually does | Replaces | Rejected alternative |
|---|---|---|---|
| `cli` | Run the DuckDB CLI correctly on 2.0 | CLI half of `install-duckdb`; the scattered `duckdb -csv -c` blocks | A “DuckDB overview” skill |
| `session` | Attach a local database and remember it | `attach-db` | Folding Quack and DuckLake into the same ATTACH |
| `query` | Run one SQL statement, or write friendly SQL from a question | `query` | A dialect encyclopedia, a triggers skill |
| `files` | Preview or convert a local or HTTP file | `read-file`, `convert-file` | Keeping `read_any` |
| `variant` | Inspect or project a semi-structured column | nothing (new) | Teaching shredding internals |
| `quack` | Serve this database, or connect a session to one | nothing (new) | Hiding `CONNECT` inside `session` |
| `lakehouse` | Query S3, R2, GCS, Azure, DuckLake, Iceberg, or Delta without downloading the lake | `s3-explore` | Four format skills |
| `migrate` | Move a database file across the 2.0 storage break, or write a file an older DuckDB can read | nothing (new) | Letting `session` run `EXPORT` on its own |
| `extensions` | Install or update an extension | extension half of `install-duckdb` | Documenting custom repositories as stable |
| `docs` | Answer from the current docs index | `duckdb-docs` | Scraping duckdb.org HTML |
| `spatial` | Answer a geography question, usually with a bbox filter | `spatial` | Vendoring `functions.md` |

`read-memories` is not replaced.

### Owner rules

- **CLI invocation, agent mode, version gate, legacy-parser fallback:** `cli`.
- **`state.sql` location and rules:** `session`.
- **Friendly SQL, ad-hoc sandbox, trigger limitations:** `query`.
- **Async I/O scope (Parquet and uncompressed seekable UTF-8 CSV only):** `files`.
- **`variant_*` vs JSON text:** `variant`.
- **Cloud secrets and “do not put access keys in the URL”:** `lakehouse`.
- **Storage version, `-storage-version`, `EXPORT`/`IMPORT`:** `migrate`.
- **`INSTALL` / `UPDATE EXTENSIONS`:** `extensions`.
- **Which docs version string to filter:** `docs`.
- **Overture release lookup and bbox predicate:** `spatial`.

## README attribution

If the new repo reuses structure or wording, the README must say, in substance:

> Portions of the skill structure and wording are adapted from [duckdb/duckdb-skills](https://github.com/duckdb/duckdb-skills), Copyright 2018-2025 Stichting DuckDB Foundation, licensed under the MIT License.

The repo must also ship the MIT license text with that copyright line (the “above copyright notice and this permission notice” condition). A URL by itself is not enough when the friendly-SQL list, the sandbox `SET`s, the state-file convention, or the FTS query are adapted rather than merely linked. Do not say the new repo is a fork, and do not tell users to `/plugin install duckdb-skills`.

## Recommended skill list

### `cli`

One-sentence purpose: Decide how to invoke the DuckDB 2.0 CLI, and stop if the binary is missing or older than 2.0.

Replaces: the CLI-install and `--update` version check in `install-duckdb`, plus every skill’s private `duckdb -csv -c` recipe.

Three facts it must contain:

1. Prefer `duckdb -agent` (no `-csv` / `-json`) so agent mode stays on: compact Markdown, a loud row cap, JSON errors on stderr. `-csv` disables the automatic agent-mode switch.
2. Require DuckDB ≥ 2.0.0. `https://duckdb.org/data/latest_stable_version.txt` is the check. Install with the official brew / install script / winget commands only after the user agrees. Do not upgrade over a 1.x binary silently.
3. Parser fallback, only after a query that used to parse now fails: `INSTALL AND LOAD legacy_parser; SET enable_legacy_parser = true;`. Do not enable it by default.

### `session`

One-sentence purpose: Attach a local DuckDB file, record it in `state.sql`, and show its tables.

Replaces: `attach-db`.

Three facts it must contain:

1. `state.sql` is append-only and shared. Paths: `.duckdb-skills/state.sql` or `~/.duckdb-skills/<project-id>/state.sql`. Restore with `duckdb -init` via the cli skill. Do not write secret **values** into the file.
2. Read storage version from `duckdb_databases().tags` before trusting the file. Creating a missing file writes `v2.0.0`, which DuckDB 1.x cannot open. Opening a 1.x file does not upgrade it. Hand any conversion to `migrate`.
3. `ATTACH IF NOT EXISTS 'path' AS alias` is for native DuckDB files only, then `DESCRIBE` and `count()` (cap the number of tables). DuckLake, Iceberg, Delta, SQLite, and Quack go to their own skills.

### `query`

One-sentence purpose: Run one SQL statement against the session or against files the user named, using friendly SQL.

Replaces: `query`.

Three facts it must contain:

1. Friendly SQL stays the house style, with 2.0 corrections: lambdas are `lambda x : expr` (arrow form is off; `SET lambda_syntax = 'enable_single_arrow'` is temporary), variables are `$x`, and `NEAREST`, data-modifying CTEs, nested schemas, and `FETCH FIRST` exist. Do not duplicate this list elsewhere.
2. Ad-hoc local files use `allowed_paths`, `enable_external_access = false`, `allow_persistent_secrets = false`, then `lock_configuration = true`. Do not use `-safe` for that. Invoke the process the way `cli` says (`-agent`, not `-csv`).
3. Triggers, if asked: `AFTER` statement triggers with `REFERENCING OLD/NEW TABLE` are the supported shape; `BEFORE ... FOR EACH ROW` and `UPDATE ... FOR EACH ROW` are not implemented yet. Integer division or modulo by zero now errors.

### `files`

One-sentence purpose: Preview a data file or convert it to another file format.

Replaces: `read-file` and `convert-file`.

Three facts it must contain:

1. Pick a reader from the suffix (`read_csv`, `read_parquet`, `read_json` / `read_ndjson`, `read_xlsx` via `excel`, `ST_Read` via `spatial`, `ATTACH ... (TYPE sqlite)`). Do not call `sqlite_master(path)`. GeoJSON needs `read_json(..., geojson := true)` or `ST_Read`, not plain `read_json_auto`.
2. Preview is `DESCRIBE`, `count()`, `LIMIT 20`. Parquet row counts come from `parquet_metadata`, not a full scan. Convert with `COPY (...) TO` and an explicit format option; `PARTITION_BY` writes a directory of Parquet or CSV.
3. Async I/O is already on for Parquet and for uncompressed seekable UTF-8 CSV. Do not tune `async_threads` unless the user asks. Object-store and lake catalogs go to `lakehouse`. `VARIANT` columns go to `variant`.

### `variant`

One-sentence purpose: Inspect a `VARIANT` value or move a JSON document into one.

Replaces: nothing. New, because 2.0 makes `VARIANT` the semi-structured type agents will meet in Parquet, DuckDB storage, and Delta.

Three facts it must contain:

1. `VARIANT` is typed and shredded, not text. Cast JSON text with `::JSON::VARIANT`. A `VARIANT` column may differ in shape per row.
2. Inspect with `variant_type`, `variant_keys`, and `variant_extract` (dot notation also works). Do not `CAST` the whole document to a struct just to look at one field.
3. Parquet read and write of `VARIANT`, including shredding, is built in. JSON mutation (`json_set` and the related functions) stays on the JSON type. Do not retell the Parquet reader options that `files` owns.

### `quack`

One-sentence purpose: Serve a DuckDB database to another DuckDB, or point this session at a remote one.

Replaces: nothing. New.

Three facts it must contain:

1. Server: `duckdb <file> -serve` or `CALL quack_serve(token => ...)`. It listens on localhost. Do not set `allow_other_hostname` except as a test. A reachable server goes behind a TLS reverse proxy.
2. Client: `ATTACH 'quack:host' AS name (TOKEN ...)` then `CONNECT name`. `DISCONNECT` returns to the local database. The CLI shortcut is `duckdb -connect`. Prefer a named secret over pasting the token into `state.sql`.
3. `CONNECT` is also how a session runs SQL on Postgres or MySQL with remote pushdown. That is not an excuse to pull the remote tables locally first.

### `lakehouse`

One-sentence purpose: Query data that lives in object storage or a lake catalog.

Replaces: `s3-explore`.

Three facts it must contain:

1. One secret table: S3 and MinIO `TYPE s3`, R2 `TYPE r2` with `ACCOUNT_ID` (rewrite `r2://` to `s3://`), GCS `TYPE gcs`, Azure `TYPE azure`. `credential_chain` needs real credentials and fails closed when the AWS profile is missing. Public buckets: no credential secret; pin region with `PROVIDER config` and `REGION` when the bucket is not `us-east-1` (Overture is `us-west-2`). Never put `?s3_access_key_id=` on the URL.
2. DuckLake 1.1 needs DuckDB 2.0. The extension still reads and writes 1.0 catalogs. Attach with `ATTACH 'ducklake:...' (DATA_PATH '...')`, not as a native file. Iceberg is an `ATTACH` to a REST catalog. Delta can `CREATE TABLE`, time-travel, and store `VARIANT`. Do not scan a catalog by globbing the data directory.
3. List prefixes with `read_blob` columns `filename`, `size`, `last_modified` only. Predicate pushdown beats download. Async I/O for Parquet is already on (`files` owns that fact). Spec migration to DuckLake 1.1 is optional and only for 1.1-only features.

### `migrate`

One-sentence purpose: Convert a database file to or from the 2.0 storage format when the user actually needs that.

Replaces: nothing. New. `session` detects; this skill converts.

Three facts it must contain:

1. 2.0 reads and writes older files in place and does **not** upgrade them. A file **created** by 2.0 is version 69 and is unreadable by 1.4 and 1.5.
2. To keep a new file readable by an older DuckDB, create it with `-storage-version` or `storage_compatibility_version` / `ATTACH ... STORAGE_VERSION`. Ignore the CLI help line that claims the default is `v0.10.0`; an unflagged new file is `v2.0.0`.
3. To move an old file onto 2.0 storage: `EXPORT DATABASE` with the old CLI, `IMPORT DATABASE` with 2.0 (or `COPY FROM DATABASE`). Do this only after the user asks. Mission-critical workloads can stay on 1.5, which is supported through March 2027.

### `extensions`

One-sentence purpose: Install or update one DuckDB extension.

Replaces: the extension half of `install-duckdb`.

Three facts it must contain:

1. `INSTALL name` uses `core`. `INSTALL name FROM community` (the old `name@community` spelling) is the community repository. `UPDATE EXTENSIONS` with no list updates everything installed; a parenthesized list updates those names.
2. Community extensions are not maintained by DuckDB Labs, and they are not built for macOS x86_64 on 2.0. Do not install one the user did not name.
3. `CREATE EXTENSION REPOSITORY` is a 2.0 WIP and its syntax may change. Do not run it from memory. Send repository-authoring questions to `docs`. CLI install and the version gate stay in `cli`.

### `docs`

One-sentence purpose: Answer a DuckDB or DuckLake question from the hosted full-text index.

Replaces: `duckdb-docs`.

Three facts it must contain:

1. DuckDB index `https://duckdb.org/data/docs-search.duckdb` has versions `2.0` and `blog` only. Default to `2.0`. There is no `lts`, `current`, or `stable` slice in that file. DuckLake index `https://ducklake.select/data/docs-search.duckdb` has version `stable` only (that slice is the 1.1 manual).
2. Score in a subquery. `WHERE score IS NOT NULL` on the same SELECT as `match_bm25(...)` errors on 2.0 because the alias has side effects. `fts_main_docs_chunks.match_bm25` is correct when the cache file is the database being opened.
3. Prefix relative `url` values with `https://duckdb.org` or `https://ducklake.select`. Cache under the home directory is fine; a failed download should stop, not invent an answer. Other skills call this skill instead of pasting doc URLs of their own.

### `spatial`

One-sentence purpose: Answer a location question with the spatial extension, using Overture only when the user has no file of their own.

Replaces: `spatial` (not its function encyclopedia).

Three facts it must contain:

1. `INSTALL`/`LOAD` is `extensions`’ job. After `LOAD spatial`, set `geometry_always_xy = true`. Spheroid distances need `POINT_2D`: `ST_Point(ST_X(geometry), ST_Y(geometry))::POINT_2D`. CSV points are `ST_Point(longitude, latitude)`.
2. Overture: resolve the release from `https://stac.overturemaps.org/catalog.json` (`latest`). Do not hardcode `2026-03-18.0`. Places categories are `taxonomy.primary`, not `categories.primary`. Filter `bbox.xmin` / `bbox.ymin` before any `ST_*`. Region pin for `s3://overturemaps-us-west-2` is the lakehouse skill’s public-bucket rule.
3. Export one result with `COPY ... TO 'out.geojson' (FORMAT GDAL, DRIVER 'GeoJSON')`. H3 is `h3` from `community`. Function signatures that are not in this skill are a `docs` lookup, not a vendored table.

## Sources

- Upstream skills and `README.md` / `LICENSE` in `duckdb-skills-upstream` (read 2026-10-22).
- [DuckDB 2.0.0 announcement](https://duckdb.org/2026/10/21/announcing-duckdb-200.html), [migration](https://duckdb.org/docs/2.0/operations_manual/migration.html), [agent mode](https://duckdb.org/docs/2.0/clients/cli/agent_mode.html), [I/O](https://duckdb.org/docs/2.0/data/io.html), [lambdas](https://duckdb.org/docs/2.0/sql/functions/lambda.html), [safe mode](https://duckdb.org/docs/2.0/clients/cli/safe_mode.html), [What’s New in the Docs for 2.0](https://duckdb.org/docs/2.0/whats_new_in_the_docs.html).
- [DuckLake 1.1](https://ducklake.select/2026/10/21/ducklake-11/) and [DuckLake docs home](https://ducklake.select/docs/stable/) (“DuckLake 1.1 requires DuckDB v2.0.0 or later”).
- Docs indexes probed with DuckDB 2.0.0: version histograms, BM25 subquery, partitioned-writes chunk.
- [Overture release calendar](https://docs.overturemaps.org/release-calendar/) and [Overture DuckDB guide](https://docs.overturemaps.org/getting-data/duckdb/) (`taxonomy.primary`, `SET s3_region`, release `2026-09-23.1` in the guide; calendar current release `2026-10-21.0`).
- Local probes: storage tag on a new file, lambda arrow vs `lambda`, `$x`, `allowed_paths` / `enable_external_access` / `allow_persistent_secrets` / `lock_configuration`, `UPDATE EXTENSIONS`, `sqlite_scan` without `sqlite_master`, S3 `credential_chain` without a profile, S3 `PROVIDER config` region pin, `COPY` formats, `geometry_always_xy` recognized by the spatial extension.
