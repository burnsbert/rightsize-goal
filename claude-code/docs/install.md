# Installation and maintenance

## Choosing a method

| | Plugin | `install.py` |
| --- | --- | --- |
| Commands to run | two | one, plus a clone |
| Needs Python to install | no | yes, 3.11+ |
| Updates | auto-update if enabled, or `claude plugin update rightsize-goal` | rerun with `--force` |
| Uninstall | `/plugin uninstall rightsize-goal` | manual file removal |
| Direct skill command | `/rightsize-goal:rightsize-goal` | `/rightsize-goal` |
| Role names | `rightsize-goal:rightsize-...` | `rightsize-...` |
| Custom config directory | follows `CLAUDE_CONFIG_DIR` | `--claude-dir PATH` |

Both install the same skill and the same five roles. The helper scripts need Python 3.11+
at run time either way; the plugin route just does not need it to install.

Pick one. Installing both ways gives you two copies of the skill and roles under different
names (`rightsize-goal:rightsize-junior-doer` and `rightsize-junior-doer`), and the manual
copy never receives plugin updates. To switch methods, uninstall the old one first.

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

Check the result with `claude plugin details rightsize-goal`. It should report one skill,
five agents, and one Stop hook. `claude plugin list` shows what is installed, and the `/plugin` **Errors**
tab surfaces loading problems.

To start a substantial run, invoke the skill with the goal:

```text
/rightsize-goal:rightsize-goal Add regression tests for the parser. Cover invalid input and defaults; all existing tests must pass.
```

The plugin's Stop hook keeps a run like this working until its validator confirms the goal.
The hook is silent in any session that does not own an active goal, makes no model call, and
does not run at all when hooks are disabled with `disableAllHooks`. See [usage](usage.md) for
how it decides, and for scope, limits, pausing, and resuming.

`--scope user` is the default. Use `--scope project` to install for one repository, which
is worth doing when a team should share the same roles.

