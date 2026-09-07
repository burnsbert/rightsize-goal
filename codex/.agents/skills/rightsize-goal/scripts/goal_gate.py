#!/usr/bin/env python3
"""Small, durable completion gate for a rightsize-goal run."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence, TextIO


STATE_VERSION = 1


class GateError(ValueError):
    """An expected CLI or state validation failure."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise GateError(f"state field {field!r} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GateError(f"state field {field!r} is not a valid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise GateError(f"state field {field!r} must be in UTC")
    return parsed.astimezone(timezone.utc)


def _nonnegative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if parsed < 0 or parsed != parsed or parsed == float("inf"):
        raise argparse.ArgumentTypeError("must be a finite nonnegative number")
    return parsed


def _nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return parsed


def _duration_hours(value: str) -> float:
    """Parse an explicit amount and time unit; keep persisted v1 bounds in hours."""
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?|\.\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\s*",
        value,
        re.IGNORECASE,
    )
    if match is None:
        raise argparse.ArgumentTypeError(
            'use a nonnegative amount and unit, such as "30 minutes" or "3 hours"'
        )
    amount = _nonnegative_float(match.group(1))
    unit = match.group(2).lower()[0]
    hours = amount * {"s": 1 / 3600, "m": 1 / 60, "h": 1, "d": 24}[unit]
    if hours >= timedelta.max.total_seconds() / 3600:
        raise argparse.ArgumentTypeError("duration is too large")
    return hours


def _validate_bounds(bounds: object) -> dict[str, float | int]:
    if not isinstance(bounds, dict):
        raise GateError("state field 'bounds' must be an object")
    allowed = {"min_hours", "max_hours", "min_iterations", "max_iterations"}
    if set(bounds) - allowed:
        raise GateError("state contains unknown bounds")
    validated: dict[str, float | int] = {}
    for name, value in bounds.items():
        is_hours = name.endswith("hours")
        valid_type = (
            isinstance(value, (int, float)) if is_hours else isinstance(value, int)
        )
        if isinstance(value, bool) or not valid_type or value < 0:
            kind = "number" if is_hours else "integer"
            raise GateError(f"state bound {name!r} must be a nonnegative {kind}")
        numeric = float(value)
        if numeric != numeric or numeric == float("inf"):
            raise GateError(f"state bound {name!r} must be finite")
        validated[name] = value
    for unit in ("hours", "iterations"):
        minimum = validated.get(f"min_{unit}")
        maximum = validated.get(f"max_{unit}")
        if minimum is not None and maximum is not None and maximum < minimum:
            raise GateError(f"max-{unit} must be greater than or equal to min-{unit}")
    return validated


