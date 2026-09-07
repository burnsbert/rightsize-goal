#!/usr/bin/env python3
"""Record prompt-free, per-assignment Claude Code token usage in a local SQLite ledger.

Claude Code writes one JSONL transcript per session under
``<claude-dir>/projects/<project-slug>/<session-id>.jsonl`` and one per subagent
under ``<claude-dir>/projects/<project-slug>/<session-id>/subagents/agent-<agent-id>.jsonl``.
Every assistant record in those files carries its own ``message.usage`` counters,
the exact ``message.model`` that served it, and the ``effort`` used for that turn.

This helper reads only those metadata fields. It never copies prompts, responses,
tool arguments, or file contents into the ledger.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
from collections import defaultdict
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence, TextIO


DIFFICULTIES = ("basic", "routine", "moderate", "hard", "expert")
OUTCOMES = ("accepted", "rework", "unresolved", "cancelled", "failed")
TOKEN_FIELDS = ("input", "cache_read", "cache_write_5m", "cache_write_1h", "output")
RATE_FIELDS = TOKEN_FIELDS
ASSUMPTIONS = (
    "standard-rate API-equivalent baseline; excludes batch, fast mode, priority tier, "
    "long-context and service-tier modifiers, server tool fees, taxes, and plan billing "
    "adjustments; not an actual invoice"
)
# A single session can legitimately contain thousands of requests. Beyond this the
# baseline is refused rather than silently truncated into a wrong subtraction.
MAX_BASELINE_KEYS = 50_000


class UsageError(ValueError):
    """An expected CLI, telemetry, or ledger validation failure."""


# --------------------------------------------------------------------------- time


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _display_now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %I:%M:%S %p %Z (UTC%z)")


# ------------------------------------------------------------------- transcripts


def claude_dir() -> Path:
    """Claude Code's configuration root, honouring CLAUDE_CONFIG_DIR."""
    raw = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(raw).expanduser() if raw else Path.home() / ".claude"


def default_db() -> Path:
    return claude_dir() / "rightsize-goal" / "usage.sqlite3"


def _unique_match(matches: Sequence[Path], description: str) -> Path | None:
    resolved = sorted({item.resolve() for item in matches})
    if not resolved:
        return None
    if len(resolved) > 1:
        listing = ", ".join(str(item) for item in resolved)
        raise UsageError(f"multiple transcripts match {description}: {listing}; pass --transcript")
    return resolved[0]


def resolve_agent_transcript(agent_id: str, root: Path, session_id: str | None = None) -> Path | None:
    """Locate ``agent-<agent_id>.jsonl`` under any project/session subagents directory."""
    if not agent_id.strip():
        raise UsageError("agent id must be nonempty")
    session = session_id if session_id else "*"
    pattern = f"projects/*/{session}/subagents/agent-{agent_id}.jsonl"
    return _unique_match(list(root.glob(pattern)), f"agent {agent_id}")


def resolve_session_transcript(session_id: str, root: Path) -> Path | None:
    """Locate the main-session transcript ``<session-id>.jsonl`` under any project."""
    if not session_id.strip():
        raise UsageError("session id must be nonempty")
    return _unique_match(list(root.glob(f"projects/*/{session_id}.jsonl")), f"session {session_id}")


