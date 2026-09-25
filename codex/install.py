#!/usr/bin/env python3
"""Install or verify the standalone Rightsize Goal Codex workflow."""

from __future__ import annotations

import argparse
import datetime
import filecmp
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required (try python3 or py -3.11).")

import tomllib


ROLES = (
    "rightsize-junior-doer",
    "rightsize-midlevel-doer",
    "rightsize-senior-doer",
    "rightsize-staff-doer",
    "rightsize-principal-doer",
)
RETIRED_ROLES = ("rightsize-upper-midlevel-doer", "rightsize-lower-senior-doer", "rightsize-astra-doer")
MANAGED_ROLES = ROLES + RETIRED_ROLES


def paths(root: Path, codex: Path, skills: Path):
    pairs = [(root / ".agents/skills/rightsize-goal", skills / "rightsize-goal")]
    pairs.extend((root / ".codex/agents" / f"{name}.toml", codex / "agents" / f"{name}.toml") for name in ROLES)
    return pairs


def same_tree(left: Path, right: Path) -> bool:
    if left.is_file() and right.is_file():
        return left.read_bytes() == right.read_bytes()
    if not left.is_dir() or not right.is_dir():
        return False
    comparison = filecmp.dircmp(left, right, ignore=["__pycache__"])
    return not comparison.left_only and not comparison.right_only and not comparison.funny_files and all(
        same_tree(left / name, right / name) for name in comparison.common
    )


def remove_role_blocks(text: str) -> str:
    role_headers = {
        re.compile(rf'^[ \t]*\[[ \t]*agents[ \t]*\.[ \t]*(?:"{re.escape(role)}"|{re.escape(role)})[ \t]*\][ \t]*(?:#.*)?$')
        for role in MANAGED_ROLES
    }
    any_header = re.compile(r"^[ \t]*\[")
    output = []
    skipping = False
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        if any(pattern.match(content) for pattern in role_headers):
            skipping = True
            continue
        if skipping and any_header.match(content):
            skipping = False
        if not skipping:
            output.append(line)
    return "".join(output).rstrip()


def configured_roles(text: str, roles: tuple[str, ...]) -> list[str]:
    headers = {
        role: re.compile(rf'^[ \t]*\[[ \t]*agents[ \t]*\.[ \t]*(?:"{re.escape(role)}"|{re.escape(role)})[ \t]*\][ \t]*(?:#.*)?$', re.MULTILINE)
        for role in roles
    }
    return [role for role, pattern in headers.items() if pattern.search(text)]


def desired_config(text: str, codex: Path, root: Path) -> str:
    original = tomllib.loads(text)
    text = remove_role_blocks(text)
    cleaned = tomllib.loads(text)
    expected = dict(original)
    if isinstance(expected.get("agents"), dict):
        expected["agents"] = {key: value for key, value in expected["agents"].items() if key not in MANAGED_ROLES}
        if not expected["agents"] and "agents" not in cleaned:
            del expected["agents"]
    if cleaned != expected:
        raise SystemExit("Cannot safely edit this config layout. Use standalone agent discovery or edit registrations manually.")
    blocks = []
    for role in ROLES:
        source = root / ".codex/agents" / f"{role}.toml"
        metadata = tomllib.loads(source.read_text(encoding="utf-8"))
        target = codex / "agents" / f"{role}.toml"
        blocks.append(
            f"[agents.{role}]\n"
            f"description = {json.dumps(metadata['description'])}\n"
            f"config_file = {json.dumps(str(target))}\n"
        )
    combined = "\n\n".join(part for part in (text, *blocks) if part) + "\n"
    tomllib.loads(combined)
    return combined


