# Claude Code release checks

## Role ladder changed since this review — re-verify before tagging

On September 8, 2026, the role ladder was simplified from seven roles (a `medium`- and a
`high`-effort variant of each paid model) to four (one role per model, each at `high`); see
[why these four roles](roles.md#why-four-roles). The live verification below predates that
change and was performed against the seven-role ladder. Its structural claims (install,
manifests, escalation gate, accounting, installer behavior) are unaffected, but the
per-role dispatch results naming `midlevel`/`medium`, `upper-midlevel`, `lower-senior`, and
`staff` describe roles that no longer exist. Re-run the live dispatch check against the
current four roles before tagging; do not treat the counts and per-role results below as
current.

On September 24, 2026 the senior role moved from Claude Opus 5 to Claude Opus 5.5, still at
`high`. Its `model: opus` alias did not change; Claude Code `2.1.282` was confirmed to serve
`claude-opus-5-5` for `--model opus`, and the tariff gained that model's rates. A live senior
dispatch on Opus 5.5 has not yet been observed, so its recorded model and effort are
unverified. The automated suite now has 65 tests.

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
- **All seven roles were dispatched and their transcripts checked.** Every one recorded the
  model and effort its definition pins, against a session default of `xhigh`:
  junior `claude-haiku-4-5-20251001` with no effort value at all (which is why that role pins
  the model only), midlevel `claude-sonnet-5`/`medium`, upper-midlevel `claude-sonnet-5`/`high`,
  lower-senior `claude-opus-5`/`medium`, senior `claude-opus-5`/`high`, staff
  `claude-fable-5-1`/`medium`, principal `claude-fable-5-1`/`high`. Subagent `effort`
  frontmatter therefore takes effect, and the ladder is what the documentation claims.
- **The Fable escalation gate holds.** Both Fable roles were sent a deliberately unrouted
  assignment — an open-ended question with no prior attempts and no bounded deliverable. Both
  returned `needs-routing-evidence` without starting an investigation, itemised what was
  missing, and named a cheaper tier for the first pass. This is the workflow's most
  cost-consequential rule and the only one whose failure is expensive by construction.
- Plugin-installed roles are addressed as `rightsize-goal:<role>`; bare names fail with
  "Agent type not found". The skill resolves the prefix at run time.
- Claude Fable 5.1 was reachable on the test account, resolving from the `fable` alias to
  `claude-fable-5-1`. **Entitlement is per account; this proves nothing about anyone
  else's.**
- The accounting helper was run end to end against the two real subagent transcripts
  produced above. It discovered both files from the agent ID alone, deduplicated the
  streaming records, recorded the exact served model identifiers and efforts, and produced
  cost figures matching an independent hand calculation to the cent fraction.
- The documented GitHub plugin install was run end to end against the published remote into an
  isolated configuration directory: marketplace add, install, and `plugin details` reporting one
  skill and seven agents.
- The installer was exercised against a temporary configuration directory for install,
  verify, idempotent rerun, conflict refusal, forced replacement with backup, and
  post-force verification.

### Automated coverage

62 tests pass locally:

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
agent, and every honest-gap path listed in [accounting](accounting.md)), and teammate
discovery (resolving `<agentName>@<teamName>` to its session transcript, not regressing the plain
subagent path, rejecting a wrong team, never mistaking an ordinary session for a teammate, and
reporting duplicates as ambiguous rather than guessing).

### First live workflow run: September 7, 2026

A real end-to-end run was executed on a disposable project: one objective, one dispatch to
`rightsize-junior-doer`, with the gate, scratch log, and ledger all exercised. The work itself
was correct — the right test added in the existing style, `greeting.py` left untouched, scope
respected — and both assertions were verified independently by the coordinator. Four defects
surfaced, all now fixed:

1. **Agent Teams changed the dispatch shape.** With `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
   set, naming a worker makes it a teammate running as its own session, whose transcript is a
   top-level `projects/<slug>/<session-id>.jsonl` rather than a file under `subagents/`. The
   returned id is `<agentName>@<teamName>`, which the original discovery logic could not
   resolve, and the team's own `config.json` records no member session id. Fixed by matching
   the `agentName`/`teamName` labels recorded inside the transcript — an exact match, not a
   heuristic. Both dispatch modes are now supported and covered by tests.
2. **The skill assumed an Opus coordinator.** It now states the requirement as capability
   rather than identity: Opus/medium and Sonnet 5/high are both good choices, Haiku is not.
3. **A specified fallback check silently verified nothing.** The dispatch offered
   `unittest discover` as a fallback for pytest-style tests, which collects zero cases and
   exits successfully — `NO TESTS RAN` reads as a pass. The skill now requires confirming that
   an acceptance check actually ran the expected number of cases, and treats a zero-case pass
   as a failed verification.
4. **A receipt imitated runner output.** The worker reported hand-written `✓ PASSED` lines for
   a check it had performed by direct invocation rather than the named runner. All seven role
   files now require the literal command and its real output, forbid composing tick marks or a
   pass summary, and require saying what was run instead when a runner is unavailable.

Measured from that run: the teammate dispatch cost **$0.0434 across 93,956 tokens and 9
requests** for a two-line change, against a measured in-process subagent floor of **$0.0095**
at the same role. Dispatch overhead, not model rate, dominates the cost of small work.

### Not covered by any automated test

- Model entitlement on any account other than the one used above.
- The quality of delegation and acceptance judgment. The escalation gate's *refusal*
  behaviour is verified above; whether the coordinator routes well across a real goal is not.
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
  confirm `claude plugin details rightsize-goal` lists one skill and four agents.
- Install from a clean source archive with `install.py` and confirm `--verify` passes.
- Start a fresh session and confirm the skill and all four roles load under both install
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
- Include the root MIT `LICENSE`, the docs, the skill helpers and references, and all four
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
