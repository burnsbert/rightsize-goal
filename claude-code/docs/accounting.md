# Usage accounting and data

The bundled `task_usage.py` helper reads Claude Code's local JSONL transcripts and stores
task metadata and attributable token counts in SQLite.

Claude Code writes one transcript per session and one per subagent:

```text
~/.claude/projects/<project-slug>/<session-id>.jsonl
~/.claude/projects/<project-slug>/<session-id>/subagents/agent-<agent-id>.jsonl
```

Because each subagent gets its own file, a worker's usage is measured directly rather than
inferred from a session aggregate, and worker tokens are never double-counted against the
coordinator. The helper needs only the agent ID that the Agent tool returned; it finds the
file itself.

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

The ledger defaults to `~/.claude/rightsize-goal/usage.sqlite3`, or the same path under
`CLAUDE_CONFIG_DIR` when that variable is set. It survives updates. `--db PATH` selects
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

The reader depends on Claude Code's local transcript format. If that format changes, or a
transcript is pruned or missing, the result is an explicit unavailable rather than a guess.
Continue the actual objective and preserve the gap.

To remove saved data, close active runs first, then remove the exact ledger or project log
directory you intend to discard. Plugin uninstall and the manual uninstall procedure both
preserve these records.
