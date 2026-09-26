# Usage accounting and data

The bundled `task_usage.py` helper reads Claude Code's local JSONL transcripts and stores
task metadata and attributable token counts in SQLite.

Claude Code writes one transcript per session and one per subagent:

```text
~/.claude/projects/<project-slug>/<session-id>.jsonl
~/.claude/projects/<project-slug>/<session-id>/subagents/agent-<agent-id>.jsonl
```

With Agent Teams enabled, a named worker instead runs as its own session and writes an ordinary
top-level transcript, identified inside the file by `agentName` and `teamName`. The helper
resolves both layouts from whatever the Agent tool returned — a bare agent id for a subagent, or
`<agentName>@<teamName>` for a teammate — by matching the labels recorded in the file rather than
guessing from timestamps.

Either way a worker's usage is measured directly rather than inferred from a session aggregate,
and worker tokens are never double-counted against the coordinator. The helper needs only the id
the Agent tool returned; it finds the file itself. `--transcript PATH` overrides discovery.

Every assistant record carries its own `message.usage` counters, the exact `message.model`
that served it, and the `effort` used for that turn. That means the ledger records what
actually ran, not what was requested — a useful distinction when a role is edited or a
model identifier rotates.

Two details are handled for you and matter for correctness:

- Streaming writes several records for one API request. The helper deduplicates on
  `requestId`, so a partial and its final record count once. Without this, a normal run
  would over-report by a factor of two or three.
- `input_tokens` already excludes cache reads and cache writes. The five priced categories
  are additive; nothing is subtracted.

## The ledger

The ledger defaults to `<current-directory>/.rightsize-goal/usage.sqlite3`. Each goal has its own `<goal-id>.jsonl` log in that directory, with only `agent_call` and `agent_result` lines. Every call identifies the agent; every result records measured tokens and estimated cost, or explicit unavailable reasons. A retry or escalation links the prior task and states why it was needed. No new Rightsize Goal usage logs are written under the user configuration directory. The local records survive updates. `--db PATH` selects
another ledger and must precede the subcommand, as must `--claude-dir PATH`.

From the installed skill directory:

```sh
python3 scripts/task_usage.py report
python3 scripts/task_usage.py report --run <run-id>
python3 scripts/task_usage.py --help
```

The complete assignment protocol and examples are in the bundled
[accounting reference](../skills/rightsize-goal/references/accounting.md).

## Interpreting results

Dollar figures are standard-rate API-equivalent estimates. They are not an invoice, and a
Claude Code subscription is not billed per token at all. Treat them as a common comparison
basis for routing decisions.

Five categories are priced separately, because they carry different rates:

| Category | Source counter |
| --- | --- |
| Uncached input | `input_tokens` |
| Cache reads | `cache_read_input_tokens` |
| 5-minute cache writes | `cache_creation.ephemeral_5m_input_tokens` |
| 1-hour cache writes | `cache_creation.ephemeral_1h_input_tokens` |
| Output | `output_tokens`, which already includes thinking tokens |

Cache writes cost more than base input and the two TTLs are priced differently, so the
helper refuses to price a cache-write total whose 5-minute and 1-hour split is missing
rather than assuming a TTL. In practice a subagent's system prompt is billed as a cache
write on its first turn, which is why every dispatch has a floor price even when the worker
does almost nothing.

Rates come from the bundled
[tariff](../skills/rightsize-goal/references/tariff.json), which links the official pricing
pages and carries a review date. Rates are copied into each assignment at `start`, so later
edits to the tariff cannot change historical calculations.

The following stay explicitly unavailable rather than being guessed: an expired or missing
tariff, a served model with no exact tariff entry, a cache-write total without its TTL
split, a record without request identity, a missing transcript, and an ambiguous transcript
match. In each case attributable tokens are preserved where they are known, and only the
dollar figure is withheld. Long-context and service-tier modifiers, server tool charges,
batch discounts, taxes, and account-specific pricing are excluded throughout. Available
worker subtotals omit unmeasured coordination and any work outside the assignment protocol.

Reports group observations by actual model, actual effort, task mode, difficulty, and tariff
version. Sample counts, acceptance, rework, failures, and coverage should be read together.
Comparing unlike tasks is not proof of savings or capability.

## Privacy and storage

The helpers make no network requests. They read local transcripts to extract counters and
labels, and skip every line that does not contain usage counters, so prompts, responses,
tool arguments, and file contents are never parsed into the ledger.

Evidence strings, lesson text, project tags, paths, and local logs can still contain
sensitive information if the coordinator writes it there. Keep them concise and avoid
secrets, private source snippets, and identifying project names when unnecessary. Claude
Code itself still processes your work according to your account and service settings.

Only one coordinator should account for an assignment on an agent at a time; the ledger
enforces one active task per agent. Run `finish` after the runtime confirms the agent has
terminated, because finishing early freezes an incomplete snapshot. A repeat `finish` is
idempotent and does not refresh an already-finished task.

`finish` also reports the worker's context size at its latest request (`context_tokens`),
since every request re-reads everything the worker has seen. A reused teammate's context keeps
growing across assignments even though each assignment is measured on its own. The helper's
`context_advice` applies three bands: below 120,000 tokens there is room for a natural follow-on;
from 120,000 to 200,000, only a small follow-on that depends on what the worker already knows; at
200,000 or more, start a fresh worker. It also reports `assignment_growth_tokens`, how much this
assignment alone added, and flags an assignment that grew past 200,000 on its own as work that
should have been split.

The reader depends on Claude Code's local transcript format. If that format changes, or a
transcript is pruned or missing, the result is an explicit unavailable rather than a guess.
Continue the actual objective and preserve the gap.

To remove saved data, close active runs first, then remove the exact ledger or project log
directory you intend to discard. Plugin uninstall and the manual uninstall procedure both
preserve these records.
