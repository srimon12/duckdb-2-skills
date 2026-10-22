# Slice: skill specification and cross-client packaging

Status: complete, with unverified items called out in Open questions
Scope: how the 2.0-pass skills are authored, structured, evaluated, and packaged so they load in Claude Code, Codex, Grok, Cursor, and other Agent Skills clients. No DuckDB fact audit.
Sources: `https://agentskills.io/specification`; `https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview`; `.../best-practices`; `https://code.claude.com/docs/en/skills`; `https://code.claude.com/docs/en/plugins/manifest-reference`; `https://code.claude.com/docs/en/plugins/create-marketplace`; `https://code.claude.com/docs/en/plugin-evals`; `https://developers.openai.com/codex/build-skills`; `https://developers.openai.com/codex/agent-configuration/agents-md`; `https://developers.openai.com/plugins/build/plugins`; `https://docs.x.ai/build/features/skills-plugins-marketplaces`; `https://cursor.com/docs/context/skills`

## Verified facts

| # | Claim | Evidence | Confidence |
| --- | --- | --- | --- |
| 1 | The portable contract is the six fields `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`. | agentskills.io/specification | Documented |
| 2 | `name` is 1-64 chars, `[a-z0-9-]`, no leading/trailing hyphen, no `--`, and must equal the parent directory. | agentskills.io/specification | Documented |
| 3 | `description` is 1-1,024 chars, non-empty, no XML; it must say what the skill does and when to use it. | spec; Anthropic overview | Documented |
| 4 | Claude Code reads the first `---` only when it is line 1; unrecognized fields are ignored, not errors. | code.claude.com/docs/en/skills | Documented |
| 5 | Claude Code truncates `description` + `when_to_use` at 1,536 chars in the skill listing; the spec cap still binds uploads. | code.claude.com/docs/en/skills | Documented |
| 6 | Codex supports `SKILL.md` at `.agents/skills`, `~/.agents/skills`, `/etc/codex/skills`, and plugin `skills/`; it lists name, description, and path under a 2% context budget (8,000 chars default). | developers.openai.com/codex/build-skills | Documented |
| 7 | Grok reads `.grok/skills`, `~/.grok/skills`, plugin `skills/`, and `[skills] paths`; it also reads Claude Code marketplaces, plugins, and skills with no extra setup. | docs.x.ai/build/features/skills-plugins-marketplaces | Documented |
| 8 | Cursor reads `.agents/skills`, `.cursor/skills`, `~/.agents/skills`, `~/.cursor/skills`, and, for compatibility, `.claude/skills` and `.codex/skills`. | cursor.com/docs/context/skills | Documented |
| 9 | Anthropic recommends SKILL.md under 500 lines and under ~5,000 tokens; references one level deep; TOC for reference files over 100 lines. | Anthropic best practices | Documented |
| 10 | Claude Code plugins are discovered from `skills/`; `plugin.json` needs only `name`, and plugin skills are namespaced `/plugin:skill`. | manifest reference; skills doc | Documented |
| 11 | `marketplace.json` requires `name`, `owner`, and `plugins`; each entry needs `name` and `source`. Missing `owner` fails validation. | create-marketplace | Documented |
| 12 | The repo's `plugin.json` is JSON-valid but has no `author`; `marketplace.json` is JSON-valid but has no `owner`. | local probe | Probed |

## 1. Portable frontmatter contract

**Rule for this pack: emit only `name` and `description`.** Add `license` only if a skill folder is distributed alone; add `metadata` only if tooling needs it. Never add a field whose behavior differs by client.

| Field | In spec | Claude Code | Codex | Grok | Cursor | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `name` | Yes, required | Yes | Yes | Yes | Yes, must match folder | **Use** |
| `description` | Yes, required | Yes | Yes | Yes | Yes | **Use** |
| `license` | Yes | Accepted, inert | Ignored/unknown | Accepted, not applied | Not listed | Safe but inert; pack LICENSE owns it |
| `compatibility` | Yes | Accepted, inert | Ignored/unknown | Accepted, not applied | Not listed | Safe but inert; omit |
| `metadata` | Yes, string map | Accepted | Ignored/unknown | String map; `author`, `short-description` shown | Accepted | Safe if string map; omit unless needed |
| `allowed-tools` | Yes, experimental | Pre-approves tools | Not listed | Accepted but does **not** grant/restrict | Not listed | Syntactically portable, semantically not; **omit** |
| `disable-model-invocation` | No | Yes | Via `agents/openai.yaml` policy | Yes | Yes | Claude-family only; **omit** |
| `user-invocable` | No | Yes | No | Yes, but `false` hides from user **and** model; only literal `true` counts | No | Semantics conflict; **omit** |
| `when_to_use` | No | Yes | No | `when-to-use` alias | No | **Omit**; fold triggers into description |
| `paths` | No | Yes | No | Yes | Yes | Client-specific; **omit** |
| `argument-hint`, `model`, `effort`, `context`, `agent`, `hooks`, `shell`, `background`, `disallowed-tools` | No | Yes | No | Partial | Partial | Claude-only; **omit** |

