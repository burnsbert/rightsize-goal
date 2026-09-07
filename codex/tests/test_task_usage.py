import importlib.util
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[1]
    / ".agents"
    / "skills"
    / "rightsize-goal"
    / "scripts"
    / "task_usage.py"
)
SPEC = importlib.util.spec_from_file_location("task_usage", MODULE_PATH)
usage = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(usage)


class TaskUsageTests(unittest.TestCase):
    def test_invalid_rates_and_inconsistent_categories_are_not_priced(self):
        tokens = {"input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 30, "reasoning_output_tokens": 10, "cache_write_tokens": 0}
        for invalid in (-1, float("nan"), float("inf")):
            tariff = {"models": {"m": {"input": invalid, "cached_input": .4, "output": 20}}}
            self.assertEqual(usage._cost({"m": tokens}, tariff)[0], "unavailable")
        tariff = {"models": {"m": {"input": 4, "cached_input": .4, "output": 20}}}
        self.assertEqual(usage._cost({"m": {**tokens, "cached_input_tokens": 101}}, tariff)[0], "unavailable")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.db = self.root / "usage.sqlite3"
        self.session = self.root / "rollout-thread-1.jsonl"
        self.tariff = self.root / "tariff.json"
        self.tariff.write_text(json.dumps({
            "version": "test-v1", "verified_on": "2026-01-01", "valid_until": "2099-01-01",
            "models": {
                "model-a": {"input": 4, "cached_input": .4, "output": 20, "source": "https://example/a"},
                "model-b": {"input": 2, "cached_input": .2, "output": 12, "source": "https://example/b"},
            },
        }), encoding="utf-8")
        self._append({"type": "session_meta", "payload": {"id": "thread-1", "cwd": "ignored"}})
        self._turn("model-a", "medium")
        self._tokens(100, 20, 30, 10)

    def tearDown(self):
        self.temporary.cleanup()

    def _append(self, value, partial=False):
        with self.session.open("a", encoding="utf-8") as stream:
            text = json.dumps(value)
            stream.write(text[:-2] if partial else text + "\n")

    def _turn(self, model, effort):
        self._append({"type": "turn_context", "payload": {"model": model, "effort": effort, "other": "ignored"}})

    def _tokens(self, input_tokens, cached, output, reasoning, cache_write=0):
        self._append({"type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": {"input_tokens": input_tokens, "cached_input_tokens": cached,
                                  "cache_write_input_tokens": cache_write, "output_tokens": output,
                                  "reasoning_output_tokens": reasoning,
                                  "total_tokens": input_tokens + output}}}})

    def _call(self, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        code = usage.main(["--db", str(self.db), *arguments], stdout=stdout, stderr=stderr)
        output = stdout.getvalue() if code == 0 else stderr.getvalue()
        return code, json.loads(output)

    def _start(self, task="task-1", run="run-1", **extra):
        arguments = ["start", "--run", run, "--task", task, "--project-tag", "project",
                     "--role", "worker", "--model", "model-a", "--effort", "medium",
                     "--mode", "delegated", "--difficulty", "routine", "--thread-id", "thread-1",
                     "--session", str(self.session), "--tariff", str(self.tariff)]
        if extra.get("prior"):
            arguments += ["--prior-task", extra["prior"]]
        return self._call(*arguments)

    def test_delta_cost_and_reasoning_is_not_double_counted(self):
        self.assertEqual(self._start()[0], 0)
        self._tokens(200, 50, 70, 25)
        code, result = self._call("finish", "--run", "run-1", "--task", "task-1",
                                  "--outcome", "accepted", "--lesson", "small lesson")
        self.assertEqual(code, 0)
        self.assertEqual(result["tokens"]["input_tokens"], 100)
        self.assertEqual(result["tokens"]["reasoning_output_tokens"], 15)
        # (70 uncached * 4 + 30 cached * .4 + 40 output * 20) / 1M
        self.assertAlmostEqual(result["cost_usd"], 0.001092)
        self.assertEqual(result["tariff_version"], "test-v1")
        self.assertIn("UTC", result["recorded_at"])

    def test_active_thread_reuse_is_rejected_then_finish_is_idempotent(self):
        self.assertEqual(self._start()[0], 0)
        code, error = self._start(task="task-2")
        self.assertEqual(code, 1)
        self.assertIn("already has active task", error["error"])
        self._tokens(101, 20, 31, 10)
        first = self._call("finish", "--run", "run-1", "--task", "task-1", "--outcome", "rework")[1]
        second = self._call("finish", "--run", "run-1", "--task", "task-1", "--outcome", "accepted")[1]
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["outcome"], "rework")

    def test_missing_finish_telemetry_is_terminal_and_explicitly_unavailable(self):
        self.assertEqual(self._start()[0], 0)
        self.session.unlink()
        code, result = self._call("finish", "--run", "run-1", "--task", "task-1", "--outcome", "failed")
        self.assertEqual(code, 0)
        self.assertEqual(result["usage_status"], "unavailable")
        self.assertIsNone(result["cost_usd"])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT status FROM tasks").fetchone()[0], "finished")
        db.close()

    def test_mixed_model_delta_is_attributed_and_priced_to_actual_model(self):
        self.assertEqual(self._start()[0], 0)
        self._turn("model-b", "high")
        self._tokens(150, 30, 50, 15)
        result = self._call("finish", "--run", "run-1", "--task", "task-1", "--outcome", "accepted")[1]
        self.assertEqual(result["actual_models"], ["model-b"])
        self.assertEqual(result["actual_efforts"], ["high"])
        # (40 uncached * 2 + 10 cached * .2 + 20 output * 12) / 1M
        self.assertAlmostEqual(result["cost_usd"], 0.000322)

    def test_counter_reset_during_task_is_unavailable(self):
        self.assertEqual(self._start()[0], 0)
        self._tokens(10, 2, 3, 1)
        result = self._call("finish", "--run", "run-1", "--task", "task-1", "--outcome", "unresolved")[1]
        self.assertEqual(result["usage_status"], "unavailable")
        self.assertIn("reset", result["usage_reason"])

    def test_cache_write_and_partial_jsonl_are_conservative(self):
        self.assertEqual(self._start()[0], 0)
        self._tokens(110, 22, 33, 11, cache_write=5)
        self._append({"type": "event_msg", "payload": {"type": "token_count"}}, partial=True)
        result = self._call("finish", "--run", "run-1", "--task", "task-1", "--outcome", "accepted")[1]
        self.assertEqual(result["usage_status"], "available")
        self.assertEqual(result["cost_status"], "unavailable")
        self.assertIn("cache-write", result["cost_reason"])

    def test_global_report_filters_groups_actuals_and_preserves_unknowns(self):
        self.assertEqual(self._start()[0], 0)
        self._tokens(120, 25, 35, 12)
        self._call("finish", "--run", "run-1", "--task", "task-1", "--outcome", "accepted", "--lesson", "keep it bounded")
        # A new thread baseline is explicitly zero; no tariff makes its cost unknown, not zero.
        code, _ = self._call("start", "--run", "run-2", "--task", "task-2", "--project-tag", "other",
                             "--role", "worker", "--model", "model-a", "--effort", "low", "--mode", "local",
                             "--difficulty", "basic", "--thread-id", "fresh-thread", "--new-thread")
        self.assertEqual(code, 0)
        self._call("finish", "--run", "run-2", "--task", "task-2", "--outcome", "cancelled")
        report = self._call("report", "--project-tag", "project")[1]
        self.assertEqual(report["samples"], 1)
        group = report["groups"][0]
        self.assertEqual((group["model"], group["effort"]), ("model-a", "medium"))
        self.assertEqual(group["cost_coverage"], {"known": 1, "unknown": 0})
        self.assertEqual(group["lessons"][0]["lesson"], "keep it bounded")
        self.assertEqual(group["lessons"][0]["task"], "task-1")

    def test_expired_tariff_keeps_usage_but_marks_cost_unavailable(self):
        tariff = json.loads(self.tariff.read_text(encoding="utf-8"))
        tariff["valid_until"] = "2000-01-01"
        self.tariff.write_text(json.dumps(tariff), encoding="utf-8")
        self.assertEqual(self._start()[0], 0)
        self._tokens(105, 21, 32, 11)
        result = self._call("finish", "--run", "run-1", "--task", "task-1", "--outcome", "accepted")[1]
        self.assertEqual(result["usage_status"], "available")
        self.assertEqual(result["cost_status"], "unavailable")
        self.assertIn("expired", result["cost_reason"])


if __name__ == "__main__":
    unittest.main()
