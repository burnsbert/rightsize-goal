# Why these seven roles

The Codex implementation of Rightsize Goal uses seven roles across four models. This
package keeps seven, but not by copying: the Claude lineup has different economics, and
the mapping was rebuilt from them. This document records the reasoning so the ladder can
be argued with rather than merely inherited.

## The ladder

| Role | Model | Effort | Task boundary |
| --- | --- | --- | --- |
| `rightsize-junior-doer` | Claude Haiku 4.5 | not supported | Explicit, low-risk work with an example or prescribed approach |
| `rightsize-midlevel-doer` | Claude Sonnet 5 | `medium` | Bounded work using established project patterns |
| `rightsize-upper-midlevel-doer` | Claude Sonnet 5 | `xhigh` | Moderately complex bounded work needing more judgment |
| `rightsize-lower-senior-doer` | Claude Opus 5 | `medium` | Hard work: ambiguity, unfamiliar integrations, real tradeoffs |
| `rightsize-senior-doer` | Claude Opus 5 | `xhigh` | Deep interacting constraints where more effort pays off |
| `rightsize-staff-doer` | Claude Fable 5.1 | `low` | Bounded expert work, only after documented Opus struggle |
| `rightsize-principal-doer` | Claude Fable 5.1 | `medium` | The hardest unresolved core, only after documented Opus struggle |

Each row is a distinct `(model, effort)` pair. No two roles resolve to the same
configuration, which is the bar a role has to clear to justify existing.

## Two levers, not one

On Claude Code, cost moves along two axes, and the second one matters more here than it
does on Codex.

**Model.** Published per-million rates put roughly a tenfold spread between the cheapest
and most expensive model in the ladder. That is a real gap, but it is much flatter than
the Codex lineup's, where the cheapest and most expensive models differ by about fiftyfold.
The practical consequence: dropping one model tier saves less than the tier names imply,
and a single rework cycle can erase it. The ladder is therefore not a licence to route
everything downward — it is a reason to route by task fit and measure the outcome.

**Effort.** Sonnet 5, Opus 5, and Fable 5.1 accept `low` through `max`, and effort changes
how many tokens a model spends at a fixed rate. Claude Code's session default is `xhigh`.
Six of the seven roles deliberately run at or below that default, and two model tiers are
split into a cheap and an expensive variant on effort alone. Choosing
`rightsize-lower-senior-doer` over `rightsize-senior-doer` is a genuine cost decision even
though both are Opus 5.

This is why the roles ship as files. The Agent tool can override a subagent's `model` at
dispatch, but it cannot override `effort`. Only a role definition can pin both, so a
generic agent with a model override does not reproduce a role and must not be substituted
for one.

## Why the junior role is Haiku only

Haiku 4.5 does not accept an effort setting; the field is simply absent from its recorded
turns. So there is exactly one Haiku tier, not two.

Haiku's band is genuinely narrow, and the role description says so:

- Its context window is smaller than the other three models', so the working set has to
  stay small.
- It is a 4.5-generation model in a ladder of 5-generation peers, a wider capability gap
  than its price gap suggests.
- It is only about half the per-token price of Sonnet 5, so the savings are modest.

It still earns a place. A measured probe of one trivial assignment on one machine — a
single dispatch that does nothing but reply — cost about **$0.0095** at the junior role
and about **$0.0238** at the lower-midlevel role, almost all of it the worker's system
prompt billed as cache-write tokens. That is the floor price of a dispatch, and the junior
role's floor is meaningfully lower. For genuinely mechanical, low-rework work it pays;
for anything that might come back for a second attempt it does not. Those are two runs,
not a benchmark; treat them as an order of magnitude, and let the ledger replace them with
your own project's evidence.

## Why not fewer roles

The obvious reductions were considered and rejected:

- **Drop `rightsize-upper-midlevel-doer`.** Then moderate-complexity work has nowhere to
  go but Opus, and the largest single price step in the ladder gets taken for work that
  did not need it.
- **Drop `rightsize-staff-doer`.** Then every Fable escalation is a principal-level
  purchase. The staff role exists precisely so the first probe into the most expensive
  model is a cheap one, and so staff cannot become a compulsory toll before principal.
- **Drop one of the Opus pair.** Opus is where hard work actually lands. Having a cheaper
  default and a deeper variant on the same model is the most-used step on the ladder.

## Why not more

Sonnet 5, Opus 5, and Fable 5.1 each support five effort levels, so a finer ladder is
technically possible. It is not obviously better. Each additional role is a routing
decision the coordinator has to make and justify in the log, and adjacent effort levels on
the same model rarely change the right answer. Seven roles already give every model tier
except Haiku both a cheap and an expensive variant. Adding an eighth would buy resolution
the evidence cannot yet support.

## What every role can and cannot do

The role files constrain behavior structurally, not only by instruction:

- **No role is granted the `Agent` or `Task` tool.** Workers cannot spawn agents, so the
  escalation gate cannot be bypassed by a worker escalating itself. A packaged test
  asserts this for all seven files.
- Every role gets `Read, Glob, Grep, Bash, Write, Edit, MultiEdit`. From
  `rightsize-upper-midlevel-doer` upward they also get `WebFetch` and `WebSearch`, because
  research synthesis is explicitly in those roles' remit.
- No role is granted artifact publishing, scheduling, messaging, or goal-state tools. The
  coordinator alone owns the session goal, the scratch log, and the gate state.
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
