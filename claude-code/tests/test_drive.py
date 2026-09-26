import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "skills" / "rightsize-goal" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("drive", SCRIPTS / "drive.py")
drive = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(drive)
import goal_gate  # noqa: E402


START = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
SESSION = "11111111-2222-3333-4444-555555555555"


class DriveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run_dir = self.root / ".rightsize-goal"
        self.run_dir.mkdir()
        self.gate = self.run_dir / "G1.gate.json"
        self.drive_path = self.run_dir / "G1.drive.json"
        self.evidence = self.root / "evidence.txt"
        self.evidence.write_text("tests passed\n", encoding="utf-8")
        self.now = START

    def tearDown(self):
        self.temporary.cleanup()

    # -- helpers ---------------------------------------------------------

    def gate_init(self, *bounds):
        code = goal_gate.main(
            ["init", "--state", str(self.gate), "--objective", "Ship it", *bounds],
            now_fn=lambda: START, stdout=io.StringIO(), stderr=io.StringIO(),
        )
        self.assertEqual(0, code)

    def cli(self, *arguments, stdin="", env=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        code = drive.main(
            list(arguments), now_fn=lambda: self.now, stdin=io.StringIO(stdin),
            stdout=stdout, stderr=stderr,
            env={"CLAUDE_CODE_SESSION_ID": SESSION} if env is None else env,
        )
        out = stdout.getvalue()
        err = stderr.getvalue()
        return code, (json.loads(out) if out.strip() else None), (json.loads(err) if err.strip() else None)

    def start(self, *extra, bounds=()):
        self.gate_init(*bounds)
        code, out, err = self.cli(
            "start", "--drive", str(self.drive_path), "--gate", str(self.gate),
            "--goal", "Add CSV export; exported rows match the active filters and tests pass.",
            *extra,
        )
        self.assertEqual(0, code, err)
        return out

    def hook(self, session=SESSION, cwd=None, stop_hook_active=False):
        payload = {
            "session_id": session,
            "cwd": str(cwd or self.root),
            "hook_event_name": "Stop",
            "stop_hook_active": stop_hook_active,
            "transcript_path": str(self.root / "t.jsonl"),
        }
        code, out, err = self.cli("hook", stdin=json.dumps(payload))
        self.assertEqual(0, code, "the hook must never fail the host")
        return out

    def assert_blocks(self, output):
        self.assertIsNotNone(output, "expected the hook to block the stop")
        self.assertEqual("block", output.get("decision"))
        self.assertTrue(output.get("reason", "").strip())
        return output["reason"]

    def assert_allows(self, output):
        self.assertTrue(output is None or output.get("decision") != "block", output)

    def done(self):
        return self.cli(
            "verdict", "--drive", str(self.drive_path), "--verdict", "DONE",
            "--reason", "all acceptance checks verified", "--evidence", str(self.evidence),
        )

    # -- start and binding -----------------------------------------------

    def test_start_records_original_goal_and_binds_session_from_environment(self):
        out = self.start()
        saved = json.loads(self.drive_path.read_text(encoding="utf-8"))
        self.assertEqual(SESSION, saved["session_id"])
        self.assertEqual("active", saved["status"])
        self.assertEqual(saved["goal"]["original"], saved["goal"]["current"])
        self.assertEqual(1, saved["goal"]["version"])
        self.assertEqual("G1", out["goal_id"])

    def test_start_refuses_to_overwrite_and_requires_a_session(self):
        self.start()
        code, _, err = self.cli("start", "--drive", str(self.drive_path), "--gate", str(self.gate), "--goal", "x")
        self.assertEqual(1, code)
        self.assertIn("exists", err["error"])
        other = self.run_dir / "G2.drive.json"
        code, _, err = self.cli("start", "--drive", str(other), "--gate", str(self.gate), "--goal", "x", env={})
        self.assertEqual(1, code)
        self.assertIn("session", err["error"])

    # -- hook scoping ----------------------------------------------------

    def test_hook_is_silent_without_an_active_goal(self):
        self.assert_allows(self.hook())
        self.assertIsNone(self.hook())

    def test_hook_ignores_goals_bound_to_other_sessions(self):
        self.start()
        self.assertIsNone(self.hook(session="someone-else"))

    def test_hook_stands_down_when_a_host_goal_drives(self):
        self.start("--mode", "host_goal")
        self.assertIsNone(self.hook())

    # -- blocking and the reason ------------------------------------------

    def test_hook_blocks_an_unvalidated_goal_and_names_open_tasks(self):
        self.start()
        self.cli("task", "--drive", str(self.drive_path), "--id", "T1", "--title", "Add export endpoint",
                 "--owner", "rightsize-midlevel-doer", "--why", "core of the goal")
        self.cli("task", "--drive", str(self.drive_path), "--id", "T2", "--title", "Old idea", "--why", "x")
        self.cli("task", "--drive", str(self.drive_path), "--id", "T2", "--status", "dropped")
        reason = self.assert_blocks(self.hook())
        self.assertIn("G1", reason)
        self.assertIn("T1", reason)
        self.assertIn("Add export endpoint", reason)
        self.assertNotIn("Old idea", reason)
        self.assertIn("rightsize-validator", reason)

    def test_hook_keeps_blocking_even_when_stop_hook_active_while_progress_continues(self):
        self.start()
        for step in range(5):
            self.cli("progress", "--drive", str(self.drive_path), "--note", f"step {step}")
            self.assert_blocks(self.hook(stop_hook_active=True))

    def test_not_done_verdict_reasons_are_fed_back(self):
        self.start()
        code, out, _ = self.cli(
            "verdict", "--drive", str(self.drive_path), "--verdict", "NOT_DONE",
            "--reason", "date filter is ignored in the export",
        )
        self.assertEqual(0, code)
        self.assertEqual([], out["repeated_reasons"])
        reason = self.assert_blocks(self.hook())
        self.assertIn("date filter is ignored", reason)

    def test_not_done_requires_reasons_and_done_requires_evidence(self):
        self.start()
        code, _, _ = self.cli("verdict", "--drive", str(self.drive_path), "--verdict", "NOT_DONE")
        self.assertEqual(1, code)
        code, _, _ = self.cli("verdict", "--drive", str(self.drive_path), "--verdict", "DONE", "--reason", "ok")
        self.assertEqual(1, code)
        code, _, _ = self.cli(
            "verdict", "--drive", str(self.drive_path), "--verdict", "DONE", "--reason", "ok",
            "--evidence", str(self.root / "missing.txt"),
        )
        self.assertEqual(1, code)

    def test_repeated_not_done_reason_is_reported(self):
        self.start()
        args = ("verdict", "--drive", str(self.drive_path), "--verdict", "NOT_DONE")
        self.cli(*args, "--reason", "Date filter is ignored.")
        self.cli("task", "--drive", str(self.drive_path), "--id", "T9", "--title", "fix", "--why", "verdict")
        code, out, _ = self.cli(*args, "--reason", "date filter is ignored", "--reason", "quoting broken")
        self.assertEqual(0, code)
        self.assertEqual(["date filter is ignored"], out["repeated_reasons"])

    def test_reason_repeated_from_any_earlier_verdict_is_reported(self):
        self.start()
        args = ("verdict", "--drive", str(self.drive_path), "--verdict", "NOT_DONE")
        self.cli(*args, "--reason", "quoting broken")
        self.cli(*args, "--reason", "date filter ignored")
        code, out, _ = self.cli(*args, "--reason", "Quoting broken!")
        self.assertEqual(0, code)
        self.assertEqual(["Quoting broken!"], out["repeated_reasons"])

    # -- DONE and freshness ----------------------------------------------

    def test_fresh_done_verdict_allows_the_stop(self):
        self.start()
        self.assertEqual(0, self.done()[0])
        self.assert_allows(self.hook())

    def test_amendment_makes_a_done_verdict_stale(self):
        self.start()
        self.done()
        code, out, _ = self.cli(
            "amend", "--drive", str(self.drive_path), "--user-words", "also support TSV",
            "--goal", "Add CSV and TSV export; rows match filters and tests pass.",
        )
        self.assertEqual(0, code)
        self.assertEqual(2, out["goal_version"])
        saved = json.loads(self.drive_path.read_text(encoding="utf-8"))
        self.assertEqual("also support TSV", saved["goal"]["amendments"][0]["user_words"])
        self.assertTrue(saved["goal"]["original"].startswith("Add CSV export;"))
        reason = self.assert_blocks(self.hook())
        self.assertIn("amended", reason.lower())

    def test_done_for_an_older_goal_version_is_not_fresh_even_without_new_work(self):
        self.start()
        self.done()
        state = json.loads(self.drive_path.read_text(encoding="utf-8"))
        self.assertTrue(drive.acceptance_fresh(state))
        state["goal"]["version"] += 1
        self.assertFalse(drive.acceptance_fresh(state))

    def test_work_after_done_makes_the_verdict_stale(self):
        self.start()
        self.done()
        self.cli("task", "--drive", str(self.drive_path), "--id", "T5", "--title", "late change", "--why", "x")
        self.assert_blocks(self.hook())

    def test_done_does_not_override_unmet_minimums(self):
        self.start(bounds=("--min-iterations", "2"))
        self.done()
        reason = self.assert_blocks(self.hook())
        self.assertIn("iteration", reason.lower())
        self.assertNotIn("dispatch rightsize-validator", reason)

    def test_complete_status_requires_a_fresh_done_verdict(self):
        self.start()
        code, _, err = self.cli("status", "--drive", str(self.drive_path), "--set", "complete")
        self.assertEqual(1, code)
        self.assertIn("DONE", err["error"])
        self.done()
        code, _, _ = self.cli("status", "--drive", str(self.drive_path), "--set", "complete")
        self.assertEqual(0, code)
        self.assertIsNone(self.hook())

    # -- pause, resume, waiting ------------------------------------------

    def test_pause_allows_stopping_and_resume_rebinds_the_session(self):
        self.start()
        code, _, _ = self.cli("status", "--drive", str(self.drive_path), "--set", "paused",
                              "--reason", "user said pause")
        self.assertEqual(0, code)
        self.assertIsNone(self.hook())
        new_session = "99999999-8888-7777-6666-555555555555"
        code, out, _ = self.cli("resume", "--drive", str(self.drive_path),
                                env={"CLAUDE_CODE_SESSION_ID": new_session})
        self.assertEqual(0, code)
        self.assertEqual("active", out["status"])
        self.assertIsNone(self.hook(session=SESSION))
        self.assert_blocks(self.hook(session=new_session))

    def test_waiting_on_user_allows_stopping(self):
        self.start()
        self.cli("status", "--drive", str(self.drive_path), "--set", "waiting_on_user",
                 "--reason", "need the production database name")
        self.assertIsNone(self.hook())

    def test_status_rejects_unknown_values_and_needs_reasons_for_pause_and_waiting(self):
        self.start()
        with redirect_stderr(io.StringIO()):
            code, _, _ = self.cli("status", "--drive", str(self.drive_path), "--set", "stopped")
        self.assertNotEqual(0, code)
        code, _, _ = self.cli("status", "--drive", str(self.drive_path), "--set", "waiting_on_user")
        self.assertEqual(1, code)

    def test_block_reason_gives_runnable_drive_commands(self):
        self.start()
        reason = self.assert_blocks(self.hook())
        self.assertIn(str((SCRIPTS / "drive.py").resolve()), reason)
        self.assertIn(str(self.drive_path.resolve()), reason)
        for command in ("task", "progress", "verdict", "status"):
            self.assertIn(f"drive.py\" {command} --drive", reason)
        self.assertIn("never edit", reason.lower())

    # -- dependencies and areas -----------------------------------------

    def add(self, task, *extra):
        code, out, err = self.cli("task", "--drive", str(self.drive_path), "--id", task,
                                  "--title", f"work {task}", "--why", "goal", *extra)
        self.assertEqual(0, code, err)
        return out

    def test_tasks_record_dependencies_and_areas(self):
        self.start()
        self.add("T1", "--area", "installer")
        self.add("T2", "--area", "installer", "--depends-on", "T1")
        saved = {t["id"]: t for t in json.loads(self.drive_path.read_text(encoding="utf-8"))["tasks"]}
        self.assertEqual(["T1"], saved["T2"]["depends_on"])
        self.assertEqual("installer", saved["T2"]["area"])

    def test_tasks_record_a_family_shown_to_the_coordinator(self):
        self.start()
        self.add("T1", "--area", "installer", "--family", "install-chain")
        self.add("T2", "--family", "install-chain", "--depends-on", "T1")
        saved = {t["id"]: t for t in json.loads(self.drive_path.read_text(encoding="utf-8"))["tasks"]}
        self.assertEqual("install-chain", saved["T2"]["family"])
        _, out, _ = self.cli("show", "--drive", str(self.drive_path))
        self.assertEqual("install-chain", out["ready_tasks"][0]["family"])
        self.assertIn("install-chain", self.assert_blocks(self.hook()))

    def test_dependencies_must_name_existing_tasks(self):
        self.start()
        code, _, err = self.cli("task", "--drive", str(self.drive_path), "--id", "T2", "--title", "x",
                                "--why", "goal", "--depends-on", "T9")
        self.assertEqual(1, code)
        self.assertIn("T9", err["error"])

    def test_hook_separates_ready_tasks_from_blocked_ones(self):
        self.start()
        self.add("T1")
        self.add("T2", "--depends-on", "T1")
        reason = self.assert_blocks(self.hook())
        ready, waiting = reason.split("Waiting on other tasks:")
        self.assertIn("T1", ready)
        self.assertNotIn("T2 ", ready)
        self.assertIn("T2", waiting)
        self.assertIn("after T1", waiting)
        self.cli("task", "--drive", str(self.drive_path), "--id", "T1", "--status", "done")
        reason = self.assert_blocks(self.hook())
        self.assertIn("T2", reason.split("Ready to start:")[1])
        self.assertNotIn("Waiting on other tasks:", reason)

    def test_show_lists_ready_and_blocked_tasks(self):
        self.start()
        self.add("T1")
        self.add("T2", "--depends-on", "T1")
        self.add("T3")
        self.cli("task", "--drive", str(self.drive_path), "--id", "T3", "--status", "dropped")
        _, out, _ = self.cli("show", "--drive", str(self.drive_path))
        self.assertEqual(["T1"], [t["id"] for t in out["ready_tasks"]])
        self.assertEqual(["T2"], [t["id"] for t in out["blocked_tasks"]])

    def test_a_dropped_dependency_does_not_block(self):
        self.start()
        self.add("T1")
        self.add("T2", "--depends-on", "T1")
        self.cli("task", "--drive", str(self.drive_path), "--id", "T1", "--status", "dropped")
        _, out, _ = self.cli("show", "--drive", str(self.drive_path))
        self.assertEqual(["T2"], [t["id"] for t in out["ready_tasks"]])

    # -- waiting on workers ----------------------------------------------

    def test_in_progress_task_allows_a_quiet_stop_without_counting_a_stall(self):
        self.start()
        self.cli("task", "--drive", str(self.drive_path), "--id", "T1", "--title", "Build export",
                 "--why", "goal", "--status", "in_progress")
        for _ in range(drive.STALL_LIMIT + 2):
            self.assertIsNone(self.hook())
        self.assertEqual(0, json.loads(self.drive_path.read_text(encoding="utf-8"))["hook"]["stalled"])
        self.cli("task", "--drive", str(self.drive_path), "--id", "T1", "--status", "done")
        self.assert_blocks(self.hook())

    def test_block_reason_explains_how_to_wait_for_workers(self):
        self.start()
        reason = self.assert_blocks(self.hook())
        self.assertIn("mark their tasks in_progress and end your turn to wait", reason)

    def test_a_reached_limit_still_asks_for_a_handoff_while_workers_run(self):
        self.start(bounds=("--max-iterations", "0"))
        self.cli("task", "--drive", str(self.drive_path), "--id", "T1", "--title", "x",
                 "--why", "goal", "--status", "in_progress")
        self.assertIn("limit", self.assert_blocks(self.hook()).lower())

    # -- loop safety -----------------------------------------------------

    def test_no_progress_releases_the_stop_and_progress_rearms_it(self):
        self.start()
        for _ in range(drive.STALL_LIMIT):
            self.assert_blocks(self.hook())
        released = self.hook()
        self.assert_allows(released)
        self.assertIn("no recorded progress", released["systemMessage"])
        self.cli("progress", "--drive", str(self.drive_path), "--note", "user steered; new plan")
        self.assert_blocks(self.hook())

    def test_limit_reached_asks_once_for_a_handoff_then_allows(self):
        self.start(bounds=("--max-iterations", "0"))
        reason = self.assert_blocks(self.hook())
        self.assertIn("limit", reason.lower())
        self.assert_allows(self.hook())
        code, _, _ = self.cli("status", "--drive", str(self.drive_path), "--set", "incomplete",
                              "--reason", "iteration limit reached")
        self.assertEqual(0, code)
        self.assertIsNone(self.hook())

    def test_incomplete_status_requires_a_reached_limit(self):
        self.start()
        code, _, err = self.cli("status", "--drive", str(self.drive_path), "--set", "incomplete",
                                "--reason", "tired")
        self.assertEqual(1, code)
        self.assertIn("limit", err["error"])

    def test_deadline_counts_as_a_limit(self):
        self.start(bounds=("--maximum-time", "1 hour"))
        self.now = START + timedelta(hours=2)
        self.assertIn("limit", self.assert_blocks(self.hook()).lower())

    # -- fail open -------------------------------------------------------

    def test_corrupt_state_fails_open_with_a_message(self):
        self.start()
        self.drive_path.write_text("{not json", encoding="utf-8")
        out = self.hook()
        self.assert_allows(out)
        self.assertIn("G1.drive.json", out["systemMessage"])

    def test_missing_gate_fails_open(self):
        self.start()
        self.gate.unlink()
        out = self.hook()
        self.assert_allows(out)
        self.assertIn("systemMessage", out)

    def test_unexpected_hook_error_allows_the_stop(self):
        self.start()
        original = drive.gate_report
        drive.gate_report = lambda *a, **k: 1 / 0
        try:
            self.assert_allows(self.hook())
        finally:
            drive.gate_report = original

    def test_malformed_hook_input_is_ignored(self):
        code, out, _ = self.cli("hook", stdin="not json")
        self.assertEqual(0, code)
        self.assertIsNone(out)

    def second_goal(self):
        second_gate = self.run_dir / "G2.gate.json"
        goal_gate.main(["init", "--state", str(second_gate), "--objective", "Next"],
                       now_fn=lambda: START, stdout=io.StringIO(), stderr=io.StringIO())
        self.now = START + timedelta(minutes=5)
        second = self.run_dir / "G2.drive.json"
        return self.cli("start", "--drive", str(second), "--gate", str(second_gate), "--goal", "Second goal")

    def test_start_refuses_while_the_session_owns_an_active_goal(self):
        self.start()
        code, _, err = self.second_goal()
        self.assertEqual(1, code)
        self.assertIn("G1", err["error"])
        self.assertFalse((self.run_dir / "G2.drive.json").exists())

    def test_a_new_goal_can_start_once_the_previous_one_is_paused(self):
        self.start()
        self.cli("status", "--drive", str(self.drive_path), "--set", "paused", "--reason", "switching")
        code, _, err = self.second_goal()
        self.assertEqual(0, code, err)
        self.assertIn("G2", self.assert_blocks(self.hook()))

    def test_resume_refuses_while_the_session_owns_another_active_goal(self):
        self.start()
        self.cli("status", "--drive", str(self.drive_path), "--set", "paused", "--reason", "switching")
        self.second_goal()
        code, _, err = self.cli("resume", "--drive", str(self.drive_path))
        self.assertEqual(1, code)
        self.assertIn("G2", err["error"])
        self.assertEqual("paused", json.loads(self.drive_path.read_text(encoding="utf-8"))["status"])

    def test_another_sessions_active_goal_does_not_block_start(self):
        self.start("--session-id", "someone-else")
        code, _, err = self.second_goal()
        self.assertEqual(0, code, err)

    def test_corrupt_sibling_is_reported_alongside_a_working_goal(self):
        self.start()
        (self.run_dir / "G9.drive.json").write_text("{broken", encoding="utf-8")
        out = self.hook()
        self.assert_blocks(out)
        self.assertIn("G9.drive.json", out["systemMessage"])


if __name__ == "__main__":
    unittest.main()
