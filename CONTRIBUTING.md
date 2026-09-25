# Contributing

Rightsize Goal is licensed under [MIT](LICENSE). Contributions are welcome under
the same license. Include only material you have the right to contribute; retain
required third-party attribution if introducing outside code or assets.

Keep host implementations separate. `codex/` owns Codex runtime integration and
`claude-code/` owns Claude Code integration; each documents its own tools, models,
installation, and limitations. Do not assume one host exposes the other's APIs, and do not
import across the two directories — a Claude Code plugin is cached on install, so a path
that leaves `claude-code/` breaks after installation. `goal_gate.py` is host-independent and
is therefore duplicated in both packages rather than shared; keep the copies in step.
The Codex plugin also keeps a packaged skill copy under `codex/skills/`; keep it in sync
with `codex/.agents/skills/`, which is the source used by the manual installer.

Use Python 3.11+; the helpers in both packages use only the standard library. From the root:

```sh
python3 -m unittest discover -s codex/tests -p "test_*.py"
python3 -m unittest discover -s claude-code/tests -p "test_*.py"
```

For Claude Code packaging changes, also run:

```sh
claude plugin validate --strict .
claude plugin validate --strict claude-code/
```

Any Claude Code change meant to reach existing plugin installs must bump `version` in
`claude-code/.claude-plugin/plugin.json` (and the root `.claude-plugin/marketplace.json`).
Installs only update when that version changes; new commits under the same version are
never delivered.

Use temporary destination directories for installer development, and an isolated
`CLAUDE_CONFIG_DIR` or `CODEX_HOME` for plugin and runtime experiments. Do not test
failure or rollback logic against your real configuration. For deliberate local workflow
development, see the symlink instructions for
[Codex](codex/docs/install.md) and [Claude Code](claude-code/docs/install.md#contributor-symlinks).

Changes to routing must preserve explicit model and effort choices, evidence-backed
escalation, acceptance checks, and honest unavailable usage. Changing a role's model or
effort means updating that host's role file, its routing table in `SKILL.md`, and its
tariff together; the packaged tests check that those agree. Add regression tests for
consequential behavior changes. Document user-visible flags and compatibility changes in
the same pull request. Never commit session transcripts, credentials, usage databases,
project scratch files, or private configuration backups.

Prices and model identifiers are facts, not estimates. When updating a tariff, cite the
official pricing page you read, change the tariff `version`, and leave historical ledger
snapshots alone.

PRs should explain the problem, the resulting behavior, the checks run, and the
limitations. See the release checklist for
[Codex](codex/docs/release.md) and [Claude Code](claude-code/docs/release.md) before
tagging a release.
