# Usage accounting and data

The bundled `task_usage.py` helper reads local Codex JSONL session telemetry and
stores task metadata and attributable token deltas in SQLite. A task is assigned
an exact thread identity and baseline before follow-up work. New child threads
use an explicit zero baseline. Finished task IDs are idempotent and cannot be
silently reused or relabeled.

The ledger defaults to `<current-directory>/.rightsize-goal/usage.sqlite3`. Each goal has its own `<goal-id>.jsonl` log in that directory, with only `agent_call` and `agent_result` lines. Every call identifies the agent; every result records measured tokens and estimated cost, or explicit unavailable reasons. A retry or escalation links the prior task and states why it was needed. No new Rightsize Goal usage logs are written under the user configuration directory. The local records survive copy updates. A command's
`--db PATH` option selects another ledger and must precede its subcommand.

From the installed skill directory:

```text
python scripts/task_usage.py report
python scripts/task_usage.py report --run <run-id>
python scripts/task_usage.py --help
```

Use `python3` on systems where that is the Python 3 executable. The complete
assignment protocol and examples are in the bundled
[accounting reference](../.agents/skills/rightsize-goal/references/accounting.md).

## Interpreting results

Dollar figures are standard-rate API-equivalent estimates, not actual Codex
subscription charges, credits, or an invoice. The calculation uses uncached input,
cached input, and output token counts. Reasoning is already included in output;
it is not added twice. Rates are copied into each assignment so later edits to
the tariff cannot change historical calculations.

The bundled [tariff](../.agents/skills/rightsize-goal/references/tariff.json) links
the official model pages and has a review/expiry date. Expired or missing tariffs,
unknown actual models, unsupported cache-write categories, missing telemetry,
counter resets, and ambiguous attribution remain explicitly unavailable rather
than being guessed. Long-context, service-tier, tool, tax, and account-specific
charges are excluded. Available worker subtotals omit unmeasured root coordination
and any work outside the assignment protocol.

Reports group observations by actual model/effort, task mode, difficulty, and
tariff version. Sample counts, acceptance, rework, failures, and coverage should
be read together. Comparing unlike tasks is not proof of savings or capability.
The `chain_groups` section also joins retries and escalations through `prior_task`
and groups their complete cost by the initially requested model/effort route and
tariff-version combination. A chain cost is complete only
when every linked assignment has known cost. `partial_chain_links` warns that a
filter omitted a parent or the recorded links are malformed.

## Privacy and storage

The helpers make no network requests. They read local session records to extract
metadata/counters and do not copy full prompts or transcripts into the ledger.
Evidence strings, lesson text, project tags, paths, and local logs can still contain
sensitive information if the coordinator writes it. Keep them concise and avoid
secrets, private source snippets, and identifying project names when unnecessary.
Codex itself still processes your work according to its account/service settings.

Only one coordinator should account for an assignment in a thread at a time.
Run `finish` after runtime-confirmed termination and flushed telemetry; finishing
early can freeze an incomplete usage snapshot. An idempotent repeat does not
refresh an already-finished task.

`finish` also reports the worker's context size at its latest turn (`context_tokens`) and
the model's context window when telemetry includes it. A reused agent's context keeps growing
across assignments even though each assignment is measured on its own. Alongside it, `finish`
reports `context_free_pct`, `eligible` (at least 30% of the window free and not compacted),
`compacted` (Codex wrote a `compacted` record during the assignment), `assignment_growth_tokens`, and `oversized`
(this assignment alone used 30% or more of the window), and writes them to the goal log.
`task_usage.py workers --run <goal-id>` lists every worker's status, idle minutes, and context
facts from its last log line, and marks it `gc_due` once it has been idle 15 minutes, falls under
30% free, or is compacted; `task_usage.py stop` records a confirmed closure. The coordinator
retires agents it no longer expects to use and closes them only when the runtime supports and confirms closure. If no
close operation is available, it retains the finished worker's actual runtime status and
records retirement from future assignments. Retirement or interruption does not establish
that a concurrency slot is free; see [worker cleanup behavior](usage.md#what-happens).

Future telemetry formats (including hosts that
do not expose JSONL rollouts) may be unavailable. Continue the actual objective
and preserve that gap.

To remove saved data, close active runs first and remove the exact ledger or
project log directory you intend to discard. Normal installation and the manual
uninstall procedure preserve these records.