def _supplied_transcript(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise UsageError(f"transcript does not exist: {resolved}")
    return resolved


def _iter_records(path: Path) -> Iterable[dict[str, Any]]:
    """Yield assistant records that carry usage counters, ignoring everything else.

    Lines are pre-filtered on a marker so ordinary message content is never parsed.
    A partially written final line is skipped rather than treated as corruption.
    """
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if '"usage"' not in line or '"assistant"' not in line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(raw, dict) or raw.get("type") != "assistant":
                    continue
                message = raw.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
                    continue
                yield raw
    except (OSError, UnicodeError) as exc:
        raise UsageError(f"cannot read transcript {path}: {exc}") from exc


def _request_key(record: dict[str, Any]) -> str | None:
    for field in ("requestId", "uuid"):
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _counter(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _zero_tokens() -> dict[str, int]:
    return {name: 0 for name in TOKEN_FIELDS}


def _record_tokens(usage: dict[str, Any]) -> dict[str, int] | None:
    """Extract the five priced token categories from one ``message.usage`` object.

    ``input_tokens`` from the Anthropic API already excludes cache reads and cache
    writes, so the categories are additive and nothing is subtracted here. Returns
    ``None`` when a required counter is missing, malformed, or internally
    inconsistent, so the caller can preserve the gap instead of guessing.
    """
    tokens = _zero_tokens()
    for target, name in (("input", "input_tokens"), ("output", "output_tokens")):
        value = _counter(usage.get(name))
        if value is None:
            return None
        tokens[target] = value

    cache_read = _counter(usage.get("cache_read_input_tokens", 0))
    if cache_read is None:
        return None
    tokens["cache_read"] = cache_read

    total_writes = _counter(usage.get("cache_creation_input_tokens", 0))
    if total_writes is None:
        return None
    split = usage.get("cache_creation")
    if total_writes == 0 and not isinstance(split, dict):
        return tokens
    if not isinstance(split, dict):
        # Cache writes happened but their 5m/1h split is unavailable, and the two
        # tiers are priced differently. Refuse rather than assume a TTL.
        return None
    five = _counter(split.get("ephemeral_5m_input_tokens", 0))
    hour = _counter(split.get("ephemeral_1h_input_tokens", 0))
    if five is None or hour is None or five + hour != total_writes:
        return None
    tokens["cache_write_5m"] = five
    tokens["cache_write_1h"] = hour
    return tokens


def read_usage(path: Path, *, skip_sidechain: bool, exclude: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Sum usage in one transcript, grouped by actual model and actual effort.

    ``exclude`` holds request keys captured as a baseline, so a reused agent's
    follow-up assignment is measured on its own rather than from the start.
    """
    by_model: dict[str, dict[str, int]] = defaultdict(_zero_tokens)
    by_effort: dict[str, dict[str, int]] = defaultdict(_zero_tokens)
    seen: set[str] = set()
    counted = 0
    for record in _iter_records(path):
        if skip_sidechain and record.get("isSidechain") is True:
            continue
        key = _request_key(record)
        if key is None:
            return {"status": "unavailable", "reason": "transcript record has no request identity"}
        if key in exclude or key in seen:
            continue
        tokens = _record_tokens(record["message"]["usage"])
        if tokens is None:
            return {"status": "unavailable", "reason": "malformed or unpriceable usage counters"}
        seen.add(key)
        model = record["message"].get("model")
        model = model if isinstance(model, str) and model.strip() else "unknown"
        effort = record.get("effort")
        effort = effort if isinstance(effort, str) and effort.strip() else "unknown"
        for name, value in tokens.items():
            by_model[model][name] += value
            by_effort[effort][name] += value
        counted += 1
    return {
        "status": "available",
        "models": {key: value for key, value in by_model.items() if any(value.values())},
        "efforts": {key: value for key, value in by_effort.items() if any(value.values())},
        "requests": counted,
        "keys": sorted(seen | set(exclude)),
    }


def read_keys(path: Path | None, *, skip_sidechain: bool) -> dict[str, Any]:
    """Capture the request keys already present, forming an assignment baseline."""
    if path is None or not path.is_file():
        return {"status": "available", "keys": [], "basis": "transcript_absent_zero"}
    keys: list[str] = []
    for record in _iter_records(path):
        if skip_sidechain and record.get("isSidechain") is True:
            continue
        key = _request_key(record)
        if key is None:
            return {"status": "unavailable", "reason": "transcript record has no request identity", "keys": []}
        keys.append(key)
        if len(keys) > MAX_BASELINE_KEYS:
            return {"status": "unavailable", "reason": "transcript exceeds the baseline size limit", "keys": []}
    return {"status": "available", "keys": sorted(set(keys)), "basis": "observed_requests"}


# ------------------------------------------------------------------------- cost


def _load_tariff(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"cannot read tariff JSON: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("models"), dict):
        raise UsageError("tariff JSON must contain a models object")
    for field in ("version", "verified_on", "valid_until"):
        if not isinstance(raw.get(field), str) or not raw[field]:
            raise UsageError(f"tariff JSON must contain string field {field}")
    try:
        valid = datetime.fromisoformat(raw["valid_until"]).date() >= datetime.now().astimezone().date()
    except ValueError as exc:
        raise UsageError("tariff valid_until must be an ISO date") from exc
    raw["_valid_at_start"] = valid
    if not valid:
        raw["_validity_reason"] = f"tariff expired on {raw['valid_until']} before the assignment started"
    return raw


def _cost(models: dict[str, dict[str, int]], tariff: dict[str, Any] | None) -> tuple[str, float | None, str | None]:
    if tariff is None:
        return "unavailable", None, "no tariff snapshot supplied at start"
    if tariff.get("_valid_at_start") is False:
        return "unavailable", None, str(tariff.get("_validity_reason", "tariff was not valid at start"))
    total = 0.0
    for model, tokens in models.items():
        rates = tariff.get("models", {}).get(model)
        if not isinstance(rates, dict):
            return "unavailable", None, f"no exact tariff entry for served model {model}"
        for field in RATE_FIELDS:
            try:
                rate = float(rates[field])
            except (KeyError, TypeError, ValueError):
                return "unavailable", None, f"tariff for {model} is missing a valid {field} rate"
            if not math.isfinite(rate) or rate < 0:
                return "unavailable", None, f"tariff for {model} has an invalid {field} rate"
            total += tokens[field] * rate / 1_000_000
    return "known", total, None


# ----------------------------------------------------------------------- ledger


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  run_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  project_tag TEXT NOT NULL,
  domain TEXT,
  role TEXT NOT NULL,
  requested_model TEXT NOT NULL,
  requested_effort TEXT NOT NULL,
  mode TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  scope TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  transcript_path TEXT,
  prior_task TEXT,
  started_at TEXT NOT NULL,
  started_at_display TEXT,
  finished_at TEXT,
  finished_at_display TEXT,
  status TEXT NOT NULL,
  outcome TEXT,
  evidence TEXT,
  lesson TEXT,
  baseline_json TEXT NOT NULL,
  usage_status TEXT,
  usage_reason TEXT,
  tokens_json TEXT,
  actual_models_json TEXT,
  actual_efforts_json TEXT,
  tariff_json TEXT,
  cost_status TEXT,
  cost_reason TEXT,
  cost_usd REAL,
  cost_assumptions TEXT NOT NULL,
  PRIMARY KEY (run_id, task_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_task_per_agent
  ON tasks(agent_id) WHERE status = 'active';
"""


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


# --------------------------------------------------------------------- commands


def _target(args: argparse.Namespace) -> tuple[str, Path | None, bool]:
    """Resolve the assignment's transcript. Returns (agent key, path, skip_sidechain)."""
    root = args.claude_dir
    if args.main:
        session = args.session_id or os.environ.get("CLAUDE_CODE_SESSION_ID")
        if not session:
            raise UsageError("--main needs --session-id or the CLAUDE_CODE_SESSION_ID environment variable")
        path = _supplied_transcript(args.transcript) if args.transcript else resolve_session_transcript(session, root)
        return f"main:{session}", path, True
    path = (
        _supplied_transcript(args.transcript)
        if args.transcript
        else resolve_agent_transcript(args.agent_id, root, args.session_id)
    )
    return args.agent_id, path, False


def start(args: argparse.Namespace) -> dict[str, Any]:
    agent_key, path, skip_sidechain = _target(args)
    if args.new_agent:
        baseline = {"status": "available", "keys": [], "basis": "explicit_new_agent_zero"}
    else:
        baseline = read_keys(path, skip_sidechain=skip_sidechain)
    tariff = _load_tariff(args.tariff)
    with closing(_connect(args.db)) as db, db:
        try:
            db.execute(
                """INSERT INTO tasks(run_id, task_id, project_tag, domain, role, requested_model,
                       requested_effort, mode, difficulty, scope, agent_id, transcript_path, prior_task,
                       started_at, started_at_display, status, baseline_json, tariff_json, cost_assumptions)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    args.run, args.task, args.project_tag, args.domain, args.role, args.model,
                    args.effort, args.mode, args.difficulty, "main" if args.main else "agent",
                    agent_key, str(path) if path else None, args.prior_task,
                    _now(), _display_now(), "active",
                    json.dumps(baseline, sort_keys=True),
                    json.dumps(tariff, sort_keys=True) if tariff else None,
                    ASSUMPTIONS,
                ),
            )
        except sqlite3.IntegrityError as exc:
            active = db.execute(
                "SELECT run_id, task_id FROM tasks WHERE agent_id=? AND status='active'", (agent_key,)
            ).fetchone()
            if active:
                raise UsageError(
                    f"{agent_key} already has active task {active['run_id']}/{active['task_id']}; finish it first"
                ) from exc
            raise UsageError(f"task already exists: {args.run}/{args.task}") from exc
    return {
        "command": "start",
        "run": args.run,
        "task": args.task,
        "status": "active",
        "agent": agent_key,
        "baseline_status": baseline["status"],
        "baseline_requests": len(baseline.get("keys", [])),
        "transcript_path": str(path) if path else None,
        "tariff_version": tariff.get("version") if tariff else None,
        "finish_before_reusing_agent": True,
    }


def finish(args: argparse.Namespace) -> dict[str, Any]:
    with closing(_connect(args.db)) as db, db:
        row = db.execute(
            "SELECT * FROM tasks WHERE run_id=? AND task_id=?", (args.run, args.task)
        ).fetchone()
        if row is None:
            raise UsageError(f"task does not exist: {args.run}/{args.task}")
        if row["status"] == "finished":
            return {
                "command": "finish", "run": args.run, "task": args.task, "status": "finished",
                "idempotent": True, "outcome": row["outcome"], "usage_status": row["usage_status"],
                "usage_reason": row["usage_reason"], "cost_status": row["cost_status"],
                "cost_reason": row["cost_reason"], "cost_usd": row["cost_usd"],
                "tokens": json.loads(row["tokens_json"]) if row["tokens_json"] else None,
                "tariff_version": json.loads(row["tariff_json"]).get("version") if row["tariff_json"] else None,
                "cost_assumptions": row["cost_assumptions"], "recorded_at": row["finished_at_display"],
            }

        skip_sidechain = row["scope"] == "main"
        baseline = json.loads(row["baseline_json"])
        path: Path | None = None
        usage: dict[str, Any]
        try:
            if args.transcript:
                path = _supplied_transcript(args.transcript)
            elif row["transcript_path"] and Path(row["transcript_path"]).is_file():
                path = Path(row["transcript_path"])
            elif row["scope"] == "main":
                path = resolve_session_transcript(row["agent_id"].split(":", 1)[1], args.claude_dir)
            else:
                path = resolve_agent_transcript(row["agent_id"], args.claude_dir)
            if path is None:
                usage = {"status": "unavailable", "reason": "transcript not found"}
            elif baseline.get("status") != "available":
                usage = {"status": "unavailable", "reason": "start baseline was unavailable"}
            else:
                usage = read_usage(
                    path, skip_sidechain=skip_sidechain, exclude=frozenset(baseline.get("keys", []))
                )
        except UsageError as exc:
            usage = {"status": "unavailable", "reason": str(exc)}

        models = usage.get("models", {}) if usage["status"] == "available" else {}
        efforts = usage.get("efforts", {}) if usage["status"] == "available" else {}
        usage_reason = usage.get("reason")
        if usage["status"] == "available":
            cost_status, cost_usd, cost_reason = _cost(
                models, json.loads(row["tariff_json"]) if row["tariff_json"] else None
            )
            totals = {name: sum(values[name] for values in models.values()) for name in TOKEN_FIELDS}
            totals["total_input"] = totals["input"] + totals["cache_read"] + totals["cache_write_5m"] + totals["cache_write_1h"]
            totals["total_tokens"] = totals["total_input"] + totals["output"]
            totals["requests"] = int(usage.get("requests", 0))
        else:
            cost_status, cost_usd, cost_reason, totals = "unavailable", None, usage_reason, None

        db.execute(
            """UPDATE tasks SET finished_at=?, finished_at_display=?, status='finished', outcome=?,
                   evidence=?, lesson=?, transcript_path=?, usage_status=?, usage_reason=?, tokens_json=?,
                   actual_models_json=?, actual_efforts_json=?, cost_status=?, cost_reason=?, cost_usd=?
               WHERE run_id=? AND task_id=?""",
            (
                _now(), _display_now(), args.outcome, args.evidence, args.lesson,
                str(path) if path else row["transcript_path"], usage["status"], usage_reason,
                json.dumps(totals, sort_keys=True) if totals is not None else None,
                json.dumps(models, sort_keys=True) if models else None,
                json.dumps(efforts, sort_keys=True) if efforts else None,
                cost_status, cost_reason, cost_usd, args.run, args.task,
            ),
        )
        tariff_version = json.loads(row["tariff_json"]).get("version") if row["tariff_json"] else None

    result = {
        "command": "finish", "run": args.run, "task": args.task, "status": "finished",
        "idempotent": False, "outcome": args.outcome, "usage_status": usage["status"],
        "tokens": totals, "actual_models": sorted(models), "actual_efforts": sorted(efforts),
        "cost_status": cost_status, "cost_usd": cost_usd, "tariff_version": tariff_version,
        "cost_assumptions": ASSUMPTIONS, "recorded_at": _display_now(),
    }
    if usage_reason:
        result["usage_reason"] = usage_reason
    if cost_reason:
        result["cost_reason"] = cost_reason
    return result


def report(args: argparse.Namespace) -> dict[str, Any]:
    query = "SELECT * FROM tasks"
    clauses: list[str] = []
    parameters: list[str] = []
    for column, value in (
        ("run_id", args.run), ("project_tag", args.project_tag),
        ("mode", args.mode), ("difficulty", args.difficulty),
    ):
        if value:
            clauses.append(f"{column}=?")
            parameters.append(value)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    with closing(_connect(args.db)) as db:
        rows = db.execute(query, parameters).fetchall()

    def _observed(raw: str | None) -> str:
        names = sorted(json.loads(raw)) if raw else []
        if not names:
            return "unknown"
        return names[0] if len(names) == 1 else "mixed:" + "+".join(names)

    groups: dict[tuple[str, ...], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        tariff_version = "none"
        if row["tariff_json"]:
            tariff_version = str(json.loads(row["tariff_json"]).get("version", "unversioned"))
        key = (
            _observed(row["actual_models_json"]), _observed(row["actual_efforts_json"]),
            row["mode"], row["difficulty"], tariff_version,
        )
        groups[key].append(row)

    output = []
    for key, items in sorted(groups.items()):
        known_costs = [float(item["cost_usd"]) for item in items if item["cost_status"] == "known"]
        token_sums = _zero_tokens()
        known_tokens = 0
        lessons: list[tuple[str, dict[str, Any]]] = []
        for item in items:
            if item["usage_status"] == "available" and item["tokens_json"]:
                known_tokens += 1
                stored = json.loads(item["tokens_json"])
                for name in TOKEN_FIELDS:
                    token_sums[name] += int(stored.get(name, 0))
            if item["lesson"]:
                lessons.append((item["finished_at"] or item["started_at"], {
                    "run": item["run_id"], "task": item["task_id"], "role": item["role"],
                    "project_tag": item["project_tag"], "domain": item["domain"],
                    "prior_task": item["prior_task"], "lesson": item["lesson"],
                }))
        outcomes = {name: sum(item["outcome"] == name for item in items) for name in OUTCOMES}
        if known_tokens:
            token_sums["total_tokens"] = sum(token_sums[name] for name in TOKEN_FIELDS)
        output.append({
            "model": key[0], "effort": key[1], "mode": key[2], "difficulty": key[3],
            "tariff_version": key[4], "samples": len(items),
            "active": sum(item["status"] == "active" for item in items),
            "roles": sorted({item["role"] for item in items}),
            "accepted": outcomes["accepted"], "rework": outcomes["rework"],
            "unresolved": outcomes["unresolved"], "cancelled": outcomes["cancelled"],
            "failures": outcomes["failed"],
            "unknown_outcomes": sum(item["outcome"] is None for item in items),
            "token_coverage": {"known": known_tokens, "unknown": len(items) - known_tokens},
            "token_totals": token_sums if known_tokens else None,
            "cost_coverage": {"known": len(known_costs), "unknown": len(items) - len(known_costs)},
            "cost_total_usd": sum(known_costs) if known_costs else None,
            "cost_mean_usd": sum(known_costs) / len(known_costs) if known_costs else None,
            "lessons": [entry for _, entry in sorted(lessons, key=lambda pair: pair[0])[-5:]],
        })
    return {"command": "report", "run": args.run, "samples": len(rows), "groups": output,
            "cost_assumptions": ASSUMPTIONS}


# --------------------------------------------------------------------------- cli


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--db", type=Path, default=default_db(), help="ledger path (default: %(default)s)")
    parser.add_argument("--claude-dir", type=Path, default=claude_dir(),
                        help="Claude Code configuration root (default: %(default)s)")
    commands = parser.add_subparsers(dest="command", required=True)

    begin = commands.add_parser("start", help="open an assignment and capture its usage baseline")
    for name, helptext in (
        ("run", "unique run identifier for this goal"),
        ("task", "task identifier, unique within the run"),
        ("project-tag", "short, nonsensitive project label"),
        ("role", "rightsize role name, or 'coordinator' for main-session work"),
        ("model", "model requested for this assignment"),
        ("effort", "effort requested for this assignment"),
        ("mode", "implement, research, or brainstorm"),
    ):
        begin.add_argument(f"--{name}", required=True, help=helptext)
    begin.add_argument("--difficulty", required=True, choices=DIFFICULTIES,
                       help="difficulty of the task itself, not of the chosen worker")
    scope = begin.add_mutually_exclusive_group(required=True)
    scope.add_argument("--agent-id", help="subagent identifier returned when the agent was spawned")
    scope.add_argument("--main", action="store_true", help="measure main-session (coordinator) work instead")
    begin.add_argument("--session-id", help="session identifier; defaults to CLAUDE_CODE_SESSION_ID for --main")
    begin.add_argument("--transcript", type=Path, help="explicit transcript path, bypassing discovery")
    begin.add_argument("--new-agent", action="store_true",
                       help="force a zero baseline for a freshly spawned agent")
    begin.add_argument("--tariff", type=Path, help="tariff JSON snapshot to store with this assignment")
    begin.add_argument("--prior-task", help="task ID this one reworks, continues, or escalates from")
    begin.add_argument("--domain", help="short, nonsensitive task-domain label")

    end = commands.add_parser("finish", help="close an assignment and attribute its usage")
    end.add_argument("--run", required=True)
    end.add_argument("--task", required=True)
    end.add_argument("--outcome", required=True, choices=OUTCOMES,
                     help="the coordinator's judgement, not the worker's self-report")
    end.add_argument("--evidence", help="short pointer to the evidence behind the outcome")
    end.add_argument("--lesson", help="one concise, evidence-linked routing lesson")
    end.add_argument("--transcript", type=Path, help="explicit transcript path, bypassing discovery")

    summary = commands.add_parser("report", help="summarise observed routing history")
    summary.add_argument("--run")
    summary.add_argument("--project-tag")
    summary.add_argument("--mode")
    summary.add_argument("--difficulty", choices=DIFFICULTIES)
    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    try:
        args = _parser().parse_args(argv)
        args.claude_dir = args.claude_dir.expanduser()
        result = {"start": start, "finish": finish, "report": report}[args.command](args)
        print(json.dumps(result, sort_keys=True), file=stdout)
        return 0
    except (UsageError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}), file=stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
