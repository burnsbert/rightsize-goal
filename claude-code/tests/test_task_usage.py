import importlib.util
import io
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = (
    Path(__file__).parents[1] / "skills" / "rightsize-goal" / "scripts" / "task_usage.py"
)
SPEC = importlib.util.spec_from_file_location("task_usage", MODULE_PATH)
usage = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(usage)

TARIFF = {
    "version": "test-rates-1",
    "verified_on": "2026-01-01",
    "valid_until": "2999-01-01",
    "models": {
        "test-model": {
            "input": 1.0, "cache_read": 2.0, "cache_write_5m": 4.0,
            "cache_write_1h": 8.0, "output": 16.0,
        }
    },
}


def turn(request_id, *, model="test-model", effort="medium", inp=0, read=0,
         write_5m=0, write_1h=0, out=0, sidechain=True, cache_split=True):
    """One assistant record shaped like a Claude Code transcript line."""
    usage_object = {
        "input_tokens": inp,
        "cache_read_input_tokens": read,
        "cache_creation_input_tokens": write_5m + write_1h,
        "output_tokens": out,
    }
    if cache_split:
        usage_object["cache_creation"] = {
            "ephemeral_5m_input_tokens": write_5m,
            "ephemeral_1h_input_tokens": write_1h,
        }
    return {
        "type": "assistant",
        "requestId": request_id,
        "isSidechain": sidechain,
        "effort": effort,
        "message": {"model": model, "usage": usage_object},
    }


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.claude = self.root / ".claude"
        self.session = "session-1"
        self.subagents = self.claude / "projects" / "-tmp-proj" / self.session / "subagents"
        self.subagents.mkdir(parents=True)
        self.db = self.root / "usage.sqlite3"
        self.tariff = self.root / "tariff.json"
        self.tariff.write_text(json.dumps(TARIFF), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, path, records, *, append=False):
        lines = "".join(json.dumps(record) + "\n" for record in records)
        with path.open("a" if append else "w", encoding="utf-8") as stream:
            stream.write(lines)

    def agent_file(self, agent_id):
        return self.subagents / f"agent-{agent_id}.jsonl"

    def session_file(self):
        return self.claude / "projects" / "-tmp-proj" / f"{self.session}.jsonl"

    def call(self, *arguments):
        out, err = io.StringIO(), io.StringIO()
        code = usage.main(
            ["--db", str(self.db), "--claude-dir", str(self.claude), *arguments],
            stdout=out, stderr=err,
        )
        payload = json.loads(out.getvalue()) if out.getvalue().strip() else None
        error = json.loads(err.getvalue()) if err.getvalue().strip() else None
        return code, payload, error

    def start(self, *extra, task="T001", agent="a1", tariff=True):
        arguments = [
            "start", "--run", "run-1", "--task", task, "--project-tag", "proj",
            "--role", "rightsize-midlevel-doer", "--model", "test-model",
            "--effort", "medium", "--mode", "implement", "--difficulty", "routine",
        ]
        if agent is not None:
            arguments += ["--agent-id", agent]
        if tariff:
            arguments += ["--tariff", str(self.tariff)]
        return self.call(*arguments, *extra)

    def finish(self, task="T001", outcome="accepted", *extra):
        return self.call("finish", "--run", "run-1", "--task", task, "--outcome", outcome, *extra)


