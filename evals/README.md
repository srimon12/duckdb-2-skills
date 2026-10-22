# Evals

The pack has three failure modes worth testing. A skill does not fire when it should, a sibling fires instead, or the right skill produces a plausible result that does not survive a row-count or type check. The first two are trigger cases. The third is the ingest task case.

## Manual loop

1. Install the pack with the client you ship to.
2. Open a fresh session. Do not name the skill in the prompt.
3. Send one row from [triggers.md](triggers.md).
4. Record three things: which skill loaded, the first command or refusal, and whether that matches the expected action.
5. Repeat three times. A description passes when the expected signal appears in all three and no wrong sibling loads.

The prompt should be something a user would type. If it names the skill, it tests the skill body, not the trigger.

## Scoring

| Result | Meaning |
| --- | --- |
| PASS | Expected skill loads and the first action matches. |
| PARTIAL | Right skill, wrong first action. The body needs a stronger rule. |
| FAIL | Wrong skill, no skill, or invented syntax. The description or the route table needs work. |

Run the trigger suite after a description change. Run the owning skill's task cases after a body or code change. Run the whole table before a release.

## Ingest task case

The file-to-Parquet workflow lives in `duckdb-files/references/ingest.md`. Its case is [ingest](ingest/README.md). The prompt is organic and the grader is deterministic. It checks the kept row count, the quarantine count, the declared types, the month partitions, the amount total, and the Parquet footer count. The reference run is:

```bash
bash evals/ingest/run_reference.sh
```

The case is blind in practice. Give the candidate `prompt.md` and the generated `orders.csv`, not the truth file, the solution, or this directory.

## Optional harness

Claude Code can run a case directory with `claude plugin eval .` when the CLI is installed. A case is a folder with `prompt.md` and at least one grader in `graders/`. Use a skill-selection grader for routing, a regex grader for an exact command, and one model-graded rubric for a decision. Do not grade tone, length, or formatting.

This repo keeps the cases in one table so every client can use them. Add a case directory only when a harness needs to run it automatically.

## What a good case checks

- The version gate fires before SQL runs.
- The exact flag, function, or column appears.
- A refusal happens before a destructive or unsupported action.
- The answer cites the manual page, not a guess.
- A wrong sibling does not load.

Pin the model and record its name with the result. A trigger that passes on one model and fails on another is a description problem, not a model problem.
