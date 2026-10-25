# Skill design: from primitives to workflows

This repo ships skills, not a manual. A skill earns its place by changing what an agent does on the next command. The unit of value is not a fact the agent can quote. It is a decision the agent makes correctly without a human in the loop.

This guide is for anyone adding or rewriting a skill. It explains the pack's abstraction ladder, the contract a high-level skill must carry, where each kind of content belongs, and how to prove the result.

## The abstraction ladder

| Level | Question the agent can answer | Example | Test |
| --- | --- | --- | --- |
| Primitive | What can I call? | `read_parquet`, `EXPLAIN`, `ATTACH` | Does the command run? |
| Pattern | What sequence solves this shape of task? | read, cast, split good and bad rows | Does it produce the expected rows? |
| Workflow | What contract survives a rerun, bad input, or a partial failure? | [batch ingest](../skills/duckdb-files/references/ingest.md) | Does the proof hold on a deliberately bad fixture? |
| Abstraction | Can the agent handle a case the examples did not cover? | [query and file diagnostics](../skills/duckdb-profile/SKILL.md) | Does it localize a failure it has not seen? |

A fact sheet is level 0. A recipe is level 1. The pack needs level 2 and 3 for every owner. A skill that only lists options leaves the agent to invent the composition, and the invention is where the wrong answer enters.

The product is not the primitive. The product is the composition, the failure handling, and the proof.

## What a high-level skill carries

A skill that reaches the workflow or abstraction level has these parts. Not every skill needs every part, but a missing part needs a reason.

| Part | Job | Example |
| --- | --- | --- |
| Trigger | Names the user nouns and symptoms that select this skill | "slow query", "row group", "schema drift" |
| Contract | Inputs, outputs, invariants, and what counts as success | "input rows = kept rows + quarantined rows" |
| State machine | The order of operations, including the failure branch | inspect, type, split, write, prove |
| Decision table | The condition before the command, with exact alternatives | "if the filter wraps a column, rewrite as a range" |
| Cost model | The resource the decision spends and the units it uses | rows, bytes, seconds, memory |
| Proof | A command or measurement that can fail | footer rows equal the kept row count |
| Stop rules | When to stop, refuse, or hand off | no `EXPLAIN ANALYZE` on a write |
| References | Lookup material, one level deep, linked at the decision point | operator map, option matrix |
| Scripts | A deterministic, repeated, fragile step | plan linter, eval fixture |

A skill without a contract is a list. A skill without a proof cannot tell success from a plausible failure. A skill without stop rules will overreach.

## The contract

Write the contract before the prose. A useful contract fits in five lines.

```text
Inputs:      one CSV path, one output directory, one partition key
Outputs:     partitioned Parquet, quarantine Parquet, proof file
Invariants:  input rows = kept rows + distinct quarantined lines
Failure:     a bad row is quarantined with a reason, never nulled silently
Proof:       sum of Parquet footer rows equals the kept count
```

For a diagnosis skill:

```text
Inputs:      query, data snapshot, binary, settings, budget
Outputs:     one dominant cause, one change, before/after evidence
Invariants:  same query, same data, same binary, same settings
Failure:     a wrong answer is not a performance problem
Proof:       the same baseline reruns with lower cost and correct rows
```

If you cannot write the proof, the workflow is not ready. If the proof needs a human to eyeball a table, make it deterministic.

## The decision procedure

An agent reads a skill while holding a specific task. Every sentence should answer one of three questions:

1. Does this change the next command?
2. Does this prevent a wrong move?
3. Does this prove the result?

Delete a sentence that answers none of them. This is why the skill body does not restate the manual, narrate history, or list every option.

Use the condition before the instruction. The condition is the part the agent has to recognize.

| Weak | Strong |
| --- | --- |
| "Use `ANALYZE` to improve statistics." | "If a base-table estimate is at least 100 times below the actual, run `ANALYZE table`." |
| "Consider partitioning." | "If the same selective filter runs repeatedly, partition by that column." |
| "Be careful with writes." | "Do not add `ANALYZE` to `INSERT`, `UPDATE`, `DELETE`, or `COPY`. It executes the write." |

Name the exact command, flag, function, column, or error string. A skill that says "check the plan" without naming the operator or field has moved the problem back to the agent.

## The cost model

A decision without a cost is a preference. Give the agent the unit it needs to compare alternatives.

| Decision | Cost unit | Useful threshold |
| --- | --- | --- |
| Scan a file or prune it | bytes read, row groups scanned | all groups scanned when a selective filter exists |
| Build a join side | rows, bytes | join output at least 10 times the largest input |
| Aggregate or sort | groups, intermediate bytes | intermediate rows above one million or bytes above hundreds of MB |
| Spill or raise memory | peak buffer memory, temp bytes | any positive `system.peak_temp_dir_size` |
| Rewrite files | write bytes, rewrite time | the query runs repeatedly, not once |

Label a heuristic as a heuristic. "100,000 to 1,000,000 rows per row group is a useful range" is advice. "`ROW_GROUP_SIZE` defaults to 122,880" is a fact. Do not mix them.

## The proof

A workflow ends with a command or measurement that can fail.

- Prefer a deterministic fixture over a live system.
- Prefer a count, a type, or a footer over a visual check.
- Make the expected output exact enough to diff.
- If the proof needs the network or a paid service, mark it as optional and provide a local path.

Examples:

```sql
SELECT sum(num_rows) FROM parquet_file_metadata('out/**/*.parquet');
```

```bash
python3 scripts/plan_lint.py --self-test
```

A proof that always passes is decoration. A proof that fails on a known bad input is a test.