### Exact constraints

| Item | Rule | Source of truth |
| --- | --- | --- |
| `name` length | 1-64 characters | Spec |
| `name` chars | lowercase `a-z`, `0-9`, `-`; no leading/trailing `-`; no `--` | Spec |
| `name` match | Exactly the parent directory name | Spec; Cursor |
| `name` reserved | No XML tags; no `anthropic`, `claude` | Anthropic docs |
| `description` length | 1-1,024 characters; target 150-280 | Spec |
| `description` shape | Third person; verb + object + scope; then `Use when ...` with exact user nouns, identifiers, and error symptoms | Anthropic; Codex |
| `description` forbidden | XML tags, first person, "This skill explains...", slash-only triggers, time-sensitive dates | Anthropic; Codex |
| YAML start | Opening `---` on line 1, no BOM or blank line | Claude Code |
| YAML style | Block scalar `>` is fine; quote any value containing `: ` if switched to plain scalar | YAML |

**Where sources disagree:**

| Conflict | Sources | Winner for this pack | Why |
| --- | --- | --- | --- |
| Name rules | Anthropic omits "match directory" and "no `--`"; spec and Cursor require them | Spec | The pack is installed by copying folders; a mismatch fails Cursor and spec validation |
| Description cap | Spec 1,024; Claude Code listing 1,536 with `when_to_use` | 1,024 | The lower cap survives upload/API packaging; Claude's extra 512 chars are not portable |
| Slash invocation | Claude/Grok/Cursor use `/`; Codex uses `$` or `/skills`; plugins namespace | Omit from descriptions | No single slash form is correct in all install modes |
| `allowed-tools` | Spec calls it experimental; Claude Code acts on it; Grok explicitly ignores it | Omit | A field with different security meaning per client is worse than no field |
| `user-invocable` | Claude Code `false` = model-only; Grok `false` = hidden from user and model | Omit | Same key, opposite behavior |
| Body length | Anthropic 500 lines / 5k tokens; Codex metadata budget is separate | Stricter of the two: 500 lines and ~5k tokens | Body still consumes context in every client |
| Nested references | Anthropic warns against; Cursor recursively discovers skill folders | One level for references | Cursor recursion is skill discovery, not a reference-chain feature |

## 2. Directory layout and progressive disclosure

| Path | Use it when | Rules |
| --- | --- | --- |
| `SKILL.md` | Always | 150-250 lines target; 500-line hard cap; <5,000 tokens. Decision rules only. |
| `references/<topic>.md` | A lookup table, option list, or long example is consulted for only some tasks | One level deep from SKILL.md; self-contained; TOC if >100 lines; 300-line target. |
| `scripts/<verb>-<noun>.py` | A deterministic, repeated, or fragile step; output matters more than code | Executable, shebang, `--help`, explicit errors, no secrets, no network by default. Reference as "run", not "read". |
| `assets/<name>` | A static template, fixture, image, or schema that is copied or read | Not instructions. Keep small; no generated binaries. |

**Split rule.** Keep a fact in SKILL.md if the agent must know it before choosing a command. Move it to `references/` if it is a lookup after the choice is made, exceeds ~40 lines, or is used by fewer than half the tasks. For this pack: split `duckdb-files` format/reader matrix, `duckdb-lakehouse` catalog options, `duckdb-migrate` setting renames, `duckdb-sql` friendly-SQL table, and `duckdb` CLI flags. Keep `duckdb-variant`, `duckdb-quack`, `duckdb-extensions`, `duckdb-docs`, `duckdb-session`, and `duckdb-python` single-file until they exceed ~250 lines.

