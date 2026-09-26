"""Distribution checks that do not call models or touch user configuration."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install as installer  # noqa: E402


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
SKILL = PACKAGE / "skills/rightsize-goal"
EFFORTS = {"low", "medium", "high", "xhigh", "max"}


class PackageTests(unittest.TestCase):
    def test_installed_skill_retains_mit_notice(self):
        self.assertEqual(
            (REPO / "LICENSE").read_text(encoding="utf-8").strip(),
            (SKILL / "LICENSE").read_text(encoding="utf-8").strip(),
        )

    def test_plugin_and_marketplace_manifests_are_consistent(self):
        plugin = json.loads((PACKAGE / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual("rightsize-goal", plugin["name"])
        self.assertTrue(plugin["version"].strip())
        self.assertEqual(plugin["version"], marketplace["metadata"]["version"])
        self.assertTrue(plugin["description"].strip())
        entries = [item for item in marketplace["plugins"] if item["name"] == plugin["name"]]
        self.assertEqual(1, len(entries), "marketplace must list the plugin exactly once")
        source = (REPO / entries[0]["source"]).resolve()
        self.assertEqual(PACKAGE.resolve(), source)

    def test_agents_and_skill_live_at_the_plugin_root(self):
        # Claude Code discovers these directories at the plugin root, never inside
        # .claude-plugin/, so a misplaced directory silently ships nothing.
        self.assertTrue((PACKAGE / "agents").is_dir())
        self.assertTrue((SKILL / "SKILL.md").is_file())
        self.assertFalse((PACKAGE / ".claude-plugin/agents").exists())
        self.assertFalse((PACKAGE / ".claude-plugin/skills").exists())

    def test_agent_payloads_match_tariff_and_skill(self):
        tariff = json.loads((SKILL / "references/tariff.json").read_text(encoding="utf-8"))
        instructions = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        roles = sorted((PACKAGE / "agents").glob("*.md"))
        self.assertEqual(sorted(f"{name}.md" for name in installer.ROLES),
                         sorted(path.name for path in roles))
        for path in roles:
            with self.subTest(role=path.name):
                fields = installer.frontmatter(path)
                self.assertEqual(path.stem, fields["name"])
                self.assertTrue(fields["description"].strip())
                self.assertTrue(path.read_text(encoding="utf-8").split("---", 2)[2].strip())
                self.assertIn(fields["name"], instructions)
                self.assertIn("effort" in fields, (True, False))
                if "effort" in fields:
                    self.assertIn(fields["effort"], EFFORTS)
                # Every role's model alias must resolve to a priced model.
                priced = tariff["role_models"][fields["name"]]
                self.assertIn(priced, tariff["models"])

    def test_stop_hook_runs_the_shipped_drive_script_from_the_plugin_root(self):
        hooks = json.loads((PACKAGE / "hooks/hooks.json").read_text(encoding="utf-8"))
        stop = hooks["hooks"]["Stop"]
        commands = [hook["command"] for group in stop for hook in group["hooks"] if hook["type"] == "command"]
        self.assertEqual(1, len(commands))
        scripts = re.findall(r'"\$\{CLAUDE_PLUGIN_ROOT\}/([^"]+)" hook', commands[0])
        self.assertEqual(3, len(scripts), commands[0])
        # python3 first, then python, then the Windows py launcher.
        interpreters = [part.strip().split(' "')[0] for part in commands[0].split("||")]
        self.assertEqual(["python3", "python", "py -3"], interpreters)
        for script in scripts:
            self.assertEqual("skills/rightsize-goal/scripts/drive.py", script)
            self.assertTrue((PACKAGE / script).is_file())
        self.assertNotIn("hooks", {path.name for path in (PACKAGE / ".claude-plugin").iterdir()})

    def test_validator_is_read_only(self):
        fields = installer.frontmatter(PACKAGE / "agents/rightsize-validator.md")
        granted = {item.strip() for item in fields["tools"].split(",")}
        self.assertFalse(granted & {"Write", "Edit", "MultiEdit", "NotebookEdit", "Agent", "Task"})
        self.assertIn("Bash", granted)
        self.assertEqual("opus", fields["model"])

    def test_validator_judges_naturally_and_scopes_follow_up_rounds(self):
        body = (PACKAGE / "agents/rightsize-validator.md").read_text(encoding="utf-8")
        for rule in ("Done is not the same as perfect", "QA engineer or product owner",
                     "follow-up round", "Notes", "from 1 to 10", "7 or higher", "polish check"):
            self.assertIn(rule, body)
        self.assertNotIn("mostly met is NOT DONE", body)

    def test_workers_cannot_spawn_agents(self):
        # The escalation gate depends on workers never dispatching for themselves.
        for name in installer.ROLES:
            fields = installer.frontmatter(PACKAGE / "agents" / f"{name}.md")
            granted = {item.strip() for item in fields["tools"].split(",")}
            with self.subTest(role=name):
                self.assertNotIn("Agent", granted)
                self.assertNotIn("Task", granted)
                self.assertIn("Read", granted)
                # The coordinator retires workers with TaskStop; workers must not message each other.
                self.assertNotIn("SendMessage", granted)
                body = (PACKAGE / "agents" / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn("compacted", body, "workers report context compaction in their receipt")
                # Every role can research online.
                self.assertTrue({"WebFetch", "WebSearch"} <= granted)

    def test_every_tariff_rate_category_is_priced_for_every_model(self):
        tariff = json.loads((SKILL / "references/tariff.json").read_text(encoding="utf-8"))
        for model, rates in tariff["models"].items():
            with self.subTest(model=model):
                for field in ("input", "cache_read", "cache_write_5m", "cache_write_1h", "output"):
                    self.assertIsInstance(rates[field], (int, float))
                    self.assertGreater(rates[field], 0)
                # The worker lifecycle rule (30% of the window free) needs every model's window.
                self.assertIsInstance(rates["context_window"], int)
                self.assertGreater(rates["context_window"], 0)

    def test_documentation_relative_links_exist(self):
        files = list(REPO.glob("*.md")) + list(PACKAGE.rglob("*.md"))
        for path in files:
            content = path.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]\n]+\]\(([^)\s]+)\)", content):
                if "://" in target or target.startswith("#"):
                    continue
                local = target.split("#", 1)[0]
                with self.subTest(document=str(path.relative_to(REPO)), target=target):
                    self.assertTrue((path.parent / local).exists())

    def test_python_cli_copy_install_and_verify_from_another_directory(self):
        with tempfile.TemporaryDirectory(prefix="rightsize package ") as directory:
            root = Path(directory)
            command = [sys.executable, str(PACKAGE / "install.py"),
                       "--claude-dir", str(root / "claude home")]
            for arguments in ([], ["--verify"]):
                result = subprocess.run(command + arguments, cwd=root, text=True,
                                        capture_output=True, timeout=60)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertFalse((root / "claude home/skills/rightsize-goal").is_symlink())
            self.assertFalse((root / "claude home/settings.json").exists())

    def test_platform_wrapper_installs_and_verifies(self):
        if os.name == "nt":
            shell = shutil.which("powershell.exe")
            prefix = ([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                       str(PACKAGE / "install.ps1")] if shell else None)
            option, verify = "-ClaudeDirectory", ["-Verify"]
        else:
            shell = shutil.which("sh")
            prefix = [shell, str(PACKAGE / "install.sh")] if shell else None
            option, verify = "--claude-dir", ["--verify"]
        if prefix is None:
            self.skipTest("platform shell is unavailable")
        with tempfile.TemporaryDirectory(prefix="rightsize wrapper ") as directory:
            root = Path(directory)
            options = [option, str(root / "claude")]
            for arguments in ([], verify):
                result = subprocess.run(prefix + options + arguments, cwd=root,
                                        text=True, capture_output=True, timeout=60)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
