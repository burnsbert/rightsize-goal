import argparse
import importlib.util
import tempfile
import tomllib
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "install.py"
SPEC = importlib.util.spec_from_file_location("rightsize_install", MODULE_PATH)
installer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.codex = self.root / ".codex"
        self.skills = self.root / ".agents" / "skills"
        self.codex.mkdir(parents=True)
        self.config = self.codex / "config.toml"
        self.config.write_text('[unrelated]\nvalue = "preserved"\n', encoding="utf-8")
        self.package = Path(__file__).parents[1]

    def tearDown(self):
        self.temporary.cleanup()

    def args(self, force=False):
        return argparse.Namespace(method="copy", force=force)

    def test_copy_install_is_verifiable_idempotent_and_preserves_config(self):
        installer.install(self.args(), self.package, self.codex, self.skills)
        self.assertEqual([], installer.verify(self.package, self.codex, self.skills))
        parsed = tomllib.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual("preserved", parsed["unrelated"]["value"])
        self.assertEqual(set(installer.ROLES), set(parsed["agents"]))
        cleaned = installer.remove_role_blocks(self.config.read_text(encoding="utf-8"))
        self.assertEqual('[unrelated]\nvalue = "preserved"', cleaned.replace("\r\n", "\n"))
        installer.install(self.args(), self.package, self.codex, self.skills)
        self.assertEqual([], installer.verify(self.package, self.codex, self.skills))

    def test_conflict_requires_force_and_forced_copy_is_backed_up(self):
        installer.install(self.args(), self.package, self.codex, self.skills)
        target = self.codex / "agents" / f"{installer.ROLES[0]}.toml"
        target.write_text("conflict", encoding="utf-8")
        with self.assertRaises(SystemExit):
            installer.install(self.args(), self.package, self.codex, self.skills)
        installer.install(self.args(force=True), self.package, self.codex, self.skills)
        self.assertEqual([], installer.verify(self.package, self.codex, self.skills))
        backups = list((self.codex / "rightsize-goal" / "install-backups").glob("*/resources/rightsize-junior-doer.toml"))
        self.assertEqual(1, len(backups))
        self.assertEqual("conflict", backups[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