def verify(root: Path, codex: Path, skills: Path, legacy_config: bool = False) -> list[str]:
    problems = []
    for source, target in paths(root, codex, skills):
        if not os.path.lexists(target):
            problems.append(f"missing: {target}")
        elif target.is_symlink():
            if target.resolve() != source.resolve():
                problems.append(f"wrong symlink target: {target}")
        elif not same_tree(source, target):
            problems.append(f"stale copy: {target}")
    for role in RETIRED_ROLES:
        target = codex / "agents" / f"{role}.toml"
        if os.path.lexists(target):
            problems.append(f"retired agent still installed: {target}")
    if not legacy_config:
        return problems
    config = codex / "config.toml"
    try:
        parsed = tomllib.loads(config.read_text(encoding="utf-8-sig"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        problems.append(f"cannot read valid config: {exc}")
        return problems
    configured = parsed.get("agents", {})
    for role in RETIRED_ROLES:
        if role in configured:
            problems.append(f"retired config registration remains: {role}")
    for role in ROLES:
        expected = (codex / "agents" / f"{role}.toml").resolve()
        entry = configured.get(role)
        if not isinstance(entry, dict) or not entry.get("config_file"):
            problems.append(f"missing config registration: {role}")
            continue
        actual = Path(entry["config_file"])
        if not actual.is_absolute():
            actual = codex / actual
        if actual.resolve() != expected:
            problems.append(f"wrong config registration: {role}")
    return problems


def install(args: argparse.Namespace, root: Path, codex: Path, skills: Path) -> None:
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required.")
    pairs = paths(root, codex, skills)
    for source, target in pairs:
        # Never allow force/rollback to remove the package itself or an ancestor.
        source_path, target_path = source.resolve(), target.parent.resolve() / target.name
        if source_path == target_path or source_path.is_relative_to(target_path) or target_path.is_relative_to(source_path):
            raise SystemExit(f"Install destination overlaps package source: {target}")
    for source, _ in pairs:
        if not source.exists():
            raise SystemExit(f"Package is incomplete; missing {source}")
        if source.suffix == ".toml":
            tomllib.loads(source.read_text(encoding="utf-8"))

    codex.mkdir(parents=True, exist_ok=True)
    skills.mkdir(parents=True, exist_ok=True)
    config = codex / "config.toml"
    old_config = config.read_bytes() if config.exists() else b""
    legacy_config = getattr(args, "legacy_config", False)
    if old_config and not legacy_config:
        try:
            existing_agents = tomllib.loads(old_config.decode("utf-8-sig")).get("agents", {})
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            existing_agents = {}
        retired_registrations = [role for role in RETIRED_ROLES if role in existing_agents]
        if retired_registrations:
            raise SystemExit("Retired role registrations remain: " + ", ".join(retired_registrations)
                             + ". They require migration: rerun with --legacy-config --force to back up and remove them.")
    new_bytes = old_config
    if legacy_config:
        old_text = old_config.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        new_bytes = desired_config(old_text, codex, root).encode("utf-8")
        old_agents = tomllib.loads(old_text).get("agents", {})
        new_agents = tomllib.loads(new_bytes.decode("utf-8"))["agents"]
        changed_roles = [role for role in (*ROLES, *RETIRED_ROLES)
                         if role in old_agents and old_agents[role] != new_agents.get(role)]
        if changed_roles and not args.force:
            raise SystemExit("Existing config registrations conflict: " + ", ".join(changed_roles) + ". Use --force to back up and replace them.")
    elif old_config:
        try:
            config_text = old_config.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
            managed_config = configured_roles(config_text, MANAGED_ROLES)
        except UnicodeError:
            managed_config = []
        if managed_config:
            raise SystemExit("Existing Rightsize Goal config registrations require migration: " + ", ".join(managed_config) + ". Rerun with --legacy-config --force.")

    conflicts = []
    for source, target in pairs:
        if not os.path.lexists(target):
            continue
        current = args.method == "symlink" and target.is_symlink() and target.resolve() == source.resolve()
        if args.method == "copy" and not target.is_symlink() and same_tree(source, target):
            current = True
        if not current:
            conflicts.append(target)
    retired_targets = [codex / "agents" / f"{role}.toml" for role in RETIRED_ROLES]
    conflicts.extend(target for target in retired_targets if os.path.lexists(target))
    if conflicts and not args.force:
        listing = "\n".join(f"  {item}" for item in conflicts)
        raise SystemExit(f"Existing resources conflict:\n{listing}\nRerun with --force to back them up and replace them.")

    stamp = datetime.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    backup = codex / "rightsize-goal/install-backups" / stamp
    moved: list[tuple[Path, Path]] = []
    created: list[Path] = []
    temporary: Path | None = None
    try:
        if conflicts or new_bytes != old_config:
            backup.mkdir(parents=True, exist_ok=False)
        if config.exists() and new_bytes != old_config:
            shutil.copy2(config, backup / "config.toml")
        for role in RETIRED_ROLES:
            target = codex / "agents" / f"{role}.toml"
            if not os.path.lexists(target):
                continue
            destination = backup / "resources" / target.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(target, destination)
            moved.append((target, destination))
        for source, target in pairs:
            if os.path.lexists(target):
                current = args.method == "symlink" and target.is_symlink() and target.resolve() == source.resolve()
                if args.method == "copy" and not target.is_symlink() and same_tree(source, target):
                    current = True
                if current:
                    continue
                destination = backup / "resources" / target.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(target, destination)
                moved.append((target, destination))
            target.parent.mkdir(parents=True, exist_ok=True)
            created.append(target)
            if args.method == "symlink":
                os.symlink(source, target, target_is_directory=source.is_dir())
            elif source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(source, target)
        if new_bytes != old_config:
            with tempfile.NamedTemporaryFile("wb", dir=codex, delete=False) as output:
                temporary = Path(output.name)
                output.write(new_bytes)
            os.replace(temporary, config)
            temporary = None
        problems = verify(root, codex, skills, legacy_config)
        if problems:
            raise RuntimeError("Installation verification failed:\n" + "\n".join(problems))
    except Exception as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if config.exists() and config.read_bytes() != old_config:
            if old_config:
                config.write_bytes(old_config)
            else:
                config.unlink()
        for target in reversed(created):
            if target.is_symlink() or target.is_file():
                target.unlink(missing_ok=True)
            elif target.is_dir():
                shutil.rmtree(target)
        for target, saved in reversed(moved):
            shutil.move(saved, target)
        if getattr(exc, "winerror", None) == 1314:
            raise SystemExit("Windows denied symlink creation. Enable Developer Mode, use an elevated terminal, or install with --method copy.") from exc
        raise

    method_label = "symbolic links" if args.method == "symlink" else "copies"
    print(f"Rightsize Goal installed with {method_label}.")
    if backup.exists():
        print(f"Backup: {backup}")
    print("Verification passed. Start a fresh Codex session to load the workflow.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=("symlink", "copy"), default="copy")
    parser.add_argument("--legacy-config", action="store_true", help="also register agents in config.toml for older hosts")
    parser.add_argument("--codex-dir", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--skills-dir", type=Path, default=Path.home() / ".agents/skills")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    codex = args.codex_dir.expanduser().resolve()
    skills = args.skills_dir.expanduser().resolve()
    if args.verify:
        problems = verify(root, codex, skills, args.legacy_config)
        if problems:
            print("Verification failed:", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
        print("Rightsize Goal installation is current and valid.")
        return 0
    install(args, root, codex, skills)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
