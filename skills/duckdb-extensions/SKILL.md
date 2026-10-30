---
name: duckdb-extensions
description: >
  Install, load, and update DuckDB 2.0 extensions, community extensions,
  and self-hosted repositories. Covers key signing, platform support,
  air-gapped manual installs, and version pinning. Use when an extension is
  missing, the user passes a repository, or when updating DuckDB extensions.
---

# Extensions

Before installing an extension, verify the 2.0 CLI from `duckdb`. Extensions installed by 1.5 are the wrong build for 2.0.

## Install and load

```sql
INSTALL AND LOAD spatial;
INSTALL AND LOAD h3 FROM community;
```

In DuckDB 2.0, activate extensions with `INSTALL AND LOAD`. If the extension binary is already cached, DuckDB skips the download. If the extension is already loaded in the session, DuckDB skips loading.

| Form | Effect |
| --- | --- |
| `INSTALL name` | Install from the official `core` repository. |
| `INSTALL name FROM community` | Install from the community repository. |
| `INSTALL name FROM core_nightly` | Install from the nightly core build. |
| `INSTALL name FROM 'https://...'` | Install directly from a custom repository URL. |
| `INSTALL name VERSION '<version>'` | Pin a published version for the 2.0 platform. If the version tag or hash is unverified, DuckDB returns HTTP 404. Test version pins in an isolated scratch directory using `extension_directories` before production use. |
| `FORCE INSTALL name` | Re-download and overwrite the cached binary. If omitted, `INSTALL` is a no-op when an extension already exists, even if the version or repository source changed. |
| `INSTALL '/path/ext.duckdb_extension'` | Install from a downloaded binary file. |
| `LOAD name` | Load an installed extension into the current session. |

When `autoinstall_known_extensions` is `true` (default), `LOAD name` installs a known extension before loading. Loading an extension automatically loads all dependencies.

## Update

```sql
UPDATE EXTENSIONS;
UPDATE EXTENSIONS (spatial, httpfs);
```

To update repository extensions to their latest builds, run `UPDATE EXTENSIONS`. Result columns are `extension_name`, `repository`, `update_result`, `previous_version`, and `current_version`.

Because `UPDATE EXTENSIONS` writes new binaries to disk without reloading running in-memory modules, restart the process before depending on updated extensions.

Update rules:
- Only `REPOSITORY` installs are updated. `UPDATE EXTENSIONS` skips `CUSTOM_PATH` installs.
- If an extension has a pinned version, `UPDATE EXTENSIONS` overwrites it with the repository's latest build. To restore a pinned version after updating, run `FORCE INSTALL name VERSION '<version>'`.
- Statically linked extensions (`autocomplete`, `core_functions`, `icu`, `json`, `parquet`, and `shell`) ship inside the DuckDB binary and cannot be updated with `UPDATE EXTENSIONS`.

## Inspect

```sql
SELECT extension_name, installed, loaded, extension_version, install_mode, installed_from
FROM duckdb_extensions()
ORDER BY extension_name;
```

Inspection columns in `duckdb_extensions()`:
- `install_mode`: `STATICALLY_LINKED`, `REPOSITORY`, `CUSTOM_PATH`, `NOT_INSTALLED`, or `UNKNOWN`.
- `installed_from`: repository name for `REPOSITORY` installs, or source file path for `CUSTOM_PATH` installs.
- `signature_key_fingerprint`: SHA-256 public key fingerprint for signed repository builds.

## Repositories

Custom repository syntax is experimental (WIP) and subject to change.

```sql
SET allow_extension_repositories = 'allowed';

CREATE EXTENSION REPOSITORY my_repo
    WITH PREFIX 'https://extensions.example.org';

INSTALL AND LOAD my_ext FROM my_repo;

SELECT repository_name, prefix, key_fingerprints
FROM duckdb_extension_repositories();

DROP EXTENSION REPOSITORY my_repo;
```

Repository permission states in `allow_extension_repositories`:
- `undecided` (default): blocks adding custom repositories.
- `allowed`: permits repository registration.
- `forbidden`: blocks registration and distrusts custom repositories already stored on disk.
- Process rule: the setting only transitions toward stricter states (`undecided` to `allowed`, or any state to `forbidden`). It cannot relax during a running process.

