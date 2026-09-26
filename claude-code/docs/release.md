# Claude Code release checks

## 1.1.3 verification — September 26, 2026

1.1.3 reworks the worker lifecycle and planning from the omniwatch and everwatch runs' evidence:
finishing without stopping, eligibility at 30% of the context window free and not compacted,
marker-based compaction detection, matching finished workers to ready tasks by follow-on type with
the tier decided on the task's merits (plus a rare borderline exception and one-step-up reuse
within task families), garbage collection from the goal log (`workers`, `stop`, and the
`agent_stopped` event), dependencies, areas, and families on tasks, follow-on briefs, ambiguity
settled before planning, parallel planning, and milestone QA passes. The validator now reads goals
as a QA engineer or product owner would, rates issues 1 to 10, scopes follow-up rounds to fixes and
their effects, and a bundled polish round after DONE gets a narrow regression check. `SendMessage`
is off every role again. The suite (126 tests) and both strict manifest validations pass; each new
rule has a test that fails when the rule is removed.

`TaskStop` was confirmed against everwatch's transcripts: all ten calls reported "Successfully
stopped task" for an in-process teammate, and each teammate's transcript ends within seconds of
its stop. The new `drive.py` reads everwatch's existing goal file, which predates the dependency
and area fields.

Compaction is read from each host's own marker (Claude Code's `compact_boundary`, Codex's
`compacted` record), not from context size. Checked against real logs: 450 recent Claude Code
transcripts gave 5 flags, all with a genuine marker and no false ones, and no zero-usage
`<synthetic>` record was misread as the worker's context. In 117 Codex session logs, counted
compactions matched the real records exactly. An earlier size-based rule falsely flagged 62 Codex
logs, mostly forked child agents whose logs begin with their parent's larger history.

Not yet observed live: a coordinator keeping idle teammates for reuse, matching them to ready
tasks, and collecting them on the 15-minute and 30%-free rules; and compaction on a real worker.

## 1.1.2 verification — September 26, 2026

1.1.2 includes the unreleased 1.1.1 changes. Both add worker-lifecycle rules: context reporting
and three-band reuse advice from `task_usage.py finish`, a flag for assignments that alone
outgrew the 200,000-token retirement point, shutdown of unneeded teammates, `SendMessage` on
every role so a teammate can accept a shutdown, and online research tools on every role. The
suite (112 tests) and both strict manifest validations pass; the new advice and the growth flag
each have tests that fail when the behavior is removed.

Evidence from real runs: a 1.1.0-era run (omniwatch) went end to end, with workers, the
validator, and a DONE verdict, but reused one teammate for five tasks and let another reach
924,000 tokens of context. A 1.1.1 run (everwatch) gave every new area a fresh teammate with no
reuse. One of its single assignments still reached 628,000 tokens, and its one shutdown request
failed because workers had no way to reply. Both runs read the skill and helpers from a
local-folder plugin install's working tree, so they picked up repository edits mid-run.

Not yet observed live: a teammate accepting a shutdown request (headless test sessions dispatch
plain background agents rather than teammates), and the coordinator applying the reuse bands.

## 1.1.0 verification — September 25, 2026

1.1.0 adds self-driving persistence: a plugin Stop hook (`hooks/hooks.json`, running
`drive.py hook`) and the read-only `rightsize-validator` role. The suite and both strict
manifest validations pass. An isolated `CLAUDE_CONFIG_DIR` install reported one skill, five
agents, and one Stop hook.

The hook was exercised live on Claude Code `2.1.282`, loading the working tree with
`--plugin-dir` and Haiku as the session model, in disposable projects with a goal pre-bound
to a known `--session-id`:

- With an unvalidated goal and all tools disabled, so no progress could be recorded, the
  session transcript shows three "Stop hook feedback" continuations carrying the goal, the
  unmet items, and the open task, followed by an unblocked stop: the no-progress release.
  The model's final reply referred to the task it only learned about from the hook.
- With a fresh DONE verdict recorded, the session finished in one turn.
- A different session in the same directory finished in one turn and left the bound goal's
  hook counters untouched.

Not yet observed live: a complete coordinator-driven run that dispatches workers, then the
validator, and ends on its DONE verdict; and the hook under Agent Teams.

## 1.0.1 verification — September 24, 2026

The plugin and marketplace manifests both declare 1.0.1. The local suite and
both strict manifest validations pass. An isolated `CLAUDE_CONFIG_DIR` install
reported one skill and four agents. A live `/goal Use the rightsize-goal skill ...`
run was attempted in a disposable project, but the isolated configuration was
not logged in; Claude Code returned `Not logged in · Please run /login` before
the workflow started. Skill invocation through that wording remains unverified
in a live authenticated session.

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
- Run `claude plugin validate --strict .` and `claude plugin validate --strict claude-code/`
  (CI runs these too).
- Observe the complete CI matrix passing, including symlink coverage on a host that permits
  symlinks. Exercise the public shell and PowerShell entry points.
- Install the plugin from the published GitHub source, not only from a local path, and
  confirm `claude plugin details rightsize-goal` lists one skill, five agents, and one Stop
  hook.
- Install from a clean source archive with `install.py` and confirm `--verify` passes.
- Start a fresh session and confirm the skill and all five roles load under both install
  methods, including the `rightsize-goal:` prefix under the plugin.
- Run a small goal in a disposable project. Confirm suitable delegation, verified
  acceptance, a saved log and gate, and honest usage results — available, or an explained
  gap.
- Test a requested pause and a resumed run using the same goal. Confirm the plugin hook
  holds an unvalidated goal open, releases on a fresh DONE, a pause, or a reached limit, and
  stands down under `/goal`. Check `/goal` set, held, and self-cleared.
- Check model availability on the intended account. Never infer it from API prices.
- Recheck tariff expiry and the linked rates, including the cache-write multipliers. Change
  the tariff version when rates change; do not rewrite historical ledger snapshots.
- Confirm `role_models` in the tariff still matches every role file's `model` alias.
- Ensure no credentials, local logs, databases, or private backups enter the release.
- Include the root MIT `LICENSE`, the docs, the skill helpers and references, the hook, and
  all five roles in any downloadable bundle.
- Update `CHANGELOG.md` and bump `version` in both `claude-code/.claude-plugin/plugin.json`
  and the root `.claude-plugin/marketplace.json`. Every change that should reach users needs
  a new version: existing installs compare `plugin.json`'s `version` and ignore new commits
  under an unchanged one. Publish only the tested commit, then tag it with
  `claude plugin tag --push` from `claude-code/`, which creates `rightsize-goal--v<version>`.

## Distribution scope

Supported installation currently covers the plugin marketplace, clone plus copy, extracted
source archive plus copy, and contributor symlinks. Plugin uninstall is a single command;
manual uninstall is documented file removal. A PyPI package, a remote bootstrap command,
and an automated uninstaller for the manual method are future options, not artifacts in
this tree.

Keep this checklist host-specific. Do not make claims about Codex behavior based on Claude
Code results, or the reverse.
