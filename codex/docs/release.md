# Codex release checks

## 1.1.6 checks: September 30, 2026

All 65 Codex tests pass. The two skill copies are identical and pass skill validation.
An isolated Codex app-server probe discovers the copied skill without a model turn.
This release changes test-planning instructions only; it has not been exercised in a
live goal. The current repository-linked skill installation reads the updated source.

## 1.1.5 checks: September 29, 2026

All 65 Codex tests pass on macOS with Python 3.13.15. The two skill copies are
identical. With Codex CLI 0.159.0, an isolated app-server probe discovers the
freshly installed skill, and an isolated marketplace install loads plugin 1.1.5.
No user configuration was changed by these checks.

The repository coordinator config, senior role, and staff role select
`gpt-6.1-sol` at medium, medium, and high reasoning respectively. Model names,
supported reasoning efforts, and all bundled standard rates were checked against
the official [model docs](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
and [API pricing](https://developers.openai.com/api/docs/pricing). A synthetic
accounting check with 1M input tokens (800K cached) and 100K output tokens prices
GPT-6.1 Sol at $1.48 and retained GPT-6 Sol at $1.56; reasoning included in output
is not counted twice. These checks cover configuration and accounting, not live
model entitlement, delegation quality, or native goal continuation. No live goal
was run for this model update.

## 1.1.3 checks: September 26, 2026

All 65 Codex tests pass, the Codex plugin validator passes, and the two skill copies are
identical. 1.1.3 brings the worker lifecycle and planning changes shared with Claude Code:
eligibility at 30% of the reported context window free and not compacted, compaction read from
Codex's own `compacted` records (a forked child's copied history is not counted), `workers` and
`stop` commands with an `agent_stopped` log event, unique thread IDs, matching finished agents to
ready tasks by follow-on type with the role decided on the task's merits, closing idle agents after
15 minutes (early when the concurrency limit blocks a dispatch), ambiguity settled before planning,
parallel planning, task families, and milestone QA passes. Compaction detection was checked against
117 real Codex session logs: counted compactions matched the real records exactly. No live
coordinator run under 1.1.3 has been observed yet.

## September 25, 2026 checks

All 60 Codex tests passed after the permission configuration changes. After the
worker cleanup instruction changes, skill validation and all seven package tests
passed. The package checks cover matching permission settings and relative role
paths in the repository config, as well as consistency between the two skill copies.

The five worker roles and repository coordinator config now default to full access,
no routine command approval prompts, and live web search. Cleanup uses a supported
close operation when available and otherwise records retirement separately from
actual runtime status. No live worker was spawned to verify effective permissions,
online retrieval, or cleanup behavior during this review. Those checks remain in
the release checklist below. Claude Code tests were not rerun in this review.

## Earlier review and verification history

The source installer, helper scripts, agent TOMLs, skill instructions, and public
documentation were reviewed. Verified defects fixed during that review:

- Partial copy failures and failed final verification now trigger rollback.
- Switching symlinks to copies requires explicit replacement and actually converts.
- Overlapping source/destination paths are rejected before replacement.
- Normal installs leave global configuration unchanged; explicit legacy mode
  validates the original TOML and checks semantic preservation of unrelated data.
- Conflicting legacy registrations require force and receive a config backup.
- Missing model/effort labels no longer inherit attribution from an earlier turn.
- Invalid state encodings and boolean gate versions are rejected.
- Python interpreter and local-time instructions work across supported OS families.
- Routing calibration sends known moderate work directly to Sol/medium, uses the Sol/high
  staff engineer as the strongest first pass for the most complex work, and uses
  one Astra/medium principal engineer escalation without a low-effort retry.
- Upgrades retire the former lower-senior and generic Astra role filenames safely;
  older staff/principal definitions are backed up and replaced when forced.

The September 24 marketplace verification used macOS, Python 3.13, and
`codex-cli 0.156.1`. Automated tests exercise package consistency, clean copy
installation and verification, backup/conflict/rollback behavior, timing gates,
platform installer entry points, and synthetic telemetry accounting. Skill metadata
validation also passes. The isolated runtime probe confirmed that Codex discovers
the freshly copied skill at its expected path without starting a model turn:

```text
python codex/scripts/check_runtime.py
```

This optional probe needs Codex CLI on PATH. It installs into a temporary directory,
starts a temporary stdio app server with a separate Codex home, requests only skill
discovery, then stops that process and removes its temporary directory.

The local suite count and result should be refreshed immediately before release.
On September 24, all 50 Codex tests and 65 Claude Code tests passed locally.
The Codex marketplace installed the Codex skill and helper scripts in an isolated
`CODEX_HOME`, while an isolated Claude Code install still reported one skill and
four agents. Both strict Claude manifest validations passed.
The new GitHub Actions matrix covers Windows, macOS, and Linux with Python 3.11
and 3.13; its remote results have not been observed in this local review.

No automated test proves model entitlement, quality of delegation, or native
goal continuation. Complete the live smoke checks below before calling a tagged
release fully validated. Do not describe this source review as a guarantee of
error-free behavior.

## Before tagging

- Run `python -m unittest discover -s codex/tests -p "test_*.py"` from the root.
- Observe the complete CI matrix passing, including symlink coverage on a host
  that permits symlinks. Exercise the public shell and PowerShell entry points.
- Install from a clean source archive, including dot-prefixed payload folders.
- Start a fresh Codex session and confirm the skill and all five named roles load;
  confirm retired upper-midlevel, lower-senior, and generic-Astra roles no longer appear
  after upgrade.
- Run a small goal in a disposable project. Confirm suitable delegation, verified
  acceptance, a saved log/gate, and honest usage results (available or explained gaps).
- In that disposable project, confirm a worker can fetch an online source and write
  an assigned file with the intended effective permissions. Check parent permission
  overrides. Verify cleanup with the host's available tools, including retirement
  without a close operation and accurate reporting when concurrency capacity is full.
- Test a requested stop and a resumed run using the same gate. On hosts exposing
  native goals, check native completion as well as local gate completion.
- Check model availability on the intended account; never infer it from API prices.
- Recheck tariff expiry and linked rates. Change the tariff version when rates change;
  do not rewrite historical ledger snapshots.
- Ensure no credentials, local logs, databases, or private backups enter the release.
- Include the root MIT `LICENSE`, docs, skill helpers/references, and all five roles
  in any downloadable bundle. Root source archives already carry these files.
- Update `CHANGELOG.md`, select a version/tag, and publish only the tested commit.

## Distribution scope

Supported instructions cover clone/copy, extracted source archive/copy,
contributor symlinks, and a Codex marketplace plugin for the skill alone.
The five custom agents still require the installer. Uninstall is documented
manual removal. A PyPI/pipx package, remote bootstrap, automated updater, and
automated uninstaller are not release artifacts in this tree.

Keep this checklist host-specific when adding Claude Code support. Do not make
claims about Claude Code testing based on Codex results.
