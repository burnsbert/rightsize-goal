# Why these roles

The Codex implementation of Rightsize Goal uses five roles across three models. This
package originally kept seven worker roles, one lower-effort and one higher-effort variant
per paid model. It was simplified to four: one role per model, each pinned at the documented
API default of `high`. A fifth role, the validator, judges completion rather than doing work.
This document records the reasoning so the ladder can be argued with rather than merely
inherited.

## The ladder

| Role | Model | Effort | Task boundary |
| --- | --- | --- | --- |
| `rightsize-junior-doer` | Claude Haiku 4.5 | not supported | Explicit, low-risk work with an example or prescribed approach |
| `rightsize-midlevel-doer` | Claude Sonnet 5 | `high` | Bounded work using established project patterns, including moderately complex work needing more judgment |
| `rightsize-senior-doer` | Claude Opus 5.5 | `high` | Hard work: ambiguity, unfamiliar integrations, real tradeoffs, deep interacting constraints |
| `rightsize-principal-doer` | Claude Fable 5.1 | `high` | Break-glass: the hardest unresolved core, only after documented Opus struggle |

Each row is a distinct model. No two worker roles resolve to the same configuration, which
is the bar a worker role has to clear to justify existing.

## The validator

| Role | Model | Effort | Job |
| --- | --- | --- | --- |
| `rightsize-validator` | Claude Opus 5.5 | `high` | Decide whether the current goal is met, from its own evidence |

The coordinator decides when it thinks the goal is done; the validator decides whether it is.
It shares the senior role's model and effort, which the "distinct configuration" bar above
would forbid for a worker, because it is not a worker: it is read-only, it does no
implementation, and its instructions are the opposite of a doer's. It receives the goal text
and where to look, never the coordinator's argument that the work is finished, and it runs
the acceptance checks itself.

It runs on Opus because a wrong DONE is the expensive mistake. It ends the goal while work
remains. The validator only runs when the coordinator claims completion, so the premium is
paid rarely. It judges the goal as a QA engineer or product owner would, not as a hunt for any
conceivable flaw: done is not the same as perfect. Follow-up rounds check the earlier reasons and
the effects of their fixes, and do not fail the goal for issues an earlier round already saw.

## Two levers, not one

On Claude Code, cost moves along two axes, and the second one matters more here than it
does on Codex.

**Model.** Published per-million rates put roughly a tenfold spread between the cheapest
and most expensive model in the ladder. That is a real gap, but it is much flatter than the
Codex lineup's, and the difference is not evenly distributed. On Codex the step from Luna to
Sol — its midlevel-to-senior boundary — is twentyfold in per-token price, so routing a task
down a tier there is a decision with large consequences in both directions. The Claude
equivalent, Sonnet 5 to Opus 5.5, is a twofold step. Sonnet 5
is a strong model that handles a great deal of real work, which means the cost of routing it
wrongly is lower, and so is the saving from routing it downward.

The practical consequence: dropping one model tier saves less than the tier names imply, and
a single rework cycle can erase it. The ladder is not a licence to route everything downward —
it is a reason to route by task fit and measure the outcome.

**Effort.** Sonnet 5, Opus 5.5, and Fable 5.1 accept `low` through `max`, and effort changes
how many tokens a model spends at a fixed rate. Claude Code's session default is `xhigh`.
Every effort-bearing role here runs at `high`.

The level is not arbitrary. Anthropic's own guidance sets the API default at `high` for
Sonnet 5 and Fable 5.1, and reserves `xhigh` for "the hardest coding and agentic tasks."
Opus 5.5 is the exception: its API default is `medium`, one level below Opus 5's, and
Anthropic reports that Opus 5.5 at `medium` beats Opus 5 at `high` on coding and
knowledge-work evaluations. The senior role still runs at `high`, one level above that
default, by choice. The senior role's documented struggle is what opens the break-glass
Fable gate, so that struggle should come from a serious attempt; `high` Opus 5.5 is still
far cheaper than a Fable escalation. Expect more tokens per senior turn than Opus 5 spent at
`high`, since Opus 5.5 thinks more per turn at a given level. `xhigh` and `max` are left
unused: this workflow is meant to spend less than a default session, not more, and an
`xhigh` role also wants a large `max_tokens` that agent frontmatter cannot set.

