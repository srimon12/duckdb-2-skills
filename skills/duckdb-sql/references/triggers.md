# Trigger reference

Read this when the user asks for a trigger, an audit trail, a transition table, or a `RETURNING` rule that a trigger changes.

## Support matrix

| Shape | Status |
| --- | --- |
| `BEFORE INSERT/UPDATE/DELETE ... FOR EACH STATEMENT` | Works |
| `AFTER INSERT ... FOR EACH STATEMENT REFERENCING NEW TABLE` | Works |
| `AFTER UPDATE ... FOR EACH STATEMENT REFERENCING OLD TABLE, NEW TABLE` | Works |
| `AFTER DELETE ... FOR EACH STATEMENT REFERENCING OLD TABLE` | Works |
| `AFTER INSERT ... FOR EACH ROW` with `NEW.col` | Works |
| `AFTER DELETE ... FOR EACH ROW` with `OLD.col` | Works |
| `BEFORE ... FOR EACH ROW` | Not implemented |
| `AFTER UPDATE ... FOR EACH ROW` | Not implemented |
| Row trigger with `REFERENCING` | Binder error |
| Transition tables on a `BEFORE` trigger | Binder error |
| `UPDATE OF col` on a statement trigger | Works |
| `UPDATE OF` with transition tables | Binder error |
| `WHEN (...)` | Parser error |
| `INSTEAD OF`, triggers on views | Not supported |
| `CREATE TEMP TRIGGER` | Not supported |
| Trigger on a temporary table | Works when the body target is also temporary; `temporary = true` |

A table cannot mix statement-level and row-level triggers:

```text
Not implemented Error: Mixing FOR EACH STATEMENT and FOR EACH ROW triggers
on the same table is not yet supported
```

Choose one level per table. A trigger on a temporary table can reference only temporary objects. A body that writes to a main-catalog table fails:

```text
Binder Error: Trigger "x" cannot reference "a" from a different catalog ("memory")
```

## RETURNING

`RETURNING` is blocked per matching event. An `INSERT ... RETURNING` fails when the table has an `INSERT` row trigger, and a `DELETE ... RETURNING` fails with a `DELETE` row trigger. `UPDATE ... RETURNING` works with an `INSERT` row trigger. A table whose triggers are all statement-level allows `RETURNING`.

Check the trigger's event before you plan a `RETURNING` proof. If the event matches a row trigger, count before and after or use the CLI `.changes`.

## Ordering and naming

All `BEFORE` triggers fire before all `AFTER` triggers. Triggers on the same event fire in creation order. Names are unique per table. `CREATE OR REPLACE TRIGGER` and `IF NOT EXISTS` work, but not together.

Inspect with:

```sql
SELECT trigger_name, event_manipulation, action_timing, for_each, temporary
FROM duckdb_triggers();
```

## Statement-level audit

```sql
CREATE TRIGGER trg_audit
    AFTER UPDATE ON target
    REFERENCING OLD TABLE AS o NEW TABLE AS n
    FOR EACH STATEMENT
        INSERT INTO audit
        SELECT n.id, o.val, n.val
        FROM o
        JOIN n ON o.id = n.id;
```

## Incremental average

The announcement's `age_statistics` example maintains an average from `AFTER INSERT` and `AFTER DELETE` statement triggers. It has no update trigger, so an update leaves the average stale.

Add an `AFTER UPDATE` statement trigger. This form assumes the nationality does not change:

```sql
CREATE TRIGGER people_update
AFTER UPDATE ON people
REFERENCING OLD TABLE AS o NEW TABLE AS n
FOR EACH STATEMENT
    MERGE INTO age_statistics s
    USING (
        SELECT o.nationality, sum(n.age - o.age) AS delta
        FROM o JOIN n ON o.name = n.name
        GROUP BY o.nationality
    ) d
    ON s.nationality = d.nationality
    WHEN MATCHED THEN UPDATE SET
        sum_age = s.sum_age + d.delta,
        average_age = (s.sum_age + d.delta) / s.num_people;
```

A nationality change needs a decrement of the old group and an increment of the new group. `UPDATE ... FOR EACH ROW` is still unsupported. `MERGE INTO` cannot target a table with triggers.

## References

- https://duckdb.org/docs/2.0/sql/statements/create_trigger.html
- https://duckdb.org/docs/2.0/sql/statements/insert.html
- https://duckdb.org/docs/2.0/sql/statements/update.html
- https://duckdb.org/docs/2.0/sql/statements/delete.html
