# Model vs baseline: why rules decide

TraceIntel can write its advice two ways: with a model (planner and reporter through
OpenRouter), or with fixed rules over the same evidence (the baseline). Both are held to
the same grounding validator. This note explains why the baseline makes the decisions and
what the model is still for.

## What the runs show

`scripts/verify_nooa_live.py` runs the 8 labelled agent scenarios with a real model and
with the baseline. The chain is scripted, so only the model varies. Latest runs
(28 Oct 2026, free-tier key; details in the [README](../README.md#live-model-vs-baseline-28-oct-2026-free-tier-openrouter-key)):

| Writer | Correct advice | Grounded | Written by the model | Median time |
| --- | --- | --- | --- | --- |
| Rule-based baseline | 8 / 8 | 8 / 8 | n/a | under 0.1 s |
| `openrouter/auto` | 4 / 8 | 8 / 8 | 8 / 8 | 24.9 s |
| `nvidia/nemotron-3.5-super-vl:free` | 7 / 8 | 8 / 8 | 0 / 8 | 44.9 s |

When the model wrote the advice, it was wrong half the time but never ungrounded. When the
pinned free model failed (bad format or a timeout), the baseline wrote the briefing, and
the one miss came from a planning timeout that cut an investigation short.

## Why the baseline should keep deciding

1. **The right answer here is a rule.** Each scenario's advice follows from on-chain facts:
   a spender held by a private key means revoke; an allowance already at zero means
   nothing to do. Rules that encode those facts are the ceiling on this test. A model can
   tie them, not beat them, and every gap between them is a mistake.
2. **Mistakes don't cost the same.** "Keep" on a drainer loses money; "revoke" on a safe
   router costs one transaction. A writer that is right 4 times in 8, even fully cited,
   can't be the one that decides.
3. **Speed and uptime.** The baseline answers in well under a second, offline. Free models
   took 25 to 45 seconds and sometimes timed out or broke the output format.
4. **Same state, same answer.** An agent or an auditor needs the verdict to repeat for the
   same chain state. Sampling makes a model's verdict vary between runs.

That is why the pre-sign check has no model in the verdict at all. The agent calling it is
already a model, so it gets structured evidence in about a second and decides how to word
it. `explain: true` is opt-in, and even then the model only picks claim IDs and can't
change the verdict.

## What the model is for

- **Choosing what to look at** when the tool budget is tight. Code enforces the budget and
  the order of prerequisites, so a bad plan can only make an investigation thinner. It
  can't make one wrong.
- **Turning cited claims into a briefing a person can read.** The validator rejects
  anything it can't trace to evidence, and the baseline takes over after one failed repair.

## When a model could win

A model can beat the baseline only on cases the rules can't settle. The clearest one is a
spender no registry lists, where the honest rule-based answer is "unknown". In the live
scoreboard that is still the largest source of warnings (27 of 100 mainnet transactions).
Settling those needs new evidence: verified source code, the protocol's own deployment
files, how long the contract has been in use. Then the test would be a set of such
spenders labelled by people, scored on whether model + tools resolves them with no
ungrounded claims and no confident mistakes. That would be a fair contest. The current 8
scenarios are not.

## Rerun

```sh
OPENROUTER_API_KEY=... OPENROUTER_MODEL=<model id> \
  PYTHONPATH=backend uv run python scripts/verify_nooa_live.py
```

Results are written to `evals/results/live-<model>.json`. The runs above are from 28 Oct
2026. Rerun them before quoting the numbers for a different model.
