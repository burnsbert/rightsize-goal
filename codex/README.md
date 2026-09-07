# Rightsize Goal for Codex

## Requirements

- Codex with custom subagents and goal tools available.
- Python 3.11 or newer.
- Access to the model names configured by the seven included roles.
- For symlinks on Windows: Developer Mode or an elevated terminal. A copy install is available when symlinks are unavailable.

## Install

Clone the repository, then run the installer from the clone:

```powershell
git clone https://github.com/burnsbert/rightsize-goal.git E:\rightsize-goal
cd E:\rightsize-goal\codex
.\install.ps1
```

On macOS or Linux:

```sh
git clone https://github.com/burnsbert/rightsize-goal.git ~/rightsize-goal
cd ~/rightsize-goal/codex
./install.sh
```

The default installation creates global symlinks for the skill under `~/.agents/skills/rightsize-goal` and the seven agent definitions under `$CODEX_HOME/agents` (normally `~/.codex/agents`). It adds only the corresponding `[agents.rightsize-*]` registrations to `$CODEX_HOME/config.toml`, after backing up that file when it changes.

If Windows cannot create symlinks, use:

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

## Run

Select `gpt-5.6-sol` with medium reasoning for the root Codex session, then invoke:

```text
/goal Use $rightsize-goal --minimum-time="30 minutes" --maximum-time="3 hours" to accomplish <objective>. Acceptance: <observable checks>.
```

The duration options belong to Rightsize Goal. The workflow uses native goal tools underneath when they are available. The minimum is a completion condition; the maximum stops new dispatches at checkpoints and produces an incomplete handoff if acceptance remains unmet.

The coordinator routes work among:

| Role | Configuration | Intended scope |
| --- | --- | --- |
| Junior | Luna/high | Very basic explicit work |
| Lower-midlevel | Luna/xhigh | Routine bounded work using established patterns |
| Upper-midlevel | Terra/high | Moderately complex bounded work |
| Lower-senior | Sol/medium | Hard implementation, research, and brainstorming |
| Senior | Sol/high | Deep interacting constraints and difficult reasoning |
| Staff | Astra/low | Bounded expert work after documented Sol struggle |
| Principal | Astra/medium | Hardest bounded work after documented Sol struggle |

Project activity is logged under `.rightsize-goal/` in the target project. Cross-project routing history and task usage are stored under `$CODEX_HOME/rightsize-goal/`. The cost figures are standard-rate API-equivalent estimates from a versioned tariff; they are useful for routing comparisons but are not an authoritative subscription bill.

## Update and test

For symlink installs, pulling this repository updates the installed files immediately. Start a fresh Codex session after pulling. Copy installs require rerunning the installer with the force option.

Run all deterministic tests from `codex/`:

```sh
python -m unittest discover -s tests -p "test_*.py"
```

The bundled model tariff has a review date. Once it expires, token accounting continues while dollar estimates remain unavailable until `references/tariff.json` is refreshed from the linked official model pages.