**Reference linking.** Link from SKILL.md at the point of use, with a read cue:

```markdown
Before choosing COPY options, read [the format matrix](references/formats.md).
```

Do not link references to other references. Anthropic warns that nested references get partially read (`head -100`). Cursor's recursive discovery applies to skill directories, not to reference chains. One level wins.

**Naming.** Lowercase kebab: `references/attach-options.md`, `scripts/check-version.sh`. No `REFERENCE.md`, `doc2.md`, spaces, backslashes, or absolute paths. The folder name is the skill identity; a reference file name should say what it owns, not its sequence.

## 3. Description patterns that trigger

Pattern: `<Verb> <object> with <product/version>. <Scope nouns and exact identifiers>. Use when <natural user phrasing, synonyms, error strings>.` Front-load the key use case; Codex may shorten descriptions when many skills are installed.

| # | Quality | Example | Why it works |
| --- | --- | --- | --- |
| 1 | Good | `Move a DuckDB 1.4 or 1.5 database to 2.0. Covers storage version 69, lambda syntax, integer division, and removed settings. Use when the user says migrate, upgrade to 2.0, or a 1.x binary cannot open the file.` | Verb-first; exact version; symptom that triggers it |
| 2 | Good | `Read, preview, or convert CSV, Parquet, JSON, Avro, Excel, SQLite, and object-storage files with DuckDB 2.0. Use when the user gives a path or URL (s3://, https://, gs://, az://) or asks for parquet, csv, or xlsx output.` | Concrete formats, concrete URL schemes, output words |
| 3 | Good | `Answer location questions with DuckDB 2.0 spatial: distance, containment, GeoJSON, Shapefile, GeoPackage, and Overture Maps. Use when the user mentions lat/lng, a bounding box, a map file, or Overture.` | Task verbs plus the vocabulary users actually type |
| 4 | Bad | `Helps with DuckDB.` | No verb, no object, no trigger; matches everything and nothing |
| 5 | Bad | `This skill explains how DuckDB 2.0 VARIANT works.` | Narration, not selection; invites a lecture instead of a command |
| 6 | Bad | `Use for all DuckDB tasks: SQL, files, lakehouse, Python, and migration.` | Poaches 11 other skills; no boundary; the router cannot route |

**Negative triggers.** Use at most one clause, and only where overlap is real: `Not for extension installs; use duckdb-extensions.` Do not put a routing table in every description. The `duckdb` router owns routing; the other 11 own their task nouns.

**Do not put `/skill-name` in the description.** Claude Code, Grok, and Cursor use `/`; Codex uses `$` or `/skills`; plugin installs namespace the skill (`/duckdb-2-skills:duckdb`). All 12 current descriptions contain a slash clause, which is both non-portable and wrong after plugin install.

## 4. Writing rules for agent-facing prose

| Rule | Do | Don't |
| --- | --- | --- |
| Mood | Imperative: `Run`, `Stop`, `Use`, `Do not` | `This skill will...`, `You might want to...` |
| Payload | A fact that changes the next command or the decision to stop | Background, history, motivation, restating the manual |
| Order | Decision order: gate -> choose -> run -> verify | Manual order: concepts -> syntax -> examples |
| Length | One claim per sentence; one command per block | Paragraphs that repeat the heading |
| Ownership | One skill owns each deep fact; others carry a one-line cross-link | The same table or warning in three skills |
| Cross-links | `See duckdb-migrate for storage 69.` | Full explanation in the referring skill |
| Verification | Stop unless `duckdb --version` prints `v2.0`. | "It is important to check the version." |
| Time | Version gate, not a date | "As of October 2026..." in the body |
| Paths | Forward slashes; relative to skill root | Backslashes, absolute home paths |
| Examples | Copy-pasteable, with expected output or error | Pseudocode that looks runnable |

**House style for all 12:**

