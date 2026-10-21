# Research method

This folder is the evidence base for the skills in `skills/`. A skill may compress a fact. It may not invent one.

## Source order

1. The DuckDB 2.0 manual snapshot in `sources/duckdb-2.0/`, taken from `duckdb/duckdb-web` at commit `37408677c0753c0b3607f8b77540df7f3096be95`.
2. The DuckLake manual snapshot in `sources/ducklake-stable/`, taken from `duckdb/ducklake-web` at commit `1b74f10e93a3905e247c12f30b8882ca683db8f4`.
3. Live pages on `duckdb.org`, `ducklake.select`, `docs.overturemaps.org`, and the GitHub release notes, for material published after the snapshot.
4. A local DuckDB binary. Every executable claim gets a probe. Record the command and the observed output.

A vendor blog post is evidence for intent. The manual and the binary are evidence for behavior. When they disagree, the binary wins and the slice records the disagreement.

## Confidence labels

- **Probed**: run against DuckDB 2.0.0 in this repo. Command and output are in the slice.
- **Documented**: stated by the 2.0 manual or DuckLake stable manual. Page path is in the slice.
- **Announced**: stated only in a release post or blog. Treat as intent, not a frozen contract.
- **Uncertain**: sources conflict, the page is ambiguous, or no probe was possible. Say what would settle it.

## Rules

- Quote exact syntax. Do not paraphrase a signature.
- One claim per row. Link the page path, not the site root.
- Separate "the skill is wrong" from "the skill is thin". They get different fixes.
- Rank gaps by what an agent would get wrong without them. A fact that changes a decision outranks a fact that is merely interesting.
- Name what does **not** deserve space. A skill pack fails by accretion as often as by omission.
- Do not edit files under `skills/`. Research workers write one slice file and their own scratch directory.
- Keep the slice under 450 lines. Tables beat paragraphs.

## Slice schema

```markdown
# Slice: <name>

Status: complete | partial
Scope: <what this slice owns>
Sources: <paths and URLs>

## Verified facts
| # | Claim | Evidence | Confidence |

## Existing skill audit
| Skill | Claim or omission | Verdict | Fix |

## Gaps worth adding
| Rank | Gap | Why an agent needs it | Home: SKILL.md or reference |

## Traps and contradictions
| Trap | What happens | Correct move | Evidence |

## What not to add
- <item and reason>

## Probe log
```text
$ command
output
```

## Open questions
- <question, and what would settle it>
```
