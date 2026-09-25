#!/usr/bin/env python3
"""Install or verify the Rightsize Goal workflow for Claude Code.

Installing the plugin (``/plugin marketplace add`` then ``/plugin install``) is the
recommended route and does not need this script. Use this installer when you want
the skill and roles as plain user-level files under your Claude Code configuration
directory, or when you are developing the workflow from a clone.
"""

from __future__ import annotations

import argparse
import datetime
import filecmp
import os
import shutil
import sys
import re
from pathlib import Path

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required (try python3 or py -3.11).")


ROLES = (
    "rightsize-junior-doer",
    "rightsize-midlevel-doer",
    "rightsize-senior-doer",
    "rightsize-principal-doer",
    "rightsize-validator",
)

SKILL = "rightsize-goal"


def default_claude_dir() -> Path:
    raw = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(raw) if raw else Path.home() / ".claude"


def paths(root: Path, claude: Path) -> list[tuple[Path, Path]]:
    """Source/destination pairs, skill first so a partial install is obvious."""
    pairs = [(root / "skills" / SKILL, claude / "skills" / SKILL)]
    pairs.extend(
        (root / "agents" / f"{name}.md", claude / "agents" / f"{name}.md") for name in ROLES
    )
    return pairs


def same_tree(left: Path, right: Path) -> bool:
    if left.is_file() and right.is_file():
        return left.read_bytes() == right.read_bytes()
    if not left.is_dir() or not right.is_dir():
        return False
    comparison = filecmp.dircmp(left, right, ignore=["__pycache__"])
    return (
        not comparison.left_only
        and not comparison.right_only
        and not comparison.funny_files
        and all(same_tree(left / name, right / name) for name in comparison.common)
    )


def frontmatter(path: Path) -> dict[str, str]:
    """Read simple ``key: value`` pairs from a Markdown YAML frontmatter block.

    Deliberately minimal: the packaged agent and skill files use flat scalar
    frontmatter, so this avoids a third-party YAML dependency. It raises on a
    missing or unterminated block rather than guessing.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SystemExit(f"Missing YAML frontmatter: {path}")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*):\s*(.*)", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    raise SystemExit(f"Unterminated YAML frontmatter: {path}")


def check_package(root: Path) -> None:
    """Fail before touching the destination if the package itself is wrong."""
    for source, _ in paths(root, Path("/nonexistent")):
        if not source.exists():
            raise SystemExit(f"Package is incomplete; missing {source}")
    for name in ROLES:
        fields = frontmatter(root / "agents" / f"{name}.md")
        if fields.get("name") != name:
            raise SystemExit(f"Agent name field does not match its filename: {name}.md")
        for required in ("description", "model"):
            if not fields.get(required):
                raise SystemExit(f"Agent {name}.md is missing a {required} field")
    skill_fields = frontmatter(root / "skills" / SKILL / "SKILL.md")
    if skill_fields.get("name") != SKILL:
        raise SystemExit(f"SKILL.md name field must be {SKILL}")


def verify(root: Path, claude: Path) -> list[str]:
    problems = []
    for source, target in paths(root, claude):
        if not os.path.lexists(target):
            problems.append(f"missing: {target}")
        elif target.is_symlink():
            if target.resolve() != source.resolve():
                problems.append(f"wrong symlink target: {target}")
        elif not same_tree(source, target):
            problems.append(f"stale copy: {target}")
    return problems


def _is_current(source: Path, target: Path, method: str) -> bool:
    if method == "symlink":
        return target.is_symlink() and target.resolve() == source.resolve()
    return not target.is_symlink() and same_tree(source, target)


def install(args: argparse.Namespace, root: Path, claude: Path) -> None:
    pairs = paths(root, claude)
    for source, target in pairs:
        # Never allow force or rollback to remove the package itself or an ancestor.
        source_path = source.resolve()
        target_path = target.parent.resolve() / target.name
        if (
            source_path == target_path
            or source_path.is_relative_to(target_path)
            or target_path.is_relative_to(source_path)
        ):
            raise SystemExit(f"Install destination overlaps package source: {target}")
    check_package(root)

    (claude / "skills").mkdir(parents=True, exist_ok=True)
    (claude / "agents").mkdir(parents=True, exist_ok=True)

    conflicts = [
        target
        for source, target in pairs
        if os.path.lexists(target) and not _is_current(source, target, args.method)
    ]
    if conflicts and not args.force:
        listing = "\n".join(f"  {item}" for item in conflicts)
        raise SystemExit(
            f"Existing resources conflict:\n{listing}\n"
            "Rerun with --force to back them up and replace them."
        )

    stamp = datetime.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    backup = claude / "rightsize-goal" / "install-backups" / stamp
    moved: list[tuple[Path, Path]] = []
    created: list[Path] = []
    try:
        if conflicts:
            backup.mkdir(parents=True, exist_ok=False)
        for source, target in pairs:
            if os.path.lexists(target):
                if _is_current(source, target, args.method):
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
        problems = verify(root, claude)
        if problems:
            raise RuntimeError("Installation verification failed:\n" + "\n".join(problems))
    except Exception as exc:
        for target in reversed(created):
            if target.is_symlink() or target.is_file():
                target.unlink(missing_ok=True)
            elif target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
        for target, saved in reversed(moved):
            shutil.move(saved, target)
        if getattr(exc, "winerror", None) == 1314:
            raise SystemExit(
                "Windows denied symlink creation. Enable Developer Mode, use an elevated "
                "terminal, or install with --method copy."
            ) from exc
        raise

    label = "symbolic links" if args.method == "symlink" else "copies"
    print(f"Rightsize Goal installed with {label}.")
    print(f"  skill:  {claude / 'skills' / SKILL}")
    print(f"  agents: {claude / 'agents'} ({len(ROLES)} roles)")
    if backup.exists():
        print(f"  backup: {backup}")
    print("Verification passed. Claude Code picks up new files within seconds;")
    print("start a fresh session if the skill or roles do not appear.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--method", choices=("symlink", "copy"), default="copy",
                        help="copy (default) is safest; symlink is for contributors working from a clone")
    parser.add_argument("--claude-dir", type=Path, default=default_claude_dir(),
                        help="Claude Code configuration directory (default: %(default)s)")
    parser.add_argument("--force", action="store_true",
                        help="back up and replace conflicting existing resources")
    parser.add_argument("--verify", action="store_true",
                        help="check an existing installation without changing anything")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    claude = args.claude_dir.expanduser().resolve()
    if args.verify:
        problems = verify(root, claude)
        if problems:
            print("Verification failed:", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
        print("Rightsize Goal installation is current and valid.")
        return 0
    install(args, root, claude)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