Claude Code auto-updates only Anthropic's own marketplaces by default. To keep this plugin
current, open `/plugin`, go to **Marketplaces**, select `rightsize-goal`, and choose
**Enable auto-update**, or update by hand as described [below](#update-conflicts-and-recovery).

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
| Five role files (`rightsize-*-doer.md`, `rightsize-validator.md`) | `~/.claude/agents/` |
| Usage ledger and goal logs created during runs | `<current-directory>/.rightsize-goal/` |
| Replacement backups | `~/.claude/rightsize-goal/install-backups/<timestamp>/` |

`CLAUDE_CONFIG_DIR` overrides `~/.claude` for the skill, the role files, and the backups; the
usage ledger and goal logs always live in the directory you run from. `--claude-dir PATH` overrides the
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

## Agent Teams (recommended)

Rightsize Goal works with or without Claude Code's Agent Teams feature, but it works better
with it. Enable it by setting an environment variable before launching Claude Code:

```sh
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

This is the only switch: there is no settings key and no slash command for it, and the name
says what it is — experimental, and subject to change.

**With Agent Teams on**, a worker dispatched with a name becomes a *teammate*: it runs as its
own addressable session, `ListAgents` lists it, and the coordinator can send it follow-up
assignments with `SendMessage` while its context is still warm. That reuse is the point when
the next task is a natural follow-on, such as fixing or extending what the teammate just built or
the next step in the same area: re-explaining that work to a fresh worker would cost real tokens.
Work in an unrelated area goes to a fresh teammate instead, because a teammate re-reads everything
it has seen on every request. The coordinator reuses a teammate freely below 120,000 tokens of
context, only for small dependent follow-ons up to 200,000, and retires it after that. It shuts
down teammates it no longer expects to use; every role can accept a shutdown request.

**With Agent Teams off**, the coordinator omits the name and dispatches an ordinary in-process
subagent. Everything still works — routing, the escalation gate, the completion gate, and usage
accounting are all unaffected. The one thing you lose is reuse: a follow-up needs a fresh worker
that must be given its context again. The skill detects which mode is live, adapts, and says in
its final report when reuse was unavailable.

**Known Claude Code bug: teammates ignore a role's `effort` frontmatter.** With Agent Teams
on, a dispatched teammate silently inherits the coordinator's own session effort instead of
the role definition's pinned `effort` — the `model` field crosses over correctly, but `effort`
does not, with no warning. This is a genuine gap in Claude Code, tracked upstream as
[anthropics/claude-code#80569](https://github.com/anthropics/claude-code/issues/80569); it does
not affect this package's Codex implementation, which has no equivalent teammate dispatch mode.
The unaffected path is a plain in-process subagent (Agent Teams off, or a coordinator that omits
the worker's name), where `effort` frontmatter is honored. Until the upstream bug is fixed, treat
a role's declared effort as reliable only on that path, and check `/tasks` while a worker is
active to see the effort it actually ran at.

As of September 24, 2026 the issue is still open with no linked fix. It was last reproduced
publicly on Claude Code `2.1.233`; nobody has re-tested it on `2.1.282`, so assume it still
applies. Because every effort-bearing role pins `high`, it only changes behavior when the
coordinator session runs at a different level — for example, a coordinator at `/effort medium`
runs its teammates at `medium`, including the senior Opus role.

A teammate is a whole session rather than a lightweight helper, so it loads its own project
instructions and orients itself before touching the work you assigned. Its floor cost per
dispatch is therefore several times a plain subagent's — see
[why these roles](roles.md#what-a-dispatch-actually-costs) for measured figures. Bundle
related work into one assignment rather than spawning a teammate for something smaller than its
own startup cost.

## Update, conflicts, and recovery

For a plugin install:

```sh
claude plugin update rightsize-goal
```

This refreshes the marketplace and installs the newer release if there is one; restart Claude
Code to load it. Claude Code compares the plugin's declared `version`, so it reports "already at
the latest version" until a release bumps that number, however many commits have landed.

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

Manual install: remove `rightsize-goal` from the installed skills directory and these five
files from the installed agents directory.

```text
rightsize-junior-doer.md
rightsize-midlevel-doer.md
rightsize-senior-doer.md
rightsize-principal-doer.md
rightsize-validator.md
```

For symlink installs, remove the links themselves, not their targets. There is no automated
uninstall command for the manual method.

By default, keep the backups and each project's `.rightsize-goal/` records. Delete those separately only if you want to discard that history.

## Troubleshooting

- **Skill or roles missing.** Run `claude plugin details rightsize-goal` for a plugin
  install, or `install.py --verify` for a manual one. Check `/plugin` → Errors. Start a
  fresh session. Installing only the skill with a generic skill installer omits the five
  roles, and the workflow will refuse to substitute a default agent for them.
- **"Agent type not found".** Under a plugin install the roles need the
  `rightsize-goal:` prefix. Read the available-agents list and use the exact string.
- **Usage shows as unavailable for a named worker.** With Agent Teams on, a teammate writes its
  own session transcript rather than a file under `subagents/`. The helper resolves both layouts
  from the `<agentName>@<teamName>` id the Agent tool returns; if it still cannot find one, pass
  `--transcript PATH` explicitly.
- **Model unavailable.** Check `/model`, or probe with
  `claude --model fable -p 'Reply with exactly: OK'`. Installing a role does not grant
  access. Do not silently repoint a role at a different model: see
  [why these roles](roles.md#changing-the-ladder) for the three files that must stay
  consistent.
- **The session stops before the goal is done.** Under a plugin install, check that the goal
  is still active (`drive.py show --drive .rightsize-goal/<goal-id>.drive.json`), bound to the
  current session (say "resume" to rebind it), and that `disableAllHooks` is not set. After
  several continuations with no recorded progress, the hook deliberately lets the session stop.
  It also lets the session wait quietly while any task is `in_progress`; if a worker died
  without reporting back, say "resume" or tell the coordinator to recheck its tasks. The hook
  needs Python on the path as `python3`, `python`, or the Windows `py` launcher; if none
  resolves, it cannot run.
- **`/goal` refuses to run.** It needs a trusted workspace and unrestricted hooks. Work can
  still proceed without it; under a manual install, only the automatic hold on session stop
  is lost.
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
