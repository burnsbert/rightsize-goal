# Rightsize Goal for Claude Code

Rightsize Goal helps Claude Code pursue substantial objectives using a small engineering
team. A coordinator assigns bounded work to a suitable model tier, verifies results, and
records usage and lessons. It seeks lower total cost including rework; savings are not
guaranteed. It is useful for multi-step implementation and investigation; trivial edits
usually do not warrant the coordination overhead.

This package ships one skill, seven subagent roles, two standard-library Python helpers,
and an installer. It uses your existing Claude Code account and permissions.

## Requirements

- Claude Code with subagent `model` and `effort` frontmatter support. Verified against
  `2.1.263`; the oldest compatible version has not been established.
- Access to Claude Haiku 4.5, Sonnet 5, Opus 5, and Fable 5.1 on your account. Roles for
  a model you cannot use will fail at dispatch. See [checking model access](#check-model-access).
- Python 3.11 or newer, for the two helper scripts. No third-party packages.
- A trusted workspace, if you want `/goal` to hold the session open.

## Install

The plugin is the easiest route. From inside Claude Code:

```text
/plugin marketplace add burnsbert/rightsize-goal
/plugin install rightsize-goal@rightsize-goal
```

Or from a terminal:

```sh
claude plugin marketplace add burnsbert/rightsize-goal
claude plugin install rightsize-goal@rightsize-goal
```

That is the whole installation. Nothing is copied into your configuration by hand,
`/plugin update` handles upgrades, and `/plugin uninstall rightsize-goal` removes it.
Confirm what landed with `claude plugin details rightsize-goal`, which lists one skill,
seven agents, and the plugin's token cost.

Under a plugin install the roles are addressed with the plugin prefix, for example
`rightsize-goal:rightsize-junior-doer`. The skill resolves this itself at run time.

### Manual install

If you would rather have plain files under your Claude Code configuration directory,
clone the repository and run the installer:

```sh
git clone https://github.com/burnsbert/rightsize-goal.git
cd rightsize-goal
python3 claude-code/install.py
python3 claude-code/install.py --verify
```

On Windows PowerShell:

```powershell
git clone https://github.com/burnsbert/rightsize-goal.git
cd rightsize-goal
python .\claude-code\install.py
python .\claude-code\install.py --verify
```

This copies the skill to `~/.claude/skills/rightsize-goal` and the seven role files to
`~/.claude/agents/`. It writes no settings and changes no existing configuration. Roles
installed this way are addressed by their bare names, without a prefix.

| Method | Best for | Keep the source directory afterward? |
| --- | --- | --- |
| Plugin from GitHub | Most users | No |
| Clone plus `install.py` | Users who want plain files or a custom `CLAUDE_CONFIG_DIR` | Only to verify or update |
| Clone plus `install.py --method symlink` | Contributors | Yes, at the same path |

Existing conflicting resources are preserved unless `--force` is supplied, which first
moves the old resources into a timestamped directory under
`~/.claude/rightsize-goal/install-backups/`.

See [installation and maintenance](docs/install.md) for custom destinations, conflicts,
backups, removal, and troubleshooting. Verification checks files, not account model
entitlement or live delegation behavior.

## Check model access

Installing a role does not grant access to its model. Check `/model` inside Claude Code,
or run one cheap probe per model from a terminal:

```sh
claude --model fable  -p 'Reply with exactly: OK'
claude --model opus   -p 'Reply with exactly: OK'
claude --model sonnet -p 'Reply with exactly: OK'
claude --model haiku  -p 'Reply with exactly: OK'
```

If Fable is unavailable, the staff and principal roles will fail at dispatch. The skill
is instructed to disclose that, treat the highest available tier as the top of the
ladder, and say in its final report that escalation was capped. Never edit a role to
point at a different model without also updating
[`references/tariff.json`](skills/rightsize-goal/references/tariff.json); the ledger
prices whatever model actually served the request.

## Run

How you invoke the skill depends on how you installed it:

| Install | Command |
| --- | --- |
| Plugin | `/rightsize-goal:rightsize-goal` |
| Manual (`install.py`) | `/rightsize-goal` |

The examples below use the plugin form. Substitute the bare form for a manual install; the
arguments are identical either way, and autocomplete after `/rightsize` shows whichever one
is live.

Select Opus with `medium` effort for the root session, then invoke the skill:

```text
/model opus
/effort medium

/rightsize-goal:rightsize-goal Add regression tests for this project's configuration parser.
Acceptance: cover invalid input and defaults; all existing tests pass.
Scope: tests only; do not change production code.
```

For work that genuinely needs time bounds:

```text
/rightsize-goal:rightsize-goal --minimum-time="30 minutes" --maximum-time="3 hours"
Investigate and fix the reported performance regression. Acceptance: reproduce it,
identify the cause, and demonstrate improvement with a benchmark.
```

The duration options belong to Rightsize Goal, not to `/goal`. The minimum is a
completion condition; the maximum stops new dispatches at checkpoints and produces an
incomplete handoff if acceptance remains unmet. Time means elapsed wall-clock time
including pauses, not active work or billed compute. A skill is not a watchdog or a
spending cap. No bounds apply by default.

To hold the session open until the work is actually done, set a session goal as well.
The coordinator will offer one; you can also type it yourself:

```text
/goal the parser regression is reproduced, fixed, and covered by a passing test
```

See [usage examples, stop and resume, and limitations](docs/usage.md).

## The roles

| Role | Model / effort | Intended scope |
| --- | --- | --- |
| Junior | Haiku 4.5 | Very basic explicit work |
| Lower-midlevel | Sonnet 5 / medium | Routine bounded work using established patterns |
| Upper-midlevel | Sonnet 5 / xhigh | Moderately complex bounded work |
| Lower-senior | Opus 5 / medium | Hard implementation, research, and brainstorming |
| Senior | Opus 5 / xhigh | Deep interacting constraints and difficult reasoning |
| Staff | Fable 5.1 / low | Bounded expert work after documented Opus struggle |
| Principal | Fable 5.1 / medium | Hardest bounded work after documented Opus struggle |

Haiku 4.5 does not take an effort setting, so the junior role pins the model only. Every
other role pins both, and the Agent tool has no dispatch-time effort override, which is
why the roles exist as files rather than as instructions. [Why these seven](docs/roles.md)
explains the boundaries, what each role can and cannot touch, and how to change them.

Project activity is logged under `.rightsize-goal/` in the target project. Cross-project
routing history and task usage live in `~/.claude/rightsize-goal/`. Cost figures are
standard-rate API-equivalent estimates from a versioned tariff; they are useful for
routing comparisons and are not an authoritative bill. A Claude Code subscription is not
billed per token at all.

See [accounting and local data](docs/accounting.md) for what is measured and what stays local.

## Update and test

For a plugin install, run `/plugin update rightsize-goal` or
`claude plugin marketplace update rightsize-goal`. For a symlink install, pulling this
repository updates the installed files immediately. Copy installs require rerunning the
installer with `--force`.

Run all deterministic tests from `claude-code/`:

```sh
python3 -m unittest discover -s tests -p "test_*.py"
```

Validate the packaging from the repository root:

```sh
claude plugin validate .
claude plugin validate claude-code/
```

The bundled model tariff has a review date. Once it expires, token accounting continues
while dollar estimates remain unavailable until
[`references/tariff.json`](skills/rightsize-goal/references/tariff.json) is refreshed
from the linked official pricing pages.

See the [contributor guide](../CONTRIBUTING.md) and
[release checks and validation status](docs/release.md).

## License

[MIT](../LICENSE), copyright 2026 Eric Burns. Independent community project; not an
official Anthropic product. Claude Code and model access are provided separately.
