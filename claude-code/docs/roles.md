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
| `rightsize-upper-midlevel-doer` | Claude Sonnet 5 | `high` | Moderately complex bounded work needing more judgment |
| `rightsize-lower-senior-doer` | Claude Opus 5 | `medium` | Hard work: ambiguity, unfamiliar integrations, real tradeoffs |
| `rightsize-senior-doer` | Claude Opus 5 | `high` | Deep interacting constraints where more effort pays off |
| `rightsize-staff-doer` | Claude Fable 5.1 | `medium` | Bounded expert work, only after documented Opus struggle |
| `rightsize-principal-doer` | Claude Fable 5.1 | `high` | The hardest unresolved core, only after documented Opus struggle |

Each row is a distinct `(model, effort)` pair. No two roles resolve to the same
configuration, which is the bar a role has to clear to justify existing.

## Two levers, not one

On Claude Code, cost moves along two axes, and the second one matters more here than it
does on Codex.

**Model.** Published per-million rates put roughly a tenfold spread between the cheapest
and most expensive model in the ladder. That is a real gap, but it is much flatter than the
Codex lineup's, and the difference is not evenly distributed. On Codex the step from Terra to
Sol is enormous — a mid-tier model to a frontier one, with the price to match — so routing a
task down a tier there is a decision with large consequences in both directions. The Claude
equivalent, Sonnet 5 to Opus 5, is a far smaller step in both price and capability. Sonnet 5
is a strong model that handles a great deal of real work, which means the cost of routing it
wrongly is lower, and so is the saving from routing it downward.

The practical consequence: dropping one model tier saves less than the tier names imply, and
a single rework cycle can erase it. The ladder is not a licence to route everything downward —
it is a reason to route by task fit and measure the outcome.

**Effort.** Sonnet 5, Opus 5, and Fable 5.1 accept `low` through `max`, and effort changes
how many tokens a model spends at a fixed rate. Claude Code's session default is `xhigh`; the
API default is `high`. Every effort-bearing role here runs at or below `high`, and each paid
model tier is split into a cheaper and a dearer variant on effort alone. Choosing
`rightsize-lower-senior-doer` over `rightsize-senior-doer` is a genuine cost decision even
though both are Opus 5.

The levels are not arbitrary. Anthropic's own guidance sets the API default at `high` for both
Sonnet 5 and Opus 5, reserves `xhigh` for "the hardest coding and agentic tasks", and calls
`low`/`medium` the primary cost lever — on Opus 5 explicitly: *"`low` and `medium` are unusually
effective on this model."* So the cheaper half of each pair sits at `medium`, and the dearer
half sits at the documented default rather than above it. `xhigh` and `max` are left unused:
this workflow is meant to spend less than a default session, not more, and an `xhigh` role also
wants a large `max_tokens` that agent frontmatter cannot set.

On Fable 5.1 the same guidance recommends `high` for most tasks and `medium`/`low` for routine
work. Since the two Fable roles fire only after documented Opus struggle — by definition the
least routine work the workflow sees — they sit at `medium` and `high`, not in the routine band.

This is why the roles ship as files. The Agent tool can override a subagent's `model` at
dispatch, but it cannot override `effort`. Only a role definition can pin both, so a
generic agent with a model override does not reproduce a role and must not be substituted
for one.

## What a dispatch actually costs

Two measured figures from this machine, both from real runs rather than estimates.

A trivial assignment dispatched as a plain in-process subagent — one that does nothing but
reply — cost about **$0.0095** at the junior role and about **$0.0238** at the lower-midlevel
role. Almost all of that is the worker's system prompt billed as cache-write tokens. That is the
floor price of a dispatch.

The same junior role dispatched as an Agent Teams *teammate*, doing a genuinely trivial two-line
test addition, cost **$0.0434 across 93,956 tokens and 9 requests**. A teammate is a full session:
it loads its own project instructions and orients itself before it reaches your task. Its floor is
roughly four to five times a subagent's.

The lesson is not "avoid teammates" — reuse across several related assignments repays that startup
cost quickly. The lesson is that a teammate is the wrong shape for one tiny errand, and that
dispatch overhead, not model rate, dominates the price of small work. Bundle accordingly.

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
lower than the lower-midlevel role's. For genuinely mechanical, low-rework work that pays; for
anything likely to come back for a second attempt it does not.

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
