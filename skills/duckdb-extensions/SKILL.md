---
name: duckdb-extensions
description: >
  Install, load, and update DuckDB 2.0 extensions, including community
  extensions and self-hosted repositories. Use when an extension is missing,
  the user passes name@community, or asks to update DuckDB extensions.
  Use /duckdb-extensions.
---

# Extensions

Require the 2.0 CLI from the `duckdb` skill before installing. An extension installed by 1.5 is the wrong build for 2.0.

## Install and load

```sql
INSTALL AND LOAD spatial;
INSTALL AND LOAD h3 FROM community;
```

`INSTALL AND LOAD` is `INSTALL`, then `LOAD`. It accepts `FORCE`, `FROM`, and `VERSION`.

```sql
FORCE INSTALL spatial FROM core VERSION 'v1.1.8';
```

A plain name comes from `core`. `name FROM community` is the community repository. `core_nightly` exists. Community extensions are third-party. From 2.0 they are not built for `osx_amd64`. Core extensions still are. DuckDB 2.1 drops `osx_amd64` entirely.

## Update

```sql
UPDATE EXTENSIONS;
UPDATE EXTENSIONS (spatial, httpfs);
```

The statement does not reload. Restart the DuckDB process before you depend on the new binary. Statically linked extensions in official builds, including `json`, `parquet`, and `icu`, are not updated this way. The result columns are `extension_name`, `repository`, `update_result`, `previous_version`, `current_version`.

To see whether the CLI itself is current:

```bash
duckdb --version
curl -fsSL https://duckdb.org/data/latest_stable_version.txt
```

Upgrade the CLI with `curl -fsSL https://install.duckdb.org | sh`. Check the version again. Do not treat Homebrew as the 2.0 source until `brew info duckdb` shows a 2.0 bottle.

## A repository you host

Work in progress. The syntax can change.

```sql
SET allow_extension_repositories = 'allowed';

CREATE EXTENSION REPOSITORY my_repo
    WITH PREFIX 'https://extensions.example.org';

INSTALL AND LOAD my_ext FROM my_repo;
```

`allow_extension_repositories` is `undecided` by default, and then you cannot add a repository. `allowed` permits adds. `forbidden` blocks adds and distrusts custom repositories already stored. While the process is running, the setting only moves toward stricter or from `undecided` to `allowed`. It does not move back to `undecided`.

At `CREATE`, DuckDB fetches the repository public keys, pins them, and prints each SHA-256 fingerprint. Compare that fingerprint with the one published out of band. You can pin a key yourself with `USING PUBLIC KEY '...'`. Keys are 2048-bit RSA. The prefix can be a local path, `https`, or `s3`.

```sql
SELECT repository_name, prefix, key_fingerprints
FROM duckdb_extension_repositories();

DROP EXTENSION REPOSITORY my_repo;
```

Pinned repositories survive restarts.

## References

- https://duckdb.org/docs/2.0/sql/statements/load_and_install.html
- https://duckdb.org/docs/2.0/sql/statements/update_extensions.html
- https://duckdb.org/docs/2.0/extensions/extension_repositories.html
- https://duckdb.org/docs/2.0/extensions/community_extensions.html
- https://duckdb.org/docs/2.0/operations_manual/migration.html
- The `name` / `name FROM community` / `UPDATE EXTENSIONS` flow comes from the `install-duckdb` skill in https://github.com/duckdb/duckdb-skills (MIT). Repository SQL is from the 2.0 docs and is marked work in progress there.
