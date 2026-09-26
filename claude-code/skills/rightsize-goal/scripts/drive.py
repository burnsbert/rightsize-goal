#!/usr/bin/env python3
"""Self-driving control state and Stop-hook decision for a Claude Code rightsize-goal run.

Claude Code only. A skill cannot start `/goal`, so the plugin ships a Stop hook that
calls `drive.py hook`. The hook keeps a session working while that session owns an
active goal whose latest validation verdict is not a fresh DONE, and stays silent in
every other session. The coordinator records the goal text, amendments, the task
list, progress, validation verdicts, and pause/resume status here; the completion
gate (goal_gate.py, shared with the Codex package) still owns time and iteration
bounds. Standard library only.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goal_gate  # noqa: E402


DRIVE_VERSION = 1
SUFFIX = ".drive.json"
STALL_LIMIT = 3
MODES = ("self", "host_goal")
STATUSES = ("active", "paused", "waiting_on_user", "complete", "incomplete")
TASK_STATUSES = ("open", "in_progress", "done", "dropped")
TASK_SOURCES = ("plan", "discovered", "validator", "audible")
VERDICTS = ("DONE", "NOT_DONE")
MAX_NOTES = 20
MAX_GOAL_CHARS = 600
MAX_LISTED_TASKS = 8


class DriveError(ValueError):
    """An expected CLI or state validation failure."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(now_fn: Callable[[], datetime]) -> str:
    current = now_fn()
    if current.tzinfo is None or current.utcoffset() is None:
        raise DriveError("clock must return a timezone-aware datetime")
    return goal_gate._format_time(current)


def goal_id_for(path: Path) -> str:
    name = path.name
    return name[: -len(SUFFIX)] if name.endswith(SUFFIX) else path.stem


# -- state ---------------------------------------------------------------


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DriveError(message)


def _validate(raw: object) -> dict:
    _require(isinstance(raw, dict), "drive state must be a JSON object")
    required = {
        "version", "goal_id", "session_id", "mode", "status", "status_reason", "gate",
        "created_at", "updated_at", "goal", "tasks", "work_epoch", "activity", "notes",
        "verdicts", "hook",
    }
    _require(set(raw) == required, "drive state fields are missing or unrecognized")
    _require(type(raw["version"]) is int and raw["version"] == DRIVE_VERSION,
             "unsupported drive state version")
    for field in ("goal_id", "session_id", "gate", "created_at", "updated_at"):
        _require(isinstance(raw[field], str) and raw[field].strip(), f"drive field {field!r} must be nonempty")
    _require(raw["mode"] in MODES, "drive mode is invalid")
    _require(raw["status"] in STATUSES, "drive status is invalid")
    _require(raw["status_reason"] is None or isinstance(raw["status_reason"], str),
             "drive status_reason must be text or null")
    goal = raw["goal"]
    _require(isinstance(goal, dict) and set(goal) == {"original", "current", "version", "amendments"},
             "drive goal is malformed")
    _require(isinstance(goal["original"], str) and isinstance(goal["current"], str)
             and goal["current"].strip(), "drive goal text must be nonempty")
    _require(type(goal["version"]) is int and goal["version"] >= 1, "drive goal version is invalid")
    _require(isinstance(goal["amendments"], list) and len(goal["amendments"]) == goal["version"] - 1,
             "drive goal amendments do not match its version")
    for field in ("work_epoch", "activity"):
        _require(type(raw[field]) is int and raw[field] >= 0, f"drive {field} is invalid")
    for field in ("tasks", "notes", "verdicts"):
        _require(isinstance(raw[field], list), f"drive {field} must be an array")
    seen: set[str] = set()
    for task in raw["tasks"]:
        _require(isinstance(task, dict) and isinstance(task.get("id"), str) and task["id"] not in seen
                 and task.get("status") in TASK_STATUSES, "drive task is malformed or duplicated")
        seen.add(task["id"])
    for verdict in raw["verdicts"]:
        _require(isinstance(verdict, dict) and verdict.get("verdict") in VERDICTS
                 and isinstance(verdict.get("reasons"), list)
                 and type(verdict.get("goal_version")) is int
                 and type(verdict.get("work_epoch")) is int, "drive verdict is malformed")
    hook = raw["hook"]
    _require(isinstance(hook, dict) and set(hook) == {"last_activity", "stalled", "limit_notified"},
             "drive hook counters are malformed")
    _require(hook["last_activity"] is None or type(hook["last_activity"]) is int, "drive hook counter is invalid")
    _require(type(hook["stalled"]) is int and hook["stalled"] >= 0, "drive hook counter is invalid")
    _require(isinstance(hook["limit_notified"], bool), "drive hook counter is invalid")
    return raw


