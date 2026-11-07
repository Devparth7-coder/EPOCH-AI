# Benchmark & evaluation

## 1. What is being measured

The full six-stage pipeline, end to end: extraction → planning → evidence retrieval → temporal analysis →
contradiction detection → verdict. Retrieval is **deterministic** (fixture provider) in benchmark mode, so the
score measures the reasoning engine rather than web-search variance. That is a deliberate, disclosed choice.

Comparison system: a **basic LLM-only baseline** (`baseline_verdict` in `run_benchmark.py`) that takes the single
most similar snippet, and — with no temporal reasoning, no contradiction analysis and no version logic — answers
`VERIFIED` if the snippet looks like it agrees, otherwise `UNVERIFIED`.

## 2. Dataset

`backend/benchmark/dataset.jsonl` — **114 labelled claims** over **19 fact families**, produced by
`backend/benchmark/build_dataset.py`.

Each family is a real, publicly documented fact with a known earlier and later state (Python 3.7 → 3.13,
React 18 → 19, Node.js 18 → 22, PostgreSQL 16 → 17, TLS 1.2 → 1.3, HTTP/2 → HTTP/3, Everest 8,848 → 8,848.86 m,
prototype metre → speed-of-light metre, EU AI Act draft → in force, GDPR, WHO PHEIC, GPT-4 and Gemini 1.5 context
windows, Ubuntu/Java/Kubernetes/Django/Vite/Tailwind releases…).

Per family, claims are written for the categories in the spec:

| Category | n | Construction |
|---|---|---|
| current information | 19 | Claim states the current documented state; two authoritative sources agree |
| outdated information | 19 | Claim asserts a superseded state as current; newer authoritative docs exist |
| partially outdated | 12 | Part of the claim survives (support window / precision), part is superseded |
| contradictory information | 26 | 19 direct falsehoods + 7 second-shape falsehoods (numeric/date/scope) |
| conflicting sources | 19 | Two credible supports, two credible denials at the same date; recency cannot resolve |
| insufficient evidence | 19 | Private operational detail no public source can address |

Labels come from construction semantics ("this claim asserts a superseded release"), never from engine output.
Fixtures carry real publication dates, source types and URLs so the temporal engine has something honest to reason
about. `notes` on every row records why the label is what it is.

## 3. Metrics

Accuracy, macro precision/recall/F1, per-class precision/recall/F1, outdated-detection recall (either
`OUTDATED` or `PARTIALLY_OUTDATED` on a gold outdated claim), citation correctness (every cited URL must be one of
the fixture URLs actually retrieved), evidence coverage (share of claims with ≥1 citation, excluding the
insufficient-evidence category by design), false verification rate, latency and cost per investigation.

## 4. Achieved results (run `20261107T052417Z`, 114 claims, simulated mode)

| Metric | EPOCH | Baseline | Δ |
|---|---|---|---|
| Verdict accuracy | **0.825** | 0.325 | +0.500 |
| Macro precision | 0.854 | 0.123 | +0.731 |
| Macro recall | 0.818 | 0.325 | +0.494 |
| Macro F1 | **0.824** | 0.174 | +0.650 |
| Outdated detection recall | **0.871** | 0.000 | +0.871 |
| Citation correctness | **1.000** | 0.000 | +1.000 |
| Evidence coverage | 1.000 | 1.000 | 0.000 |
| False verification rate ↓ | **0.182** | 0.763 | −0.581 |
| Mean latency (pipeline) | 12.5 ms | — | — |
| Cost / investigation | $0.00 (deterministic mode) | — | — |

Per class:

| Verdict | precision | recall | F1 | n |
|---|---|---|---|---|
| VERIFIED | 0.818 | 0.947 | 0.878 | 19 |
| PARTIALLY_OUTDATED | 1.000 | 0.667 | 0.800 | 12 |
| OUTDATED | 0.682 | 0.789 | 0.732 | 19 |
| CONTRADICTED | 0.833 | 0.769 | 0.800 | 26 |
| UNVERIFIED | 0.792 | 1.000 | 0.884 | 19 |
| CONFLICTING | 1.000 | 0.737 | 0.849 | 19 |

