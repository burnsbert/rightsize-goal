"""Distribution checks that do not call models or touch user configuration."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
SKILL = PACKAGE / ".agents/skills/rightsize-goal"


class PackageTests(unittest.TestCase):
    def test_codex_marketplace_packages_codex_skill(self):
        marketplace = json.loads((REPO / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual("rightsize-goal", marketplace["name"])
        self.assertEqual(1, len(marketplace["plugins"]))
        entry = marketplace["plugins"][0]
        self.assertEqual("rightsize-goal", entry["name"])
        self.assertEqual({"source": "local", "path": "./codex"}, entry["source"])
        plugin_root = (REPO / entry["source"]["path"]).resolve()
        self.assertEqual(PACKAGE.resolve(), plugin_root)
        manifest = json.loads((plugin_root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(entry["name"], manifest["name"])
        self.assertEqual("./skills/", manifest["skills"])
        packaged_skill = plugin_root / manifest["skills"] / "rightsize-goal"
        source_files = {path.relative_to(SKILL) for path in SKILL.rglob("*")
                        if path.is_file() and "__pycache__" not in path.parts}
        packaged_files = {path.relative_to(packaged_skill) for path in packaged_skill.rglob("*")
                          if path.is_file()}
        self.assertEqual(source_files, packaged_files)
        for relative in source_files:
            self.assertEqual((SKILL / relative).read_bytes(), (packaged_skill / relative).read_bytes())
        self.assertTrue((packaged_skill / "scripts/goal_gate.py").is_file())
        self.assertTrue((packaged_skill / "scripts/task_usage.py").is_file())

    def test_installed_skill_retains_mit_notice(self):
        self.assertEqual((REPO / "LICENSE").read_text(encoding="utf-8").strip(),
                         (SKILL / "LICENSE").read_text(encoding="utf-8").strip())

    def test_platform_wrapper_installs_and_verifies(self):
        if os.name == "nt":
            shell = shutil.which("powershell.exe")
            prefix = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                      str(PACKAGE / "install.ps1")] if shell else None
        else:
            shell = shutil.which("sh")
            prefix = [shell, str(PACKAGE / "install.sh")] if shell else None
        if prefix is None:
            self.skipTest("platform shell is unavailable")
        with tempfile.TemporaryDirectory(prefix="rightsize wrapper ") as directory:
            root = Path(directory)
            if os.name == "nt":
                options = ["-CodexDirectory", str(root / "codex"), "-SkillsDirectory", str(root / "skills")]
                verify = ["-Verify"]
            else:
                options = ["--codex-dir", str(root / "codex"), "--skills-dir", str(root / "skills")]
                verify = ["--verify"]
            for arguments in ([], verify):
                result = subprocess.run(prefix + options + arguments, cwd=root,
                                        text=True, capture_output=True, timeout=30)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_agent_payloads_match_tariff_and_skill(self):
        tariff = json.loads((SKILL / "references/tariff.json").read_text(encoding="utf-8"))
        instructions = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        roles = list((PACKAGE / ".codex/agents").glob("*.toml"))
        self.assertEqual(5, len(roles))
        self.assertEqual({"rightsize-junior-doer", "rightsize-midlevel-doer",
                          "rightsize-senior-doer", "rightsize-staff-doer",
                          "rightsize-principal-doer"}, {path.stem for path in roles})
        for path in roles:
            with self.subTest(role=path.name):
                agent = tomllib.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(path.stem, agent["name"])
                self.assertTrue(agent["description"].strip())
                self.assertTrue(agent["developer_instructions"].strip())
                self.assertIn(agent["model"], tariff["models"])
                self.assertIn(agent["name"], instructions)
                self.assertIn(agent["model_reasoning_effort"], {"low", "medium", "high", "xhigh"})

    def test_documentation_relative_links_exist(self):
        files = list(REPO.glob("*.md")) + list(PACKAGE.rglob("*.md"))
        for path in files:
            content = path.read_text(encoding="utf-8")
            for target in re.findall(r'\[[^\]\n]+\]\(([^)\s]+)\)', content):
                if "://" in target or target.startswith("#"):
                    continue
                local = target.split("#", 1)[0]
                with self.subTest(document=path.name, target=target):
                    self.assertTrue((path.parent / local).exists())

    def test_python_cli_copy_install_and_verify_from_another_directory(self):
        with tempfile.TemporaryDirectory(prefix="rightsize package ") as directory:
            root = Path(directory)
            command = [sys.executable, str(PACKAGE / "install.py"),
                       "--codex-dir", str(root / "codex home"),
                       "--skills-dir", str(root / "skills")]
            for arguments in ([], ["--verify"]):
                result = subprocess.run(command + arguments, cwd=root, text=True,
                                        capture_output=True, timeout=30)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertFalse((root / "codex home/config.toml").exists())
            self.assertFalse((root / "skills/rightsize-goal").is_symlink())


if __name__ == "__main__":
    unittest.main()
