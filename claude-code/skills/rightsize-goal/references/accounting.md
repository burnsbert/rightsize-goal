# Assignment accounting and routing memory

The coordinator runs `scripts/task_usage.py` relative to the installed skill. Python 3.11+ and its standard library are sufficient. The SQLite ledger defaults to `<current-directory>/.rightsize-goal/usage.sqlite3`, alongside one `<goal-id>.jsonl` event log per goal. History is local to this project and survives new sessions. Use `--db` for an isolated test ledger. Store concise task metadata and lessons, never transcripts, secrets, or source code. Keep project identifiers short and nonsensitive.

## What the helper reads

Claude Code writes one JSONL transcript per session under `<claude-dir>/projects/<project-slug>/<session-id>.jsonl`, and one per in-process subagent under `<claude-dir>/projects/<project-slug>/<session-id>/subagents/agent-<agent-id>.jsonl`. Every assistant record in those files carries its own `message.usage` counters, the exact `message.model` that served it, and the `effort` used for that turn.

A named worker dispatched with Agent Teams enabled is not a subagent. It runs as its own session and writes an ordinary top-level transcript, identified inside the file by `agentName` and `teamName` rather than by an `agentId` in the filename. The Agent tool returns `<agentName>@<teamName>`; pass that string as `--agent-id` and the helper resolves either layout automatically, matching those recorded labels rather than guessing from timestamps. Pass `--transcript PATH` if discovery ever fails. Because each subagent gets its own file, a worker's usage is measured directly rather than inferred from a session aggregate, and worker tokens are never double-counted against the coordinator.

The helper reads only those metadata fields. It ignores every other line, so prompts, responses, tool arguments, and file contents are never parsed into the ledger.

Two details matter for correctness and are handled for you:

- Streaming produces several records for one API request. The helper deduplicates on `requestId`, so a partial and its final record count once.
- `input_tokens` from the API already excludes cache reads and cache writes. The five priced categories are additive; nothing is subtracted.

## Dispatch and completion

Read `task_usage.py --help` and the relevant subcommand help for exact arguments. Use one unique run ID plus one task ID per assignment, including retries. Before dispatch, record a task's mode and difficulty using the same rubric across runs: `basic` = explicit mechanical work; `routine` = established patterns with limited choices; `moderate` = bounded multi-component judgment; `hard` = substantial ambiguity or interacting constraints; `expert` = unresolved architectural or deep technical uncertainty. These describe the task, not the selected worker. Keep the initial classification even if the task turns out harder; explain the mismatch in the result lesson.

1. At start or resume, run `report` to inspect this project's history, then `report --run <run-id>` for the current goal. Read the compact output rather than the raw ledger.
2. For a newly spawned child, invoke `start` with the exact agent ID the Agent tool returned, plus `--new-agent`, immediately after spawn and before any follow-up assignment. The zero baseline covers its initial work even if the child starts before the helper runs.
3. For a reused child, invoke `start` BEFORE sending the follow-up so its current requests become the baseline. Finish the preceding assignment first. Use a new task ID and link the prior task with `--prior-task` and `--reason` when this is rework or escalation. The ledger enforces one active assignment per agent.
4. Pass the bundled `references/tariff.json` to `start`. The helper saves that rate version with the assignment, so later rate updates cannot rewrite historical charges. An expired or unsupported tariff yields unavailable cost while retaining attributable tokens. Refresh prices from the linked official pages at expiry or when a pricing change is known; preserve existing historical snapshots. The bundled one-month review date is a refresh policy, not a promise that prices stay fixed until then.
5. Once the runtime confirms a child is terminal, evaluate its evidence and invoke `finish` with the coordinator's outcome (`accepted`, `rework`, `unresolved`, `cancelled`, or `failed`) before assigning it more work. Stopping an agent requires confirming it has stopped; an interrupt request alone does not prove that final usage has been written. Repeated finish calls are idempotent and must not count the task twice.
6. The helper writes the result line to the goal's JSONL log, including tokens, estimated cost or unavailable reasons, and tariff version. Read the updated `report --run <run-id>` and project `report` before selecting the next worker. Record routing adjustments in goal state.