1. H1 is a short noun phrase, no terminal period: `# DuckDB 2.0 SQL`, `# Database sessions`, `# VARIANT`.
2. First paragraph: one sentence of scope plus the version gate where the skill runs DuckDB. No "When to use" section; the description owns that.
3. H2s are task phases or decision branches, not nouns copied from the manual. Maximum 8 H2s in SKILL.md.
4. Code fences always carry a language (`sql`, `bash`, `python`, `json`). One command per fence unless the sequence must be atomic.
5. Every warning names the wrong move and the correct move: `Do not use x -> x + 1; write lambda x: x + 1.`
6. `## References` is always last: manual URLs first, then one provenance line for adapted MIT work. No dated probe logs.
7. If a skill has no executable claim, it has no verification section. Do not add a decorative checklist.
8. Cross-link with the skill name in backticks, not a URL to this repo.
9. Facts that only a maintainer needs go to `research/`, not SKILL.md.
10. Keep one blank line between sections; no HTML, badges, emoji, or tables of contents inside SKILL.md.

**Owner map (one deep fact, one home):**

| Deep fact | Owner | Every other skill |
| --- | --- | --- |
| CLI version gate, agent mode, output flags | `duckdb` | One-line link only |
| Storage version 69 and migration order | `duckdb-migrate` | `duckdb` and `duckdb-session` warn, then link |
| Reader/format matrix and COPY options | `duckdb-files` | `duckdb-variant` links for Parquet shredding |
| `VARIANT` casts, functions, shredding | `duckdb-variant` | `duckdb-lakehouse` links for Delta variant rules |
| DuckLake/Iceberg/Delta attach and options | `duckdb-lakehouse` | `duckdb-extensions` links for install |
| Extension install, update, repositories | `duckdb-extensions` | `duckdb` gives one fallback line |
| Quack server, `CONNECT`, pushdown | `duckdb-quack` | `duckdb` route table only |
| Docs full-text search and version filter | `duckdb-docs` | `duckdb` route table only |
| Python client breaks and exceptions | `duckdb-python` | `duckdb-migrate` links for storage |
| Overture release id and schema | `duckdb-spatial` | `duckdb-files` links for remote reads |

## 5. Evaluation

**Minimum viable loop, no harness.** Fresh session with only the plugin loaded; paste a prompt that never names the skill; record (a) which skill loaded, (b) the first command or refusal, (c) whether the answer matches the expected decision. Run each case 3 times. A skill passes if the expected signal appears in all 3 and no wrong skill appears. This catches the two failures that matter: not triggering and triggering the wrong sibling.

**Harness option.** Claude Code's `claude plugin eval .` reads `evals/<case>/prompt.md` and `evals/<case>/graders/*.md`, runs with and without the plugin, and reports `WITH`, `W/OUT`, and `Δ`. Use it when the Claude Code CLI is available. The same case files are readable by a human or a shell loop for Codex/Grok/Cursor. Do not maintain a second YAML format.

### Proposed `evals/` layout

```text
evals/
├── README.md                       # how to run, how to grade, model pin
├── trigger/                        # non-case group directory
│   ├── sql-lambda/
│   │   ├── prompt.md               # "Add 1 to every element in this list..."
│   │   └── graders/skill-fired.md  # tool_used: Skill, input_match duckdb-sql
│   ├── files-not-sql/
│   │   ├── prompt.md               # "Preview this parquet file..."
│   │   └── graders/skill-fired.md
│   └── docs-not-core/
│       ├── prompt.md               # "Find the 2.0 page for variant_extract"
│       └── graders/{docs-fired.md,core-not-fired.md}  # docs min:1; duckdb min:0 max:0
├── task/
│   ├── migrate-storage-69/
│   │   ├── prompt.md
│   │   ├── case.yaml               # optional fixtures
│   │   └── graders/
│   │       ├── skill-fired.md
│   │       ├── command.md          # regex over trace: export/import, no 1.x write
│   │       └── decision.md         # llm rubric: stop before writing 69 for 1.x readers
│   └── ...
├── fixtures/                       # small CSV/Parquet/GeoJSON; no secrets
└── results/                        # generated; .gitignore
```

`trigger/` and `task/` are group folders, not cases; only directories with `prompt.md` or `case.yaml` are cases. Every case needs at least one grader. Use `tool_used: Skill` for selection, `regex` on `last_message` or `trace` for a command/identifier, and one `llm` rubric for a decision. Do not use `llm` to grade long files; use `regex` on the file.

### Cases per skill family

