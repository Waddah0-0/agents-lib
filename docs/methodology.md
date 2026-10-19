# How the AI Code Detector scores code

This page explains what the AI Code Detector's numbers mean, how they are produced, and how
far to trust them. It describes **methodology v1** (detector 0.2.0).

**The short version:** the detector is good at *ranking* repositories (more AI-like above
less AI-like) and bad at *deciding* about a single one. It must not be used as the basis for
accusing anyone, and the numbers below show why.

## What goes into the estimate

**1. An LLM judge reads a sample of files.** A local model (default `qwen3.5:9b` through
Ollama) reads up to 20 files per repository, chosen as a deterministic mix of files that the
heuristics consider AI-like, human-like and neutral. For each file it gives a likelihood, a
confidence, and line numbers pointing at evidence for and against. The quoted lines in the
report are taken from the file, not from the model, so evidence cannot be invented. The code
is fenced by random markers and declared as data, so instructions hidden in a repository
cannot steer the model. A fifth of the files are judged twice with the rubric reordered; if
the two answers disagree a lot, confidence drops.

**2. Heuristic signals read every Python, JavaScript and TypeScript file:** comment density,
comments that restate the code, naming habits, personal or informal comments, commented-out
code and leftover debugging statements.

**3. They are combined at repository level** with weights fitted on data (see below):

```
log-odds = 1.38 + 0.27 x (files' average signal log-odds) + 1.54 x (judge's average log-odds)
```

The judge carries most of the weight because, in evaluation, it was the only source of
evidence that worked on recent code.

**4. The range** comes from resampling the files 1,000 times and taking the 10th to 90th
percentile; the judge term is recomputed for every resample, so a verdict on only a few files
widens it. Resampling measures how much the files disagree, not how unsure the method is, so
the reported range is also at least ±0.15 wide at low confidence and ±0.07 at medium.

## What is reported but not scored

- **AI-tool markers:** config files such as `CLAUDE.md` or `.cursorrules`, co-author trailers
  and bot authors from nine tools, each verified against a real commit. They prove a tool was
  *used*, not how much code it wrote, and they are trivial to add or remove.
- **Commit history and README style.** In evaluation, a long, messy history separated old
  projects from new ones, not people from AI. Weighting it made every recent human project in
  the dataset look AI-written, so it is shown only as context.

## Without a model

If no model is configured or reachable, the detector uses a signals-only model and reports
**low confidence**. In evaluation, signals alone ranked repositories only modestly better than
chance and flagged a large share of human repositories.

## How it was measured

Dataset v1 has 70 repositories:

| | Python | JavaScript / TypeScript |
|---|---|---|
| Human, before 2021 | 22 | 10 |
| Human, after 2023 (Gentoo, no-AI policy) | 5 | 0 |
| AI-built, 2025 or later | 16 | 17 |

They were split by repository into train (44), validation (13) and test (13). Weights were
fitted on train only, choices were made on validation, and the test split was scored once.

Results (repository level; `eval/results/v1_final_*.json`):

| | Train (44) | Validation (12) | Test (13) |
|---|---|---|---|
| **With the judge:** AUC | 0.87 | 0.97 | 1.00 |
| False positives at 0.5 | 13% | 29% | 0% |
| AI repositories above 0.5 | 90% | 100% | 83% |
| Calibration error | 0.19 | 0.25 | 0.21 |
| **Signals only:** AUC | 0.73 | 1.00 | 0.79 |
| False positives at 0.5 | 39% | 57% | 29% |

On the test split, every human repository scored at most 0.43, including recent human code
(Gentoo's `portage`, 0.28), and five of six AI repositories scored above 0.5. **The test split
is small:** with 7 human and 6 AI repositories, one more mistake would move the AUC by about
0.02-0.03 and the false-positive rate by 14 points. Treat these numbers as encouraging, not
as proof. (One validation repository could not be fetched: its pinned commit was removed
upstream.)

## What the numbers mean for you

- **The estimate is a ranking signal, not a probability you can quote.** The methodology is
  not calibrated: its numbers do not match real frequencies, so confidence never goes above
  "medium".
- **There is no "likely AI" verdict.** A threshold of 0.915 kept false positives at or below
  5% on the training repositories, but caught only 1 of 21 AI repositories there. At any
  lower threshold the detector flags human projects.
- **Read the evidence.** The useful output is the list of lines the judge pointed at and the
  signals that fired, on both sides.

## Known weaknesses

1. **Generated-looking human code scores high.** Projects with large, repetitive data files
   (locale tables in `dateparser` and `pendulum`) were judged AI-like.
2. **Few recent human projects.** Only five, all Python and from one ecosystem. Results on
   other recent human code are uncertain.
3. **Agent-built projects only.** Code written with light AI help, or AI code edited by people,
   is not represented, and the detector has not been tested on it.
4. **Memorisation.** Famous pre-2021 projects may be recognised by the model from its training
   data, which inflates results on them.
5. **Tool mix.** Claude-built repositories are the largest group among the AI samples.

The datasets, results and tools are in `agents/ai_code_detector/eval/`; anyone can re-run them.