class UsageAccountingTests(Fixture):
    def test_prices_every_category_from_the_transcript(self):
        self.write(self.agent_file("a1"), [
            turn("req-1", inp=1000, read=2000, write_5m=3000, write_1h=4000, out=5000)
        ])
        self.assertEqual(0, self.start("--new-agent")[0])
        code, result, _ = self.finish()
        self.assertEqual(0, code)
        expected = (1000 * 1 + 2000 * 2 + 3000 * 4 + 4000 * 8 + 5000 * 16) / 1_000_000
        self.assertEqual("known", result["cost_status"])
        self.assertAlmostEqual(expected, result["cost_usd"])
        self.assertEqual(["test-model"], result["actual_models"])
        self.assertEqual(["medium"], result["actual_efforts"])
        self.assertEqual(1, result["tokens"]["requests"])
        self.assertEqual(15000, result["tokens"]["total_tokens"])

    def test_streaming_duplicates_of_one_request_count_once(self):
        record = turn("req-1", inp=10, write_5m=100, out=5)
        self.write(self.agent_file("a1"), [record, record, record])
        self.assertEqual(0, self.start("--new-agent")[0])
        result = self.finish()[1]
        self.assertEqual(1, result["tokens"]["requests"])
        self.assertEqual(100, result["tokens"]["cache_write_5m"])

    def test_reused_agent_measures_only_the_new_assignment(self):
        self.write(self.agent_file("a1"), [turn("req-1", out=1000)])
        self.assertEqual(0, self.start("--new-agent")[0])
        self.assertEqual(0, self.finish()[0])
        # A follow-up assignment on the same agent: baseline now covers req-1.
        self.assertEqual(0, self.start(task="T002")[0])
        self.write(self.agent_file("a1"), [turn("req-2", out=7)], append=True)
        result = self.finish(task="T002")[1]
        self.assertEqual(7, result["tokens"]["output"])
        self.assertEqual(1, result["tokens"]["requests"])

    def test_one_active_assignment_per_agent(self):
        self.write(self.agent_file("a1"), [turn("req-1", out=1)])
        self.assertEqual(0, self.start("--new-agent")[0])
        code, _, error = self.start(task="T002")
        self.assertEqual(1, code)
        self.assertIn("already has active task", error["error"])

    def test_finish_is_idempotent_and_does_not_recount(self):
        self.write(self.agent_file("a1"), [turn("req-1", out=100)])
        self.assertEqual(0, self.start("--new-agent")[0])
        first = self.finish()[1]
        self.write(self.agent_file("a1"), [turn("req-2", out=999)], append=True)
        second = self.finish()[1]
        self.assertTrue(second["idempotent"])
        self.assertEqual(first["cost_usd"], second["cost_usd"])
        self.assertEqual(first["tokens"], second["tokens"])

    def test_main_session_scope_excludes_subagent_records(self):
        self.write(self.session_file(), [
            turn("req-main", sidechain=False, out=10),
            turn("req-child", sidechain=True, out=1000),
        ])
        arguments = [
            "start", "--run", "run-1", "--task", "M001", "--project-tag", "proj",
            "--role", "coordinator", "--model", "test-model", "--effort", "medium",
            "--mode", "implement", "--difficulty", "hard", "--main",
            "--session-id", self.session, "--new-agent", "--tariff", str(self.tariff),
        ]
        self.assertEqual(0, self.call(*arguments)[0])
        result = self.call("finish", "--run", "run-1", "--task", "M001", "--outcome", "accepted")[1]
        self.assertEqual(10, result["tokens"]["output"])