def load(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DriveError(f"drive state does not exist: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DriveError(f"cannot read valid drive state: {path}: {exc}") from exc
    return _validate(raw)


def _save(path: Path, state: dict, now_fn: Callable[[], datetime]) -> None:
    state["updated_at"] = _stamp(now_fn)
    _validate(state)
    goal_gate._atomic_replace(path, state)


def _bump(state: dict, *, work: bool) -> None:
    state["activity"] += 1
    if work:
        state["work_epoch"] += 1


# -- gate and freshness --------------------------------------------------


def latest_verdict(state: dict) -> dict | None:
    return state["verdicts"][-1] if state["verdicts"] else None


def acceptance_fresh(state: dict) -> bool:
    verdict = latest_verdict(state)
    return (
        verdict is not None
        and verdict["verdict"] == "DONE"
        and verdict["goal_version"] == state["goal"]["version"]
        and verdict["work_epoch"] == state["work_epoch"]
    )


def gate_report(state: dict, now_fn: Callable[[], datetime]) -> dict:
    arguments = ["check", "--state", state["gate"]]
    if acceptance_fresh(state):
        arguments.append("--acceptance-met")
    stdout, stderr = io.StringIO(), io.StringIO()
    code = goal_gate.main(arguments, now_fn=now_fn, stdout=stdout, stderr=stderr)
    if code == 1 or not stdout.getvalue().strip():
        detail = stderr.getvalue().strip() or "no gate output"
        raise DriveError(f"completion gate check failed: {detail}")
    report = json.loads(stdout.getvalue())
    gate_state = goal_gate._load_state(Path(state["gate"]))
    report["not_before"] = gate_state["not_before"]
    return report


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def open_tasks(state: dict) -> list[dict]:
    return [task for task in state["tasks"] if task["status"] in ("open", "in_progress")]


def _unmet(state: dict, task: dict) -> list[str]:
    status = {t["id"]: t["status"] for t in state["tasks"]}
    return [dep for dep in task.get("depends_on") or [] if status.get(dep) not in ("done", "dropped")]


def ready_tasks(state: dict) -> list[dict]:
    """Open tasks whose dependencies are all done or dropped, so they can start now."""
    return [t for t in state["tasks"] if t["status"] == "open" and not _unmet(state, t)]


def blocked_tasks(state: dict) -> list[dict]:
    return [t for t in state["tasks"] if t["status"] == "open" and _unmet(state, t)]


# -- hook ----------------------------------------------------------------


def _acceptance_lines(state: dict) -> list[str]:
    verdict = latest_verdict(state)
    if verdict is None:
        return ["No validation verdict yet."]
    if verdict["verdict"] == "NOT_DONE":
        lines = ["Latest validation verdict is NOT DONE:"]
        lines.extend(f"  - {reason}" for reason in verdict["reasons"])
        lines.append("Turn each reason into tasks before continuing.")
        return lines
    if verdict["goal_version"] != state["goal"]["version"]:
        return [f"The goal was amended after the last DONE verdict (verdict covered v{verdict['goal_version']}, "
                f"the goal is now v{state['goal']['version']}). Validate again once the amended goal is met."]
    return ["Work was recorded after the last DONE verdict. Validate again before finishing: a polish "
            "check if this was a polish round, which only looks for regressions from that round."]


def _commands(drive_path: Path) -> list[str]:
    run = f'"{sys.executable or "python3"}" "{Path(__file__).resolve()}"'
    target = f'--drive "{drive_path.resolve()}"'
    return [
        "Record changes with these commands; never edit the drive file by hand:",
        f"  {run} task {target} --id <id> [--title ... --why ... --owner <role>] [--status open|in_progress|done|dropped]",
        f'  {run} progress {target} --note "<what changed>"',
        f'  {run} verdict {target} --verdict DONE|NOT_DONE --reason "<reason>" [--evidence <saved receipt>]',
        f'  {run} status {target} --set paused|waiting_on_user --reason "<why>"',
    ]


def _block_reason(state: dict, report: dict, drive_path: Path) -> str:
    goal = state["goal"]
    text = goal["current"]
    if len(text) > MAX_GOAL_CHARS:
        text = text[: MAX_GOAL_CHARS - 3] + "..."
    lines = [
        f"Rightsize Goal {state['goal_id']} is still active (goal v{goal['version']}). Do not end the turn yet.",
        f"Goal: {text}",
        "Not yet met:",
    ]
    unmet = report.get("unmet", [])
    if "acceptance" in unmet:
        lines.extend(f"- {line}" if not line.startswith("  ") else line for line in _acceptance_lines(state))
    if "min_hours" in unmet:
        lines.append(f"- Minimum time not reached (not before {report['not_before']}).")
    if "min_iterations" in unmet:
        minimum = report.get("bounds", {}).get("min_iterations")
        lines.append(f"- Minimum iterations not reached ({report.get('iteration_count', 0)} of {minimum}).")
    def listed(heading: str, tasks: list[dict], note=lambda task: "") -> None:
        if not tasks:
            return
        lines.append(heading)
        for task in tasks[:MAX_LISTED_TASKS]:
            owner = f" [{task['owner']}]" if task.get("owner") else ""
            tags = [value for value in (task.get("area"), task.get("family") and f"family {task['family']}") if value]
            area = f" ({', '.join(tags)})" if tags else ""
            lines.append(f"- {task['id']}{owner}{area} {task['title']}{note(task)}")
        if len(tasks) > MAX_LISTED_TASKS:
            lines.append(f"- ...and {len(tasks) - MAX_LISTED_TASKS} more")

    running = [t for t in state["tasks"] if t["status"] == "in_progress"]
    listed("In progress:", running)
    listed("Ready to start:", ready_tasks(state))
    listed("Waiting on other tasks:", blocked_tasks(state),
           lambda task: " (after " + ", ".join(_unmet(state, task)) + ")")
    if not open_tasks(state):
        lines.append("Open tasks: none recorded.")
    validate = ("When you believe the goal is met, dispatch rightsize-validator and record its verdict. "
                if "acceptance" in unmet else
                "The goal is validated; do not validate again unless you change the work. ")
    lines.append(
        "Next: update the task list with drive.py, then dispatch the next task to the cheapest capable role. "
        "If workers are still running, mark their tasks in_progress and end your turn to wait for them. "
        + validate +
        "If the user asked to stop or pause, or you need their input, record that status with drive.py instead."
    )
    lines.extend(_commands(drive_path))
    return "\n".join(lines)


def _find_goal(run_dir: Path, session_id: str) -> tuple[Path | None, dict | None, list[str]]:
    corrupt: list[str] = []
    best: tuple[str, Path, dict] | None = None
    for path in sorted(run_dir.glob(f"*{SUFFIX}")):
        try:
            state = load(path)
        except DriveError:
            corrupt.append(path.name)
            continue
        if state["session_id"] != session_id or state["status"] != "active" or state["mode"] != "self":
            continue
        key = state["created_at"]
        if best is None or key >= best[0]:
            best = (key, path, state)
    if best is None:
        return None, None, corrupt
    return best[1], best[2], corrupt


def hook(stdin: TextIO, stdout: TextIO, now_fn: Callable[[], datetime]) -> int:
    """Decide a Stop event. Never fails the host: every error allows the stop."""
    try:
        payload = json.loads(stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict) or not isinstance(payload.get("session_id"), str):
        return 0
    cwd = Path(payload.get("cwd") or os.getcwd())
    run_dir = cwd / ".rightsize-goal"
    if not run_dir.is_dir():
        return 0
    path, state, corrupt = _find_goal(run_dir, payload["session_id"])
    if state is None:
        if corrupt:
            _emit(stdout, {"systemMessage": "Rightsize Goal could not read "
                           + ", ".join(corrupt) + "; not holding the session open."})
        return 0
    assert path is not None
    warning = ("Rightsize Goal could not read " + ", ".join(corrupt) + "; those goals are not being tracked."
               if corrupt else None)
    try:
        report = gate_report(state, now_fn)
    except (DriveError, goal_gate.GateError, json.JSONDecodeError, OSError) as exc:
        _emit(stdout, {"systemMessage": f"Rightsize Goal {state['goal_id']}: {exc}; not holding the session open."})
        return 0

    decision = report["decision"]
    if decision == "completion_eligible":
        return 0
    if decision == "limit_reached":
        if state["hook"]["limit_notified"]:
            return 0
        state["hook"]["limit_notified"] = True
        _save_quietly(path, state, now_fn)
        limits = ", ".join(report.get("limits_reached", [])) or "a bound"
        _emit(stdout, {"decision": "block", "reason": (
            f"Rightsize Goal {state['goal_id']} reached its limit ({limits}). Stop dispatching new work, "
            "checkpoint running workers, give the user an incomplete handoff listing the unmet criteria, "
            "then record status incomplete with drive.py.")})
        return 0

    if any(task["status"] == "in_progress" for task in state["tasks"]):
        # Workers are running; their completion notification wakes the coordinator.
        return 0

    counters = state["hook"]
    if counters["last_activity"] == state["activity"]:
        counters["stalled"] += 1
    else:
        counters["stalled"] = 0
    counters["last_activity"] = state["activity"]
    _save_quietly(path, state, now_fn)
    if counters["stalled"] >= STALL_LIMIT:
        _emit(stdout, {"systemMessage": (
            f"Rightsize Goal {state['goal_id']} made no recorded progress across {STALL_LIMIT} continuation "
            "prompts, so the session is being allowed to stop. Steer it, or say resume to continue.")})
        return 0
    decision = {"decision": "block", "reason": _block_reason(state, report, path)}
    if warning:
        decision["systemMessage"] = warning
    _emit(stdout, decision)
    return 0


def _save_quietly(path: Path, state: dict, now_fn: Callable[[], datetime]) -> None:
    try:
        _save(path, state, now_fn)
    except (DriveError, goal_gate.GateError):
        pass


def _emit(stdout: TextIO, payload: dict) -> None:
    print(json.dumps(payload), file=stdout)


# -- CLI -----------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start", help="create the control state for a new goal")
    start.add_argument("--drive", required=True, type=Path)
    start.add_argument("--gate", required=True, type=Path)
    start.add_argument("--goal", required=True, help="the user's goal text, verbatim")
    start.add_argument("--session-id", help="defaults to CLAUDE_CODE_SESSION_ID")
    start.add_argument("--mode", choices=MODES, default="self",
                       help="host_goal when Claude Code's own /goal drives persistence")

    amend = commands.add_parser("amend", help="record a user audible and the reworded goal")
    amend.add_argument("--drive", required=True, type=Path)
    amend.add_argument("--user-words", required=True)
    amend.add_argument("--goal", required=True, help="the full reworded goal text")

    task = commands.add_parser("task", help="add a task or update one")
    task.add_argument("--drive", required=True, type=Path)
    task.add_argument("--id", required=True)
    task.add_argument("--title")
    task.add_argument("--owner", help="the role that owns it, e.g. rightsize-midlevel-doer")
    task.add_argument("--why")
    task.add_argument("--status", choices=TASK_STATUSES)
    task.add_argument("--source", choices=TASK_SOURCES)
    task.add_argument("--depends-on", help="comma-separated task ids that must be done first")
    task.add_argument("--area", help="code area or theme, e.g. installer or frontend/ui, used to match workers")
    task.add_argument("--family", help="dependency chain this task belongs to, planned as one worker's sequence")

    progress = commands.add_parser("progress", help="record meaningful progress")
    progress.add_argument("--drive", required=True, type=Path)
    progress.add_argument("--note", required=True)

    verdict = commands.add_parser("verdict", help="record the validator's verdict")
    verdict.add_argument("--drive", required=True, type=Path)
    verdict.add_argument("--verdict", required=True, choices=VERDICTS)
    verdict.add_argument("--reason", action="append", default=[])
    verdict.add_argument("--evidence", type=Path)
    verdict.add_argument("--validator", help="the validator's agent id")

    status = commands.add_parser("status", help="pause, wait, complete, or end incomplete")
    status.add_argument("--drive", required=True, type=Path)
    status.add_argument("--set", required=True, choices=STATUSES)
    status.add_argument("--reason")

    resume = commands.add_parser("resume", help="reactivate a goal and bind it to this session")
    resume.add_argument("--drive", required=True, type=Path)
    resume.add_argument("--session-id", help="defaults to CLAUDE_CODE_SESSION_ID")

    show = commands.add_parser("show", help="summarize the goal state")
    show.add_argument("--drive", required=True, type=Path)

    commands.add_parser("hook", help="Claude Code Stop hook entry point (reads the hook input on stdin)")
    return parser


def _refuse_second_active_goal(drive_path: Path, session: str) -> None:
    """One active goal per session: a second one would silently orphan the first."""
    for path in sorted(drive_path.parent.glob(f"*{SUFFIX}")):
        if path.resolve() == drive_path.resolve():
            continue
        try:
            other = load(path)
        except DriveError:
            continue
        if other["session_id"] == session and other["status"] == "active":
            raise DriveError(f"this session already owns active goal {other['goal_id']}; "
                             "complete, pause, or finish it before starting or resuming another")


def _session(args: argparse.Namespace, env: Mapping[str, str]) -> str:
    session = args.session_id or env.get("CLAUDE_CODE_SESSION_ID", "")
    if not session.strip():
        raise DriveError("no session id: pass --session-id or run inside Claude Code (CLAUDE_CODE_SESSION_ID)")
    return session


def _summary(path: Path, state: dict) -> dict:
    verdict = latest_verdict(state)
    return {
        "goal_id": state["goal_id"],
        "status": state["status"],
        "mode": state["mode"],
        "goal_version": state["goal"]["version"],
        "goal": state["goal"]["current"],
        "open_tasks": [{"id": t["id"], "title": t["title"], "owner": t.get("owner"), "status": t["status"],
                        "area": t.get("area"), "depends_on": t.get("depends_on") or []}
                       for t in open_tasks(state)],
        "ready_tasks": [{"id": t["id"], "title": t["title"], "owner": t.get("owner"), "area": t.get("area"),
                         "family": t.get("family")}
                        for t in ready_tasks(state)],
        "blocked_tasks": [{"id": t["id"], "title": t["title"], "waiting_on": _unmet(state, t)}
                          for t in blocked_tasks(state)],
        "latest_verdict": None if verdict is None else {"verdict": verdict["verdict"], "reasons": verdict["reasons"],
                                                         "goal_version": verdict["goal_version"]},
        "acceptance_fresh": acceptance_fresh(state),
        "drive": str(path),
    }


def _run(args: argparse.Namespace, now_fn: Callable[[], datetime], env: Mapping[str, str]) -> dict:
    now = _stamp(now_fn)
    if args.command == "start":
        session = _session(args, env)
        if not args.goal.strip():
            raise DriveError("goal text must be nonempty")
        goal_gate._load_state(args.gate)
        _refuse_second_active_goal(args.drive, session)
        state = {
            "version": DRIVE_VERSION,
            "goal_id": goal_id_for(args.drive),
            "session_id": session,
            "mode": args.mode,
            "status": "active",
            "status_reason": None,
            "gate": str(args.gate.resolve()),
            "created_at": now,
            "updated_at": now,
            "goal": {"original": args.goal, "current": args.goal, "version": 1, "amendments": []},
            "tasks": [],
            "work_epoch": 0,
            "activity": 0,
            "notes": [],
            "verdicts": [],
            "hook": {"last_activity": None, "stalled": 0, "limit_notified": False},
        }
        _validate(state)
        goal_gate._write_new(args.drive, state)
        return _summary(args.drive, state)

    state = load(args.drive)
    if args.command == "show":
        return _summary(args.drive, state)

    if args.command == "amend":
        if not args.user_words.strip() or not args.goal.strip():
            raise DriveError("user words and the reworded goal must be nonempty")
        goal = state["goal"]
        goal["version"] += 1
        goal["current"] = args.goal
        goal["amendments"].append({"version": goal["version"], "at": now,
                                   "user_words": args.user_words, "goal": args.goal})
        _bump(state, work=True)
    elif args.command == "task":
        existing = next((t for t in state["tasks"] if t["id"] == args.id), None)
        depends = None
        if args.depends_on is not None:
            depends = [item.strip() for item in args.depends_on.split(",") if item.strip()]
            known = {t["id"] for t in state["tasks"]}
            unknown = [dep for dep in depends if dep not in known or dep == args.id]
            if unknown:
                raise DriveError("--depends-on must name other existing tasks: " + ", ".join(unknown))
        if existing is None:
            if not (args.title and args.title.strip()) or not (args.why and args.why.strip()):
                raise DriveError("a new task needs --title and --why")
            state["tasks"].append({
                "id": args.id, "title": args.title, "owner": args.owner, "why": args.why,
                "status": args.status or "open", "source": args.source or "plan",
                "depends_on": depends or [], "area": args.area, "family": args.family,
                "added_at": now, "updated_at": now,
            })
        else:
            changes = {k: v for k, v in (("title", args.title), ("owner", args.owner), ("why", args.why),
                                          ("status", args.status), ("source", args.source),
                                          ("depends_on", depends), ("area", args.area),
                                          ("family", args.family)) if v is not None}
            if not changes:
                raise DriveError("nothing to update")
            existing.update(changes)
            existing["updated_at"] = now
        _bump(state, work=True)
    elif args.command == "progress":
        if not args.note.strip():
            raise DriveError("progress note must be nonempty")
        state["notes"] = (state["notes"] + [{"at": now, "note": args.note}])[-MAX_NOTES:]
        _bump(state, work=True)
    elif args.command == "verdict":
        reasons = [reason for reason in args.reason if reason.strip()]
        if not reasons:
            raise DriveError("a verdict needs at least one --reason")
        evidence = None
        if args.verdict == "DONE":
            if args.evidence is None or not args.evidence.exists():
                raise DriveError("a DONE verdict needs --evidence pointing at an existing file")
            evidence = str(args.evidence.resolve())
        earlier = {_normalize(r) for v in state["verdicts"] if v["verdict"] == "NOT_DONE" for r in v["reasons"]}
        repeated = [r for r in reasons if args.verdict == "NOT_DONE" and _normalize(r) in earlier]
        state["verdicts"].append({
            "verdict": args.verdict, "reasons": reasons, "evidence": evidence, "validator": args.validator,
            "goal_version": state["goal"]["version"], "work_epoch": state["work_epoch"], "at": now,
        })
        _bump(state, work=False)
        _save(args.drive, state, now_fn)
        return {**_summary(args.drive, state), "repeated_reasons": repeated}
    elif args.command == "status":
        target = args.set
        if target in ("paused", "waiting_on_user", "incomplete") and not (args.reason and args.reason.strip()):
            raise DriveError(f"status {target} needs --reason")
        if target in ("complete", "incomplete"):
            report = gate_report(state, now_fn)
            if target == "complete" and not acceptance_fresh(state):
                raise DriveError("status complete needs a DONE verdict for the current goal and work")
            if target == "complete" and report["decision"] != "completion_eligible":
                raise DriveError("status complete needs every gate minimum met: " + ", ".join(report["unmet"]))
            if target == "incomplete" and report["decision"] != "limit_reached":
                raise DriveError("status incomplete is only for a reached limit; pause instead")
        state["status"] = target
        state["status_reason"] = args.reason
        _bump(state, work=False)
    elif args.command == "resume":
        if state["status"] == "complete":
            raise DriveError("this goal is complete; start a new goal instead")
        session = _session(args, env)
        _refuse_second_active_goal(args.drive, session)
        state["session_id"] = session
        state["status"] = "active"
        state["status_reason"] = None
        state["hook"] = {"last_activity": None, "stalled": 0, "limit_notified": False}
        _bump(state, work=False)
    _save(args.drive, state, now_fn)
    return _summary(args.drive, state)


def main(
    argv: Sequence[str] | None = None,
    *,
    now_fn: Callable[[], datetime] = _utc_now,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    env: Mapping[str, str] | None = None,
) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if args.command == "hook":
        try:
            return hook(stdin, stdout, now_fn)
        except Exception:  # never let a hook bug trap or break the user's session
            return 0
    try:
        result = _run(args, now_fn, os.environ if env is None else env)
    except (DriveError, goal_gate.GateError) as exc:
        print(json.dumps({"error": str(exc)}), file=stderr)
        return 1
    print(json.dumps(result, sort_keys=True), file=stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