## Stop rules and handoffs

The most expensive failure is a confident agent that keeps going after the useful work is done. Write the stop condition.

- Stop when the result meets the budget.
- Stop when the next change is larger than the remaining gap.
- Stop before a destructive or irreversible action. State the action and ask.
- Stop when the bottleneck is outside this skill. Hand off to the owner.

Handoffs are one line and one skill name. Do not restate the other skill's deep fact.

```markdown
A wrong value is not a profiling problem. Read `duckdb-sql` for the result traps first.
```

## Where content goes

| Content | Home | Rule |
| --- | --- | --- |
| A fact the agent must know before choosing a command | `SKILL.md` | Keep it short. One owner. |
| A lookup table used after the choice | `references/` | Link at the point of use. One level. |
| A deterministic, repeated, fragile step | `scripts/` | Executable, `--help`, explicit errors, no secrets. |
| A static fixture or template | `assets/` | Small, no binaries unless necessary. |
| Evidence, probes, and per-skill verdicts | `research/` | A claim without a source does not enter a skill. |
| A failure mode worth catching | `evals/` | Trigger, task, or refusal. |
| A guide for maintainers | `docs/` | Not loaded by the agent at task time. |

The split rule: if the agent must know it before the first command, keep it in `SKILL.md`. If it is a lookup after the choice, or used on fewer than half the runs, move it to a reference. If it is a step that must produce the same output every time, write a script.

Do not add a reference that repeats the skill body. Do not add a script that only wraps one command. Do not add a top-level skill when an existing owner already has the trigger.

## Writing rules

- Imperative mood. "Run", "check", "refuse".
- Condition before instruction.
- One claim per sentence. One command per block unless the sequence must be atomic.
- Exact nouns, flags, functions, columns, and errors.
- Units on every number.
- No history, no motivation, no "simply", no "just".
- No em dashes. No colon as a connector. No decorative tables.
- A warning names the wrong move and the correct move.
- A cross-link uses the skill name in backticks, not a URL to this repo.
- A code block always has a language.
- A reference opens with one sentence that says when to read it.

## Review checklist

Use this before a skill ships.

1. The description starts with the job and ends with a `Use when` clause.
2. The first action changes the next command, not the next paragraph.
3. The contract is explicit: inputs, outputs, invariants, failure.
4. The state machine covers the failure branch and the rerun.
5. The cost model names a unit and distinguishes facts from heuristics.
6. The proof can fail and is reproducible.
7. The stop and refusal rules come before a destructive action.
8. Every deep fact has one owner. Other skills link, not repeat.
9. References are one level deep and linked at the decision point.
10. The trigger table, probe, and research audit are updated in the same change.

## Worked example: diagnostics

The first version of `duckdb-profile` was a symptom table plus an operator map. It could answer "what is a Hash Join?" It could not reliably answer "why is this unseen query slow?"

The rewrite adds:

- A case file: question, baseline, budget, measurement, finding, proof.
- A cost model: rows, bytes, seconds, memory, and the join cardinality estimate.
- A failure-class catalog: non-sargable filter, layout, cardinality, statistics, memory, I/O, client, concurrency.
- A workflow for slow queries, OOM, remote scans, Parquet health, regression, and production-safe profiling.
- A script that captures the plan, ranks findings, and returns an exit code.
- A self-test that proves the linter finds a cross product and a full scan, and does not flag a sargable point lookup.

The abstraction is not the operator table. The abstraction is the decision procedure that uses the table.

## Worked example: ingest

`duckdb-files/references/ingest.md` did not become a new skill. `duckdb-files` already owned the reader, the COPY options, and the partition triggers. The new value was a contract and a proof:

```text
raw text -> typed rows -> good + quarantine -> partitioned Parquet -> input = kept + rejected
```

The task case in `evals/ingest` makes the contract executable. A separate ingest skill would have duplicated the triggers and split the owner. The reference is the right home because the workflow is used on a minority of file tasks, but when it is used, the proof matters.

## Anti-patterns

| Anti-pattern | Why it fails | Fix |
| --- | --- | --- |
| Manual restatement | The agent already has the manual; the skill adds no decision | Keep the decision and the failure mode |
| Feature list | The agent cannot tell which feature applies | Turn it into a decision table |
| Recipe without a proof | A plausible wrong answer passes | Add a count, type, or footer check |
| Hidden side effect | `EXPLAIN ANALYZE` runs writes | Say it before the command, not after |
| "Just use X" | Hides the tradeoff and the exception | Name the condition and the alternative |
| No stop condition | The agent keeps optimizing or rewriting | Add a budget and a stop rule |
| Duplicated deep fact | Two skills drift | Pick one owner and link |
| Reference chain | The agent reads the first 100 lines and misses the rule | One level, linked at the point of use |
| Decorative script | Adds maintenance without changing the answer | Keep the command in the skill |
| Date in the body | Goes stale and reads as history | Put it in `research/` |

## Keeping the pack in sync

A skill change is a pack change. Update these in the same commit:

- `README.md`: skill table, counts, install notes.
- `CONTRIBUTING.md`: owner map and reference list.
- `research/08-skill-audit.md`: what changed and why.
- `research/09-verified-facts.md`: new probes and confidence.
- `evals/triggers.md`: a prompt for each changed description.
- `evals/`: a task case when the proof changed.
- `scripts/probe.py`: an executable claim when the fact is executable.
- `scripts/check-skills.py`: a structural rule when the same mistake can recur.
- `.claude-plugin/plugin.json`: version when the release changes.

The pack is small enough that a stale count is a credibility problem. Treat the docs as part of the product.
