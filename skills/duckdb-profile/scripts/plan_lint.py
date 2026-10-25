#!/usr/bin/env python3
"""Turn a DuckDB 2.0 plan into ranked, evidence-backed findings.

Default mode is plan-only: it runs EXPLAIN and never executes the query.
Pass --analyze to run EXPLAIN ANALYZE, which executes the statement.

Examples:
    python3 plan_lint.py --query "SELECT * FROM a, b"
    python3 plan_lint.py --db analytics.duckdb --query-file slow.sql --analyze
    python3 plan_lint.py --query "SELECT ..." --json
    python3 plan_lint.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

SCAN_TYPES = {
    "TABLE_SCAN",
    "SEQ_SCAN",
    "PARQUET_SCAN",
    "READ_CSV",
    "READ_JSON",
    "READ_AVRO",
    "READ_XLSX",
    "DELIM_SCAN",
    "CHUNK_SCAN",
    "EXPRESSION_SCAN",
    "SAMPLE",
}

METADATA_TYPES = {"COLUMN_DATA_SCAN"}

JOIN_TYPES = {
    "HASH_JOIN",
    "CROSS_PRODUCT",
    "PIECEWISE_MERGE_JOIN",
    "NESTED_LOOP_JOIN",
    "BLOCKWISE_NL_JOIN",
    "DELIM_JOIN",
    "LEFT_DELIM_JOIN",
    "RIGHT_DELIM_JOIN",
    "IE_JOIN",
    "ASOF_JOIN",
}

BLOCKING_TYPES = {
    "HASH_GROUP_BY",
    "PERFECT_HASH_GROUP_BY",
    "ORDER_BY",
    "TOP_N",
    "WINDOW",
    "HASH_JOIN",
    "PIECEWISE_MERGE_JOIN",
    "DELIM_JOIN",
    "LEFT_DELIM_JOIN",
    "RIGHT_DELIM_JOIN",
    "IE_JOIN",
}

WRAPPER_TYPES = {"RESULT_COLLECTOR", "EXPLAIN_ANALYZE", "EXPLAIN"}

WRITE_WORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|COPY|CREATE|DROP|ALTER|TRUNCATE|"
    r"ATTACH|DETACH|CALL|EXPORT|IMPORT|VACUUM|CHECKPOINT|LOAD|INSTALL)\b",
    re.IGNORECASE,
)


@dataclass
class Node:
    name: str
    depth: int
    children: list["Node"] = field(default_factory=list)
    parent: "Node | None" = None
    est: float | None = None
    actual: float | None = None
    time: float | None = None
    bytes_out: float | None = None
    rows_scanned: float | None = None
    row_groups_scanned: float | None = None
    row_groups_total: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> str:
        if self.parent is None:
            return self.name
        return f"{self.parent.path} > {self.name}"


@dataclass
class Finding:
    code: str
    severity: str
    title: str
    evidence: str
    move: str
    prove: str
    node: str = ""
    score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "title": self.title,
            "evidence": self.evidence,
            "move": self.move,
            "prove": self.prove,
            "node": self.node,
        }


def strip_sql(sql: str) -> str:
    """Replace comments and string literals so keyword checks do not fire on data."""
    out: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            while i < n and sql[i] != "\n":
                i += 1
        elif ch == "/" and i + 1 < n and sql[i + 1] == "*":
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
        elif ch in ("'", '"', "`"):
            quote = ch
            i += 1
            while i < n:
                if sql[i] == quote:
                    if quote != "`" and i + 1 < n and sql[i + 1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                if sql[i] == "\\" and quote == "'":
                    i += 2
                else:
                    i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def has_multiple_statements(sql: str) -> bool:
    cleaned = strip_sql(sql).strip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1]
    return ";" in cleaned


def parse_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "NULL", "None"}:
        return None
    text = text.lstrip("~").strip()
    try:
        return float(text)
    except ValueError:
        return None


def extra(node: dict[str, Any], key: str) -> Any:
    info = node.get("extra_info") or {}
    if key in info:
        return info[key]
    lowered = key.lower()
    for existing, value in info.items():
        if existing.lower() == lowered:
            return value
    return None


def build_node(raw: dict[str, Any], depth: int = 0, parent: Node | None = None) -> Node:
    name = str(raw.get("type") or raw.get("name") or "UNKNOWN").upper()
    node = Node(
        name=name,
        depth=depth,
        parent=parent,
        est=parse_number(extra(raw, "Estimated Cardinality")),
        actual=parse_number(raw.get("intermediate_rows")),
        time=parse_number(raw.get("timing")),
        bytes_out=parse_number(raw.get("intermediate_size_bytes")),
        rows_scanned=parse_number(raw.get("rows_scanned")),
        row_groups_scanned=parse_number(raw.get("row_groups_scanned")),
        row_groups_total=parse_number(raw.get("total_row_groups_to_scan")),
        extra=dict(raw.get("extra_info") or {}),
    )
    for child_raw in raw.get("children") or []:
        if isinstance(child_raw, dict):
            node.children.append(build_node(child_raw, depth + 1, node))
    return node


def parse_plan(text: str) -> tuple[str, dict[str, Any], list[Node]]:
    """Return (mode, metadata, roots) for plan-only or analyzed JSON."""
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    starts = [index for index in (text.find("{"), text.find("[")) if index >= 0]
    if starts:
        text = text[min(starts) :]
    decoder = json.JSONDecoder()
    values: list[Any] = []
    pos = 0
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            break
        try:
            value, end = decoder.raw_decode(text, pos)
        except json.JSONDecodeError as exc:
            raise ValueError(f"could not parse DuckDB JSON at offset {pos}: {exc}") from exc
        values.append(value)
        pos = end
    if not values:
        raise ValueError("DuckDB returned no JSON")
    value = values[-1]
    if isinstance(value, dict) and "operator" in value:
        roots = [build_node(raw) for raw in value.get("operator") or [] if isinstance(raw, dict)]
        return "analyzed", value, roots
    if isinstance(value, dict) and "latency" in value and "children" in value:
        raise ValueError(
            "legacy_metrics_format is on; run SET legacy_metrics_format=false before using plan_lint"
        )
    if isinstance(value, dict) and "result" in value and "operator" not in value:
        return "no_profile", value, []
    if isinstance(value, dict) and ("name" in value or "type" in value):
        return "plan", {}, [build_node(value)]
    if isinstance(value, list):
        roots = [build_node(raw) for raw in value if isinstance(raw, dict)]
        return "plan", {}, roots
    raise ValueError(f"unrecognized DuckDB plan shape: {type(value).__name__}")


def walk(nodes: Iterable[Node]) -> Iterable[Node]:
    for node in nodes:
        yield node
        yield from walk(node.children)


def child_sum(node: Node) -> float:
    return sum(child.actual or 0.0 for child in node.children)


def fmt_num(value: float | None) -> str:
    if value is None:
        return "?"
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}k"
    if value == int(value):
        return str(int(value))
    return f"{value:.3g}"


def fmt_bytes(value: float | None) -> str:
    if value is None:
        return "?"
    units = ["B", "kB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if abs(size) < 1000 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1000
    return f"{value:.1f} B"


def fmt_time(value: float | None) -> str:
    if value is None:
        return "?"
    if value < 0.001:
        return f"{value * 1_000_000:.0f}us"
    if value < 1:
        return f"{value * 1000:.1f}ms"
    return f"{value:.2f}s"


def add(findings: list[Finding], finding: Finding) -> None:
    findings.append(finding)


def diagnose(roots: list[Node], meta: dict[str, Any], mode: str) -> list[Finding]:
    findings: list[Finding] = []
    nodes = list(walk(roots))

    system = meta.get("system") or {}
    io = meta.get("io") or {}
    query = meta.get("query") or {}
    peak_temp = parse_number(system.get("peak_temp_dir_size"))
    peak_buffer = parse_number(system.get("peak_buffer_memory"))
    total_read = parse_number(io.get("total_bytes_read"))
    total_written = parse_number(io.get("total_bytes_written"))

    if mode == "no_profile" or not roots:
        add(
            findings,
            Finding(
                code="no_profile",
                severity="info",
                title="No operator profile was produced",
                evidence=(
                    "The query returned a result but DuckDB had no profiler root. "
                    "This commonly means a metadata-only plan such as count(*), min, or max, "
                    "or a DDL statement. It is not a query failure."
                ),
                move=(
                    "Check the query result separately. If you meant to measure scan work, "
                    "use a row-level filter or select a column, then rerun with --analyze."
                ),
                prove="Compare the query result with a plan that contains a real scan.",
                score=1,
            ),
        )
        return findings

    if peak_temp and peak_temp > 0:
        add(
            findings,
            Finding(
                code="spill",
                severity="critical",
                title="Query spilled to the temporary directory",
                evidence=(
                    f"system.peak_temp_dir_size = {fmt_bytes(peak_temp)}; "
                    f"system.peak_buffer_memory = {fmt_bytes(peak_buffer)}; "
                    f"io.total_bytes_written = {fmt_bytes(total_written)}"
                ),
                move=(
                    "Find the blocking operator with the largest intermediate row count. "
                    "Reduce it with a pre-filter or pre-aggregate before touching memory_limit. "
                    "If the spill is unavoidable, put temp_directory on a local SSD and raise max_temp_directory_size."
                ),
                prove=(
                    "Rerun the same query with the same binary and compare "
                    "system.peak_temp_dir_size and query.total_time."
                ),
                score=peak_temp,
            ),
        )

    for node in nodes:
        if node.name in {"CROSS_PRODUCT"}:
            out = node.actual if node.actual is not None else node.est
            child_total = child_sum(node)
            severity = "critical" if (out or child_total) >= 10_000 else "high"
            add(
                findings,
                Finding(
                    code="cross_product",
                    severity=severity,
                    title="Cross product" + (" on large inputs" if severity == "critical" else ""),
                    evidence=(
                        f"node output = {fmt_num(node.actual)} rows; "
                        f"children = {fmt_num(child_sum(node))} rows"
                    ),
                    move=(
                        "Add the missing equality predicate. If the cross product is deliberate, "
                        "keep both inputs tiny and say so with ON true or a comment."
                    ),
                    prove="Rerun EXPLAIN ANALYZE and confirm the node is HASH_JOIN or the output is bounded.",
                    node=node.path,
                    score=(out or child_total) + 1,
                ),
            )

        if node.name in {"NESTED_LOOP_JOIN", "BLOCKWISE_NL_JOIN"}:
            out = node.actual or node.est or 0
            if out >= 100_000:
                add(
                    findings,
                    Finding(
                        code="nested_loop",
                        severity="high" if out >= 1_000_000 else "medium",
                        title="Nested-loop join on a large input",
                        evidence=f"node output = {fmt_num(out)} rows",
                        move=(
                            "Look for an equality rewrite, a range join with a smaller key, "
                            "or a pre-aggregation on the outer side."
                        ),
                        prove="Rerun EXPLAIN ANALYZE and compare the join input and output rows.",
                        node=node.path,
                        score=out,
                    ),
                )

        if node.name in METADATA_TYPES:
            add(
                findings,
                Finding(
                    code="metadata_only",
                    severity="info",
                    title="Plan is answered from metadata",
                    evidence=(
                        "The plan contains COLUMN_DATA_SCAN, so DuckDB did not scan a data file. "
                        "This is common for count(*), min, and max over a single table or Parquet file."
                    ),
                    move=(
                        "Do not use this query as a scan benchmark. Add a row-level filter "
                        "or select a data column, then measure again."
                    ),
                    prove="A real scan appears only after a row-level filter or a data-column projection.",
                    node=node.path,
                    score=1,
                ),
            )

        if node.name in SCAN_TYPES:
            scanned = node.row_groups_scanned
            total = node.row_groups_total
            filters = str(extra({"extra_info": node.extra}, "Filters") or "").strip()
            dynamic = str(extra({"extra_info": node.extra}, "Dynamic Filters") or "").strip()
            if dynamic:
                add(
                    findings,
                    Finding(
                        code="dynamic_filter",
                        severity="info",
                        title="Runtime filter is pruning this scan",
                        evidence=f"Dynamic Filters: {dynamic}",
                        move=(
                            "This pruning exists only during execution. Do not judge the plan by "
                            "the plan-only tree; compare Row Groups Scanned in the analyzed profile."
                        ),
                        prove="Rerun plan-only and analyzed; the analyzed scan should read fewer groups.",
                        node=node.path,
                        score=1,
                    ),
                )
            if total and total >= 2 and scanned is not None and scanned >= total:
                severity = "high" if filters else "medium"
                add(
                    findings,
                    Finding(
                        code="full_scan",
                        severity=severity,
                        title="Scan read every row group",
                        evidence=(
                            f"Row Groups Scanned: {fmt_num(scanned)} / {fmt_num(total)}; "
                            f"Filters: {filters or '(none)'}; "
                            f"rows_scanned: {fmt_num(node.rows_scanned)}"
                        ),
                        move=(
                            "If a filter exists, make it a range on the bare column. "
                            "A cast or function around the data column defeats pruning; a foldable "
                            "expression on a partition column can still prune files. "
                            "If the data is unsorted, sort or partition by the filter column before writing. "
                            "Remember that the denominator is after file-list pruning, so 1/1 can mean "
                            "one selected file, not a healthy dataset. If there is no filter, confirm "
                            "the full scan is intended."
                        ),
                        prove=(
                            "Rerun EXPLAIN ANALYZE and confirm Row Groups Scanned is below the total, "
                            "or that Data Read fell."
                        ),
                        node=node.path,
                        score=(node.rows_scanned or 0) + 1,
                    ),
                )
            if (
                node.rows_scanned == 0
                and node.row_groups_scanned
                and node.row_groups_scanned > 0
            ):
                add(
                    findings,
                    Finding(
                        code="scan_zero_output",
                        severity="info",
                        title="Scan read row groups but emitted no rows",
                        evidence=(
                            f"Row Groups Scanned: {fmt_num(node.row_groups_scanned)} / "
                            f"{fmt_num(node.row_groups_total)}; rows_scanned: 0"
                        ),
                        move=(
                            "The filter matched nothing after the scan. Check the predicate and the "
                            "row-group statistics; this is a valid empty result, not a scan failure."
                        ),
                        prove="Rerun with a predicate that should match one row.",
                        node=node.path,
                        score=1,
                    ),
                )

        if node.actual and node.est and node.actual >= 1000:
            ratio = node.actual / max(node.est, 1e-9)
            if ratio >= 100 or ratio <= 0.01:
                severity = "high" if ratio >= 1000 or ratio <= 0.001 else "medium"
                direction = "under" if ratio >= 1 else "over"
                add(
                    findings,
                    Finding(
                        code="estimate_gap",
                        severity=severity,
                        title=f"Planner {direction}estimated rows at {node.name}",
                        evidence=(
                            f"estimated = {fmt_num(node.est)}; actual = {fmt_num(node.actual)}; "
                            f"ratio = {ratio:.3g}x"
                        ),
                        move=(
                            "For a base table, run ANALYZE and check whether the predicate is selective. "
                            "For a join, check the key cardinality and whether the filter was pushed down. "
                            "Do not add LIMIT to a blocking operator to hide the gap."
                        ),
                        prove="Rerun EXPLAIN and compare the estimated rows at the same node.",
                        node=node.path,
                        score=(node.actual or 0) * abs(ratio - 1) ** 0.5,
                    ),
                )

        if node.name in JOIN_TYPES and node.name != "CROSS_PRODUCT" and node.actual and node.children:
            largest_child = max((child.actual or 0) for child in node.children)
            if largest_child and node.actual >= 10_000 and node.actual >= largest_child * 10:
                add(
                    findings,
                    Finding(
                        code="join_multiplication",
                        severity="high",
                        title="Join output is much larger than either input",
                        evidence=(
                            f"join output = {fmt_num(node.actual)} rows; "
                            f"largest input = {fmt_num(largest_child)} rows; "
                            f"multiplier = {node.actual / largest_child:.0f}x"
                        ),
                        move=(
                            "Check for a many-to-many key. Pre-aggregate or deduplicate the build side, "
                            "or join on a key with the intended cardinality."
                        ),
                        prove="Rerun EXPLAIN ANALYZE and compare the join output with the input sizes.",
                        node=node.path,
                        score=node.actual,
                    ),
                )

        if node.name in BLOCKING_TYPES and node.actual and node.actual >= 1_000_000:
            add(
                findings,
                Finding(
                    code="blocking_operator",
                    severity="medium",
                    title="Blocking operator receives a large intermediate result",
                    evidence=(
                        f"{node.name}: intermediate_rows = {fmt_num(node.actual)}; "
                        f"intermediate_size_bytes = {fmt_bytes(node.bytes_out)}. "
                        "intermediate_size_bytes is the output chunk footprint, not hash-table or sort memory."
                    ),
                    move=(
                        "Filter or aggregate before this operator. If the shape cannot change, "
                        "check system.peak_buffer_memory and system.peak_temp_dir_size, then "
                        "raise memory_limit or add temp_directory in that order of preference."
                    ),
                    prove="Rerun EXPLAIN ANALYZE and compare intermediate rows and peak buffer memory.",
                    node=node.path,
                    score=node.actual,
                ),
            )

        if node.actual and node.actual >= 1_000_000 and node.time and node.time > 0:
            total_time = sum((n.time or 0) for n in nodes if n.name not in WRAPPER_TYPES)
            if (
                total_time > 0
                and node.time / total_time >= 0.5
                and node.name not in WRAPPER_TYPES
                and node.name not in SCAN_TYPES
            ):
                add(
                    findings,
                    Finding(
                        code="time_hotspot",
                        severity="medium",
                        title="One operator dominates execution time",
                        evidence=(
                            f"{node.name} time = {fmt_time(node.time)}; "
                            f"share = {100 * node.time / total_time:.0f}% of measured operator time"
                        ),
                        move="Optimize this operator first. A change elsewhere cannot beat Amdahl's law.",
                        prove="Rerun EXPLAIN ANALYZE and compare this operator's time and share.",
                        node=node.path,
                        score=node.time * 1000,
                    ),
                )

    if total_read and total_read >= 1_000_000_000:
        add(
            findings,
            Finding(
                code="io_heavy",
                severity="low",
                title="Query read at least 1 GB",
                evidence=(
                    f"io.total_bytes_read = {fmt_bytes(total_read)}"
                    + (
                        "; includes spill reads because system.peak_temp_dir_size is positive"
                        if peak_temp and peak_temp > 0
                        else ""
                    )
                ),
                move=(
                    "Check projection, partition pruning, and file count before adding threads. "
                    "For remote data, compare Data Read with the compressed file size. "
                    "If the query spilled, Data Read is an upper bound, not the scan bytes."
                ),
                prove="Rerun and compare io.total_bytes_read.",
                score=total_read,
            ),
        )

    if mode == "plan":
        add(
            findings,
            Finding(
                code="plan_only",
                severity="info",
                title="Estimates only",
                evidence="The plan did not execute, so actual rows, timings, row-group scans, and spill are absent.",
                move="Run the same command with --analyze on a safe copy or a bounded query to measure actuals.",
                prove="Compare the estimate with the actual at the same operator.",
            ),
        )

    dedup: dict[tuple[str, str], Finding] = {}
    for finding in findings:
        key = (finding.code, finding.node or finding.title)
        current = dedup.get(key)
        if current is None or SEVERITY_ORDER[finding.severity] < SEVERITY_ORDER[current.severity]:
            dedup[key] = finding
    ordered = sorted(
        dedup.values(),
        key=lambda f: (SEVERITY_ORDER[f.severity], -f.score, f.title),
    )
    return ordered


def render_setting(setting: str) -> str:
    """Quote a bare setting value so --set memory_limit=100MB works."""
    key, separator, raw = setting.partition("=")
    if not separator or not key.strip() or raw == "":
        raise ValueError(f"setting must look like key=value, got {setting!r}")
    value = raw.strip()
    bare = (
        value[0] in "'\"[$"
        or value.lower() in {"true", "false", "null"}
        or re.fullmatch(r"-?\d+(?:\.\d+)?", value) is not None
    )
    if not bare:
        value = "'" + value.replace("'", "''") + "'"
    return f"SET {key.strip()} = {value};"


def run_duckdb(
    duckdb_bin: str,
    sql: str,
    db: str | None,
    timeout: int,
    readonly: bool,
    settings: list[str],
) -> subprocess.CompletedProcess[str]:
    prefix = "SET explain_output = 'physical_only';\n"
    prefix += "".join(render_setting(setting) + "\n" for setting in settings)
    command = [duckdb_bin, "-no-agent", "-json"]
    if readonly:
        command.append("-readonly")
    if db:
        command.append(db)
    command.extend(["-c", prefix + sql])
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def make_query(analyze: bool, query: str) -> str:
    statement = query.strip()
    if statement.endswith(";"):
        statement = statement[:-1]
    verb = "EXPLAIN ANALYZE (FORMAT JSON)" if analyze else "EXPLAIN (FORMAT JSON)"
    return f"{verb}\n{statement}"


def render_markdown(
    mode: str,
    query: str,
    meta: dict[str, Any],
    roots: list[Node],
    findings: list[Finding],
    top: int,
) -> str:
    query_meta = meta.get("query") or {}
    io = meta.get("io") or {}
    system = meta.get("system") or {}
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    verdict = ", ".join(
        f"{counts[level]} {level}" for level in ("critical", "high", "medium", "low") if counts.get(level)
    ) or ("no profile (metadata-only or DDL)" if mode == "no_profile" else "no defects found")

    lines: list[str] = []
    lines.append("# Plan diagnosis")
    lines.append("")
    executed = mode in {"analyzed", "no_profile"}
    lines.append(f"**Mode:** {mode} (query {'executed' if executed else 'not executed'})")
    lines.append(f"**Verdict:** {verdict}")
    lines.append("")
    lines.append("**Query:**")
    lines.append("")
    lines.append("```sql")
    lines.append(query.strip()[:4000])
    lines.append("```")
    lines.append("")
    if mode == "analyzed":
        lines.append("## Measurements")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("| --- | --- |")
        lines.append(f"| Query total time | {fmt_time(parse_number(query_meta.get('total_time')))} |")
        lines.append(f"| Rows scanned | {fmt_num(parse_number(query_meta.get('total_rows_scanned')))} |")
        lines.append(f"| Row groups scanned | {fmt_num(parse_number(query_meta.get('total_row_groups_scanned')))} |")
        lines.append(f"| Intermediate rows | {fmt_num(parse_number(query_meta.get('total_intermediate_rows')))} |")
        lines.append(f"| Data read | {fmt_bytes(parse_number(io.get('total_bytes_read')))} |")
        lines.append(f"| Peak buffer memory | {fmt_bytes(parse_number(system.get('peak_buffer_memory')))} |")
        lines.append(f"| Peak temp directory | {fmt_bytes(parse_number(system.get('peak_temp_dir_size')))} |")
        lines.append("")

    lines.append("## Findings")
    lines.append("")
    if not findings:
        lines.append("No structural defect passed the thresholds. The query may still be slow for reasons outside the plan: client fetch, serialization, lock waits, or a cold cache.")
        lines.append("")
    for index, finding in enumerate(findings[:top], 1):
        lines.append(f"### {index}. {finding.severity.upper()}: {finding.title}")
        lines.append("")
        if finding.node:
            lines.append(f"**Node:** `{finding.node}`")
            lines.append("")
        lines.append(f"**Evidence:** {finding.evidence}")
        lines.append("")
        lines.append(f"**Move:** {finding.move}")
        lines.append("")
        lines.append(f"**Prove:** {finding.prove}")
        lines.append("")

    measured = [n for n in walk(roots) if n.name not in WRAPPER_TYPES and n.time and n.time > 0]
    if measured:
        total_time = sum(n.time or 0 for n in measured)
        lines.append("## Cost centers")
        lines.append("")
        lines.append("| Operator | Actual rows | Time | Share |")
        lines.append("| --- | ---: | ---: | ---: |")
        for node in sorted(measured, key=lambda n: n.time or 0, reverse=True)[:8]:
            share = 100 * (node.time or 0) / total_time if total_time else 0
            lines.append(
                f"| `{node.name}` | {fmt_num(node.actual)} | {fmt_time(node.time)} | {share:.0f}% |"
            )
        lines.append("")
        lines.append("Operator times are exclusive. Their sum can differ from query total time because planning and serialization are outside the operator tree.")
        lines.append("")

    if roots:
        lines.append("## Operator tree")
        lines.append("")
        lines.append("```text")
        for node in walk(roots):
            bits = [node.name]
            if node.est is not None:
                bits.append(f"est={fmt_num(node.est)}")
            if node.actual is not None:
                bits.append(f"rows={fmt_num(node.actual)}")
            if node.time is not None:
                bits.append(f"time={fmt_time(node.time)}")
            if node.row_groups_total:
                bits.append(f"row_groups={fmt_num(node.row_groups_scanned)}/{fmt_num(node.row_groups_total)}")
            lines.append("  " * node.depth + " ".join(bits))
        lines.append("```")
        lines.append("")

    lines.append("## Stop rules")
    lines.append("")
    lines.append("- Do not run `EXPLAIN ANALYZE` on a write unless the write is intended. It executes the statement.")
    lines.append("- Do not add `LIMIT` to a blocking operator and call it a fix. The work happens before the limit.")
    lines.append("- Do not raise `memory_limit` before the query shape is fixed. A bigger limit hides the symptom.")
    lines.append("- Do not change file layout for a one-off query. Rewrite the query first.")
    lines.append("- Do not trust a plan-only estimate for row-group pruning or spill. Measure with `--analyze`.")
    return "\n".join(lines) + "\n"


def render_json(
    mode: str,
    query: str,
    meta: dict[str, Any],
    roots: list[Node],
    findings: list[Finding],
    top: int,
) -> str:
    nodes = [
        {
            "name": node.name,
            "depth": node.depth,
            "estimated_rows": node.est,
            "actual_rows": node.actual,
            "time_seconds": node.time,
            "intermediate_size_bytes": node.bytes_out,
            "rows_scanned": node.rows_scanned,
            "row_groups_scanned": node.row_groups_scanned,
            "row_groups_total": node.row_groups_total,
            "extra_info": node.extra,
        }
        for node in walk(roots)
    ]
    payload = {
        "mode": mode,
        "query": query,
        "findings": [finding.as_dict() for finding in findings[:top]],
        "metrics": {
            "result": meta.get("result"),
            "query": meta.get("query"),
            "io": meta.get("io"),
            "system": meta.get("system"),
        },
        "operators": nodes,
    }
    return json.dumps(payload, indent=2, default=str) + "\n"


def self_test(duckdb_bin: str) -> int:
    """Build a small deterministic database and assert the linter finds known defects."""
    with tempfile.TemporaryDirectory(prefix="plan-lint-") as tmp:
        db = str(Path(tmp) / "test.duckdb")
        setup = (
            "CREATE TABLE a AS SELECT range AS i FROM range(1000);"
            "CREATE TABLE b AS SELECT range AS i FROM range(1000);"
            "COPY (SELECT range AS id FROM range(100000) ORDER BY id) "
            f"TO '{tmp}/sorted.parquet' (FORMAT parquet, ROW_GROUP_SIZE 10000);"
        )
        proc = subprocess.run(
            [duckdb_bin, "-no-agent", db, "-c", setup],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            print(f"setup failed: {proc.stderr}", file=sys.stderr)
            return 2

        cases = [
            (
                "cross join",
                "SELECT count(*) FROM a, b",
                True,
                "cross_product",
            ),
            (
                "non-sargable filter",
                f"SELECT count(*) FROM '{tmp}/sorted.parquet' "
                "WHERE CAST(id AS VARCHAR) LIKE '1%'",
                True,
                "full_scan",
            ),
            (
                "sargable filter",
                f"SELECT count(*) FROM '{tmp}/sorted.parquet' WHERE id = 99999",
                True,
                None,
            ),
            (
                "metadata-only count",
                f"SELECT count(*) FROM '{tmp}/sorted.parquet'",
                True,
                "no_profile",
            ),
        ]
        failures = 0
        for label, query, analyze, expected in cases:
            mode, meta, roots = load_and_diagnose(duckdb_bin, db, query, analyze, [], 120)
            findings = diagnose(roots, meta, mode)
            codes = {finding.code for finding in findings}
            if expected and expected not in codes:
                print(f"FAIL {label}: expected {expected}, got {sorted(codes)}")
                failures += 1
            elif expected is None and "full_scan" in codes:
                print(f"FAIL {label}: unexpected full_scan")
                failures += 1
            else:
                print(f"PASS {label}: {sorted(codes)}")
    return 1 if failures else 0


def load_and_diagnose(
    duckdb_bin: str,
    db: str | None,
    query: str,
    analyze: bool,
    settings: list[str],
    timeout: int,
) -> tuple[str, dict[str, Any], list[Node]]:
    proc = run_duckdb(duckdb_bin, make_query(analyze, query), db, timeout, False, settings)
    if proc.returncode != 0:
        message = proc.stderr.strip().splitlines()
        raise RuntimeError(message[0] if message else "duckdb failed")
    return parse_plan(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint a DuckDB 2.0 query plan and return ranked findings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "By default the query is only explained. --analyze executes it.\n"
            "Examples:\n"
            "  plan_lint.py --query 'SELECT * FROM a, b'\n"
            "  plan_lint.py --db app.duckdb --query-file slow.sql --analyze\n"
            "  plan_lint.py --query 'SELECT ...' --json"
        ),
    )
    parser.add_argument("--query", help="SQL to diagnose. Mutually exclusive with --query-file.")
    parser.add_argument("--query-file", type=Path, help="Read SQL from a file.")
    parser.add_argument("--db", help="Database file to open before the query.")
    parser.add_argument("--analyze", action="store_true", help="Run EXPLAIN ANALYZE. Executes the statement.")
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Permit --analyze on a statement that looks like a write.",
    )
    parser.add_argument("--readonly", action="store_true", help="Open the database with -readonly.")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="SET before the query. Repeatable.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--top", type=int, default=10, help="Maximum findings to show (default: 10).")
    parser.add_argument("--timeout", type=int, default=120, help="DuckDB timeout in seconds (default: 120).")
    parser.add_argument("--duckdb", default=os.environ.get("DUCKDB", "duckdb"), help="DuckDB binary (default: $DUCKDB or duckdb).")
    parser.add_argument("--self-test", action="store_true", help="Run the built-in deterministic checks.")
    args = parser.parse_args()

    if args.self_test:
        try:
            return self_test(args.duckdb)
        except OSError as exc:
            print(f"error: cannot run {args.duckdb!r}: {exc}", file=sys.stderr)
            return 2

    if bool(args.query) == bool(args.query_file):
        parser.error("pass exactly one of --query or --query-file")
    query = args.query if args.query else args.query_file.read_text(encoding="utf-8")
    if not query.strip():
        parser.error("query is empty")
    if has_multiple_statements(query):
        parser.error("pass one statement, not a script")

    cleaned = strip_sql(query)
    if args.analyze and WRITE_WORDS.search(cleaned) and not args.allow_write:
        print(
            "refusing --analyze: the statement looks like a write. "
            "Use plan-only, a read-only copy, or pass --allow-write if the side effect is intended.",
            file=sys.stderr,
        )
        return 2

    try:
        mode, meta, roots = load_and_diagnose(
            args.duckdb, args.db, query, args.analyze, args.set, args.timeout
        )
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    findings = diagnose(roots, meta, mode)
    if args.json:
        sys.stdout.write(render_json(mode, query, meta, roots, findings, args.top))
    else:
        sys.stdout.write(render_markdown(mode, query, meta, roots, findings, args.top))

    worst = min((SEVERITY_ORDER[f.severity] for f in findings), default=SEVERITY_ORDER["info"])
    return 1 if worst <= SEVERITY_ORDER["high"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
