# Model vs baseline: why rules decide

TraceIntel can write its advice two ways: with a model (planner and reporter through
OpenRouter), or with fixed rules over the same evidence (the baseline). Both are held to
the same grounding validator. This note explains why the baseline makes the decisions and
what the model is still for.

## What the runs show

`scripts/verify_nooa_live.py` runs the 8 labelled agent scenarios with a real model and
with the baseline. The chain is scripted, so only the model varies. Full table in the
[README](../README.md#live-model-vs-baseline). The runs that matter here:

| Writer | Correct advice | Written by the model | Median time |
| --- | --- | --- | --- |
| Rule-based baseline | 8 / 8 | n/a | under 0.1 s |
| NIM Nemotron 3.5 Super, thinking off | 7 / 8 | 7 / 8 | 29 s |
| NIM Nemotron 3 Ultra, thinking off | 2 / 8 | 8 / 8 | 9 s |
| NIM Nemotron 3.5 Super, thinking on | 5 / 8 | 0 / 8 | 40 s |
| `openrouter/auto` | 4 / 8 | 8 / 8 | 25 s |

Every run was fully grounded: no briefing cited anything the tools hadn't verified.

Two lessons:

- **Reasoning models need reasoning off for this job.** The planner and reporter ask for a
  small structured answer (a few tool calls, or a few claim IDs). With reasoning on, the
  model spent the token budget thinking and the answer was cut off, so the format check
  failed and the baseline took over every time. Switching it off (NIM's
  `enable_thinking: false`) let Nemotron Super write 7 of 8 briefings.
- **Grounded is not the same as right.** Nemotron Ultra cited real evidence in all 8
  briefings and still gave the wrong advice in 6. The validator can prove a claim is
  backed by evidence. It can't prove the advice drawn from it is wise.

## Why the baseline should keep deciding

1. **The right answer here is a rule.** Each scenario's advice follows from on-chain facts:
   a spender held by a private key means revoke; an allowance already at zero means
   nothing to do. Rules that encode those facts are the ceiling on this test. A model can
   tie them, not beat them, and every gap between them is a mistake.
2. **Mistakes don't cost the same.** "Keep" on a drainer loses money; "revoke" on a safe
   router costs one transaction. A writer that cites real evidence every time and is still
   right only 2 times in 8 (Nemotron Ultra) can't be the one that decides.
3. **Speed and uptime.** The baseline answers in well under a second, offline. Hosted
   models took 9 to 124 seconds per scenario, and some timed out on the free tier.
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

Put the provider settings in `.env` (git ignores it), then:

```sh
# .env: LLM_PROVIDER=nvidia_nim, NVIDIA_API_KEY=nvapi-..., NVIDIA_MODEL=<catalog id>
#   or: OPENROUTER_API_KEY=..., OPENROUTER_MODEL=<model id>
PYTHONPATH=backend uv run python scripts/verify_nooa_live.py
```

Results are written to `evals/results/live-<provider>_<model>.json`. The NIM runs are from
26 Nov 2026 and the OpenRouter runs from 28 Oct 2026. Rerun them before quoting numbers
for a different model.
