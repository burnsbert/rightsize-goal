import argparse
import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "install.py"
SPEC = importlib.util.spec_from_file_location("rightsize_claude_install", MODULE_PATH)
installer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.claude = self.root / ".claude"
        self.claude.mkdir(parents=True)
        # Unrelated user state that installation must never disturb.
        self.settings = self.claude / "settings.json"
        self.settings.write_text('{"theme": "dark"}\n', encoding="utf-8")
        self.package = Path(__file__).parents[1]
        # The installer prints a success summary; keep unit output readable.
        quiet = contextlib.redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def tearDown(self):
        self.temporary.cleanup()

    def args(self, force=False, method="copy"):
        return argparse.Namespace(method=method, force=force)

    @property
    def skill(self):
        return self.claude / "skills" / "rightsize-goal"

    def role(self, index=0):
        return self.claude / "agents" / f"{installer.ROLES[index]}.md"

    def test_copy_install_is_verifiable_idempotent_and_leaves_settings_alone(self):
        original = self.settings.read_bytes()
        installer.install(self.args(), self.package, self.claude)
        self.assertEqual([], installer.verify(self.package, self.claude))
        self.assertEqual(original, self.settings.read_bytes())
        self.assertTrue((self.skill / "scripts/task_usage.py").is_file())
        self.assertEqual(len(installer.ROLES), len(list((self.claude / "agents").glob("*.md"))))
        installer.install(self.args(), self.package, self.claude)
        self.assertEqual([], installer.verify(self.package, self.claude))

    def test_install_creates_no_configuration_files(self):
        installer.install(self.args(), self.package, self.claude)
        created = {path.name for path in self.claude.iterdir()}
        self.assertEqual({"settings.json", "skills", "agents"}, created)

    def test_conflict_requires_force_and_forced_copy_is_backed_up(self):
        installer.install(self.args(), self.package, self.claude)
        self.role().write_text("conflict", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "conflict"):
            installer.install(self.args(), self.package, self.claude)
        installer.install(self.args(force=True), self.package, self.claude)
        self.assertEqual([], installer.verify(self.package, self.claude))
        backups = list(
            (self.claude / "rightsize-goal" / "install-backups").glob(
                f"*/resources/{installer.ROLES[0]}.md"
            )
        )
        self.assertEqual(1, len(backups))
        self.assertEqual("conflict", backups[0].read_text(encoding="utf-8"))

    def test_verify_reports_missing_and_stale_resources(self):
        self.assertTrue(installer.verify(self.package, self.claude))
        installer.install(self.args(), self.package, self.claude)
        self.role().write_text("drifted", encoding="utf-8")
        problems = installer.verify(self.package, self.claude)
        self.assertEqual(1, len(problems))
        self.assertIn("stale copy", problems[0])

    def test_failure_restores_conflicting_resources(self):
        installer.install(self.args(), self.package, self.claude)
        self.role().write_text("user content", encoding="utf-8")
        with patch.object(installer.shutil, "copy2", side_effect=OSError("copy failed")):
            with self.assertRaisesRegex(OSError, "copy failed"):
                installer.install(self.args(force=True), self.package, self.claude)
        self.assertEqual("user content", self.role().read_text(encoding="utf-8"))

    def test_partial_copy_failure_rolls_back(self):
        def fail_copy(source, target, **kwargs):
            Path(target).mkdir()
            (Path(target) / "partial").write_text("partial", encoding="utf-8")
            raise OSError("disk full")

        with patch.object(installer.shutil, "copytree", side_effect=fail_copy):
            with self.assertRaisesRegex(OSError, "disk full"):
                installer.install(self.args(), self.package, self.claude)
        self.assertFalse(self.skill.exists())

    def test_post_install_verification_failure_rolls_back(self):
        with patch.object(installer, "verify", return_value=["bad install"]):
            with self.assertRaisesRegex(RuntimeError, "bad install"):
                installer.install(self.args(), self.package, self.claude)
        self.assertFalse(self.skill.exists())
        self.assertFalse(self.role().exists())

    def test_forced_source_overlap_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "overlaps"):
            installer.install(self.args(force=True), self.package, self.package)

    def test_incomplete_package_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(SystemExit, "incomplete"):
                installer.install(self.args(), Path(directory), self.claude)
        self.assertFalse(self.skill.exists())

    def test_symlink_to_copy_requires_force_then_converts(self):
        (self.claude / "skills").mkdir(parents=True, exist_ok=True)
        link = self.skill
        try:
            link.symlink_to(self.package / "skills/rightsize-goal", target_is_directory=True)
        except OSError as exc:  # pragma: no cover - platform dependent
            self.skipTest(f"symlinks unavailable: {exc}")
        with self.assertRaises(SystemExit):
            installer.install(self.args(), self.package, self.claude)
        installer.install(self.args(force=True), self.package, self.claude)
        self.assertFalse(link.is_symlink())
        self.assertEqual([], installer.verify(self.package, self.claude))

    def test_symlink_install_verifies_and_is_idempotent(self):
        try:
            installer.install(self.args(method="symlink"), self.package, self.claude)
        except OSError as exc:  # pragma: no cover - platform dependent
            self.skipTest(f"symlinks unavailable: {exc}")
        self.assertTrue(self.skill.is_symlink())
        self.assertEqual([], installer.verify(self.package, self.claude))
        installer.install(self.args(method="symlink"), self.package, self.claude)
        self.assertEqual([], installer.verify(self.package, self.claude))


class FrontmatterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "agent.md"

    def tearDown(self):
        self.temporary.cleanup()

    def test_reads_scalar_fields(self):
        self.path.write_text("---\nname: a\nmodel: opus\n---\nbody\n", encoding="utf-8")
        self.assertEqual({"name": "a", "model": "opus"}, installer.frontmatter(self.path))

    def test_missing_block_is_rejected(self):
        self.path.write_text("no frontmatter\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "Missing YAML frontmatter"):
            installer.frontmatter(self.path)

    def test_unterminated_block_is_rejected(self):
        self.path.write_text("---\nname: a\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "Unterminated YAML frontmatter"):
            installer.frontmatter(self.path)


if __name__ == "__main__":
    unittest.main()
