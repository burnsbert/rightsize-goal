import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[1] / "skills" / "rightsize-goal" / "scripts" / "goal_gate.py"
)
SPEC = importlib.util.spec_from_file_location("goal_gate", MODULE_PATH)
goal_gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(goal_gate)


START = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)


class GoalGateTests(unittest.TestCase):
    def test_corrupt_encoding_and_boolean_version_are_rejected(self):
        self.init()
        saved = json.loads(self.state.read_text(encoding="utf-8"))
        saved["version"] = True
        for data in (b"\xff", json.dumps(saved).encode("utf-8")):
            with self.subTest(data=data):
                self.state.write_bytes(data)
                code, _, error = self.run_cli(["check", "--state", str(self.state)])
                self.assertEqual(1, code)
                self.assertIsNotNone(error)
                self.assertEqual(data, self.state.read_bytes())

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "goal.json"
        self.evidence = self.root / "evidence.txt"
        self.evidence.write_text("verified\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, arguments, now=START):
        stdout, stderr = io.StringIO(), io.StringIO()
        code = goal_gate.main(
            arguments,
            now_fn=lambda: now,
            stdout=stdout,
            stderr=stderr,
        )
        output = json.loads(stdout.getvalue()) if stdout.getvalue() else None
        error = json.loads(stderr.getvalue()) if stderr.getvalue() else None
        return code, output, error

    def init(self, *bounds):
        return self.run_cli(
            ["init", "--state", str(self.state), "--objective", "Ship it", *bounds]
        )

    def add_iteration(self, identifier, now=START):
        return self.run_cli(
            [
                "iteration",
                "--state",
                str(self.state),
                "--id",
                identifier,
                "--hypothesis",
                "A",
                "--action",
                "B",
                "--result",
                "C",
                "--evidence",
                str(self.evidence),
            ],
            now=now,
        )

    def test_reported_case_one_hour_ten_iterations_still_continues(self):
        self.init("--min-hours", "6", "--min-iterations", "20")
        for number in range(10):
            self.add_iteration(f"i{number}", START + timedelta(minutes=number))
        code, report, error = self.run_cli(
            ["check", "--state", str(self.state), "--acceptance-met"],
            now=START + timedelta(hours=1),
        )
        self.assertEqual(2, code)
        self.assertIsNone(error)
        self.assertEqual("continue", report["decision"])
        self.assertEqual({"min_hours", "min_iterations"}, set(report["unmet"]))
        self.assertEqual(1.0, report["elapsed_hours"])
        self.assertEqual(10, report["iteration_count"])
        self.assertIn("not billed or active work time", report["elapsed_basis"])

    def test_duration_flags_persist_and_enforce_exact_boundaries(self):
        code, state, error = self.init(
            "--minimum-time=30 minutes", "--maximum-time=3 hours"
        )
        self.assertEqual(0, code)
        self.assertIsNone(error)
        self.assertEqual({"min_hours": 0.5, "max_hours": 3.0}, state["bounds"])
        self.assertEqual("2026-01-02T12:30:00Z", state["not_before"])
        self.assertEqual("2026-01-02T15:00:00Z", state["deadline"])
        for seconds, acceptance, expected in (
            (1799, True, 2), (1800, True, 0),
            (10799, False, 2), (10800, False, 3),
        ):
            with self.subTest(seconds=seconds, acceptance=acceptance):
                args = ["check", "--state", str(self.state)]
                if acceptance:
                    args.append("--acceptance-met")
                code, _, _ = self.run_cli(args, now=START + timedelta(seconds=seconds))
                self.assertEqual(expected, code)

    def test_supported_duration_units(self):
        for text, hours in (("30m", .5), ("1.5 HOURS", 1.5), ("60 seconds", 1/60), (".5 day", 12), ("0 minutes", 0)):
            with self.subTest(text=text):
                self.assertAlmostEqual(hours, goal_gate._duration_hours(text))

    def test_invalid_duration_and_conflicting_alias_fail_without_state(self):
        for args in (
            ("--minimum-time=-1 minutes",),
            ("--minimum-time=30",),
            ("--maximum-time=forever",),
            ("--minimum-time=NaN hours",),
            ("--minimum-time=30 minutes", "--min-hours=1"),
            ("--maximum-time=3 hours", "--max-hours=4"),
        ):
            with self.subTest(args=args), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    self.init(*args)
                self.assertEqual(2, raised.exception.code)
                self.assertFalse(self.state.exists())

    def test_duration_maximum_below_minimum_rejected(self):
        code, _, error = self.init("--minimum-time=3 hours", "--maximum-time=30 minutes")
        self.assertEqual(1, code)
        self.assertIn("max-hours", error["error"])
        self.assertFalse(self.state.exists())

    def test_acceptance_and_both_minima_are_a_conjunction(self):
        self.init("--min-hours", "1", "--min-iterations", "1")
        self.add_iteration("i1", START + timedelta(minutes=1))
        code, report, _ = self.run_cli(
            ["check", "--state", str(self.state)], now=START + timedelta(hours=2)
        )
        self.assertEqual((2, ["acceptance"]), (code, report["unmet"]))
        code, report, _ = self.run_cli(
            ["check", "--state", str(self.state), "--acceptance-met"],
            now=START + timedelta(hours=2),
        )
        self.assertEqual((0, "completion_eligible"), (code, report["decision"]))

    def test_cap_is_incomplete_when_minimum_or_acceptance_is_unmet(self):
        self.init(
            "--min-hours",
            "2",
            "--max-hours",
            "3",
            "--min-iterations",
            "2",
            "--max-iterations",
            "4",
        )
        code, report, _ = self.run_cli(
            ["check", "--state", str(self.state), "--acceptance-met"],
            now=START + timedelta(hours=3),
        )
        self.assertEqual(3, code)
        self.assertEqual("limit_reached", report["decision"])
        self.assertEqual(["min_iterations"], report["unmet"])
        self.assertEqual(["max_hours"], report["limits_reached"])

    def test_cap_does_not_override_completed_conditions(self):
        self.init("--min-iterations", "1", "--max-iterations", "1")
        self.add_iteration("only")
        code, report, _ = self.run_cli(
            ["check", "--state", str(self.state), "--acceptance-met"]
        )
        self.assertEqual((0, "completion_eligible"), (code, report["decision"]))
        self.assertEqual(["max_iterations"], report["limits_reached"])

    def test_duplicate_iteration_and_reinit_preserve_state(self):
        self.init("--min-iterations", "2")
        self.add_iteration("same")
        before = self.state.read_bytes()
        code, _, error = self.add_iteration("same", START + timedelta(minutes=2))
        self.assertEqual(1, code)
        self.assertIn("duplicate", error["error"])
        self.assertEqual(before, self.state.read_bytes())
        code, _, error = self.init("--min-iterations", "99")
        self.assertEqual(1, code)
        self.assertIn("already exists", error["error"])
        self.assertEqual(before, self.state.read_bytes())

    def test_missing_evidence_does_not_mutate_state(self):
        self.init()
        before = self.state.read_bytes()
        self.evidence.unlink()
        code, _, error = self.add_iteration("missing")
        self.assertEqual(1, code)
        self.assertIn("evidence does not exist", error["error"])
        self.assertEqual(before, self.state.read_bytes())

    def test_inconsistent_bounds_are_rejected_without_creating_state(self):
        code, _, error = self.init("--min-hours", "6", "--max-hours", "5")
        self.assertEqual(1, code)
        self.assertIn("max-hours", error["error"])
        self.assertFalse(self.state.exists())

        code, _, error = self.init(
            "--min-iterations", "20", "--max-iterations", "10"
        )
        self.assertEqual(1, code)
        self.assertIn("max-iterations", error["error"])
        self.assertFalse(self.state.exists())

    def test_malformed_state_and_backwards_clock_are_non_mutating(self):
        self.state.write_text("not json", encoding="utf-8")
        before = self.state.read_bytes()
        code, _, error = self.run_cli(["check", "--state", str(self.state)])
        self.assertEqual(1, code)
        self.assertIn("cannot read valid state", error["error"])
        self.assertEqual(before, self.state.read_bytes())

        self.state.unlink()
        self.init()
        before = self.state.read_bytes()
        code, _, error = self.run_cli(
            ["check", "--state", str(self.state)], now=START - timedelta(seconds=1)
        )
        self.assertEqual(1, code)
        self.assertIn("clock moved backwards", error["error"])
        self.assertEqual(before, self.state.read_bytes())


if __name__ == "__main__":
    unittest.main()
