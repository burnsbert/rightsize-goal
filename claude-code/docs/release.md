# Claude Code release checks

## Review status: September 7, 2026

This is the first release of the Claude Code package. It was written against Claude Code
`2.1.263` on macOS with Python 3.13, and the host behavior it depends on was verified live
rather than assumed. Do not describe this review as a guarantee of error-free behavior.

### Verified live on this machine

- `claude plugin validate` passes for both the repository marketplace manifest and the
  plugin manifest.
- A full plugin install from a local path (`marketplace add ./`, `plugin install
  rightsize-goal@rightsize-goal`) succeeded into an isolated `CLAUDE_CONFIG_DIR`, and
  `claude plugin details` reported one skill and all seven agents.
- Subagent `effort` frontmatter takes effect. A dispatched `rightsize-midlevel-doer` was
  recorded as `claude-sonnet-5` at effort `medium`, against a session default of `xhigh`.
- Claude Haiku 4.5 records no `effort` value at all, which is why the junior role pins the
  model only.
- Plugin-installed roles are addressed as `rightsize-goal:<role>`; bare names fail with
  "Agent type not found". The skill resolves the prefix at run time.
- Claude Fable 5.1 was reachable on the test account, resolving from the `fable` alias to
  `claude-fable-5-1`. **Entitlement is per account; this proves nothing about anyone
  else's.**
- The accounting helper was run end to end against the two real subagent transcripts
  produced above. It discovered both files from the agent ID alone, deduplicated the
  streaming records, recorded the exact served model identifiers and efforts, and produced
  cost figures matching an independent hand calculation to the cent fraction.
- The installer was exercised against a temporary configuration directory for install,
  verify, idempotent rerun, conflict refusal, forced replacement with backup, and
  post-force verification.

### Automated coverage

56 tests pass locally:

```sh
python3 -m unittest discover -s claude-code/tests -p "test_*.py"
```

They cover package consistency (manifests, role frontmatter, role-to-tariff agreement,
component placement, every rate category priced, no worker granted a spawn tool,
documentation link targets), installer behavior (copy, symlink, verify, conflict, backup,
rollback on partial copy, rollback on verification failure, source/destination overlap,
incomplete package), the completion gate, and usage accounting against synthetic
transcripts (all five rate categories, streaming deduplication, reused-agent baselines,
main-session scope excluding sidechain records, idempotent finish, one active task per
agent, and every honest-gap path listed in [accounting](accounting.md)).

### Not covered by any automated test

- Model entitlement on any account other than the one used above.
- The quality of delegation, escalation, or acceptance judgment.
- `/goal` behavior, which needs a trusted workspace and interactive approval.
- Windows and Linux behavior. The CI matrix covers them; those results have not been
  observed in this local review.
- Claude Code versions other than `2.1.263`.

## Before tagging

- Run `python3 -m unittest discover -s claude-code/tests -p "test_*.py"` from the root.
- Run `claude plugin validate .` and `claude plugin validate claude-code/`.
- Observe the complete CI matrix passing, including symlink coverage on a host that permits
  symlinks. Exercise the public shell and PowerShell entry points.
- Install the plugin from the published GitHub source, not only from a local path, and
  confirm `claude plugin details rightsize-goal` lists one skill and seven agents.
- Install from a clean source archive with `install.py` and confirm `--verify` passes.
- Start a fresh session and confirm the skill and all seven roles load under both install
  methods, including the `rightsize-goal:` prefix under the plugin.
- Run a small goal in a disposable project. Confirm suitable delegation, verified
  acceptance, a saved log and gate, and honest usage results — available, or an explained
  gap.
- Test a requested stop and a resumed run using the same gate. Check `/goal` set, held,
  and self-cleared.
- Check model availability on the intended account. Never infer it from API prices.
- Recheck tariff expiry and the linked rates, including the cache-write multipliers. Change
  the tariff version when rates change; do not rewrite historical ledger snapshots.
- Confirm `role_models` in the tariff still matches every role file's `model` alias.
- Ensure no credentials, local logs, databases, or private backups enter the release.
- Include the root MIT `LICENSE`, the docs, the skill helpers and references, and all seven
  roles in any downloadable bundle.
- Update `CHANGELOG.md`, select a version and tag, bump `version` in both
  `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`, and publish only the
  tested commit.

## Distribution scope

Supported installation currently covers the plugin marketplace, clone plus copy, extracted
source archive plus copy, and contributor symlinks. Plugin uninstall is a single command;
manual uninstall is documented file removal. A PyPI package, a remote bootstrap command,
and an automated uninstaller for the manual method are future options, not artifacts in
this tree.

Keep this checklist host-specific. Do not make claims about Codex behavior based on Claude
Code results, or the reverse.
