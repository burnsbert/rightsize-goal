# Rightsize Goal for Codex

Rightsize Goal helps Codex pursue substantial objectives using a small engineering
team. A coordinator assigns bounded work to a suitable model tier, verifies results,
and records usage and lessons. It seeks lower total cost including rework; savings
are not guaranteed. For a one-step request, the main thread completes it directly
without dispatching agents or creating persistent goal state.

This package ships one skill, five custom agents, two standard-library Python
helpers, and installers. It uses your existing Codex account, with full-access
permission defaults for all five workers.

## Requirements

- A local Codex host with custom subagents enabled. Native goal tools are required
  for automatic continuation, but current-session work can use saved goal state.
- Python 3.11 or newer.
- Access to the model names configured by the five included roles.
- For optional symlinks on Windows: Developer Mode or appropriate privileges.

## Install

For the full workflow, clone the repository and run the installer. It installs
the Codex skill and all five custom agents:

```powershell
git clone https://github.com/burnsbert/rightsize-goal.git
cd rightsize-goal
python codex/install.py
python codex/install.py --verify
```

On macOS or Linux:

```sh
git clone https://github.com/burnsbert/rightsize-goal.git
cd rightsize-goal
sh codex/install.sh
sh codex/install.sh --verify
```

The default installation copies the skill to `~/.agents/skills/rightsize-goal`
and the five agent definitions to `$CODEX_HOME/agents` (normally `~/.codex/agents`).
It leaves global configuration unchanged. Older hosts needing explicit registrations
can opt into `--legacy-config`, which backs up changed configuration first.

From `codex/`, Windows users can also run:

```powershell
.\install.ps1 -Method copy
```

Existing conflicting resources are preserved unless `-Force` (PowerShell) or `--force` (shell/Python) is supplied. Forced replacement moves the old resources into a timestamped directory under `$CODEX_HOME/rightsize-goal/install-backups/`.

Verify an installation at any time:

```powershell
.\install.ps1 -Verify
```

```sh
./install.sh --verify
```

After installing or updating, start a fresh Codex session so the skill and custom agents are loaded.

| Method | Best for | Keep source directory afterward? |
| --- | --- | --- |
| Clone + default copy | Most users | Only to verify/update against that version |
| Download/extract GitHub source ZIP + copy | Users without Git | Only to verify/update |
| Clone + `--method symlink` | Contributors | Yes, at the same path |

Keep dot-prefixed folders when extracting an archive. Codex users can also add
this repository as a marketplace and install `rightsize-goal@rightsize-goal`.
That plugin safely installs the **Codex skill only**. Codex plugins cannot yet
bundle custom agents, so the five roles still need `codex/install.py` for the
full workflow. Use the installer as the supported full install path; avoid
combining plugin and manual installs of the skill, which creates two copies
that can drift. See [installation and maintenance](docs/install.md) for the
plugin commands and details.

See [installation and maintenance](docs/install.md) for custom destinations,
legacy mode, conflicts, backups, removal, and troubleshooting. Verification checks
files, not account model entitlement or live goal/subagent behavior.

## Run

Select `gpt-6-sol` with medium reasoning for the root Codex session, then invoke:

```text
Use $rightsize-goal to add regression tests for this project's configuration parser.
Acceptance: cover invalid input and defaults; all existing tests pass.
Scope: tests only; do not change production code.
```

The skill starts a native goal for substantial work when goal tools are available.
`/goal Use $rightsize-goal to <objective>` is also a valid explicit entry point.
For work that actually needs time bounds:

```text
/goal Use $rightsize-goal --minimum-time="30 minutes" --maximum-time="3 hours" to accomplish <objective>. Acceptance: <observable checks>.
```

The duration options belong to Rightsize Goal. The workflow uses native goal tools underneath when they are available. The minimum is a completion condition; the maximum stops new dispatches at checkpoints and produces an incomplete handoff if acceptance remains unmet.

Time means elapsed wall-clock time including pauses, not active work or billed
compute. A skill is not a watchdog or spending cap. No bounds apply by default.
See [usage examples, stop/resume, and limitations](docs/usage.md).

The coordinator routes work among:

| Role | Configuration | Intended scope |
| --- | --- | --- |
| Junior | Luna/high | Very basic explicit work and factual research without judgment calls |
| Lower-midlevel | Luna/xhigh | Routine bounded work and evidence gathering using defined criteria |
| Senior | Sol/medium | Moderate to hard implementation, research, and brainstorming |
| Staff | Sol/high | Strongest pre-Astra first pass for the most complex work; deep interacting constraints |
| Principal | Astra/medium | Bounded expert work after documented Sol struggle |

Known moderate work goes directly to Sol/medium rather than using Luna as a cheap trial.
The most complex work goes directly to Sol/high when Astra escalation is a credible
risk. Astra has one medium-effort principal engineer role so the escalation receives
enough reasoning budget without an Astra/low retry.

Every role sets the following defaults for filesystem access, network access
from commands, and live web research:

```toml
sandbox_mode = "danger-full-access"
approval_policy = "never"
web_search = "live"
```

The coordinator must also run with full access. This repository's
[project configuration](../.codex/config.toml) sets these defaults and registers
the five distributed roles using relative paths. In another trusted project,
merge the three settings above into its `.codex/config.toml` before starting
Codex. For a one-off CLI session, use
`codex --sandbox danger-full-access --ask-for-approval never --search`.
In the app or IDE, select full access for the parent session before delegating.

The parent's active permission overrides can take precedence over role defaults;
agent files cannot override managed restrictions. See the official
[subagent permission documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)
and [permission settings](https://learn.chatgpt.com/docs/agent-approvals-security).
Full access includes files outside the repository. Assigned scope still applies:
research is read-only unless artifact ownership is assigned, and commits,
publishing, and external messages require explicit authorization. Those boundaries
are agent instructions rather than filesystem restrictions.

Each goal has a unique `.rightsize-goal/<goal-id>.jsonl` call/result log in the target project. Task usage and routing history remain in that project's `.rightsize-goal/usage.sqlite3`. The cost figures are standard-rate API-equivalent estimates from a versioned tariff; they are useful for routing comparisons but are not an authoritative subscription bill.

See [accounting and local data](docs/accounting.md) for measurement gaps and privacy.

## Update and test

For symlink installs, pulling this repository updates the installed files immediately. Start a fresh Codex session after pulling. Copy installs require rerunning the installer with the force option.

Run all deterministic tests from `codex/`:

```sh
python -m unittest discover -s tests -p "test_*.py"
```

The bundled model tariff has a review date. Once it expires, token accounting continues while dollar estimates remain unavailable until `references/tariff.json` is refreshed from the linked official model pages.

See the [contributor guide](../CONTRIBUTING.md) and
[release checks and validation status](docs/release.md).

## License

[MIT](../LICENSE), copyright 2026 Eric Burns. Independent community project;
not an official OpenAI product. Codex and model access are provided separately.
