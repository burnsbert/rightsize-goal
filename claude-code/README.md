# Rightsize Goal for Claude Code

Rightsize Goal helps Claude Code pursue substantial objectives using a small engineering
team. A coordinator assigns bounded work to a suitable model tier, verifies results, and
records usage and lessons. It seeks lower total cost including rework; savings are not
guaranteed. For a one-step request, the main session completes it directly without
dispatching agents or creating persistent goal state.

Under a plugin install it is also persistent: a Stop hook keeps the session working until an
independent validator confirms the goal is met, the way `/goal` would, while each task goes to
the cheapest capable model.

This package ships one skill, five subagent roles (four worker tiers and a validator), a Stop
hook, three standard-library Python helpers, and an installer. It uses your existing Claude
Code account and permissions.

## Requirements

- Claude Code with subagent `model` and `effort` frontmatter support. Verified against
  `2.1.263`, and the `opus` alias was confirmed to serve Opus 5.5 on `2.1.282`; the oldest
  compatible version has not been established.
- Access to Claude Haiku 4.5, Sonnet 5, Opus 5.5, and Fable 5.1 on your account. Roles for
  a model you cannot use will fail at dispatch. See [checking model access](#check-model-access).
- Python 3.11 or newer for persistent runs using the two helper scripts. No third-party packages.
- A trusted workspace, if you want `/goal` to hold the session open.
- Optionally `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. Recommended, not required: it lets the
  coordinator reuse a warm worker across related assignments instead of rebuilding its context
  each time. Everything works without it. See [Agent Teams](docs/install.md#agent-teams-recommended).

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

That is the whole installation. Nothing is copied into your configuration by hand, and
`/plugin uninstall rightsize-goal` removes it. Claude Code does not auto-update third-party
marketplaces by default; see [update and test](#update-and-test) to turn that on or update by
hand.
Confirm what landed with `claude plugin details rightsize-goal`, which lists one skill,
five agents, one Stop hook, and the plugin's token cost.

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

This copies the skill to `~/.claude/skills/rightsize-goal` and the five role files to
`~/.claude/agents/`. It writes no settings and changes no existing configuration. Roles
installed this way are addressed by their bare names, without a prefix. It does not install
the plugin's Stop hook, so a manual install relies on `/goal` to hold the session open.

Use one method, not both. A plugin install and a manual install side by side give you two
copies of the skill and roles under different names, and the manual copy never receives
plugin updates.

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

If Fable is unavailable, the principal role will fail at dispatch. The skill
is instructed to disclose that, treat the highest available tier as the top of the
ladder, and say in its final report that escalation was capped. Never edit a role to
point at a different model without also updating
[`references/tariff.json`](skills/rightsize-goal/references/tariff.json); the ledger
prices whatever model actually served the request.

## Run

Choose a capable coordinator, then give the skill your goal and how you will know it is
done:

```text
/model opus
/effort medium

/rightsize-goal:rightsize-goal Add regression tests for this project's configuration parser. Cover invalid input and defaults; all existing tests must pass. Change tests only, not production code.
```

Under a plugin install that is all it takes. The coordinator keeps a living task list,
dispatches each task to the cheapest capable role, and when it believes the goal is met,
sends `rightsize-validator` to check the work against your goal. A NOT DONE verdict becomes
new tasks; only a DONE verdict ends the run. The plugin's Stop hook holds the session open
until then, so the work carries on without you typing "continue".

- **Change course** by saying so. The coordinator records your words, rewords the goal, and
  re-plans; the validator judges the amended goal.
- **Pause** by saying "stop" or "pause", and **resume** by saying "resume", in the same or a
  later session. Esc always interrupts.
- If the run makes no recorded progress for several continuations, the hook lets the
  session stop and says so, rather than spinning.

Opus at `medium` and Sonnet 5 at `high` are capable coordinators; Haiku is not suitable
for this role. The command name depends on how you installed it:

| Install | Command | What holds the session open |
| --- | --- | --- |
| Plugin | `/rightsize-goal:rightsize-goal` | The plugin's Stop hook |
| Manual (`install.py`) | `/rightsize-goal` | `/goal`, which the skill offers or gives you to paste |

You can also start under Claude Code's own `/goal`, for example
`/goal Use the rightsize-goal skill to ...`. The skill then lets `/goal` drive and its own
hook stands down, so only one of them keeps the session going.

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

See [usage examples, stop and resume, and limitations](docs/usage.md).

## The roles

| Role | Model / effort | Intended scope |
| --- | --- | --- |
| Junior | Haiku 4.5 | Very basic explicit work |
| Midlevel | Sonnet 5 / high | Bounded work using established patterns, including moderately complex work needing more judgment |
| Senior | Opus 5.5 / high | Hard implementation, research, brainstorming, and deep interacting constraints |
| Principal | Fable 5.1 / high | Break-glass only: hardest bounded work after documented Opus struggle |
| Validator | Opus 5.5 / high, read-only | Checks the finished work against your goal and returns DONE or NOT DONE |

Haiku 4.5 does not take an effort setting, so the junior role pins the model only. Every
other role pins both, and the Agent tool has no dispatch-time effort override, which is
why the roles exist as files rather than as instructions. [Why these roles](docs/roles.md)
explains the boundaries, what each role can and cannot touch, and how to change them.

Each goal has a unique `.rightsize-goal/<goal-id>.jsonl` call/result log in the target project. Task usage and routing history remain in that project's `.rightsize-goal/usage.sqlite3`. Cost figures are
standard-rate API-equivalent estimates from a versioned tariff; they are useful for
routing comparisons and are not an authoritative bill. A Claude Code subscription is not
billed per token at all.

See [accounting and local data](docs/accounting.md) for what is measured and what stays local.

## Update and test

For a plugin install, either turn on auto-update for this marketplace (`/plugin` →
**Marketplaces** → `rightsize-goal` → **Enable auto-update**) or update by hand:

```sh
claude plugin update rightsize-goal
```

That refreshes the marketplace and installs any newer release; restart Claude Code to load
it. An install only changes when the plugin's `version` changes, so an unchanged version
reports "already at the latest version" even if the repository has moved on.

For a symlink install, pulling this repository updates the installed files immediately.
Copy installs require rerunning the installer with `--force`.

Run all deterministic tests from `claude-code/`:

```sh
python3 -m unittest discover -s tests -p "test_*.py"
```

Validate the packaging from the repository root:

```sh
claude plugin validate --strict .
claude plugin validate --strict claude-code/
```

CI runs the same two commands, so a manifest warning fails the build.

The bundled model tariff has a review date. Once it expires, token accounting continues
while dollar estimates remain unavailable until
[`references/tariff.json`](skills/rightsize-goal/references/tariff.json) is refreshed
from the linked official pricing pages.

See the [contributor guide](../CONTRIBUTING.md) and
[release checks and validation status](docs/release.md).

## License

[MIT](../LICENSE), copyright 2026 Eric Burns. Independent community project; not an
official Anthropic product. Claude Code and model access are provided separately.