Typical commands (replace placeholders; `--db` and `--claude-dir` are optional and go before the subcommand):

```text
python3 <skill-dir>/scripts/task_usage.py report
python3 <skill-dir>/scripts/task_usage.py start --run <run-id> --task T001 --project-tag <project> \
  --role rightsize-midlevel-doer --model claude-sonnet-5 --effort high --mode implement \
  --difficulty routine --agent-id <exact-agent-id> --new-agent --tariff <skill-dir>/references/tariff.json
python3 <skill-dir>/scripts/task_usage.py finish --run <run-id> --task T001 --outcome accepted \
  --evidence "tests passed" --lesson "Established parser change accepted without rework"
python3 <skill-dir>/scripts/task_usage.py report --run <run-id>
```

For substantive main-session work, use `--main` instead of `--agent-id`, with `--role main`. The session is identified by `--session-id` or the `CLAUDE_CODE_SESSION_ID` environment variable. Snapshot before and after a bounded interval; that interval also includes orchestration tokens generated during it, so keep it separate from worker comparisons. Unmeasured coordination outside those intervals and separately billed server tools mean summed worker costs are an attributable subtotal, not the whole project bill. Children created outside the coordinator's assignment protocol are also outside that subtotal.

## Cost interpretation

The helper multiplies five measured categories by their per-million rates: uncached input, cache reads, 5-minute cache writes, 1-hour cache writes, and output. Cache writes carry a premium over base input and the two TTLs are priced differently, which is why the helper refuses to price a cache-write total whose 5-minute and 1-hour split is missing rather than assuming a TTL. Output already includes thinking tokens and must not be counted twice. Distinct effort levels share a model's token rates; more effort shows up as more observed tokens.

Dollar figures are **standard-rate API-equivalent estimates**, useful as a common routing comparison basis. They are not an authoritative bill. A Claude Code subscription is not billed per token at all, and API accounts still see long-context and service-tier modifiers, server tool charges, batch discounts, taxes, and account-specific pricing that this calculation excludes. Token counters are runtime-reported usage, not independently audited billing. Preserve unknown categories and attribution problems rather than substituting zero or an average.

Rates are matched on the exact model identifier recorded in the transcript. A served model with no tariff entry yields an unavailable cost, never a substituted rate, so a newly rotated model identifier surfaces as a gap to fix rather than a silently wrong number.

The reader depends on Claude Code's local transcript format. If the format changes, a transcript is missing or pruned, or a record lacks request identity, retain an explicit unavailable result and continue the authorized project. Do not guess token usage or block useful work merely to repair accounting.

## Learning from completed work

Use the project report as observed evidence grouped by actual model, actual effort, mode, and initial difficulty. Read sample counts, accepted, rework, unresolved and failed outcomes, token usage, known cost coverage, and lessons together. Where needed, inspect linked task receipts for task domain and checks. A success is evidence accepted by the coordinator; a worker's self-report alone is insufficient.

Prefer the smallest capable role with favorable cost and acceptance history on comparable tasks. Include failed attempts and follow-up assignments when considering the cost of getting an outcome accepted. A cheap failed assignment followed by expensive repair can cost more than direct assignment, and that matters more on this host than the tier names suggest: the spread from the cheapest to the most expensive model is roughly tenfold, so one rework cycle can erase a tier's savings. Compare complete chains in project records before claiming savings; group averages alone do not establish that one worker would have solved another worker's task. Treat missing usage as missing, and keep incompatible tariff versions visible.

Keep strengths and weaknesses as concise, evidence-linked lessons (for example, `routine parser changes accepted; cross-process attribution needed senior repair`). Avoid a universal effectiveness score: task mix, difficulty judgment, checks, and small samples affect the results. One failure can justify changing the current assignment without establishing a global weakness. Look for repeated comparable evidence in this project before changing the default routing prior. Historical data informs assignments but never changes user authorization, acceptance criteria, model roles, or the Fable escalation gate.