def _validate_state(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise GateError("state must be a JSON object")
    required = {
        "version",
        "objective",
        "started_at",
        "not_before",
        "deadline",
        "bounds",
        "iterations",
    }
    if set(raw) != required:
        raise GateError("state fields are missing or unrecognized")
    if raw["version"] != STATE_VERSION:
        raise GateError("unsupported state version")
    if not isinstance(raw["objective"], str) or not raw["objective"].strip():
        raise GateError("state objective must be nonempty")

    bounds = _validate_bounds(raw["bounds"])
    started = _parse_time(raw["started_at"], "started_at")
    not_before = _parse_time(raw["not_before"], "not_before")
    deadline = (
        None if raw["deadline"] is None else _parse_time(raw["deadline"], "deadline")
    )
    expected_not_before = started + timedelta(hours=float(bounds.get("min_hours", 0)))
    if not_before != expected_not_before:
        raise GateError("state not_before is inconsistent with min_hours")
    max_hours = bounds.get("max_hours")
    expected_deadline = (
        None if max_hours is None else started + timedelta(hours=float(max_hours))
    )
    if deadline != expected_deadline:
        raise GateError("state deadline is inconsistent with max_hours")

    if not isinstance(raw["iterations"], list):
        raise GateError("state iterations must be an array")
    seen: set[str] = set()
    for index, record in enumerate(raw["iterations"]):
        if not isinstance(record, dict) or set(record) != {
            "id",
            "hypothesis",
            "action",
            "result",
            "evidence",
            "recorded_at",
        }:
            raise GateError(f"iteration {index} is malformed")
        for field in ("id", "hypothesis", "action", "result", "evidence"):
            if not isinstance(record[field], str) or not record[field].strip():
                raise GateError(f"iteration {index} field {field!r} must be nonempty")
        if record["id"] in seen:
            raise GateError("state contains duplicate iteration IDs")
        seen.add(record["id"])
        recorded = _parse_time(record["recorded_at"], f"iterations[{index}].recorded_at")
        if recorded < started:
            raise GateError(f"iteration {index} predates the goal")
    return raw


def _load_state(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as stream:
            raw = json.load(stream)
    except FileNotFoundError as exc:
        raise GateError(f"state does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read valid state: {path}: {exc}") from exc
    return _validate_state(raw)


def _write_new(path: Path, state: dict) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(state, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise GateError(f"state already exists: {path}") from exc
    except OSError as exc:
        raise GateError(f"cannot create state: {path}: {exc}") from exc


def _atomic_replace(path: Path, state: dict) -> None:
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(state, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise GateError(f"cannot update state atomically: {path}: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _current_time(now_fn: Callable[[], datetime], state: dict | None = None) -> datetime:
    current = now_fn()
    if current.tzinfo is None or current.utcoffset() is None:
        raise GateError("clock must return a timezone-aware datetime")
    current = current.astimezone(timezone.utc)
    if state is not None:
        latest = _parse_time(state["started_at"], "started_at")
        for index, record in enumerate(state["iterations"]):
            recorded = _parse_time(record["recorded_at"], f"iterations[{index}].recorded_at")
            latest = max(latest, recorded)
        if current < latest:
            raise GateError("clock moved backwards relative to persisted state")
    return current


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a new goal gate state file")
    init.add_argument("--state", required=True, type=Path)
    init.add_argument("--objective", required=True)
    minimum = init.add_mutually_exclusive_group()
    minimum.add_argument(
        "--minimum-time", dest="min_hours", type=_duration_hours,
        metavar="DURATION", help='minimum elapsed time, e.g. "30 minutes"',
    )
    minimum.add_argument("--min-hours", type=_nonnegative_float, help="legacy numeric-hours option")
    maximum = init.add_mutually_exclusive_group()
    maximum.add_argument(
        "--maximum-time", dest="max_hours", type=_duration_hours,
        metavar="DURATION", help='maximum elapsed time, e.g. "3 hours"',
    )
    maximum.add_argument("--max-hours", type=_nonnegative_float, help="legacy numeric-hours option")
    init.add_argument("--min-iterations", type=_nonnegative_int)
    init.add_argument("--max-iterations", type=_nonnegative_int)

    iteration = commands.add_parser("iteration", help="append an evidence-backed iteration")
    iteration.add_argument("--state", required=True, type=Path)
    iteration.add_argument("--id", required=True)
    iteration.add_argument("--hypothesis", required=True)
    iteration.add_argument("--action", required=True)
    iteration.add_argument("--result", required=True)
    iteration.add_argument("--evidence", required=True, type=Path)

    check = commands.add_parser("check", help="evaluate the completion gate")
    check.add_argument("--state", required=True, type=Path)
    check.add_argument("--acceptance-met", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    now_fn: Callable[[], datetime] = _utc_now,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "init":
            if not args.objective.strip():
                raise GateError("objective must be nonempty")
            bounds = {
                name: value
                for name, value in (
                    ("min_hours", args.min_hours),
                    ("max_hours", args.max_hours),
                    ("min_iterations", args.min_iterations),
                    ("max_iterations", args.max_iterations),
                )
                if value is not None
            }
            _validate_bounds(bounds)
            current = _current_time(now_fn)
            state = {
                "version": STATE_VERSION,
                "objective": args.objective,
                "started_at": _format_time(current),
                "not_before": _format_time(
                    current + timedelta(hours=float(bounds.get("min_hours", 0)))
                ),
                "deadline": (
                    None
                    if "max_hours" not in bounds
                    else _format_time(
                        current + timedelta(hours=float(bounds["max_hours"]))
                    )
                ),
                "bounds": bounds,
                "iterations": [],
            }
            _write_new(args.state, state)
            print(json.dumps(state, sort_keys=True), file=stdout)
            return 0

        state = _load_state(args.state)
        current = _current_time(now_fn, state)
        if args.command == "iteration":
            text_fields = (args.id, args.hypothesis, args.action, args.result)
            if any(not value.strip() for value in text_fields):
                raise GateError("iteration text fields must be nonempty")
            if not args.evidence.exists():
                raise GateError(f"evidence does not exist: {args.evidence}")
            if any(record["id"] == args.id for record in state["iterations"]):
                raise GateError(f"duplicate iteration ID: {args.id}")
            record = {
                "id": args.id,
                "hypothesis": args.hypothesis,
                "action": args.action,
                "result": args.result,
                "evidence": str(args.evidence.resolve()),
                "recorded_at": _format_time(current),
            }
            state["iterations"].append(record)
            _atomic_replace(args.state, state)
            print(json.dumps(record, sort_keys=True), file=stdout)
            return 0

        started = _parse_time(state["started_at"], "started_at")
        elapsed_hours = (current - started).total_seconds() / 3600
        count = len(state["iterations"])
        bounds = state["bounds"]
        unmet: list[str] = []
        if not args.acceptance_met:
            unmet.append("acceptance")
        if elapsed_hours < float(bounds.get("min_hours", 0)):
            unmet.append("min_hours")
        if count < int(bounds.get("min_iterations", 0)):
            unmet.append("min_iterations")

        limits_reached: list[str] = []
        if "max_hours" in bounds and elapsed_hours >= float(bounds["max_hours"]):
            limits_reached.append("max_hours")
        if "max_iterations" in bounds and count >= int(bounds["max_iterations"]):
            limits_reached.append("max_iterations")

        if not unmet:
            decision, exit_code = "completion_eligible", 0
        elif limits_reached:
            decision, exit_code = "limit_reached", 3
        else:
            decision, exit_code = "continue", 2
        report = {
            "decision": decision,
            "unmet": unmet,
            "limits_reached": limits_reached,
            "acceptance_met": args.acceptance_met,
            "elapsed_hours": elapsed_hours,
            "elapsed_basis": "wall-clock time since init; not billed or active work time",
            "iteration_count": count,
            "bounds": bounds,
        }
        print(json.dumps(report, sort_keys=True), file=stdout)
        return exit_code
    except (GateError, OverflowError) as exc:
        print(json.dumps({"error": str(exc)}), file=stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