This package previously ran a lower-effort variant of each paid model at `medium` alongside
the `high` variant — Anthropic notes that on Opus 5, *"`low` and `medium` are unusually
effective."* That split was removed in favor of one role per model at `high`; see
[why four roles](#why-four-roles) for what was given up.

This is why the roles ship as files. The Agent tool can override a subagent's `model` at
dispatch, but it cannot override `effort`. Only a role definition can pin both, so a
generic agent with a model override does not reproduce a role and must not be substituted
for one.

A role definition reliably pinning `effort` currently depends on how it is dispatched: a
Claude Code bug makes an Agent Teams teammate silently inherit the coordinator's own session
effort instead of the role's, while a plain in-process subagent honors it correctly. See
[Agent Teams](install.md#agent-teams-recommended) for the tracked issue and the affected
path; this is a Claude Code limitation with no equivalent in the Codex implementation.

## What a dispatch actually costs

Two measured figures from this machine, both from real runs rather than estimates.

A trivial assignment dispatched as a plain in-process subagent — one that does nothing but
reply — cost about **$0.0095** at the junior role and about **$0.0238** at the midlevel
role, then running at `medium` effort; this ladder now runs that role at `high`, so expect a
higher floor. Almost all of that cost is the worker's system prompt billed as cache-write
tokens. That is the floor price of a dispatch.

The same junior role dispatched as an Agent Teams *teammate*, doing a genuinely trivial two-line
test addition, cost **$0.0434 across 93,956 tokens and 9 requests**. A teammate is a full session:
it loads its own project instructions and orients itself before it reaches your task. Its floor is
roughly four to five times a subagent's.

The lesson is not "avoid teammates": reusing a teammate for natural follow-ons while its context
has room repays that startup cost quickly. Reusing it for unrelated work does not, because every
request re-reads its whole context, so the coordinator gives work in an unrelated area to a fresh
teammate, and stops teammates once they are idle 15 minutes, under 30% of their window free, or
compacted. The lesson is that a teammate
is the wrong shape for one tiny errand, and that dispatch overhead, not model rate, dominates the
price of small work. Bundle accordingly.

These are single runs on one machine, not a benchmark. Let the ledger replace them with your own
project's evidence.

## Why the junior role is Haiku only

Haiku 4.5 does not accept an effort setting; the field is simply absent from its recorded
turns. So there is exactly one Haiku tier, not two.

Haiku's band is genuinely narrow, and the role description says so:

- Its context window is smaller than the other three models', so the working set has to
  stay small.
- It is a 4.5-generation model in a ladder of 5-generation peers, a wider capability gap
  than its price gap suggests.
- It is only about half the per-token price of Sonnet 5, so the savings are modest.

It still earns a place. As the measured figures above show, its dispatch floor is meaningfully
lower than the midlevel role's. For genuinely mechanical, low-rework work that pays; for
anything likely to come back for a second attempt it does not.

## Why four roles

The package originally shipped seven roles: a `medium`-effort and a `high`-effort variant of
each paid model (Sonnet 5, Opus 5, Fable 5.1), plus the effort-less Haiku junior. It was
simplified to one role per model, each at `high`, trading away three things:

- **The upper-midlevel tier.** Moderately complex bounded work — multi-file changes,
  localized debugging, research synthesis — no longer has a dedicated Sonnet/high role
  between routine midlevel work and an Opus escalation. It is folded into
  `rightsize-midlevel-doer`, which now runs at `high` and covers both bands. The tradeoff:
  every midlevel dispatch, even a small routine one, now spends `high`-effort tokens rather
  than `medium`.
- **The lower-senior probe.** There is no more `medium`-effort Opus role to test whether
  more tokens on the same model resolves a hard question before committing to `high`.
  Hard work now goes straight to `rightsize-senior-doer` at `high`.
- **The staff probe.** There is no more `medium`-effort Fable role to take a first, cheaper
  pass at a discriminating hypothesis before a deeper principal run. Every Fable escalation
  now runs at `rightsize-principal-doer` depth.

## Why not fewer than four

Merging further was considered and rejected:

- **Merge junior into midlevel.** Then every basic, explicit task pays Sonnet/high rates
  and loses Haiku's meaningfully lower dispatch floor (see the measured figures above) for
  work that never needed a `high`-effort Sonnet 5 turn.
- **Merge midlevel into senior.** Then routine bounded work — the bulk of ordinary
  engineering — pays Opus rates by default, twice Sonnet's, for work that does not need
  it.
- **Merge senior into principal.** Then every hard task that would have stopped at a
  documented Opus struggle instead pays Fable rates directly — the largest single price step
  in the ladder — defeating the escalation
  gate's entire purpose: buying expensive effort only for the portion that is actually
  difficult.

## Why not more

Sonnet 5, Opus 5.5, and Fable 5.1 each support five effort levels, so a finer ladder is
technically possible. It is not obviously better. Each additional role is a routing
decision the coordinator has to make and justify in the log, and adjacent effort levels on
the same model rarely change the right answer. Four roles already give every model tier a
role; splitting one into a lower-effort and a higher-effort variant is the reduction this
package chose against, not a resolution the evidence currently supports adding back.

## What every role can and cannot do

The role files constrain behavior structurally, not only by instruction:

- **No role is granted the `Agent` or `Task` tool.** Workers cannot spawn agents, so the
  escalation gate cannot be bypassed by a worker escalating itself. A packaged test
  asserts this for every role file.
- Every worker role gets `Read, Glob, Grep, Bash, Write, Edit, MultiEdit`.
- Every role, including the validator, gets `WebFetch` and `WebSearch` so it can research
  online. No role gets `SendMessage`: the coordinator stops workers with `TaskStop`, and workers
  never message each other or hand work around the coordinator. A packaged test asserts both.
- `rightsize-validator` gets no file-editing tools: enough to run checks, read the work, and
  look things up. A packaged test asserts it stays that way.
- No role is granted artifact publishing, scheduling, or goal-state tools. The
  coordinator alone owns the session goal, the goal log, and the gate state.
- Every role is instructed not to commit, push, publish, or send external messages unless
  the assignment explicitly authorizes it.

Permission mode is not set in the role files, so workers inherit the session's permission
mode rather than widening it.

## Changing the ladder

The roles are plain Markdown files in `agents/`. To adjust one, edit its `model` or
`effort` frontmatter — but keep three things consistent or the accounting will quietly
degrade:

1. `references/tariff.json` must contain an entry for the exact model identifier that
   ends up being served, or every assignment for that role reports an unavailable cost.
   Update `role_models` in the same file so the packaged consistency test still passes.
2. The role must still appear by name in `SKILL.md`, which is where the coordinator learns
   when to use it. A packaged test asserts this too.
3. `effort` must be one of `low`, `medium`, `high`, `xhigh`, `max`, and must be omitted
   for a model that does not accept it.

If you remove a role entirely, remove it from `install.py`'s `ROLES` tuple, from
`SKILL.md`'s routing table, and from `role_models`. The test suite will tell you if you
miss one.
