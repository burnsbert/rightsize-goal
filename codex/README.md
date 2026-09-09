# Rightsize Goal for Codex

Rightsize Goal helps Codex pursue substantial objectives using a small engineering
team. A coordinator assigns bounded work to a suitable model tier, verifies results,
and records usage and lessons. It seeks lower total cost including rework; savings
are not guaranteed. It is useful for multi-step implementation and investigation;
trivial edits usually do not warrant the coordination overhead.

This package ships one skill, six custom agents, two standard-library Python
helpers, and installers. It uses your existing Codex account and permissions.

## Requirements

- A local Codex host with custom subagents enabled. Native goal tools are required
  for automatic continuation, but current-session work can use saved scratch state.
- Python 3.11 or newer.
- Access to the model names configured by the six included roles.
- For optional symlinks on Windows: Developer Mode or appropriate privileges.

## Install

Clone the repository, then run the installer from the clone:

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
and the six agent definitions to `$CODEX_HOME/agents` (normally `~/.codex/agents`).
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

Keep dot-prefixed folders when extracting an archive. All methods use the same
installer. A plugin, PyPI/pipx package, and remote bootstrap command have not been
shipped; earlier suggestions for those were design options, not working commands.

See [installation and maintenance](docs/install.md) for custom destinations,
legacy mode, conflicts, backups, removal, and troubleshooting. Verification checks
files, not account model entitlement or live goal/subagent behavior.

## Run

Select `gpt-5.6-sol` with medium reasoning for the root Codex session, then invoke:

```text
Use $rightsize-goal to add regression tests for this project's configuration parser.
Acceptance: cover invalid input and defaults; all existing tests pass.
Scope: tests only; do not change production code.
```

If your host supports `/goal`, prefix the request with it for native continuation.
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
| Upper-midlevel | Terra/high | Moderate implementation and research requiring bounded judgment |
| Senior engineer | Sol/medium | Hard implementation, research, and brainstorming |
| Staff engineer | Sol/high | Strongest pre-Astra first pass for the most complex and challenging work |
| Principal engineer | Astra/medium | Bounded unresolved work after documented Sol struggle |

Known moderate work goes directly to Terra rather than using Luna as a cheap trial.
The most complex work goes directly to Sol/high when Astra escalation is a credible
risk. Astra has one medium-effort principal engineer role so the escalation receives
enough reasoning budget without an Astra/low retry.

Project activity is logged under `.rightsize-goal/` in the target project. Cross-project routing history and task usage are stored under `$CODEX_HOME/rightsize-goal/`. The cost figures are standard-rate API-equivalent estimates from a versioned tariff; they are useful for routing comparisons but are not an authoritative subscription bill.

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