| Family | Cases (prompt -> expected signal) |
| --- | --- |
| Core / router (`duckdb`) | 1. "Which DuckDB am I on? Run a query and give me JSON." -> version gate, `-json`/`-agent`, not `-csv`. 2. "I have 1.5.6; open this new .duckdb file." -> stop and route to `duckdb-migrate`. |
| SQL / VARIANT (`duckdb-sql`, `duckdb-variant`) | 1. "Add 1 to every list element." -> `lambda x: x + 1`, not `x -> x + 1`. 2. "Log row changes with a trigger." -> `CREATE TRIGGER`, correct limits. 3. "Extract `a.b` from a VARIANT column." -> `variant_extract`/`v.a`, `variant_typeof`. |
| Files / session (`duckdb-files`, `duckdb-session`) | 1. "Preview `s3://bucket/x.parquet`." -> httpfs + secret + `read_parquet`. 2. "Convert CSV to xlsx." -> `COPY ... (FORMAT xlsx)` after `INSTALL excel`. 3. "Keep this database attached across CLI calls." -> `-init state.sql`. |
| Lakehouse / extensions (`duckdb-lakehouse`, `duckdb-extensions`) | 1. "Attach DuckLake at this Postgres catalog." -> `ATTACH ... (TYPE ducklake)`. 2. "Time-travel this Delta table to version 3." -> `AT (VERSION => 3)`. 3. "Install community extension h3." -> `INSTALL h3 FROM community; LOAD h3`. |
| Server / docs (`duckdb-quack`, `duckdb-docs`) | 1. "Serve this database over Quack on localhost." -> `duckdb -serve`, localhost default. 2. "Find the 2.0 page for `variant_extract`." -> docs FTS with version `2.0`, not `lts`. |
| Migration / Python / spatial (`duckdb-migrate`, `duckdb-python`, `duckdb-spatial`) | 1. "Upgrade a 1.5 database without breaking 1.x readers." -> export/import or pin, storage 69 warning. 2. "Fix Python that calls `.arrow()` after 2.0." -> client migration action. 3. "Get Overture coffee shops in this bbox." -> STAC `latest`, `taxonomy.primary`. |

**Negative trigger cases (add 3):** "Install the spatial extension" -> `duckdb-extensions`, not `duckdb-spatial`; "What changed in 2.0?" -> `duckdb-docs`, not `duckdb`; "Write a SELECT" -> `duckdb-sql`, not `duckdb-files`.

**Rubric rules.** 3-5 checks per task case, each PASS/FAIL: version gate, exact command/identifier, stop/refuse condition, no invented syntax, cites the manual page. No points for tone, formatting, or length. A rubric that a different correct approach fails is a bad rubric.

**Regression.** Run the trigger suite on every description edit; run the owning skill's task cases on every body/code edit; run the full suite before a release. Pin the model, 3 runs, threshold 0.8, compare `WITH` to `W/OUT`. Record the date, model, and `Δ` in `evals/results/` but do not commit results. If a trigger case passes but `Δ` is negative, suspect the judge before the skill.

## 6. Packaging

### Current manifests

| File | Status | Missing / wrong | Fix |
| --- | --- | --- | --- |
| `.claude-plugin/plugin.json` | Valid JSON and schema-valid; `name`, `description`, `version`, `license`, `keywords` present | `author` missing (validator warning; `--strict` fails); `homepage` and `repository` absent | Add `author: {name: "duckdb-2-skills contributors"}`, `homepage`, `repository`; keep `version` as the single version owner |
| `.claude-plugin/marketplace.json` | JSON-valid but **invalid marketplace**: required `owner` missing | Add `owner: {name: "duckdb-2-skills contributors"}`; entry repeats `version`, `license`, `keywords` | Remove the repeated fields from the entry; keep `name`, `source`, `description`; `source: "./"` is valid for a root plugin |
| Root `plugin.json` (Codex portable) | Absent | Codex plugins use a root manifest with `$schema`, `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords` | Add only if publishing a Codex plugin; otherwise document the copy install. If both exist, generate one from the other, never hand-edit both |

`claude plugin validate --strict .` was not run because the Claude Code CLI is absent on this machine. The missing `owner` is a documented hard failure, not a warning.

### Install commands to document

