# Installation and maintenance

## Requirements and compatibility

Use Python 3.11 or newer. Check with `python --version` (`python3 --version` on
macOS/Linux). On Windows, `py -3.11 codex/install.py` is an alternative if that
Python version is installed. The PowerShell wrapper invokes `python`; the shell
wrapper invokes `python3`. No third-party Python packages are required.

Use a local Codex release supporting standalone custom agent TOML files and
the configured model/effort combinations. Current [official agent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)
describes user-level discovery under `~/.codex/agents`. A precise oldest compatible
Codex version has not been established. Hosted environments without local Python,
filesystem access, or custom subagents are not supported by this installer.

## Files installed

| Resource | Default destination |
| --- | --- |
| Skill, references, helpers | `~/.agents/skills/rightsize-goal/` |
| Six `rightsize-*-doer.toml` definitions | `$CODEX_HOME/agents/` |
| Usage ledger created during runs | `$CODEX_HOME/rightsize-goal/usage.sqlite3` |
| Replacement/config backups | `$CODEX_HOME/rightsize-goal/install-backups/<timestamp>/` |

`CODEX_HOME` defaults to `~/.codex`. It affects the agents and usage ledger, not
the default skill directory. `--codex-dir PATH` and `--skills-dir PATH` override
installer destinations. They do not configure Codex to discover an arbitrary
location. If using a custom Codex home, launch Codex with the same `CODEX_HOME`.

Normal installation copies resources and leaves `config.toml` byte-for-byte
unchanged. It does not change your main model, permissions, credentials, or limits.
Run only one installer at a time and do not edit the same files while it runs.

## Alternative entry points

From the repository root:

```powershell
./codex/install.ps1
./codex/install.ps1 -Verify
```

```sh
sh codex/install.sh
sh codex/install.sh --verify
```

For a contributor symlink install:

```text
python codex/install.py --method symlink
```

Windows symlinks require Developer Mode or appropriate privileges. Default copy
installation does not require either. Symlinks track changes in the clone; moving
or deleting it breaks the installation. Start a new Codex session after updates.

## Older hosts and existing installations

For a host requiring explicit `[agents.<name>]` registrations, use:

```text
python codex/install.py --legacy-config
python codex/install.py --verify --legacy-config
```

PowerShell uses `-LegacyConfig`. This mode backs up changed configuration and
replaces only the six active registrations and removes retired Rightsize Goal registrations. Unsupported config layouts are
rejected rather than rewritten unsafely. It does not make unavailable models or
goal tools available. New default installs do not remove prior legacy registrations.

Upgrading from the earlier role roster requires `--force`. Existing role files are
backed up before the installer changes Sol/medium from `rightsize-lower-senior-doer`
to `rightsize-senior-doer`, Sol/high to `rightsize-staff-doer`, and Astra/medium to
`rightsize-principal-doer`. The generic `rightsize-astra-doer` filename is retired.
If the earlier install used legacy config registration, include
`--legacy-config --force` so registrations are migrated too. The installer refuses
a default update that would leave retired registrations pointing at removed files.

## Update, conflicts, and recovery

Pull the desired Git tag/commit or extract the desired source archive, then run:

```text
python codex/install.py --force
python codex/install.py --verify
```

Include `--legacy-config` if maintaining legacy registrations. For symlink installs,
pulling updates files immediately; rerun with `--method symlink --force` if the
clone path or installed resources changed. To convert a symlink install to copies,
use `--method copy --force`.

Without `--force`, differing installed files are preserved and reported as conflicts.
With it, old resources move into a timestamped backup before replacement. If copying,
configuration writing, or final verification fails, the installer attempts to remove
partial new resources and restore old ones. Backups remain available for recovery;
they may include symlinks, which still depend on their original source path.

To restore manually, close Codex, inspect the printed backup path, and move each
saved resource from `resources/` back to its matching destination above. Review
the backed-up `config.toml` before restoring it: replacing your entire current
config could discard changes made after that backup. Usage history is independent
of installed source files.

## Uninstall

Close Codex. Remove only `rightsize-goal` from the installed skills directory and
the six files below from the installed agents directory:

```text
rightsize-junior-doer.toml
rightsize-midlevel-doer.toml
rightsize-upper-midlevel-doer.toml
rightsize-senior-doer.toml
rightsize-staff-doer.toml
rightsize-principal-doer.toml
```

For symlink installs, remove the links themselves, not their targets. If you used
legacy mode, remove the matching six `[agents.rightsize-...]` tables from
`config.toml`, leaving other tables/settings intact. Restart Codex.
Older installations may also contain retired `rightsize-lower-senior-doer` and
`rightsize-astra-doer` files or config tables; remove those exact entries too.

By default, keep usage history, backups, and each project's `.rightsize-goal/`
records. Delete those separately only if you want to discard that history.
There is currently no automated uninstall command.

## Troubleshooting

- **Skill or agents missing:** start a fresh session; check destinations and
  `CODEX_HOME`; run `--verify`. An older host may need legacy mode. Installing
  only the skill with a generic skill installer omits the six agent definitions.
- **Model unavailable:** inspect your account/host's model access. Installing a
  role does not grant access. Do not silently replace model names and assume
  the original routing or pricing still applies.
- **No `/goal` or native goal tools:** invoke `$rightsize-goal` directly. Work can
  continue in the session with saved state, but automatic continuation is unavailable.
- **Python not found/too old:** install Python 3.11+ and select the correct interpreter.
- **PowerShell blocks scripts:** run `python codex/install.py` directly.
- **Permission denied:** ensure the chosen destination is writable; default copy
  mode avoids symlink privilege requirements.
- **Stale copy/conflict:** inspect local changes, then use `--force` to back up and
  replace them if appropriate.
- **Usage unavailable:** see [accounting](accounting.md). Missing telemetry is
  explicit and should not block the actual objective.

Verification compares installed files with the source checkout/archive. It is not
a live test of Codex loading the agents, model entitlement, or native goal behavior.