Confusion (gold → predicted, non-zero cells):

```
VERIFIED            → VERIFIED 18, CONTRADICTED 1
PARTIALLY_OUTDATED  → PARTIALLY_OUTDATED 8, OUTDATED 4
OUTDATED            → OUTDATED 15, CONTRADICTED 2, VERIFIED 1, UNVERIFIED 1
CONTRADICTED        → CONTRADICTED 20, UNVERIFIED 4, OUTDATED 2
UNVERIFIED          → UNVERIFIED 19
CONFLICTING         → CONFLICTING 14, VERIFIED 3, OUTDATED 1, CONTRADICTED 1
```

Calibration: Platt-style fit `z = a + b·support + c·contradiction + 1.1·quality − 0.6`, `a=1.469, b=1.018,
c=0.0147`, **Brier 0.142** over 114 samples, stored in `app/services/research/calibration.json` and displayed in
the report.

### Experiment targets (explicitly *not* results)

These are goals, not claims. None is displayed as an achieved value anywhere in the product:

- ≥ 0.90 verdict accuracy on a live-retrieval benchmark of similar construction.
- ≥ 0.95 outdated-detection recall.
- False verification rate ≤ 0.05.
- Held-out (out-of-sample) Brier score ≤ 0.10.
- `PARTIALLY_OUTDATED` F1 ≥ 0.85.

## 5. Honest failure analysis

Observed error modes in this run, with causes:

1. **`PARTIALLY_OUTDATED` → `OUTDATED` (4 cases).** When a claim's surviving component has only one supporting
   source, support quality lands under the 0.33 partial threshold and the claim collapses into fully outdated.
   This is the weakest boundary in the engine.
2. **`CONFLICTING` → `VERIFIED` (3 cases).** A denial phrased as cessation ("no longer a supported release")
   can be read as agreement when the claim itself is negative. Polarity is classified as *denial* vs *cessation*
   to reduce this, but absolute vs. bounded negation remains genuinely hard without world knowledge.
3. **`CONTRADICTED` → `UNVERIFIED` (4 cases).** Claims about a *reported* state ("the documentation states
   that…") sometimes fail the subject gate: the claim's entities are about the reporting act rather than the
   subject, so evidence about the subject is filtered as context.
4. **`VERIFIED` → `CONTRADICTED` (1 case).** A near-duplicate figure within 2% tolerance plus an unrelated
   supersession cue in the same passage tips one claim the wrong way.

## 6. Reproducing

```bash
cd backend
python benchmark/build_dataset.py                      # writes benchmark/dataset.jsonl (114 rows)
python benchmark/run_benchmark.py                      # runs, prints the table, writes results/
python benchmark/run_benchmark.py --limit 30           # quick subset
python benchmark/run_benchmark.py --persist            # also writes benchmark_results rows to the app DB
python benchmark/run_benchmark.py --fit-calibration    # refits calibration.json from this run
python benchmark/run_benchmark.py --live               # use configured live providers (non-reproducible)
```

Artefacts: `benchmark/results/run_<id>.json` (per-claim predictions with explanations and cited URLs) and
`benchmark/results/latest.json` (read by `GET /api/v1/benchmark/latest` and rendered on the landing page).

The benchmark runs against an isolated temporary SQLite database and never pollutes the application's research
history (`--persist` writes only the two `benchmark_results` rows to the app database).

## 7. Known limitations of this evaluation

- Retrieval is deterministic, so retrieval *quality* is not being measured here.
- Calibration is fitted in-sample on the same 114 claims that report the Brier score — optimistic by construction.
- The dataset is synthetic-but-fact-grounded: real facts, constructed claims. It is not a sample of user traffic.
- Latency and cost reflect deterministic mode (local CPU work, zero provider calls). Live-mode figures are
  reported by the observability page only when live providers are actually configured.
