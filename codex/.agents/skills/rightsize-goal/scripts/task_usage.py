#!/usr/bin/env python3
"""Record prompt-free, per-task Codex token usage in a global SQLite database."""

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
from typing import Any, Sequence, TextIO


DIFFICULTIES = ("basic", "routine", "moderate", "hard", "expert")
OUTCOMES = ("accepted", "rework", "unresolved", "cancelled", "failed")
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "cache_write_tokens")
ASSUMPTIONS = "standard-rate API-equivalent baseline; excludes long-context, fast-mode, tool, and other modifiers; not an actual invoice"


class UsageError(ValueError):
    pass


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _display_now() -> str:
    current = datetime.now().astimezone()
    return current.strftime("%Y-%m-%d %I:%M:%S %p %Z (UTC%z)")


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def default_db() -> Path:
    return _codex_home() / "rightsize-goal" / "usage.sqlite3"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
          run_id TEXT NOT NULL, task_id TEXT NOT NULL, project_tag TEXT NOT NULL, domain TEXT,
          role TEXT NOT NULL, requested_model TEXT NOT NULL, requested_effort TEXT NOT NULL,
          mode TEXT NOT NULL, difficulty TEXT NOT NULL, thread_id TEXT NOT NULL,
          session_path TEXT, prior_task TEXT, started_at TEXT NOT NULL, started_at_display TEXT,
          finished_at TEXT, finished_at_display TEXT,
          status TEXT NOT NULL, outcome TEXT, evidence TEXT, lesson TEXT,
          baseline_json TEXT NOT NULL, usage_status TEXT, tokens_json TEXT,
          actual_models_json TEXT, tariff_json TEXT, cost_status TEXT, cost_usd REAL,
          cost_assumptions TEXT NOT NULL,
          PRIMARY KEY (run_id, task_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_task_per_thread
          ON tasks(thread_id) WHERE status = 'active';
        """
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
    for name in ("domain", "started_at_display", "finished_at_display", "actual_efforts_json", "usage_reason", "cost_reason"):
        if name not in columns:
            connection.execute(f"ALTER TABLE tasks ADD COLUMN {name} TEXT")
    return connection


def _event_kind(raw: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        return None, {}
    outer = raw.get("type")
    inner = payload.get("type")
    if outer == "session_meta":
        return "session_meta", payload
    if outer == "turn_context":
        return "turn_context", payload
    if inner == "token_count" or outer == "token_count":
        return "token_count", payload
    return None, {}


def _iter_relevant(path: Path):
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                # Avoid decoding message/user content. A partial final JSONL record is ignored.
                if not any(marker in line for marker in ('"session_meta"', '"turn_context"', '"token_count"')):
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(raw, dict):
                    kind, payload = _event_kind(raw)
                    if kind:
                        yield kind, payload
    except (OSError, UnicodeError) as exc:
        raise UsageError(f"cannot read session telemetry {path}: {exc}") from exc


def _session_id(path: Path) -> str | None:
    for kind, payload in _iter_relevant(path):
        if kind == "session_meta":
            value = payload.get("id") or payload.get("thread_id")
            return value if isinstance(value, str) else None
    return None


def resolve_session(thread_id: str, supplied: Path | None = None) -> Path | None:
    if supplied is not None:
        path = supplied.expanduser().resolve()
        if not path.is_file():
            raise UsageError(f"session telemetry does not exist: {path}")
        found = _session_id(path)
        if found != thread_id:
            raise UsageError(f"session telemetry thread is {found!r}, not {thread_id!r}")
        return path
    root = _codex_home() / "sessions"
    if not root.exists():
        return None
    matches: list[Path] = []
    # Filename matching narrows normal rollouts; metadata is still authoritative.
    candidates = list(root.rglob("*.jsonl"))
    candidates.sort(key=lambda item: thread_id not in item.name)
    for candidate in candidates:
        if _session_id(candidate) == thread_id:
            matches.append(candidate.resolve())
    if len(matches) > 1:
        raise UsageError(f"multiple session files match thread {thread_id}; pass --session")
    return matches[0] if matches else None


def _zero_tokens() -> dict[str, int]:
    return {name: 0 for name in TOKEN_FIELDS}


def _usage_object(payload: dict[str, Any]) -> dict[str, Any] | None:
    info = payload.get("info")
    candidates = (info.get("total_token_usage"), info.get("total_usage")) if isinstance(info, dict) else ()
    candidates += (payload.get("total_token_usage"), payload.get("usage"))
    return next((item for item in candidates if isinstance(item, dict)), None)


def _counter(usage: dict[str, Any]) -> dict[str, int] | None:
    result = _zero_tokens()
    aliases = {
        "input_tokens": ("input_tokens",),
        "cached_input_tokens": ("cached_input_tokens", "input_tokens_cached"),
        "output_tokens": ("output_tokens",),
        "reasoning_output_tokens": ("reasoning_output_tokens", "reasoning_tokens"),
        "cache_write_tokens": ("cache_write_tokens", "cache_write_input_tokens", "cache_creation_input_tokens", "input_tokens_cache_write"),
    }
    for target, names in aliases.items():
        for name in names:
            value = usage.get(name)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                result[target] = value
                break
    required = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
    if any(not any(isinstance(usage.get(alias), int) and not isinstance(usage.get(alias), bool) and usage.get(alias) >= 0 for alias in aliases[name]) for name in required):
        return None
    cache_aliases = aliases["cache_write_tokens"]
    if any(alias in usage for alias in cache_aliases) and not any(isinstance(usage.get(alias), int) and not isinstance(usage.get(alias), bool) and usage.get(alias) >= 0 for alias in cache_aliases):
        return None
    return result


def snapshot(path: Path) -> dict[str, Any]:
    totals: dict[str, dict[str, int]] = defaultdict(_zero_tokens)
    effort_totals: dict[str, dict[str, int]] = defaultdict(_zero_tokens)
    previous: dict[str, int] | None = None
    model = "unknown"
    effort = "unknown"
    events = 0
    resets = 0
    for kind, payload in _iter_relevant(path):
        if kind == "turn_context":
            # A new turn without attribution must not inherit the preceding turn's labels.
            model = "unknown"
            effort = "unknown"
            candidate = payload.get("model")
            if isinstance(candidate, str) and candidate.strip():
                model = candidate
            candidate_effort = payload.get("effort") or payload.get("reasoning_effort")
            if isinstance(candidate_effort, str) and candidate_effort.strip():
                effort = candidate_effort
        elif kind == "token_count":
            usage = _usage_object(payload)
            if usage is None:
                continue
            current = _counter(usage)
            if current is None:
                return {"status": "unavailable", "reason": "malformed token_count telemetry", "models": {}, "efforts": {}, "resets": resets}
            if previous is None:
                delta = current
            elif any(current[name] < previous[name] for name in TOKEN_FIELDS):
                delta = current
                resets += 1
            else:
                delta = {name: current[name] - previous[name] for name in TOKEN_FIELDS}
            for name, value in delta.items():
                totals[model][name] += value
                effort_totals[effort][name] += value
            previous = current
            events += 1
    if events == 0:
        return {"status": "unavailable", "reason": "no token_count telemetry", "models": {}, "efforts": {}, "resets": 0}
    return {"status": "available", "models": dict(totals), "efforts": dict(effort_totals), "resets": resets}


def _subtract_dimension(after: dict[str, Any], before: dict[str, Any], dimension: str) -> dict[str, dict[str, int]] | None:
    result: dict[str, dict[str, int]] = {}
    for key in set(after.get(dimension, {})) | set(before.get(dimension, {})):
        values = {name: int(after.get(dimension, {}).get(key, {}).get(name, 0)) - int(before.get(dimension, {}).get(key, {}).get(name, 0)) for name in TOKEN_FIELDS}
        if any(value < 0 for value in values.values()):
            return None
        if any(values.values()):
            result[key] = values
    return result


def _delta(after: dict[str, Any], before: dict[str, Any]) -> tuple[str, dict[str, dict[str, int]], dict[str, dict[str, int]], str | None]:
    if after.get("status") != "available":
        return "unavailable", {}, {}, str(after.get("reason", "missing telemetry"))
    if before.get("status") != "available":
        return "unavailable", {}, {}, "start baseline telemetry unavailable"
    if int(after.get("resets", 0)) > int(before.get("resets", 0)):
        return "unavailable", {}, {}, "token counter reset during task interval"
    models = _subtract_dimension(after, before, "models")
    efforts = _subtract_dimension(after, before, "efforts")
    if models is None or efforts is None:
        return "unavailable", {}, {}, "telemetry history shrank or was replaced"
    return "available", models, efforts, None


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
        raw["_valid_at_start"] = datetime.fromisoformat(raw["valid_until"]).date() >= datetime.now().astimezone().date()
    except ValueError as exc:
        raise UsageError("tariff valid_until must be an ISO date") from exc
    if not raw["_valid_at_start"]:
        raw["_validity_reason"] = f"tariff expired on {raw['valid_until']} before task start"
    return raw


def _cost(models: dict[str, dict[str, int]], tariff: dict[str, Any] | None) -> tuple[str, float | None, str | None]:
    if tariff is None:
        return "unavailable", None, "no tariff snapshot supplied at start"
    if tariff.get("_valid_at_start") is False:
        return "unavailable", None, str(tariff.get("_validity_reason", "tariff was not valid at task start"))
    total = 0.0
    for model, tokens in models.items():
        if tokens.get("cache_write_tokens", 0):
            return "unavailable", None, f"cache-write pricing unsupported for {model}"
        rates = tariff.get("models", {}).get(model)
        if not isinstance(rates, dict):
            return "unavailable", None, f"no exact tariff for actual model {model}"
        try:
            # output_tokens already includes reasoning tokens; never add reasoning again.
            uncached = tokens["input_tokens"] - tokens["cached_input_tokens"]
            if uncached < 0 or tokens["reasoning_output_tokens"] > tokens["output_tokens"]:
                return "unavailable", None, "inconsistent token category totals"
            prices = [float(rates[key]) for key in ("input", "cached_input", "output")]
            if any(not math.isfinite(price) or price < 0 for price in prices):
                return "unavailable", None, f"invalid tariff for actual model {model}"
            total += (uncached * prices[0] + tokens["cached_input_tokens"] * prices[1] + tokens["output_tokens"] * prices[2]) / 1_000_000
        except (KeyError, TypeError, ValueError):
            return "unavailable", None, f"invalid tariff for actual model {model}"
    return "known", total, None


def start(args: argparse.Namespace) -> dict[str, Any]:
    session = resolve_session(args.thread_id, args.session)
    if args.new_thread:
        baseline = {"status": "available", "models": {}, "efforts": {}, "resets": 0, "basis": "explicit_new_thread_zero"}
    elif session is None:
        baseline = {"status": "unavailable", "reason": "session telemetry not found", "models": {}, "resets": 0}
    else:
        baseline = snapshot(session)
    tariff = _load_tariff(args.tariff)
    with closing(_connect(args.db)) as db, db:
        try:
            db.execute(
                """INSERT INTO tasks(run_id,task_id,project_tag,domain,role,requested_model,requested_effort,mode,difficulty,
                   thread_id,session_path,prior_task,started_at,started_at_display,status,baseline_json,tariff_json,cost_assumptions)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (args.run, args.task, args.project_tag, args.domain, args.role, args.model, args.effort, args.mode, args.difficulty,
                 args.thread_id, str(session) if session else None, args.prior_task, _now(), _display_now(), "active",
                 json.dumps(baseline, sort_keys=True), json.dumps(tariff, sort_keys=True) if tariff else None, ASSUMPTIONS),
            )
        except sqlite3.IntegrityError as exc:
            existing = db.execute("SELECT run_id,task_id FROM tasks WHERE thread_id=? AND status='active'", (args.thread_id,)).fetchone()
            if existing:
                raise UsageError(f"thread already has active task {existing['run_id']}/{existing['task_id']}") from exc
            raise UsageError(f"task already exists: {args.run}/{args.task}") from exc
    return {"command": "start", "run": args.run, "task": args.task, "status": "active", "baseline_status": baseline["status"], "session_path": str(session) if session else None, "finish_before_reusing_thread": True}