class HonestGapTests(Fixture):
    def test_missing_cache_ttl_split_is_unavailable_not_guessed(self):
        self.write(self.agent_file("a1"), [
            turn("req-1", write_5m=500, out=1, cache_split=False)
        ])
        self.assertEqual(0, self.start("--new-agent")[0])
        result = self.finish()[1]
        self.assertEqual("unavailable", result["usage_status"])
        self.assertIsNone(result["cost_usd"])
        self.assertIn("unpriceable", result["usage_reason"])

    def test_inconsistent_cache_split_is_rejected(self):
        record = turn("req-1", write_5m=100, out=1)
        record["message"]["usage"]["cache_creation_input_tokens"] = 999
        self.write(self.agent_file("a1"), [record])
        self.assertEqual(0, self.start("--new-agent")[0])
        self.assertEqual("unavailable", self.finish()[1]["usage_status"])

    def test_unknown_served_model_keeps_tokens_and_drops_cost(self):
        self.write(self.agent_file("a1"), [turn("req-1", model="rotated-model", out=42)])
        self.assertEqual(0, self.start("--new-agent")[0])
        result = self.finish()[1]
        self.assertEqual("available", result["usage_status"])
        self.assertEqual(42, result["tokens"]["output"])
        self.assertEqual("unavailable", result["cost_status"])
        self.assertIn("no exact tariff entry", result["cost_reason"])

    def test_expired_tariff_keeps_tokens_and_drops_cost(self):
        expired = dict(TARIFF, valid_until=str(date.today() - timedelta(days=1)))
        self.tariff.write_text(json.dumps(expired), encoding="utf-8")
        self.write(self.agent_file("a1"), [turn("req-1", out=42)])
        self.assertEqual(0, self.start("--new-agent")[0])
        result = self.finish()[1]
        self.assertEqual(42, result["tokens"]["output"])
        self.assertEqual("unavailable", result["cost_status"])
        self.assertIn("expired", result["cost_reason"])

    def test_absent_tariff_yields_tokens_without_cost(self):
        self.write(self.agent_file("a1"), [turn("req-1", out=42)])
        self.assertEqual(0, self.start("--new-agent", tariff=False)[0])
        result = self.finish()[1]
        self.assertEqual(42, result["tokens"]["output"])
        self.assertEqual("unavailable", result["cost_status"])

    def test_missing_transcript_is_reported_not_zeroed(self):
        self.assertEqual(0, self.start("--new-agent")[0])
        result = self.finish()[1]
        self.assertEqual("unavailable", result["usage_status"])
        self.assertIsNone(result["tokens"])
        self.assertIn("transcript not found", result["usage_reason"])

    def test_record_without_request_identity_is_unavailable(self):
        record = turn("req-1", out=5)
        del record["requestId"]
        self.write(self.agent_file("a1"), [record])
        self.assertEqual(0, self.start("--new-agent")[0])
        self.assertEqual("unavailable", self.finish()[1]["usage_status"])

    def test_ambiguous_transcript_match_is_an_error(self):
        other = self.claude / "projects" / "-tmp-other" / "session-2" / "subagents"
        other.mkdir(parents=True)
        for path in (self.agent_file("a1"), other / "agent-a1.jsonl"):
            self.write(path, [turn("req-1", out=1)])
        code, _, error = self.start()
        self.assertEqual(1, code)
        self.assertIn("multiple transcripts match", error["error"])

    def test_partial_final_line_is_ignored(self):
        self.write(self.agent_file("a1"), [turn("req-1", out=5)])
        with self.agent_file("a1").open("a", encoding="utf-8") as stream:
            stream.write('{"type":"assistant","message":{"usage":{"input')
        self.assertEqual(0, self.start("--new-agent")[0])
        self.assertEqual(5, self.finish()[1]["tokens"]["output"])

    def _main_start(self, *extra):
        return self.call(
            "start", "--run", "run-1", "--task", "M001", "--project-tag", "proj",
            "--role", "coordinator", "--model", "test-model", "--effort", "medium",
            "--mode", "implement", "--difficulty", "hard", "--main", *extra,
        )

    def test_main_scope_without_a_session_identifier_is_rejected(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            code, _, error = self._main_start()
        self.assertEqual(1, code)
        self.assertIn("--session-id", error["error"])

    def test_main_scope_falls_back_to_the_session_environment_variable(self):
        self.write(self.session_file(), [turn("req-main", sidechain=False, out=3)])
        with patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": self.session}):
            self.assertEqual(0, self._main_start("--new-agent", "--tariff", str(self.tariff))[0])
        result = self.call("finish", "--run", "run-1", "--task", "M001", "--outcome", "accepted")[1]
        self.assertEqual(3, result["tokens"]["output"])


class TeammateDiscoveryTests(Fixture):
    """Agent Teams runs a named agent as its own session, not as a subagent."""

    def teammate(self, name, team, records):
        path = self.claude / "projects" / "-tmp-proj" / f"{name}-session.jsonl"
        header = {"type": "user", "agentName": name, "teamName": team,
                  "sessionId": f"{name}-session", "isSidechain": False}
        self.write(path, [header, *records])
        return path

    def test_resolves_a_teammate_from_the_returned_agent_id(self):
        expected = self.teammate("worker-a", "session-abc",
                                 [turn("req-1", sidechain=False, out=5)])
        found = usage.resolve_agent_transcript("worker-a@session-abc", self.claude)
        self.assertEqual(expected.resolve(), found)

    def test_teammate_usage_is_measured_and_priced(self):
        self.teammate("worker-a", "session-abc",
                      [turn("req-1", sidechain=False, inp=100, out=50)])
        self.assertEqual(0, self.start("--new-agent", agent="worker-a@session-abc")[0])
        result = self.finish()[1]
        self.assertEqual("available", result["usage_status"])
        self.assertEqual(50, result["tokens"]["output"])
        self.assertAlmostEqual((100 * 1 + 50 * 16) / 1_000_000, result["cost_usd"])

    def test_a_plain_subagent_still_resolves_when_teams_is_off(self):
        # The fallback must not regress the non-teams dispatch path.
        self.write(self.agent_file("abc123"), [turn("req-1", out=7)])
        found = usage.resolve_agent_transcript("abc123", self.claude)
        self.assertEqual(self.agent_file("abc123").resolve(), found)

    def test_the_wrong_team_does_not_match(self):
        self.teammate("worker-a", "session-abc", [turn("req-1", sidechain=False, out=5)])
        self.assertIsNone(usage.resolve_agent_transcript("worker-a@session-zzz", self.claude))

    def test_an_ordinary_session_is_never_mistaken_for_a_teammate(self):
        self.write(self.session_file(), [turn("req-1", sidechain=False, out=5)])
        self.assertIsNone(usage.resolve_agent_transcript("worker-a@session-abc", self.claude))

    def test_duplicate_teammate_names_are_ambiguous_not_guessed(self):
        self.teammate("worker-a", "session-abc", [turn("req-1", sidechain=False, out=5)])
        other = self.claude / "projects" / "-tmp-other"
        other.mkdir(parents=True)
        self.write(other / "dup.jsonl", [
            {"type": "user", "agentName": "worker-a", "teamName": "session-abc"},
            turn("req-2", sidechain=False, out=5),
        ])
        with self.assertRaisesRegex(usage.UsageError, "multiple transcripts match"):
            usage.resolve_agent_transcript("worker-a@session-abc", self.claude)


class ReportTests(Fixture):
    def test_report_groups_by_served_model_effort_and_tariff(self):
        self.write(self.agent_file("a1"), [turn("req-1", out=10)])
        self.write(self.agent_file("a2"), [turn("req-2", effort="xhigh", out=20)])
        for task, agent in (("T001", "a1"), ("T002", "a2")):
            self.assertEqual(0, self.start("--new-agent", task=task, agent=agent)[0])
            self.assertEqual(0, self.finish(task=task, outcome="accepted")[0])
        result = self.call("report", "--run", "run-1")[1]
        self.assertEqual(2, result["samples"])
        efforts = sorted(group["effort"] for group in result["groups"])
        self.assertEqual(["medium", "xhigh"], efforts)
        for group in result["groups"]:
            self.assertEqual("test-model", group["model"])
            self.assertEqual("test-rates-1", group["tariff_version"])
            self.assertEqual(1, group["accepted"])
            self.assertEqual({"known": 1, "unknown": 0}, group["cost_coverage"])

    def test_report_separates_known_and_unknown_coverage(self):
        self.write(self.agent_file("a1"), [turn("req-1", out=10)])
        self.assertEqual(0, self.start("--new-agent", task="T001", agent="a1")[0])
        self.assertEqual(0, self.finish(task="T001")[0])
        self.assertEqual(0, self.start("--new-agent", task="T002", agent="missing")[0])
        self.assertEqual(0, self.finish(task="T002", outcome="failed")[0])
        result = self.call("report", "--run", "run-1")[1]
        coverage = {group["model"]: group["cost_coverage"] for group in result["groups"]}
        self.assertEqual({"known": 1, "unknown": 0}, coverage["test-model"])
        self.assertEqual({"known": 0, "unknown": 1}, coverage["unknown"])


class TariffValidationTests(Fixture):
    def test_malformed_tariff_is_rejected_at_start(self):
        for content in ("{", json.dumps({"models": {}}), json.dumps(dict(TARIFF, valid_until="soon"))):
            with self.subTest(content=content):
                self.tariff.write_text(content, encoding="utf-8")
                code, _, error = self.start("--new-agent", task=f"T{hash(content) % 999:03d}")
                self.assertEqual(1, code)
                self.assertIn("tariff", error["error"])


if __name__ == "__main__":
    unittest.main()
