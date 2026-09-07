# Installation and maintenance

## Choosing a method

| | Plugin | `install.py` |
| --- | --- | --- |
| Commands to run | two | one, plus a clone |
| Needs Python to install | no | yes, 3.11+ |
| Updates | `/plugin update rightsize-goal` | rerun with `--force` |
| Uninstall | `/plugin uninstall rightsize-goal` | manual file removal |
| Skill command | `/rightsize-goal:rightsize-goal` | `/rightsize-goal` |
| Role names | `rightsize-goal:rightsize-...` | `rightsize-...` |
| Custom config directory | follows `CLAUDE_CONFIG_DIR` | `--claude-dir PATH` |

Both install the same skill and the same seven roles. The helper scripts need Python 3.11+
at run time either way; the plugin route just does not need it to install.

## Plugin installation

From inside Claude Code:

```text
/plugin marketplace add burnsbert/rightsize-goal
/plugin install rightsize-goal@rightsize-goal
```

The equivalent terminal commands are `claude plugin marketplace add burnsbert/rightsize-goal`
and `claude plugin install rightsize-goal@rightsize-goal`. To install from a local clone
instead of GitHub, point the marketplace at the clone with a path that starts with `./`:

```sh
claude plugin marketplace add ./rightsize-goal
```

Check the result with `claude plugin details rightsize-goal`. It should report one skill
and seven agents. `claude plugin list` shows what is installed, and the `/plugin` **Errors**
tab surfaces loading problems.

`--scope user` is the default. Use `--scope project` to install for one repository, which
is worth doing when a team should share the same roles.

## Manual installation

Use Python 3.11 or newer. Check with `python3 --version`, or `python --version` on Windows.
`py -3.11 claude-code\install.py` also works if that version is installed. No third-party
packages are required.

```sh
python3 claude-code/install.py
python3 claude-code/install.py --verify
```

Wrappers exist for both platforms and take the same options with platform-native spelling:

```sh
sh claude-code/install.sh
sh claude-code/install.sh --verify
```

```powershell
.\claude-code\install.ps1
.\claude-code\install.ps1 -Verify
```

### Files installed

| Resource | Default destination |
| --- | --- |
| Skill, references, helpers | `~/.claude/skills/rightsize-goal/` |
| Seven `rightsize-*-doer.md` role files | `~/.claude/agents/` |
| Usage ledger created during runs | `~/.claude/rightsize-goal/usage.sqlite3` |
| Replacement backups | `~/.claude/rightsize-goal/install-backups/<timestamp>/` |

`CLAUDE_CONFIG_DIR` overrides `~/.claude` for all four. `--claude-dir PATH` overrides the
installer's destination for a single run; it does not configure Claude Code to look
somewhere else, so if you use a custom configuration directory, launch Claude Code with the
same `CLAUDE_CONFIG_DIR`.

Installation writes only the files above. It does not touch `settings.json`, your model,
permissions, credentials, or limits, and it creates no configuration file of its own. A
packaged test asserts that nothing but `skills/` and `agents/` appears. Run only one
installer at a time and do not edit the same files while it runs.

### Contributor symlinks

```sh
python3 claude-code/install.py --method symlink
```

Symlinks track changes in the clone, so a `git pull` updates the installation immediately.
Moving or deleting the clone breaks it. Windows symlinks require Developer Mode or
sufficient privileges; the default copy method requires neither. To convert a symlink
install back to copies, use `--method copy --force`.

## Update, conflicts, and recovery

For a plugin install:

```sh
claude plugin marketplace update rightsize-goal
```

For a copy install, pull the desired tag or commit and rerun:

```sh
python3 claude-code/install.py --force
python3 claude-code/install.py --verify
```

Without `--force`, differing installed files are preserved and reported as conflicts. With
it, the old resources move into a timestamped backup directory before replacement. If
copying or the final verification fails, the installer removes the partial new resources
and restores the old ones before re-raising the error.

To restore manually, inspect the printed backup path and move each saved file from
`resources/` back to its matching destination in the table above. Backups may contain
symlinks, which still depend on their original source path. Usage history is independent of
installed source files.

Claude Code watches both the skills and agents directories and reloads within seconds. A
newly created `agents` directory is the exception; start a fresh session if the roles do
not appear.

## Uninstall

Plugin: `/plugin uninstall rightsize-goal`, then
`/plugin marketplace remove rightsize-goal` if you no longer want the marketplace entry.

Manual install: remove `rightsize-goal` from the installed skills directory and these seven
files from the installed agents directory.

```text
rightsize-junior-doer.md
rightsize-midlevel-doer.md
rightsize-upper-midlevel-doer.md
rightsize-lower-senior-doer.md
rightsize-senior-doer.md
rightsize-staff-doer.md
rightsize-principal-doer.md
```

For symlink installs, remove the links themselves, not their targets. There is no automated
uninstall command for the manual method.

By default, keep the usage ledger, the backups, and each project's `.rightsize-goal/`
records. Delete those separately only if you want to discard that history.

## Troubleshooting

- **Skill or roles missing.** Run `claude plugin details rightsize-goal` for a plugin
  install, or `install.py --verify` for a manual one. Check `/plugin` → Errors. Start a
  fresh session. Installing only the skill with a generic skill installer omits the seven
  roles, and the workflow will refuse to substitute a default agent for them.
- **"Agent type not found".** Under a plugin install the roles need the
  `rightsize-goal:` prefix. Read the available-agents list and use the exact string.
- **Model unavailable.** Check `/model`, or probe with
  `claude --model fable -p 'Reply with exactly: OK'`. Installing a role does not grant
  access. Do not silently repoint a role at a different model: see
  [why these seven roles](roles.md#changing-the-ladder) for the three files that must stay
  consistent.
- **`/goal` refuses to run.** It needs a trusted workspace and unrestricted hooks. Work can
  still proceed without it; only the automatic hold on session stop is lost.
- **Python not found or too old.** Install Python 3.11+ and select the right interpreter.
  Only the two helper scripts need it, so the skill can still guide work without them —
  but the completion gate and the usage ledger will be unavailable, and the coordinator
  should say so rather than pretending otherwise.
- **PowerShell blocks scripts.** Run `python .\claude-code\install.py` directly.
- **Permission denied.** Ensure the chosen destination is writable; the default copy mode
  avoids symlink privilege requirements.
- **Stale copy or conflict.** Inspect your local changes, then use `--force` to back them
  up and replace them if appropriate.
- **Usage unavailable.** See [accounting](accounting.md). A missing measurement is reported
  explicitly and should never block the actual objective.

Verification compares installed files with the source checkout. It is not a live test of
Claude Code loading the roles, of model entitlement, or of delegation quality.