| Client | Install | Invoke | Note |
| --- | --- | --- | --- |
| Claude Code, local | `claude --plugin-dir .` | `/duckdb-2-skills:duckdb` | Plugin skills are namespaced; `/duckdb` is wrong here |
| Claude Code, GitHub | `/plugin marketplace add srimon12/duckdb-2-skills` then `/plugin install duckdb-2-skills@duckdb-2-skills` | `/duckdb-2-skills:duckdb` | Fails today until `owner` is added |
| Grok | `grok --plugin-dir .` or `cp -R skills/. .grok/skills/` | `/duckdb` when copied; verify the plugin form with `/skills` | Grok also reads Claude marketplaces/plugins; project `.grok/skills` may need project trust |
| Codex | `mkdir -p .agents/skills && cp -R skills/. .agents/skills/` | `$duckdb` or `/skills` | User-level: `~/.agents/skills`. Plugin: `codex plugin marketplace add srimon12/duckdb-2-skills`; install via Plugins Directory |
| Cursor | `mkdir -p .cursor/skills && cp -R skills/. .cursor/skills/` | `/duckdb` | Cursor also reads `.claude/skills` and `.codex/skills` |
| Any Agent Skills client | Copy `skills/<name>/` into its skills root | Client-specific | The folder is the unit; no build step |

**README changes.** Add a Codex section and a Cursor section. Replace "Grok, this repository" copy commands with one table of client roots. State both invocation forms: `/duckdb` when copied as a bare skill, `/duckdb-2-skills:duckdb` when installed as a plugin. Do not promise a command that the current manifest cannot install.

## 7. Validation checklist, ranked

| Rank | Check | Rule | Tool |
| --- | --- | --- | --- |
| 1 | Manifest | Plugin JSON parses; `name` matches marketplace entry; `owner` present; no duplicate version owners | `claude plugin validate --strict .`; `json.tool` |
| 2 | Frontmatter parses | Opening `---` on line 1; YAML parses; `name` and `description` present; only allowed fields | `check-skills.py`, `skills-ref validate` |
| 3 | Name | `^[a-z0-9]+(?:-[a-z0-9]+)*$`, <=64, equals directory, no reserved words | `check-skills.py` |
| 4 | Description | 1-1,024 chars; contains `Use when`; first 120 chars name the domain; no XML, first person, or slash-only clause | `check-skills.py` |
| 5 | Links | Every `[text](path)` resolves inside the skill root; no `..`; no absolute paths; no nested reference links | link checker |
| 6 | Files | Every file named in prose exists (`references/...`, `scripts/...`, `assets/...`); scripts executable | link checker |
| 7 | Sections | Exactly one H1; `## References` last; no heading-level skips; no empty sections | `check-skills.py` |
| 8 | Banned strings | No stale identifiers from `scripts/banned.txt` (for example `categories.primary`, `x -> x + 1`, `sqlite_master(`) | `grep -Ff` |
| 9 | Line budgets | SKILL.md <=500, warn >250; reference <=300, TOC if >100 | `wc -l` |
| 10 | Duplicate facts | No code block or 80%-similar sentence owned by two skills; cross-links instead | similarity script + review |
| 11 | Description uniqueness | Pairwise similarity <0.8; no two skills claim the same trigger nouns | similarity script |
| 12 | Hygiene | No Windows paths, absolute home paths, secrets, dates in body, or HTML | `check-skills.py` |

Check 1 is first because a missing `owner` makes installation fail before any skill is read. Checks 2-4 are next because a bad name or description means the skill never loads or never triggers. Checks 5-6 catch broken progressive disclosure. Checks 7-8 catch navigation and stale facts. Checks 9-12 are maintenance quality.

## 8. Existing skill audit (structure only)

Shared: all 12 have exactly `name` + `description`; all end with `## References`; all use a folded `>` description of 205-277 chars; all 12 contain a `Use when` clause and a `/duckdb...` clause; none has `references/`, `scripts/`, `assets/`, a `## Verify` section, or a `license` field; no file contains a relative Markdown link. Line counts: 43-136. Snapshot: files as read on 2026-10-22, before other rewrite work; re-run after edits.