def finish(args: argparse.Namespace) -> dict[str, Any]:
    with closing(_connect(args.db)) as db, db:
        row = db.execute("SELECT * FROM tasks WHERE run_id=? AND task_id=?", (args.run, args.task)).fetchone()
        if row is None:
            raise UsageError(f"task does not exist: {args.run}/{args.task}")
        if row["status"] == "finished":
            return {"command": "finish", "run": args.run, "task": args.task, "status": "finished", "idempotent": True, "outcome": row["outcome"], "usage_status": row["usage_status"], "cost_status": row["cost_status"], "cost_usd": row["cost_usd"], "tokens": json.loads(row["tokens_json"]) if row["tokens_json"] else None, "usage_reason": row["usage_reason"], "cost_reason": row["cost_reason"], "cost_assumptions": row["cost_assumptions"], "recorded_at": row["finished_at_display"], "tariff_version": json.loads(row["tariff_json"]).get("version") if row["tariff_json"] else None}
        supplied = args.session
        if supplied is None and row["session_path"]:
            supplied = Path(row["session_path"])
        before = json.loads(row["baseline_json"])
        try:
            session = resolve_session(row["thread_id"], supplied)
            after = snapshot(session) if session else {"status": "unavailable", "reason": "session telemetry not found"}
        except UsageError as exc:
            session = None
            after = {"status": "unavailable", "reason": str(exc)}
        usage_status, models, efforts, usage_reason = _delta(after, before)
        tariff = json.loads(row["tariff_json"]) if row["tariff_json"] else None
        if usage_status == "available":
            cost_status, cost_usd, cost_reason = _cost(models, tariff)
        else:
            cost_status, cost_usd, cost_reason = "unavailable", None, usage_reason
        totals = {name: sum(values[name] for values in models.values()) for name in TOKEN_FIELDS} if usage_status == "available" else None
        if totals is not None:
            totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]
        db.execute(
            """UPDATE tasks SET finished_at=?,finished_at_display=?,status='finished',outcome=?,evidence=?,lesson=?,session_path=?,
               usage_status=?,tokens_json=?,actual_models_json=?,actual_efforts_json=?,cost_status=?,cost_usd=?,usage_reason=?,cost_reason=? WHERE run_id=? AND task_id=?""",
            (_now(), _display_now(), args.outcome, args.evidence, args.lesson, str(session) if session else row["session_path"],
             usage_status, json.dumps(totals, sort_keys=True) if totals is not None else None,
             json.dumps(models, sort_keys=True) if usage_status == "available" else None,
             json.dumps(efforts, sort_keys=True) if usage_status == "available" else None,
             cost_status, cost_usd, usage_reason, cost_reason, args.run, args.task),
        )
    result = {"command": "finish", "run": args.run, "task": args.task, "status": "finished", "idempotent": False, "outcome": args.outcome, "usage_status": usage_status, "tokens": totals, "actual_models": sorted(models), "actual_efforts": sorted(efforts), "cost_status": cost_status, "cost_usd": cost_usd, "tariff_version": tariff.get("version") if tariff else None, "cost_assumptions": ASSUMPTIONS, "recorded_at": _display_now()}
    if usage_reason:
        result["usage_reason"] = usage_reason
    if cost_reason:
        result["cost_reason"] = cost_reason
    return result


