import argparse
import importlib.util
import tempfile
import tomllib
import unittest
from unittest.mock import patch
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

    def args(self, force=False, legacy_config=True):
        return argparse.Namespace(method="copy", force=force, legacy_config=legacy_config)

    def test_standalone_install_preserves_config_bytes(self):
        original = self.config.read_bytes()
        installer.install(self.args(legacy_config=False), self.package, self.codex, self.skills)
        self.assertEqual(original, self.config.read_bytes())
        self.assertEqual([], installer.verify(self.package, self.codex, self.skills))

    def test_fresh_standalone_install_does_not_create_config(self):
        self.config.unlink()
        installer.install(self.args(legacy_config=False), self.package, self.codex, self.skills)
        self.assertFalse(self.config.exists())
        self.assertEqual([], installer.verify(self.package, self.codex, self.skills))

    def test_legacy_registration_conflict_requires_force(self):
        original = '[agents.rightsize-junior-doer]\nconfig_file = "custom.toml"\n'
        self.config.write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "registrations conflict"):
            installer.install(self.args(), self.package, self.codex, self.skills)
        self.assertEqual(original, self.config.read_text(encoding="utf-8"))
        self.assertFalse((self.skills / "rightsize-goal").exists())

    def test_retired_agents_require_force_and_are_backed_up(self):
        retired = self.codex / "agents" / "rightsize-lower-senior-doer.toml"
        retired.parent.mkdir(parents=True)
        retired.write_text("old lower-senior role", encoding="utf-8")
        with self.assertRaises(SystemExit):
            installer.install(self.args(legacy_config=False), self.package, self.codex, self.skills)
        installer.install(self.args(force=True, legacy_config=False), self.package, self.codex, self.skills)
        self.assertFalse(retired.exists())
        backups = list((self.codex / "rightsize-goal/install-backups").glob("*/resources/rightsize-lower-senior-doer.toml"))
        self.assertEqual(1, len(backups))
        self.assertEqual("old lower-senior role", backups[0].read_text(encoding="utf-8"))

    def test_legacy_upgrade_removes_retired_registrations(self):
        retired = installer.RETIRED_ROLES[0]
        self.config.write_text(f'[agents.{retired}]\ndescription = "old"\nconfig_file = "old.toml"\n', encoding="utf-8")
        installer.install(self.args(force=True), self.package, self.codex, self.skills)
        configured = tomllib.loads(self.config.read_text(encoding="utf-8"))["agents"]
        self.assertNotIn(retired, configured)
        self.assertEqual(set(installer.ROLES), set(configured))

    def test_default_upgrade_does_not_leave_retired_config_dangling(self):
        retired = installer.RETIRED_ROLES[0]
        old_file = self.codex / "agents" / f"{retired}.toml"
        old_file.parent.mkdir(parents=True)
        old_file.write_text("old role", encoding="utf-8")
        original = f'[agents."{retired}"]\ndescription = "old"\nconfig_file = "old.toml"\n'
        self.config.write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "require migration"):
            installer.install(self.args(force=True, legacy_config=False), self.package, self.codex, self.skills)
        self.assertEqual("old role", old_file.read_text(encoding="utf-8"))
        self.assertEqual(original, self.config.read_text(encoding="utf-8"))
        self.assertFalse((self.skills / "rightsize-goal").exists())

    def test_default_upgrade_requires_migration_for_active_legacy_roles(self):
        role = "rightsize-staff-doer"
        old_file = self.codex / "agents" / f"{role}.toml"
        old_file.parent.mkdir(parents=True)
        old_file.write_text("old Astra staff role", encoding="utf-8")
        original = f'[agents.{role}]\ndescription = "old Astra staff"\nconfig_file = "agents/{role}.toml"\n'
        self.config.write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "require migration"):
            installer.install(self.args(force=True, legacy_config=False), self.package, self.codex, self.skills)
        self.assertEqual("old Astra staff role", old_file.read_text(encoding="utf-8"))
        self.assertEqual(original, self.config.read_text(encoding="utf-8"))

    def test_forced_upgrade_replaces_old_staff_and_principal_definitions(self):
        agents = self.codex / "agents"
        agents.mkdir(parents=True)
        for role in ("rightsize-staff-doer", "rightsize-principal-doer"):
            (agents / f"{role}.toml").write_text(f"old {role}", encoding="utf-8")
        installer.install(self.args(force=True, legacy_config=False), self.package, self.codex, self.skills)
        for role in ("rightsize-staff-doer", "rightsize-principal-doer"):
            installed = tomllib.loads((agents / f"{role}.toml").read_text(encoding="utf-8"))
            self.assertEqual(role, installed["name"])
            backups = list((self.codex / "rightsize-goal/install-backups").glob(f"*/resources/{role}.toml"))
            self.assertEqual(1, len(backups))

    def test_failure_restores_conflicting_resources(self):
        installer.install(self.args(), self.package, self.codex, self.skills)
        target = self.codex / "agents" / f"{installer.ROLES[0]}.toml"
        target.write_text("user content", encoding="utf-8")
        original = self.config.read_bytes()
        with patch.object(installer.shutil, "copy2", side_effect=OSError("copy failed")):
            with self.assertRaisesRegex(OSError, "copy failed"):
                installer.install(self.args(force=True), self.package, self.codex, self.skills)
        self.assertEqual("user content", target.read_text(encoding="utf-8"))
        self.assertEqual(original, self.config.read_bytes())

    def test_partial_copy_failure_rolls_back(self):
        original = self.config.read_bytes()
        def fail_copy(source, target, **kwargs):
            target.mkdir()
            (target / "partial").write_text("partial", encoding="utf-8")
            raise OSError("disk full")
        with patch.object(installer.shutil, "copytree", side_effect=fail_copy):
            with self.assertRaisesRegex(OSError, "disk full"):
                installer.install(self.args(), self.package, self.codex, self.skills)
        self.assertFalse((self.skills / "rightsize-goal").exists())
        self.assertEqual(original, self.config.read_bytes())

    def test_post_install_verification_failure_rolls_back(self):
        original = self.config.read_bytes()
        with patch.object(installer, "verify", return_value=["bad install"]):
            with self.assertRaisesRegex(RuntimeError, "bad install"):
                installer.install(self.args(), self.package, self.codex, self.skills)
        self.assertFalse((self.skills / "rightsize-goal").exists())
        self.assertEqual(original, self.config.read_bytes())

    def test_forced_source_overlap_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "overlaps"):
            installer.install(self.args(force=True), self.package,
                              self.package / ".codex", self.package / ".agents/skills")

    def test_legacy_edit_rejects_invalid_or_unsafe_config(self):
        for content in ('invalid = [', 'note = """\n[agents.rightsize-junior-doer]\nkept = 1\n"""\n'):
            with self.subTest(content=content):
                self.config.write_text(content, encoding="utf-8")
                with self.assertRaises((SystemExit, installer.tomllib.TOMLDecodeError)):
                    installer.install(self.args(), self.package, self.codex, self.skills)
                self.assertEqual(content, self.config.read_text(encoding="utf-8"))
                self.assertFalse((self.skills / "rightsize-goal").exists())

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

    def test_upgrade_backs_up_retired_and_renamed_roles(self):
        agents = self.codex / "agents"
        agents.mkdir()
        for role in installer.RETIRED_ROLES:
            (agents / f"{role}.toml").write_text("old role", encoding="utf-8")
        for role in ("rightsize-senior-doer", "rightsize-staff-doer"):
            (agents / f"{role}.toml").write_text("old definition", encoding="utf-8")
        old_config = self.config.read_text(encoding="utf-8")
        old_config += "\n".join(
            f'\n[agents.{role}]\nconfig_file = "agents/{role}.toml"\n'
            for role in installer.RETIRED_ROLES
        )
        self.config.write_text(old_config, encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "Retired role registrations remain"):
            installer.install(self.args(force=True, legacy_config=False), self.package, self.codex, self.skills)
        with self.assertRaisesRegex(SystemExit, "registrations conflict"):
            installer.install(self.args(), self.package, self.codex, self.skills)
        self.assertEqual(old_config, self.config.read_text(encoding="utf-8"))
        installer.install(self.args(force=True), self.package, self.codex, self.skills)
        self.assertEqual([], installer.verify(self.package, self.codex, self.skills, True))
        parsed = tomllib.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(set(installer.ROLES), set(parsed["agents"]))
        for role in installer.RETIRED_ROLES:
            self.assertFalse((agents / f"{role}.toml").exists())
            backups = list((self.codex / "rightsize-goal/install-backups").glob(f"*/resources/{role}.toml"))
            self.assertEqual(1, len(backups))
            self.assertEqual("old role", backups[0].read_text(encoding="utf-8"))
        for role in ("rightsize-senior-doer", "rightsize-staff-doer"):
            backups = list((self.codex / "rightsize-goal/install-backups").glob(f"*/resources/{role}.toml"))
            self.assertEqual(1, len(backups))
            self.assertEqual("old definition", backups[0].read_text(encoding="utf-8"))

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