| Skill | H1 style | Body shape | Structural inconsistency | Fix |
| --- | --- | --- | --- | --- |
| `duckdb` | Noun phrase | 4 numbered H2s + route table | Only skill with numbered H2s; router is otherwise a normal skill | Drop numbers; keep `## Route`; move CLI flags to `references/cli.md` |
| `duckdb-sql` | Imperative | 8 H2s, 136 lines | Longest; decision rules mixed with a friendly-SQL lookup table | Keep gates/lambdas/triggers; move friendly-SQL table to `references/friendly-sql.md` |
| `duckdb-session` | Sentence | 4 H2s | H1 is a sentence; no task verb | `# Database sessions`; add `## Verify` only if a command is checkable |
| `duckdb-files` | Imperative | 3 H2s | Reader/format matrix is lookup-only | Move to `references/formats.md`; keep the choose-reader decision |
| `duckdb-variant` | Noun | 3 H2s | Fine; content is compact | Keep single-file; add one-line version gate |
| `duckdb-quack` | Noun | 5 H2s | Fine; no verification block | Keep; add a stop condition for non-localhost auth |
| `duckdb-lakehouse` | Noun | 3 H2s | Three catalogs and attach options in 110 lines | Move option tables to `references/catalogs.md`; keep per-catalog decisions |
| `duckdb-extensions` | Noun | 3 H2s | Fine | Keep; ensure community and repository paths stay distinct |
| `duckdb-docs` | Imperative | 2 H2s | Only skill with a dated "Checked 2026-10-22" line outside `## References` | Move the date/count to `research/`; keep the version filter and cache rule |
| `duckdb-migrate` | Imperative | 2 H2s | Broad task with only two H2s; rename table inline | Add `## Inventory`, `## Export/import`, `## SQL changes`; move renames to `references/setting-renames.md` |
| `duckdb-python` | Noun | No task H2; only `## References` | Thinnest (43 lines); table-only; reads as a note, not a workflow | Add `## Relations`, `## Arrow/Polars`, `## Threads`, `## Transactions`; keep it as the 12th skill per PLAN |
| `duckdb-spatial` | Noun | One H2; most content unheaded | Only one task H2; Overture dominates | Add `## Distance and containment`, `## Files`, `## Overture`; move the schema detail to `references/overture.md` |

**Cross-cutting fixes.** Standardize H1 to a noun phrase. Remove all `/duckdb-*` clauses from descriptions; put invocation in README. Replace bare URL lists with `- [Manual: <page>](https://...) — <what it owns>` and one final provenance line. Decide one verification policy: either a single `## Verify` block with commands, or no block and a `References` line; do not scatter dates.

## Gaps worth adding

| Rank | Gap | Why an agent needs it | Home |
| --- | --- | --- | --- |
| 1 | Marketplace `owner` and plugin `author` metadata | Install fails or emits strict-validation warnings before any skill runs | `.claude-plugin/marketplace.json`, `plugin.json` |
| 2 | Portable descriptions without slash commands or Claude-only fields | Codex uses `$`, plugin installs namespace, and `user-invocable` semantics conflict | All 12 descriptions |
| 3 | Trigger and task evals | Description edits silently break routing; no regression signal today | `evals/` |
| 4 | Reference split for lookup tables | `duckdb-files`, `duckdb-sql`, `duckdb-lakehouse`, `duckdb-migrate` will exceed the 250-line target during rewrite | `references/` |
| 5 | Scripted checks | The rules in this slice are prose-only and will drift | `scripts/check-skills.py`, `scripts/banned.txt` |
| 6 | Codex and Cursor install docs | README covers Claude and Grok only; Codex users have no documented path | `README.md` |
| 7 | One owner per deep fact | Storage 69, Overture release, and extension install rules are repeated or implied in several skills | Router + owner table |
| 8 | Consistent H1/section order | Agents navigate by headings; 12 different shapes add load | All 12 |
| 9 | Verification policy | Dates and probe claims are scattered; maintainers cannot tell what was run | `research/` + `## References` |
| 10 | Link style | Bare URLs are not clickable in some clients and cannot be link-checked | All 12 `## References` |

## Traps and contradictions