Key management and storage:
- When executing `CREATE EXTENSION REPOSITORY`, DuckDB fetches 2048-bit RSA public keys from the repository, pins them locally, and prints each SHA-256 fingerprint. Verify this fingerprint against the publisher's out-of-band release.
- To pin keys offline without network requests, specify `USING PUBLIC KEY '...'`.
- Repository prefix paths support local filesystem paths, `https`, or `s3`.
- Repository definitions persist globally under `~/.duckdb/extension_repositories/` across restarts rather than inside database files.
- `extension_repository_directory` defines the root trust anchor. While signature verification remains enabled, configure this setting at startup only.
- For a one-off mirror, run `SET custom_extension_repository = 'https://mirror.example.org'`. While `core` and `community` fall back to backup mirrors automatically on connection failures, custom repositories do not provide automatic fallback.

## Platform and security

Community extensions are third-party contributions not maintained by DuckDB Labs. DuckDB 2.0 does not build community extensions for `osx_amd64`. Core extensions still build for `osx_amd64` in 2.0, while 2.1 drops `osx_amd64` entirely.

Security settings default to `allow_community_extensions = true` and `allow_unsigned_extensions = false`. Never use `-unsigned` or `SET allow_unsigned_extensions = true` in production; use signed repositories with pinned RSA keys.

Binary directories:
- Extensions reside under `~/.duckdb/extensions/<duckdb-version>/<platform>/`.
- To configure multiple search paths, pass a list to `extension_directories`. DuckDB installs into the first directory and loads from all listed directories.
- Avoid the singular `extension_directory` setting. DuckDB 2.0 deprecates it with a warning.

## Troubleshoot

| Symptom | Cause and fix |
| --- | --- |
| `HTTP 404` with candidate list | Extension name misspelling or wrong repository. Check spelling or specify `FROM core`, `FROM community`, or `FROM core_nightly`. |
| `HTTP 451` | CDN geographic access restriction. Use `custom_extension_repository` with a mirror, a VPN, or a downloaded binary. |
| `Extension ... is not available` on dev build | Nightly development builds lack stable extensions. Switch to an official release binary. |
| Version mismatch after CLI upgrade | Stale binary cached from previous version. Run `FORCE INSTALL name` or `UPDATE EXTENSIONS`. |
| Stale extension loads after update | Binary updated on disk while process retains cached in-memory code. Restart the DuckDB process. |
| Local build fails to load extension | Platform architecture or ABI mismatch. Inspect `install_path` via `duckdb_extensions()`. |

If a repository is unreachable or air-gapped, install from a local file:

```sql
FORCE INSTALL '/absolute/path/spatial.duckdb_extension';
```

File installation rules:
- DuckDB accepts `.duckdb_extension.gz` and decompresses it automatically during `INSTALL`. Decompress manually only if the installer rejects the archive.
- To load an extension directly without copying it into `extension_directories`, run `LOAD '/absolute/path/name.duckdb_extension'`. DuckDB derives the extension name from the filename basename.
- To uninstall an extension, delete the `.duckdb_extension` file from disk. DuckDB provides no SQL uninstall command.

## Verify

```sql
INSTALL AND LOAD httpfs;
SELECT extension_name, loaded, install_mode
FROM duckdb_extensions()
WHERE extension_name = 'httpfs';
```

Confirm `loaded` returns `true`. If `INSTALL AND LOAD` fails, inspect the error output: DuckDB returns the repository URL and target platform string, differentiating unknown extension names from network or SSL transport failures.

## References

- [Installing extensions](https://duckdb.org/docs/2.0/extensions/installing_extensions.html) details repository forms, force install, and directory paths.
- [LOAD and INSTALL](https://duckdb.org/docs/2.0/sql/statements/load_and_install.html) documents statement syntax and options.
- [UPDATE EXTENSIONS](https://duckdb.org/docs/2.0/sql/statements/update_extensions.html) documents extension updates and result columns.
- [Extension repositories](https://duckdb.org/docs/2.0/extensions/extension_repositories.html) details experimental custom repositories and key pinning.
- [Community extensions](https://duckdb.org/docs/2.0/extensions/community_extensions.html) covers community policies and platform architecture rules.
- [Securing extensions](https://duckdb.org/docs/2.0/operations_manual/securing_duckdb/securing_extensions.html) specifies unsigned extension risks and trust anchors.
- Extension installation workflows adapted from the `install-duckdb` skill in https://github.com/duckdb/duckdb-skills (MIT).
