# DuckDB 2.0.0 LTS migration briefing

Factual notes from official DuckDB pages, checked 2026-10-22. Nothing below is inferred from the commit list.

Release: DuckDB 2.0.0 LTS, 2026-10-21.

Official names, both published:

- Announcement and release calendar: “Cinnamon Teal” (*Spatula cyanoptera*).
- GitHub release title: DuckDB v2.0.0 “Cyanoptera”, “named ‘Cyanoptera’ after Spatula Cyanoptera”.

The GitHub release body is a short intro plus a “What’s Changed” pull-request list. It has no breaking-changes section. It points at the announcement. The only migration-relevant PR title pulled from that list is “Deprecate Implicit Table-Function Identifier String Conversion” ([#23350](https://github.com/duckdb/duckdb/pull/23350)). Behavior is taken from the docs below, not from the PR.

The 2026-08-17 preview says some details changed before release and tells readers to use the announcement and the migration guide. One verified difference: the preview called the lambda transition “completed”; the release only disables the old syntax by default and keeps a setting until v2.1. Do not treat the preview as the migration contract.

Primary pages:

- https://duckdb.org/docs/2.0/operations_manual/migration.html (the `/docs/preview/` and `/docs/current/` migration URLs redirect here)
- https://duckdb.org/2026/10/21/announcing-duckdb-200.html
- https://duckdb.org/docs/2.0/internals/storage.html
- https://duckdb.org/release_calendar.html

The migration guide says the breaking set is small. It names the new default storage format, and the lambda step, as the main ones. It also says mission-critical workloads may wait for patch releases; the calendar lists 2.0.1 for 2026-11-18 and marks that date tentative. It recommends a shadow system before switching production.

## Support windows

Source: https://duckdb.org/release_calendar.html unless noted.

Policy text on that page: starting with v1.4.0, every other DuckDB version is an LTS release. Community support for an LTS version is currently a year after release. Two stated exceptions: v1.4 support was extended until November 17, 2026, and v1.5 (called a non-LTS version in that paragraph) was extended until March 2027.

| Line | Released | Calendar end-of-life cell | Other official wording |
| --- | --- | --- | --- |
| 2.0.0 LTS, Cinnamon Teal | 2026-10-21 | 2027-10-22 | Announcement: “support until at least October 2027.” |
| 1.4.0 LTS, Andium | 2025-09-16 | 2026-11-17 | Migration guide: “DuckDB 1.4 LTS reaches its end of life on November 17, 2026.” Announcement: “until late November 2026.” |
| 1.5.0, Variegata | 2026-03-09 | 2027-03-01 | Calendar prose and the migration guide: support extended “until March 2027.” Announcement: extended “until March 2027, effectively also turning it into an LTS release.” |

The announcement also says three lines are current: 2.0 (LTS), 1.4 (still supported until late November 2026), and 1.5 (extended through March 2027).

## Breaking changes

### 1. Default storage format is version 69 (v2.0.0)

**What changed.** New database files created by DuckDB 2.0.0 use storage version 69, the v2.0.0 format, by default. DuckDB v1.0 through v1.5 create files with storage version 64 (corresponding to v1.0.0) by default. Older versions can opt in to a newer format with an explicit storage version.

Storage-version table (https://duckdb.org/docs/2.0/internals/storage.html):

| Storage version | DuckDB version(s) listed |
| --- | --- |
| 69 | v2.0.x |
| 68 | v1.5.x |
| 67 | v1.4.x |
| 66 | v1.3.x |
| 65 | v1.2.x |
| 64 | v0.9.x, v0.10.x, v1.0.0, v1.1.x |

The same page says the on-disk field immediately after the four magic bytes `DUCK` is `999` for files created in the v2.0.0 format. It says that field is not always the storage version, and that the version to trust is the one in the database headers (`duckdb_databases()` → `tags['storage_version']`). The documented example result for a v2.0.0 file is `v2.0.0+`.

Documented format differences versus earlier storage versions: lazy column-metadata load, `DICT_FSST` string compression on by default, more compact row-deletion storage, stronger corruption checks on read.

**Old behavior.** A file created by v1.0–v1.5 is storage version 64 by default. DuckDB 1.5.6 can read storage versions 64 through 68.

**New behavior.** A file created by v2.0.0 with no storage override is version 69. Versions before 2.0.0 cannot read it.

Opening that file with v1.5.6, as printed on the migration page:

```
IO Error: Trying to read a database file with version number 69, but we can only read versions between 64 and 68.
The database file was created with a newer version of DuckDB.

Newer DuckDB version might introduce backward incompatible changes (possibly guarded by compatibility settings).
See the storage page for migration strategy and more information: https://duckdb.org/internals/storage
```

The storage page adds: DuckDB 1.5.5 and earlier report version number 999 instead of 69.

**Forward and backward.**

- Backward: DuckDB 2.0.0 can read and write database files created by earlier versions. A write does not upgrade the file’s storage version, so the file stays readable by the earlier version.
- Forward: a file in the default v2.0.0 format cannot be opened by any DuckDB before 2.0.0. General forward compatibility is documented as best effort, not a guarantee.
- The reverse of “open a 2.0 default file with 1.x” fails. The reverse of “open a pre-2.0 file with 2.0” works, and the file’s storage version is preserved.

**Who it affects.** Any `.db` / `.duckdb` file, every client that opens it (CLI, Python, and others), and any deployment where more than one DuckDB process shares a file. The migration guide says a file created by a v2.0.0 process is unreadable by older processes still attached to that file.

**Official migration action.**

Keep a new file readable by an older DuckDB by setting the storage version at create time. The migration guide’s CLI example:

```
~/.duckdb/cli/latest/duckdb my.db -storage-version v1.5.6 -c "CREATE TABLE t (x INT);"
~/.duckdb/cli/1.5.6/duckdb my.db
```

The same page says the version can also be set with `storage_compatibility_version` or with `STORAGE_VERSION` on `ATTACH`. The storage page’s documented forms:

```
ATTACH 'file.db' (STORAGE_VERSION 'v1.2.0');
ATTACH 'file.db' (STORAGE_VERSION 'latest');
```

```
duckdb -storage-version v1.2.0 my_database.duckdb
duckdb -storage-version latest my_database.duckdb
```

```
SET storage_compatibility_version = 'latest';
SET storage_compatibility_version = 'v1.4.0';
```

Python, from the storage page and the Python migration page:

```
duckdb.connect("file.db", config={'storage_compatibility_version': 'v1.4.0'})
duckdb.connect("file.db", config={"storage_compatibility_version": "v1.5.0"})
```

The configuration reference lists `storage_compatibility_version` as `VARCHAR`, default `latest`: “Sets the DuckDB version for which data is serialized to the DuckDB file during checkpointing.” The storage page says the value is the minimum DuckDB version that should still be able to read the file. Files written that way cannot be opened by a release older than the version named. `latest` means the latest storage version.

Move an existing database onto the v2.0.0 format with the old binary, then the new one:

```
/older/duckdb mydata.old.db -c "EXPORT DATABASE 'tmp'"
/newer/duckdb mydata.new.db -c "IMPORT DATABASE 'tmp'"
```

The storage page also shows, on DuckDB 1.2.0+:

```
ATTACH 'file1.db';
ATTACH 'converted_file.db' (STORAGE_VERSION 'v1.0.0');
COPY FROM DATABASE file1 TO converted_file;
```

That second snippet is the documented way to copy *down* to an older storage version. `EXPORT` / `IMPORT` is the documented way to move an old file up.

**Optional old behavior.** Yes, but only by writing a chosen older storage version. There is no setting that makes a version-69 file readable by 1.x. Setting name: `storage_compatibility_version`. CLI flag: `-storage-version`. `ATTACH` option: `STORAGE_VERSION`.

**Canonical URL.** https://duckdb.org/docs/2.0/operations_manual/migration.html#storage-format and https://duckdb.org/docs/2.0/internals/storage.html

### 2. Single-arrow lambda syntax is off by default

**What changed.** The lambda transition started in v1.3. v1.3 deprecated `x -> x + 1` in favor of Python-style `lambda x : x + 1`, and added `lambda_syntax`. From v1.3 through v1.5, `default` enabled both syntaxes. v1.5 is the last release that accepts the single arrow without explicitly enabling it. v2.0.0 disables the single arrow under `default`. v2.1 will remove both the setting and the single-arrow syntax.

**Old syntax, disabled by default in v2.0.0** (migration page):

```
SELECT list_transform([1, 2, 3], x -> x + 1);
```

**New syntax:**

```
SELECT list_transform([1, 2, 3], lambda x : x + 1);
```

The lambda-function page also shows the parameter form `lambda parameters : expression`, for example `lambda x : x + 1`, `lambda x, y : x + y`.

Documented values, from the lambda page:

```
SET lambda_syntax = 'default';
SET lambda_syntax = 'enable_single_arrow';
SET lambda_syntax = 'disable_single_arrow';
```

Under v2.0 `default`, only the Python-style syntax is enabled.

**Who it affects.** SQL that passes a lambda to list functions (`list_transform`, `list_filter`, `list_reduce`, and their aliases) or uses a lambda in `COLUMNS`. That includes SQL files, views, macros, and SQL strings in every client.

**Official migration action.** Rewrite `x -> expr` to `lambda x : expr`. If queries cannot be rewritten yet, for the session (migration guide’s words):

```
SET lambda_syntax = 'enable_single_arrow';
```

**Optional old behavior.** Yes, until v2.1. Setting name: `lambda_syntax`. Exact opt-in value: `'enable_single_arrow'`. The configuration reference lists it as a deprecated `VARCHAR`, default `DEFAULT`, scope `GLOBAL`: “Configures the use of the deprecated single arrow operator (`->`) for lambda functions.”

**Canonical URL.** https://duckdb.org/docs/2.0/operations_manual/migration.html#lambda-syntax and https://duckdb.org/docs/2.0/sql/functions/lambda.html#deprecated-syntax

### 3. PEG parser is the default; `legacy_parser` restores the old parser

**What changed.** v2.0.0 replaced the PostgreSQL-derived parser with a PEG parser. The PEG parser was opt-in in v1.5 and is the default in v2.0.0. The old parser remains available only through the new `legacy_parser` extension. The docs say the new parser is meant to accept queries the old parser accepted, and that errors now include source locations. They do not list a SQL dialect that parses on one and not the other.

**Old.** PostgreSQL-derived parser, the default through v1.5.

**New.** PEG parser by default. To go back:

```
INSTALL AND LOAD legacy_parser;
SET enable_legacy_parser = true;
```

To return to the PEG parser:

```
SET enable_legacy_parser = false;
```

The announcement also prints `SET enable_legacy_parser = true;` alone. The migration guide and the extension page both require `INSTALL AND LOAD legacy_parser` first.

**Who it affects.** Every SQL statement, in files and in clients. Extensions can now add grammar; that is new surface, not a removal.

**Official migration action.** No rewrite is specified. If a query that parsed before fails, file an issue. To restore the old parser, install and load `legacy_parser`, then set `enable_legacy_parser` to true.

**Optional old behavior.** Yes. Extension name: `legacy_parser`. Setting name: `enable_legacy_parser`. Exact statement: `SET enable_legacy_parser = true;`.

**Canonical URL.** https://duckdb.org/docs/2.0/operations_manual/migration.html#sql-parser and https://duckdb.org/docs/2.0/core_extensions/legacy_parser.html

### 4. Integer division and modulo by zero error instead of returning NULL

**What changed.** `//` and `%` by zero now raise. The migration page’s examples are `1 // 0` and `1 % 0`. The pragmas page also lists `INTERVAL '1' DAY / 0`.

**Old.** DuckDB 1.x returned `NULL` (pragmas page: “similarly to DuckDB 1.x”).

**New.** Error text from the migration page:

```
Invalid Input Error: Division by zero in expression (1 // 0). Use TRY(...) to return NULL for this expression, or SET error_on_division_by_zero=false to return NULL for all divisions by zero.
```

`1 / 0` still returns `inf`. Floating-point division still follows IEEE semantics unless `ieee_floating_point_ops` is set to false; the pragmas page says that, with IEEE off, `1.0 / 0.0`, `0.0 / 0.0`, and `-1.0 / 0.0` throw, and `error_on_division_by_zero = false` is what makes those return `NULL` as well.

**Who it affects.** SQL using integer `//` or `%` (and interval division by zero) in files, views, and clients.

**Official migration action.** For one expression, `TRY(1 // 0)`. For every such division in the session, the statement printed in the error:

```
SET error_on_division_by_zero=false
```

The pragmas page writes it as:

```
SET error_on_division_by_zero = false;
```

**Optional old behavior.** Yes, for now. Setting name: `error_on_division_by_zero`. The pragmas page says this setting is deprecated, will be removed in a future release, and that setting it prints a deprecation warning in the CLI. The long-term replacement it names is `TRY(...)`, not the setting.

**Canonical URL.** https://duckdb.org/docs/2.0/operations_manual/migration.html#division-by-zero and https://duckdb.org/docs/2.0/configuration/pragmas.html#ieee-floating-point-operation-semantics

### 5. `preserve_identifier_case` is a VARCHAR, not a BOOLEAN

**What changed.** The setting’s type changed from `BOOLEAN` to `VARCHAR`.

**Old values.** `true` and `false`. These are still accepted. `true` maps to `'preserve_case'`. `false` maps to `'lowercase'`.

**New values.** `'preserve_case'` (default), `'lowercase'`, `'uppercase'`. The configuration reference describes it as “How to fold non-quoted identifiers,” type `VARCHAR`, default `preserve_case`.

**Who it affects.** Sessions, client configuration, and any SQL or tooling that `SET`s this option. Unquoted identifier folding changes only if the value is `'lowercase'` or `'uppercase'`. The default remains preserving case.

**Official migration action.** None required if `true` / `false` are still sent. New code should send the VARCHAR values.

**Optional old behavior.** The old booleans still work, with the mapping above. There is no separate compatibility setting. Setting name: `preserve_identifier_case`.

**Canonical URL.** https://duckdb.org/docs/2.0/operations_manual/migration.html#identifier-case-setting and https://duckdb.org/docs/2.0/configuration/overview.html

### 6. S3 URL query parameters are no longer settings

**What changed.** S3 settings passed on the object URL are ignored as settings. The `?` and the text after it are part of the object key.

**Old.** `s3://bucket/file.csv?s3_access_key_id=...` supplied S3 settings.

**New.** That URL is an object key that includes `?s3_access_key_id=...`. Credentials belong in secrets (https://duckdb.org/docs/2.0/configuration/secrets_manager.html).

**Who it affects.** SQL and client code that reads or writes `s3://` (and other URLs handled by `httpfs`) with settings in the query string. The setting exists only after `httpfs` is loaded.

**Official migration action.** Use secrets. To keep the old parse:

```
SET s3_enable_deprecated_url_parameters = true
```

**Optional old behavior.** Yes. Setting name: `s3_enable_deprecated_url_parameters`. Configuration reference: type `BOOLEAN`, default `NULL`. “NULL disables them by default; false permanently disables them for this database instance.” `true` is the documented opt-in.

**Canonical URL.** https://duckdb.org/docs/2.0/operations_manual/migration.html#s3-url-parameters

### 7. Removed and deprecated settings

The migration page does not name any removed SQL function. It names removed or inert settings.

| Setting | Status in 2.0 | Replacement on the migration page |
| --- | --- | --- |
| `custom_profiling_settings` | Removed | `tracked_metrics`. Pragmas page: default `['*']` (all metrics). Example: `SET tracked_metrics = ['query.*', 'operator.*'];` |
| `enable_http_logging` | Removed | `CALL enable_logging('HTTP');` |
| `http_logging_output` | Removed | Same. Logging page also names `duckdb_logs_parsed('HTTP')`. `redact_http_logs` still exists and defaults to `true`. |
| `profiling_mode` | Deprecated; the value has no effect | `PRAGMA enable_profiling` to turn profiling on. Detailed profiling information is always collected. The configuration table instead says “Use `enable_profiling` and `profiling_coverage` instead,” type `VARCHAR`, default `NULL`, scope `LOCAL`. |

**Who it affects.** SQL, scripts, and client configuration that set these names. HTTP logging specifically affects anyone using the old HTTP log settings, which require the logging framework instead.

**Optional old behavior.** No for the three removed settings. `profiling_mode` can still be set and does nothing.

**Canonical URL.** https://duckdb.org/docs/2.0/operations_manual/migration.html#removed-and-deprecated-settings , https://duckdb.org/docs/2.0/configuration/pragmas.html#profiling-mode , https://duckdb.org/docs/2.0/operations_manual/logging/overview.html#logging-specific-types

### 8. CLI log storage (documented on the 2.0 migration page; behavior since v1.5.0)

**What changed.** Since v1.5.0, the CLI’s default log storage is `shell_log_storage`. It prints warnings to the console and cannot be queried. Clients other than the CLI still default to `memory`.

**Old, for a 1.4 CLI user.** Not restated on this page beyond the “since v1.5.0” line. The 2.0 logging page says non-CLI clients default to `memory`, where `duckdb_logs` is queryable.

**New, in the CLI.** Warnings print. `duckdb_logs`, `duckdb_logs_parsed()`, and `truncate_duckdb_logs()` error on `shell_log_storage`. To query logs:

```
CALL enable_logging(storage = 'memory');
```

Switching the CLI off `shell_log_storage` stops printing warnings. Restore with:

```
CALL enable_logging(storage = 'shell_log_storage');
```

**Who it affects.** The DuckDB CLI, not other clients. Relevant when moving from 1.4 to 2.0; 1.5 already had this default.

**Optional old behavior.** Not a version switch. Storage name to query logs: `'memory'`. Storage name for the CLI default: `'shell_log_storage'`.

**Canonical URL.** https://duckdb.org/docs/2.0/operations_manual/migration.html#log-storage-in-the-cli and https://duckdb.org/docs/2.0/operations_manual/logging/overview.html

### 9. Implicit identifier-to-string conversion in table functions (deprecated, not removed)

**What changed.** A bare identifier used as a table-function argument used to become a string. As of 2.0 this is deprecated. The default still converts, and logs a warning.

**Old.** `glob(no_such_file.csv)` was treated as `glob('no_such_file.csv')`, with no warning required by the current text.

**New default.** Same conversion, plus a warning. Explicit form:

```
glob('no_such_file.csv')
```

Setting `table_function_identifier_conversion`:

- `DEFAULT`: convert and warn (the v2.0 default).
- `ENABLE_IMPLICIT_STRING`: convert silently (previous behavior).
- `DISABLE_IMPLICIT_STRING`: binder error instead of converting.

```
SET table_function_identifier_conversion = 'DISABLE_IMPLICIT_STRING';
```

Configuration reference: type `VARCHAR`, default `DEFAULT`.

**Who it affects.** SQL that calls table functions with an unquoted path or other unbound identifier (`glob(...)` and similar), in files and clients.

**Official migration action.** Write a string literal. Silence the warning only with `ENABLE_IMPLICIT_STRING`. Turn the conversion off with `DISABLE_IMPLICIT_STRING`.

**Optional old behavior.** Yes. Setting name: `table_function_identifier_conversion`. Exact silent value: `'ENABLE_IMPLICIT_STRING'`.

**Canonical URL.** https://duckdb.org/docs/2.0/sql/dialect/sql_quirks.html#implicit-conversion-of-identifiers-in-table-function-arguments

### 10. ICU library removed from the core build (queries unchanged)

**What changed.** The ICU C library is no longer a DuckDB dependency. Time zones, calendars, and collations are implemented inside the `icu` extension, using IANA time-zone data compressed to about 45 kB. The announcement says behavior is unchanged and the native path is faster. The migration page says no query changes are required. Custom builds no longer have ICU bundled.

**Old / new SQL.** No syntax change is documented. The preview’s examples, which the announcement says still work, are illustrative only; the migration page does not reprint them.

**Who it affects.** Custom builds and packagers. Not SQL authors, according to the migration page.

**Official migration action.** None for queries. File an issue if ICU behavior differs.

**Optional old behavior.** No setting to link the old ICU library is documented.

**Canonical URL.** https://duckdb.org/docs/2.0/operations_manual/migration.html#icu-removed-from-the-core-build and https://duckdb.org/docs/2.0/core_extensions/icu.html

### 11. C API v2 is new and not stable

**What changed.** DuckDB 2.0 ships a second C API that can expose file systems, table functions, and other pieces to extensions. The migration page and the C API overview both say it is not stable and the interface may change. Neither page says the previous C API was removed or renamed. This briefing does not claim a v1 symbol break, because no such list is on those pages.

**Who it affects.** Extension authors and embedders who choose the v2 C API. The announcement also says writing an extension against it, and self-hosting an extension repository, are the intended use. Repository syntax is separately marked “may change” on the announcement (`SET allow_extension_repositories = 'allowed';`, `CREATE EXTENSION REPOSITORY`, `INSTALL AND LOAD ... FROM`).

**Official migration action.** None is required to keep calling the pre-2.0 C API, on the pages read. Do not depend on C API v2 signatures across releases until it is marked stable.

**Optional old behavior.** Not applicable on the pages read. There is no `SET` that selects C API v1 versus v2.

**Canonical URL.** https://duckdb.org/docs/2.0/operations_manual/migration.html#c-api-v2 and https://duckdb.org/docs/2.0/clients/c/overview.html#c-api-v2

### 12. Python client breaks

Source: https://duckdb.org/docs/2.0/clients/python/migration.html . The page says each item is a 1.x form that must change on 2.0. These are client API breaks, not SQL breaks. The main migration page does not repeat them; it only links storage. They are included because that Python page is the official client migration list.

| Area | 1.x | 2.0 | Restore old behavior? |
| --- | --- | --- | --- |
| Python version | Older CPython, including 3.10 | Python 3.11 or newer. Free-threaded CPython is not supported. On 3.10, `pip install duckdb` installs a 1.x release. | No setting. Use a 1.x package on 3.10. |
| Arrow / Polars on `execute()` | `con.execute(query).fetch_arrow_table()`, `fetch_record_batch()`, `arrow()`, `pl()` | Those methods are gone from `execute()` results. `to_arrow_table()` and `to_arrow_reader()` on an `execute()` result copy the rows and warn. Use `con.sql(query).to_arrow_table()`, `con.sql(query).to_arrow_reader()`, or `con.sql(query).pl()`. | No. |
| Relation fetch | `rel.fetchone()`, `rel.fetchmany(n)`, `rel.execute()`, `rel.fetch_df_chunk()` | Removed. A relation does not keep a result between calls; each read runs the query again. For a `fetchone` / `fetchmany` loop, use `con.execute(query)`. To walk a relation: `for row in rel.iter_rows()`. Streamed batches: `rel.to_arrow_reader()`. Replace `rel.execute()` with `rel.materialize()`. | No. |
| Strings in expressions | In `ColumnExpression("s") == "x"` and `rel.update(set={"a": "x"})`, `"x"` named a column | A plain string is a value. The comparison is text equality and warns if `x` is also a column. `update()` raises `TypeError` on a plain string. Column: `col("x")`. Text: `lit("x")`. | No. |
| Dotted names | `ColumnExpression("t.x")` was column `x` of `t` | `"t.x"` is one column name. A missing column raises `BinderException`. Write `col("t", "x")`. | No. |
| Non-string dict keys | `con.values({1: "a"})` made a `STRUCT` field named `1` | In `values()` and in expressions, that dict is a `MAP`, here `MAP(INTEGER, VARCHAR)`. String keys make a `STRUCT`. | No. |
| Attribute vs column | `rel.offset` was the column `offset` | `offset`, `sample`, `head`, `rename`, `pivot`, `drop`, `unnest`, `unpivot`, `preview`, and `group_by` are methods. The column is `rel["offset"]`. | No. |
| `sql()` of DDL / DML | `con.sql("CREATE TABLE t (i INTEGER)")` returned `None` | It returns a relation over what the statement returned. A REPL or notebook prints that relation, which runs the query again. The statement still runs at the call. Use `con.execute()` for DDL and DML. | No. |
| Open `execute()` results | Other queries could run while a result was partly read | Another query on that connection raises `ResourceInUseException` until the result is consumed or ended with `con.complete()` or `con.abort()`. The next `execute()` replaces the open result. | No. |
| One connection, several threads | Calls waited for each other | A call while another thread uses the connection raises `ResourceInUseException`. Use one `con.cursor()` per thread. | No. |
| Failed `execute()` inside a transaction | After `con.begin()`, a catalog, binder, or parser error left the transaction usable | Any failed `execute()` aborts the transaction. `con.commit()` then rolls it back. Any other statement raises `TransactionException` until `con.rollback()`. | No. |
| `overwrite=False` | `rel.write_csv(path, overwrite=False)` and `rel.write_parquet(path, overwrite=False)` replaced an existing file | They raise `IOException`. Omit `overwrite` to replace the file. | No. |
| `Decimal` with a positive exponent | `Decimal("1E+2")` became `1.00` of type `DECIMAL(3,2)` | It is `100` of type `DECIMAL(3,0)`. | No setting is named. |
| Arrow batch size | Relation Arrow output defaulted to 1_000_000 rows | Default is 131_072 rows. Pass `batch_size` to `to_arrow_table()` or `to_arrow_reader()`. | The old size is a parameter, not a global setting. |
| Database files | A file written by DuckDB 1.5 opens in DuckDB 1.5 | DuckDB 1.5 cannot open a default-format file written by DuckDB 2.0. To keep 1.5 readability: `config={"storage_compatibility_version": "v1.5.0"}`. | Yes. Setting: `storage_compatibility_version`. Python example value: `"v1.5.0"`. |

**Canonical URL.** https://duckdb.org/docs/2.0/clients/python/migration.html

### 13. Other deprecations on the announcement (not SQL rewrites)

These are on https://duckdb.org/2026/10/21/announcing-duckdb-200.html and, where noted, a docs page. They are not in the migration guide’s breaking-change list.

- **Amalgamation build.** Deprecated. It bundled DuckDB into one header and one source file. The announcement says it is now too large to be useful in most cases. No replacement `SET` is given. The announcement links the 1.4 building page for the old description.
- **macOS x86_64 (`osx_amd64`).** Requirements page: support level Partial. DuckDB and core extensions are still built. Starting with 2.0.0, community extensions are not built for `osx_amd64`. DuckDB 2.1 will stop supporting `osx_amd64`. No setting restores community-extension builds.
- **Compiler.** Building DuckDB requires C++17. Announcement and https://duckdb.org/docs/2.0/whats_new_in_the_docs.html . Release builds default to Clang on Linux and macOS; on Windows the CLI is Clang and most core extensions are still MSVC.
- **Clients shipping late.** Announcement: CLI and Python were available on release day. Go, R, Java, and some extensions can take a few days.

**Canonical URL.** https://duckdb.org/2026/10/21/announcing-duckdb-200.html#deprecations and https://duckdb.org/docs/2.0/operations_manual/installing_duckdb/requirements.html#supported-platforms

## What the migration page does not list as removed

No removed SQL function is named on https://duckdb.org/docs/2.0/operations_manual/migration.html . The removals it does name are the settings in section 7. `error_on_division_by_zero` and `lambda_syntax` and `profiling_mode` are deprecated, not removed, in 2.0.0.

## Implications for an agent skill

The skill must state these facts, not a general “2.0 is incompatible” line:

- New files from 2.0.0 are storage version 69. DuckDB before 2.0.0 cannot open them. 1.5.6’s error says it can read versions 64 through 68; 1.5.5 and earlier report 999 for the same file. The header field after `DUCK` is 999 and is not the version to quote; `tags['storage_version']` is.
- 2.0.0 can read and write a pre-2.0 file, and that write keeps the old storage version.
- To create a file an older DuckDB can read: `-storage-version`, `SET storage_compatibility_version = '...'`, or `ATTACH ... (STORAGE_VERSION '...')`. The Python example for 1.5 is `config={"storage_compatibility_version": "v1.5.0"}`. Default of the setting is `latest`.
- To upgrade an old file: `EXPORT DATABASE` on the old binary, `IMPORT DATABASE` on 2.0.0. That is not the same as opening the old file in 2.0.0.
- v1.0–v1.5 create storage version 64 by default. Do not tell users that a 1.4 or 1.5 file is version 67 or 68 unless they set an explicit storage version.
- Replace `x -> x + 1` with `lambda x : x + 1`. Temporary restore: `SET lambda_syntax = 'enable_single_arrow';`. Gone in v2.1, setting included.
- PEG is the default parser. Old parser: `INSTALL AND LOAD legacy_parser;` then `SET enable_legacy_parser = true;`. Back: `SET enable_legacy_parser = false;`.
- `1 // 0` and `1 % 0` throw. `1 / 0` is still `inf`. One-off NULL is `TRY(1 // 0)`. Session-wide NULL is `SET error_on_division_by_zero = false`, and that setting is deprecated.
- `preserve_identifier_case` values are `'preserve_case'` (default), `'lowercase'`, `'uppercase'`. `true` and `false` still map to the first and second.
- `s3://bucket/key?s3_access_key_id=...` is now one object key. Opt in with `SET s3_enable_deprecated_url_parameters = true` after loading `httpfs`. Default `NULL` means disabled.
- `custom_profiling_settings`, `enable_http_logging`, and `http_logging_output` are gone. Replacements: `tracked_metrics`, and `CALL enable_logging('HTTP')`. `profiling_mode` does nothing.
- Bare identifiers as table-function arguments still work and warn. Silent old behavior: `SET table_function_identifier_conversion = 'ENABLE_IMPLICIT_STRING';`.
- CLI logs are not in `duckdb_logs` until `CALL enable_logging(storage = 'memory');`.
- Python 2.0 needs CPython 3.11+, and the method removals in the table above are hard breaks with no compatibility setting, except storage compatibility and `batch_size`.
- C API v2 is unstable. Do not claim the old C API was removed.
- Support to cite: 2.0.0 LTS through 2027-10-22 (calendar; announcement says at least October 2027), 1.4 LTS through 2026-11-17, 1.5 through 2027-03-01 (calendar cell; prose says March 2027).
- `osx_amd64` is partial in 2.0: no community extensions; 2.1 drops the platform. Building needs C++17. The amalgamation build is deprecated.

## Uncertainties

- The calendar still calls 1.5 a non-LTS version with support extended until March 2027, and its table cell is 2027-03-01. The announcement says that extension “effectively” makes 1.5 an LTS release and says “until March 2027,” not March 1. Both wordings are official. The calendar cell is the only full date published for 1.5.
- The announcement’s “until at least October 2027” for 2.0 is looser than the calendar cell 2027-10-22. No page explains the one-day gap past the 2026-10-21 release date.
- The storage-version table does not say whether “68 | v1.5.x” means “1.5 writes 68 by default” or “68 is the newest version that line can read.” The prose on the same page says v1.0–v1.5 create version 64 by default and can opt in to a newer format. This briefing follows that prose. It does not state which integer `-storage-version v1.5.6` or `storage_compatibility_version = 'v1.5.0'` writes.
- The migration guide’s compatibility example uses `-storage-version v1.5.6`. The Python migration page uses `"v1.5.0"`. Neither page says those strings differ in on-disk version.
- `profiling_mode`’s replacement is `PRAGMA enable_profiling` on the pragmas page’s deprecation note, and `enable_profiling` plus `profiling_coverage` in the configuration table. Both are on official pages. The migration page only says the setting’s value has no effect and points at `PRAGMA enable_profiling`.
- No page read here lists removed SQL functions. Absence from the migration page is not a proof that no function was removed in a client or an extension.
- The C API pages read do not say whether any pre-2.0 C symbol was removed. Only C API v2’s instability is documented.
- The GitHub release notes were not used as a behavior source beyond the title, the one-sentence naming, the link to the announcement, and the existence of PR #23350. The PR list is not a migration guide.
