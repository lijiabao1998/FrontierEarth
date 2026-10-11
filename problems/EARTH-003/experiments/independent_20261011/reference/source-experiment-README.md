# EARTH-003: small historical Poisson occurrence baseline

This is a first baseline reproduction on **27 real public catalog events**, not a live forecast, warning system, new predictor or completion of EARTH-003. The parent card remains OPEN.

## Frozen scope

- USGS ComCat, earthquake type, preferred magnitude >=4.0; inclusive latitude 32..42 and longitude -125..-114; depth -100..1000 km.
- UTC calendar days: calibration 2017, untouched test 2018. The API's inclusive end timestamp is locally filtered to the exclusive 2019-01-01 boundary.
- Fit lambda from **event counts**, then daily occurrence probability p=1-exp(-lambda). Compare with calibration **active-day** Bernoulli climatology, p=0 and p=0.5.
- No random train/test split, hyperparameter search, test refit, spatial transfer or declustering.
- Brier and clipped natural-log Bernoulli loss; one occupied reliability bin per constant model. Lower scores are better.

The pre-analysis specification is in `runs/20261009T105820460779Z-gpt-EARTH-003/frozen-spec.json`; the admission timestamp is in `round.json`. Its meaning and model metrics were fixed before retrieval. See `chronology.json` for the metadata-only claim update and the implementation-level RNG detail not included in the original specification.

## Results

Calibration: 11 events on 11 of 365 days. Test: 16 events on 16 of 365 days. Neither period contains a multiple-event day at this threshold.

| Constant model | p | Test Brier | Test log loss |
|---|---:|---:|---:|
| Poisson event-rate baseline | 0.0296873951 | 0.0421142273 | 0.1829872107 |
| Bernoulli active-day climatology | 0.0301369863 | 0.0421017076 | 0.1827714713 |
| Zero probability | 0 | 0.0438356164 | 1.2112228434 |
| Half probability | 0.5 | 0.25 | 0.6931471806 |

Observed test occurrence frequency is 0.0438356164. The Poisson calibration gap (observed minus predicted) is 0.0141482213. Its descriptive 30-day circular-block 95% percentile intervals are Brier [0.0266518951, 0.0601536149], log loss [0.1256683766, 0.2498591839], calibration gap [-0.0022901348, 0.0333263035]. These intervals condition on the estimated calibration probabilities: they omit calibration-parameter uncertainty and need not have nominal coverage under long dependence or nonstationarity.

Poisson does not improve on the Bernoulli comparator in this tiny holdout. The difference is not an independently established performance effect. A constant forecast provides a single reliability point, not a meaningful multi-bin reliability curve. Monthly records are diagnostics, not independent replications. At the fixed diagnostic threshold p>=0.5, the Poisson model marks zero days and misses every event day; this is not a safety threshold or an operational policy recommendation. Lead time is not applicable.

## Reproduce offline

Run from the repository root with Python 3.12 (tested 3.12.14), standard library only:

```sh
python problems/EARTH-003/experiments/catalog-poisson/test_baseline.py
python problems/EARTH-003/experiments/catalog-poisson/baseline.py
```

The program checks the raw SHA-256 against retrieval metadata, checks the independent count endpoint, validates required fields/duplicates, and recreates results.json, daily.csv, monthly.csv. Reference stdout is archived. `daily.csv` includes calibration fitted constants for audit only; calibration rows are not held-out forecasts and are not included in test scores.

Optional new acquisition (public data may have changed; preserve the archived snapshot for exact reproduction):

```sh
python problems/EARTH-003/experiments/catalog-poisson/retrieve.py
```

Retrieval uses two unauthenticated requests, each capped at 25 seconds and 2 MB. The original process had a 60-second shell cap. The analysis process had a 30-second cap. There is no added package or service dependency.

## Uncertainty implementation

Python 3.12.14 `random.Random(196003)` (MT19937). Each of 2,000 sequential resamples draws 13 starts using `randrange(365)`, expands each to 30 consecutive indices modulo365, concatenates, and truncates to365. No reseeding between resamples. Probabilities stay fixed. Each percentile uses linear interpolation at (n-1)q. Source fixed this construction before its first numerical result; the original JSON froze block size, resample count, seed and quantiles, but did not name the RNG algorithm. This incompleteness is disclosed rather than represented as a fully preregistered RNG choice.

## Checks and limitations

14 author tests cover analytic scores, event/active-day distinction, timezone/split/end/magnitude/spatial boundaries, duplicates, missing/nonfinite values, block construction, quantiles, and an intentionally wrong evaluator. Independent review is recorded separately, with its precise scope. Governance validates metadata/path contracts, not scientific truth.

Missing raw fields: horizontalError 2/27 and magError 25/27; no imputation. Magnitudes: 25 mw, 2 ml; no harmonization. Networks: nc15, ci10, nn2. All statuses are reviewed, which does not establish completeness. Catalog threshold uncertainty cannot be quantified reliably from these sparse missing error fields. Zero-filled days mean no matching recorded event, not certified absence of earthquakes.

Magnitude completeness, network drift, detection loss after larger earthquakes, revisions and dependence remain unverified. This current snapshot contains post-event revisions. Absence of multiple-event days does not establish earthquake independence. There is only one region and one held-out year. No external time/region replication, ground-motion model, prospective evaluation or physical-mechanism test was performed. No scientific novelty is claimed.

Raw data and redistribution basis are under `problems/EARTH-003/results/catalog-poisson/DATA-LICENSE.md`. Source audit, budget and failed access/authorization attempts are preserved in the round directory. Original deadline: 2026-10-09 11:27 UTC; zero spending.

## Independent computational review

A separate reviewer implemented filtering, calendar aggregation, all four scores and all bootstrap intervals without importing author code, using affine sufficient-statistic formulas. 145 numerical checks passed, maximum difference 4.44e-16. A +0.001 score tamper and a duplicate event ID with updated hash were both rejected. Reviewer saw the original results; review was not blind and RNG details were supplied after the first result. This is independent computational checking, not independent empirical validation. Completeness, vintage availability, lag-autocorrelation estimator and utility remain outside this check.

```sh
python problems/EARTH-003/experiments/catalog-poisson/independent-review/verify_earth.py problems/EARTH-003/results/catalog-poisson
```

Reviewer source is copied unchanged. The original independent-review.json and negative-controls.json are in the result directory. A local replay reproduces the reviewer JSON exactly.
