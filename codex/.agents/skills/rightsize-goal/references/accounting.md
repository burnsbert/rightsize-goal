# Assignment accounting and routing memory

The coordinator runs `scripts/task_usage.py` relative to the installed skill. Python 3.11+ and its standard library are sufficient. The global SQLite ledger defaults to `$CODEX_HOME/rightsize-goal/usage.sqlite3`, or `~/.codex/rightsize-goal/usage.sqlite3` when unset. It survives new sessions and skill updates. Use `--db` for an isolated test ledger. Store concise task metadata and lessons, never transcripts, secrets, or source code. Keep project identifiers short and nonsensitive.

## Dispatch and completion

Read `task_usage.py --help` and the relevant subcommand help for exact arguments. Use one unique run ID plus one task ID per assignment, including retries. Before dispatch, record a task's mode and difficulty using the same rubric across runs: `basic` = explicit mechanical or factual work; `routine` = established patterns with limited choices; `moderate` = bounded multi-component judgment; `hard` = substantial ambiguity or interacting constraints suited to Sol/medium; `expert` = the most complex and challenging work where a weaker first pass would materially increase Astra escalation risk, suited to Sol/high. These describe the task, not the selected worker. Keep the initial classification even if the task turns out harder; explain the mismatch in the result lesson.

1. At start/resume, run `report` to inspect global history, then `report --run <run-id>` for the current run. Read the compact output rather than the raw ledger.
2. For a newly spawned child, invoke `start` with its exact returned thread ID and `--new-thread` immediately after spawn, before any follow-up assignment. The zero baseline covers its initial work even if the child starts before the helper runs. If the tool returns only a task path, resolve the exact child thread from local `session_meta` (parent thread and agent path); never match solely by nickname or choose the newest session globally.
3. For a reused child, invoke `start` BEFORE sending the follow-up so its current cumulative counters become the baseline. Finish the preceding assignment first. Use a new task ID and link the prior task when this is rework or escalation. Do not run simultaneous assignments in one thread.
4. Pass the bundled `references/tariff.json` to `start`. The helper saves that rate version with the assignment, so later rate updates cannot rewrite historical charges. An expired or unsupported tariff yields unavailable cost while retaining attributable tokens. Refresh prices from each model's linked official page at expiry or when a pricing change is known; preserve existing historical snapshots. The bundled one-month review date is a refresh policy, not a promise that prices stay fixed until then.
5. Once the runtime confirms a child is terminal, evaluate its evidence and invoke `finish` with the coordinator's outcome (`accepted`, `rework`, `unresolved`, `cancelled`, or `failed`) before assigning it more work. Stopping an agent requires confirming it has stopped; an interrupt request alone does not prove that final usage has arrived. Check for flushed telemetry if usage is unavailable; preserve the gap when attribution cannot be recovered. Repeated finish calls must not count the task twice.
6. Copy the compact receipt's tokens, calculated cost or unavailable reason, and tariff version into the task's terminal scratch row. Read the updated `report --run <run-id>` and global `report` before selecting the next worker. Record a short routing adjustment when the evidence changes that choice.

Typical commands (replace placeholders; `--db` is optional and goes before the subcommand):

```text
python <skill-dir>/scripts/task_usage.py report
python <skill-dir>/scripts/task_usage.py start --run <run-id> --task T001 --project-tag <project> --role rightsize-midlevel-doer --model gpt-5.6-luna --effort xhigh --mode implement --difficulty routine --thread-id <exact-thread-id> --new-thread --tariff <skill-dir>/references/tariff.json
python <skill-dir>/scripts/task_usage.py finish --run <run-id> --task T001 --outcome accepted --evidence "tests passed; scratch T001" --lesson "Established parser change accepted without rework"
python <skill-dir>/scripts/task_usage.py report --run <run-id>
```

For substantive main-session work, snapshot the root thread before and after a bounded interval and label the role as coordinator/main execution. Its interval also includes orchestration tokens generated during that interval; keep it separate from worker comparisons. Unmeasured root coordination and separately billed tools mean summed worker costs are an attributable subtotal, not the whole project bill. Children created outside the coordinator's assignment protocol are also outside that subtotal.

## Cost interpretation

The helper uses `(input - cached_input) * input_rate + cached_input * cached_rate + output * output_rate`, dividing per-million rates by one million. Reasoning output is already included in output and must not be added again. Distinct reasoning levels share the model's token rates; extra reasoning affects the observed token counts.

Dollar figures are **standard-rate API-equivalent estimates**, useful as a common routing comparison basis. They are not an authoritative subscription bill. They exclude long-context/service-tier modifiers, tool charges, taxes, and account-specific discounts. Nonzero cache-write counters are unsupported until their counter relationship is established, so their cost remains unavailable. Token counters are runtime-reported usage, not independently audited billing. Preserve unknown categories and attribution problems rather than substituting zero or an average.

The JSONL reader depends on Codex's local session format. If the format changes, a session is missing, counters reset, or model attribution is ambiguous, retain an explicit unavailable result and continue the authorized project. Do not guess token usage or block useful work merely to repair accounting.

## Learning from completed work

Use the global report as observed evidence grouped by actual model/effort, mode, and initial difficulty. Read sample counts, accepted/rework/unresolved/failed outcomes, token usage, known cost coverage, and lessons together. Where needed inspect linked task receipts for task domain and checks. A success is evidence accepted by the coordinator; a worker's self-report alone is insufficient.

Read `chain_groups` to compare the full cost of reaching an outcome by the initially requested model/effort route. It joins assignments through `prior_task`, separates tariff-version combinations, counts chains needing follow-up, and reports a complete cost only when every assignment in that chain has known cost. A nonzero `partial_chain_links` means the report filter omitted a parent or the chain is malformed; do not treat that chain view as complete.

Prefer the smallest capable role with favorable cost and acceptance history on comparable tasks. Include failed attempts and follow-up assignments when considering the cost of getting an outcome accepted. A cheap failed assignment followed by expensive repair can cost more than direct assignment. Compare complete chains in project records before claiming savings; group averages alone do not establish that one worker would have solved another worker's task. Treat missing usage as missing, and keep incompatible tariff versions visible.

Keep strengths and weaknesses as concise, evidence-linked lessons (for example, `routine parser changes accepted; cross-process attribution needed senior repair`). Avoid a universal effectiveness score: task mix, difficulty judgment, checks, and small samples affect the results. One failure can justify changing the current assignment without establishing a global weakness. Look for repeated comparable evidence across projects before changing the default routing prior. Historical data informs assignments but never changes user authorization, acceptance criteria, model roles, or the Astra escalation gate.