| Trap | What happens | Correct move | Evidence |
| --- | --- | --- | --- |
| Marketplace has no `owner` | `claude plugin marketplace add` validation fails; the README install path is dead | Add `owner.name` | create-marketplace |
| Plugin skills are namespaced | User types `/duckdb`, gets nothing after plugin install | Document `/duckdb-2-skills:duckdb`; remove `/duckdb` from descriptions | skills doc |
| Slash trigger in description | Codex users invoke `$duckdb`; the description's `/duckdb` is noise | Use natural nouns in descriptions; invocation belongs in README | Codex skills doc |
| `user-invocable: false` | In Claude Code it means model-only; in Grok it hides the skill from the model too | Do not use the field | Grok skills page |
| `allowed-tools` | Claude Code pre-approves; Grok explicitly does not grant or restrict | Do not rely on it for safety or permissions | Spec; Grok skills page |
| `disable-model-invocation` | Works in Claude/Cursor/Grok; no spec/Codex equivalent | Keep skills auto-invoked; do not add it | Spec; Codex page |
| Name/dir mismatch | Loads in Claude Code, fails spec validation and Cursor | Keep folder == `name`; script it | Spec; Cursor |
| YAML starts after a blank line | Claude Code treats the whole file as body; no metadata | Opening `---` on line 1; lint it | Claude Code skills doc |
| Description truncation | Claude listing cuts at 1,536; Codex shortens under pressure | Front-load the use case; keep <280 chars | Claude Code; Codex |
| Nested references | Agent previews with `head -100` and misses the rule | One level deep; TOC in long references | Anthropic best practices |
| Codex description budget | Many installed skills shorten descriptions; a weak first clause disappears | Put domain + task in the first 120 chars | Codex skills doc |
| Two plugin manifests | Root `plugin.json` and `.claude-plugin/plugin.json` drift on version/name | One canonical file; generate the other at release | Manifest docs; Codex plugin docs |
| Grok project skills in an untrusted repo | `grok inspect` showed `Project trusted: no` and no project `duckdb-*` skills | Use `~/.grok/skills` or accept project trust; verify with `grok inspect` | Local probe; uncertain whether trust or inspect scope |

## What not to add

- No `when_to_use`, `argument-hint`, `allowed-tools`, `disable-model-invocation`, `user-invocable`, `paths`, `model`, `context`, or `hooks` in skill frontmatter. They narrow the pack to one client or change meaning across clients.
- No "When to use" section in the body. The description is the only trigger surface; a second copy drifts.
- No per-skill README, CHANGELOG, or LICENSE. The pack LICENSE and `THIRD-PARTY-NOTICES.md` own that.
- No `scripts/` or `assets/` just to look complete. Add them only for a deterministic step or a real static artifact.
- No reference-to-reference links, and no reference file that restates SKILL.md.
- No duplicated deep tables for storage version, Overture schema, or extension install rules. Cross-link the owner.
- No model-specific prose ("Claude should...", "Codex should..."). Write for any agent.
- No 13th top-level skill in the 2.0 pass. Superseded in the next-phase pass by `duckdb-profile`; a separate ingest skill was still rejected.

## Probe log

```text
$ python3 -m json.tool .claude-plugin/plugin.json
plugin.json: valid JSON
$ python3 -m json.tool .claude-plugin/marketplace.json
marketplace.json: valid JSON
$ python3 - <<'PY' (keys)
plugin keys: ['description', 'keywords', 'license', 'name', 'version']
marketplace keys: ['name', 'plugins']
entry keys: ['description', 'keywords', 'license', 'name', 'source', 'version']
marketplace owner: MISSING
plugin author: MISSING
$ command -v claude; command -v codex
(no output; exit 1)
$ cp -R skills research/scratch/08/.grok/skills && cd research/scratch/08 && grok inspect
Project trusted: no
Skills (82) ... all "user"; no duckdb-* project skill listed
$ wc -l skills/*/SKILL.md
43-136 lines per skill; total 1,088
```

## Open questions

- Does Grok require project trust before loading `./.grok/skills`? `grok inspect` in an untrusted scratch repo did not list the copied `duckdb-*` skills. Settle it by accepting trust in a disposable repo and re-running `grok inspect`.
- Does Codex CLI have a non-interactive `plugin install` command? The docs show `codex plugin marketplace add` and install through the Plugins Directory, not a CLI install verb. Settle it with `codex plugin --help` on an installed CLI.
- Does Codex error on unknown frontmatter keys or ignore them? The docs require only `name` and `description`; they do not state validation behavior. Settle it with a two-field vs extra-field fixture.
- Does Claude Code `--plugin-dir` load `skills/` when `.claude-plugin/plugin.json` is absent? Components have default locations, but it was not probed. Settle it with a minimal plugin and `claude plugin details`.
- Is a per-skill `license` field worth the duplication? The spec allows it; Claude Code and Grok ignore it. If every skill is distributed only in this repo, the root LICENSE is the single owner.
- Will the pack keep `duckdb-python` as a separate skill if it stays at 43 lines? PLAN says keep 12; the structural fix is to give it task H2s, not to merge it silently.