def report(args: argparse.Namespace) -> dict[str, Any]:
    query = "SELECT * FROM tasks"
    clauses: list[str] = []
    parameters: list[str] = []
    for column, value in (("run_id", args.run), ("project_tag", args.project_tag), ("mode", args.mode), ("difficulty", args.difficulty)):
        if value:
            clauses.append(f"{column}=?")
            parameters.append(value)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    with closing(_connect(args.db)) as db:
        rows = db.execute(query, parameters).fetchall()
    groups: dict[tuple[str, str, str, str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        observed = sorted(json.loads(row["actual_models_json"]).keys()) if row["actual_models_json"] else []
        actual_model = observed[0] if len(observed) == 1 else ("mixed:" + "+".join(observed) if observed else "unknown")
        tariff_version = "none"
        if row["tariff_json"]:
            tariff_version = str(json.loads(row["tariff_json"]).get("version", "unversioned"))
        efforts = sorted(json.loads(row["actual_efforts_json"]).keys()) if row["actual_efforts_json"] else []
        actual_effort = efforts[0] if len(efforts) == 1 else ("mixed:" + "+".join(efforts) if efforts else "unknown")
        groups[(actual_model, actual_effort, row["mode"], row["difficulty"], tariff_version)].append(row)
    output = []
    for key, items in sorted(groups.items()):
        known_costs = [float(item["cost_usd"]) for item in items if item["cost_status"] == "known"]
        token_sums = _zero_tokens()
        known_tokens = 0
        lessons: list[tuple[str, dict[str, Any]]] = []
        actual_models: set[str] = set()
        for item in items:
            if item["usage_status"] == "available" and item["tokens_json"]:
                known_tokens += 1
                stored_tokens = json.loads(item["tokens_json"])
                for name in TOKEN_FIELDS:
                    token_sums[name] += int(stored_tokens.get(name, 0))
            if item["lesson"]:
                lessons.append((item["finished_at"] or item["started_at"], {"run": item["run_id"], "task": item["task_id"], "project_tag": item["project_tag"], "domain": item["domain"], "lesson": item["lesson"], "prior_task": item["prior_task"]}))
            if item["actual_models_json"]:
                actual_models.update(json.loads(item["actual_models_json"]).keys())
        outcomes = {name: sum(item["outcome"] == name for item in items) for name in OUTCOMES}
        if known_tokens:
            token_sums["total_tokens"] = token_sums["input_tokens"] + token_sums["output_tokens"]
        latest_lessons = [entry for _, entry in sorted(lessons, key=lambda pair: pair[0])[-5:]]
        output.append({"model": key[0], "effort": key[1], "mode": key[2], "difficulty": key[3], "tariff_version": key[4], "samples": len(items), "active": sum(item["status"] == "active" for item in items), "accepted": outcomes["accepted"], "rework": outcomes["rework"], "failures": outcomes["failed"], "unresolved": outcomes["unresolved"], "cancelled": outcomes["cancelled"], "unknown_outcomes": sum(item["outcome"] is None for item in items), "actual_models": sorted(actual_models), "token_coverage": {"known": known_tokens, "unknown": len(items) - known_tokens}, "token_totals": token_sums if known_tokens else None, "cost_coverage": {"known": len(known_costs), "unknown": len(items) - len(known_costs)}, "cost_total_usd": sum(known_costs) if known_costs else None, "cost_mean_usd": sum(known_costs) / len(known_costs) if known_costs else None, "lessons": latest_lessons})
    return {"command": "report", "run": args.run, "samples": len(rows), "groups": output, "cost_assumptions": ASSUMPTIONS}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=default_db())
    commands = parser.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("start")
    for name in ("run", "task", "project-tag", "role", "model", "effort", "mode", "thread-id"):
        begin.add_argument(f"--{name}", required=True)
    begin.add_argument("--difficulty", required=True, choices=DIFFICULTIES)
    begin.add_argument("--session", type=Path)
    begin.add_argument("--new-thread", action="store_true")
    begin.add_argument("--tariff", type=Path)
    begin.add_argument("--prior-task")
    begin.add_argument("--domain")
    end = commands.add_parser("finish")
    end.add_argument("--run", required=True)
    end.add_argument("--task", required=True)
    end.add_argument("--outcome", required=True, choices=OUTCOMES)
    end.add_argument("--evidence")
    end.add_argument("--lesson")
    end.add_argument("--session", type=Path)
    summary = commands.add_parser("report")
    summary.add_argument("--run")
    summary.add_argument("--project-tag")
    summary.add_argument("--mode")
    summary.add_argument("--difficulty", choices=DIFFICULTIES)
    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    try:
        args = _parser().parse_args(argv)
        result = {"start": start, "finish": finish, "report": report}[args.command](args)
        print(json.dumps(result, sort_keys=True), file=stdout)
        return 0
    except (UsageError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}), file=stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
