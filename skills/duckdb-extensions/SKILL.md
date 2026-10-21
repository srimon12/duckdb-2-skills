---
name: duckdb-extensions
description: >
  Install, load, and update DuckDB 2.0 extensions, including community
  extensions and self-hosted repositories. Covers signing, platform support,
  offline installs, and version pinning. Use when an extension is missing, the
  user passes a repository name, or asks to update DuckDB extensions.
---

# Extensions

Before installing, require the 2.0 CLI from `duckdb`. An extension installed by 1.5 is the wrong build for 2.0.

## Install and load

```sql
INSTALL AND LOAD spatial;
INSTALL AND LOAD h3 FROM community;
```

`INSTALL AND LOAD` is new in 2.0. It skips the install when the extension is cached and skips the load when it is already loaded.

| Form | Effect |
| --- | --- |
| `INSTALL name` | Install from `core`. |
| `INSTALL name FROM community` | Install from the community repository. |
| `INSTALL name FROM core_nightly` | Nightly core build. |
| `INSTALL name FROM 'https://...'` | A repository URL. |
| `INSTALL name VERSION 'v1.1.8'` | Pin a version. A hash is also valid. |
| `FORCE INSTALL name` | Re-download and overwrite the cached copy. Without `FORCE`, an installed extension is a no-op, even if the version or repository changed. |
| `INSTALL '/path/ext.duckdb_extension'` | Install a downloaded file. |
| `LOAD name` | Load an installed extension. |

`LOAD` also installs a known extension when `autoinstall_known_extensions` is on, which is the default. Loading an extension loads its dependencies.

## Update

```sql
UPDATE EXTENSIONS;
UPDATE EXTENSIONS (spatial, httpfs);
```

The result columns are `extension_name`, `repository`, `update_result`, `previous_version`, and `current_version`. The statement does not reload. Before depending on the new binary, restart the process.

Statically linked extensions in official builds, including `autocomplete`, `core_functions`, `icu`, `json`, `parquet`, and `shell`, are not updated this way. They ship with the binary.

## Inspect

```sql
SELECT extension_name, installed, loaded, extension_version, install_mode, installed_from
FROM duckdb_extensions()
ORDER BY extension_name;
```

`install_mode` is `STATICALLY_LINKED`, `REPOSITORY`, or `NOT_INSTALLED`. `installed_from` names the repository. `signature_key_fingerprint` is populated for signed repository installs.

## Repositories

Work in progress. The syntax can change.

```sql
SET allow_extension_repositories = 'allowed';

CREATE EXTENSION REPOSITORY my_repo
    WITH PREFIX 'https://extensions.example.org';

INSTALL AND LOAD my_ext FROM my_repo;

SELECT repository_name, prefix, key_fingerprints
FROM duckdb_extension_repositories();

DROP EXTENSION REPOSITORY my_repo;
```

`allow_extension_repositories` is `undecided` by default, and then you cannot add a repository. `allowed` permits adds. `forbidden` blocks adds and distrusts custom repositories already stored. While the process runs, the setting only moves toward stricter, or from `undecided` to `allowed`.

At `CREATE`, DuckDB fetches the repository public keys, pins them, and prints each SHA-256 fingerprint. Compare it with the fingerprint published out of band. `USING PUBLIC KEY '...'` pins a key without fetching it. Keys are 2048-bit RSA. The prefix can be a local path, `https`, or `s3`. Pinned repositories are stored globally under `~/.duckdb/extension_repositories/`, not in the database file, and survive restarts. `extension_repository_directory` is the trust anchor; while signature checking is on, it can only be set at startup.

For a one-off mirror, `SET custom_extension_repository = 'https://mirror.example.org'` changes the default. The `core` and `community` repositories fall back to their backup mirrors automatically. A custom repository does not.

## Platform and security

Community extensions are third-party and are not maintained by DuckDB Labs. Starting in 2.0, they are not built for `osx_amd64`. Core extensions still are, and 2.1 drops `osx_amd64` entirely.

`allow_community_extensions` defaults to `true`. `allow_unsigned_extensions` defaults to `false`. `-unsigned` and `SET allow_unsigned_extensions = true` are for development only. A signed repository plus a pinned public key is the production path.

Extensions live under `~/.duckdb/extensions/<duckdb-version>/<platform>/`. `extension_directories` is a list. DuckDB installs into the first entry and loads from all of them. The singular `extension_directory` is deprecated in 2.0 and warns.

## Troubleshoot

| Symptom | Check |
| --- | --- |
| `HTTP 404` with a candidate list | The name is wrong, or the extension is in another repository. Try `FROM core`, `FROM community`, `FROM core_nightly`. |
| `HTTP 451` | The CDN blocks the region. Use a mirror, a VPN, or a downloaded file. |
| `Extension ... is not available` on a dev build | Nightly builds do not keep the stable extension set. Use a release binary. |
| Version mismatch after a CLI upgrade | `FORCE INSTALL name` or `UPDATE EXTENSIONS`. |
| A stale extension loads | Restart the process; `UPDATE EXTENSIONS` does not reload. |
| A local build cannot load an extension | Platform or version mismatch. Check `duckdb_extensions().install_path`. |

When the repository is unreachable, download a file manually:

```sql
FORCE INSTALL '/absolute/path/spatial.duckdb_extension';
```

A gzipped file must be decompressed first. `LOAD '/absolute/path/name.duckdb_extension'` skips the installed copy. The basename determines the extension name. There is no uninstall command; delete the `.duckdb_extension` file.

## Verify

```sql
INSTALL AND LOAD httpfs;
SELECT extension_name, loaded, install_mode
FROM duckdb_extensions()
WHERE extension_name = 'httpfs';
```

`loaded` must be `true`. A failure names the repository URL and the platform, which is enough to tell a name error from a network error.

## References

- [Installing extensions](https://duckdb.org/docs/2.0/extensions/installing_extensions.html) owns repositories, force install, and paths.
- [LOAD and INSTALL](https://duckdb.org/docs/2.0/sql/statements/load_and_install.html) owns the statement forms.
- [UPDATE EXTENSIONS](https://duckdb.org/docs/2.0/sql/statements/update_extensions.html) owns the result columns.
- [Extension repositories](https://duckdb.org/docs/2.0/extensions/extension_repositories.html) owns the WIP repository SQL.
- [Community extensions](https://duckdb.org/docs/2.0/extensions/community_extensions.html) owns the platform note.
- [Securing extensions](https://duckdb.org/docs/2.0/operations_manual/securing_duckdb/securing_extensions.html) owns the unsigned-extension risk.
- The `name` / `FROM community` / `UPDATE EXTENSIONS` flow comes from the `install-duckdb` skill in https://github.com/duckdb/duckdb-skills (MIT).
