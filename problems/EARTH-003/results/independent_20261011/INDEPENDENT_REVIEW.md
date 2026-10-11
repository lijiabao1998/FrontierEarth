# Fourth batch independent artifact review

Verdict: **ARTIFACT_REVIEW_PASS**. Reviewed by the separate `/root/independent_review` session on 2026-10-11 UTC. No material artifact or claim-boundary blocker was found in the saved first attempts. This report audits static code, saved files, raw outputs, command records, and byte identity. The reviewer did not execute scientific functions, import author or harness modules, rerun a verifier, or perform a second experimental replay. This is not external peer review or certification of the broader BIO-001 or EARTH-003 research claims.

## Files and frozen identity

Reviewed the actual per-repository `problems/<PID>/experiments/independent_20261011/` protocol, verifier, common code, admission guard, bounded runner, source manifest and references, and `results/independent_20261011/attempt-1/` launch, execution, result, stdout, stderr and saved case artifacts. The preceding static signoff is `evidence/FOURTH_STATIC_SIGNOFF.json` (SHA256 `90d4d5ecd31b6d23741c4352a62742b50d3ced01a56abb9738f71a778318236d`). All 12 signed per-repository core/protocol/manifest hashes were rechecked unchanged during this artifact review.

BIO source is `f88f06450e40379deba5de3ef67213536c0d9641`; all 11 source snapshots match the source manifest sizes and SHA256 values and the original base Git blobs. Its protocol SHA256 is `91d9ecb5b4b05d5974b8cc6fce3952da194048e4aedc733c08898adb270c0020`. All 27 recorded execution inputs match disk bytes and frozen Git blobs at protocol commit `65e38c5f5bf05f819965880f46654157c4101006`.

EARTH source is `9c903c7734d5a84323ffbc5e55dbd8ccc7df5fa1`; all 19 snapshots likewise match their manifest and original Git blobs. Its protocol SHA256 is `6de99d7e3359e06113de0148622f9a715ad8781d25baaebcb9cdd5e27829cada`. All 35 execution inputs match disk bytes and frozen Git blobs at protocol commit `28defcec12023360c3c32e8678a642d19968a7b2`.

The audited tracked diff from each pinned base contained additions for this round and no changes to original tracked files. This statement concerns the audited repository diff, not an exhaustive audit of unrelated filesystem contents.

## Admission, commands and resource evidence

Saved public-body readbacks contain the posted bounded scopes and budgets. BIO PR2 comment `6113364102` was created at 20:24:36 UTC; EARTH PR4 comment `6113364775` at 20:24:40 UTC. The seal command completed with exit 0 at 20:27:30.955525. Official admission records are BIO 20:27:33.126829 and EARTH 20:27:35.286385 UTC; the protocol-commit command completed at 20:27:39.959710. These precede both launches. Readback, admission and freeze evidence was checked locally; this reviewer made no external write.

| Saved attempt | Launch UTC | Finish UTC | Child wall seconds | Child exit |
|---|---|---|---:|---:|
| BIO-001 attempt-1 | 20:27:54.137003 | 20:27:58.240267 | 3.9380266000225674 | 0 |
| EARTH-003 attempt-1 | 20:28:02.878564 | 20:28:04.209139 | 1.1637182999984361 | 0 |

Launch records use timezone offsets; the table converts them to UTC. Saved commands run Python with `-X utf8`, the new verifier, and explicit `--repo`, `--round`, and new-attempt `--output` paths. Both execution records report affinity mask 1, CPU count 1, inherited child affinity, USD 0, no timeout and no replay. Their intervals do not overlap and both finish before the fixed 20:36:38 UTC deadline. The static guard/runner review plus these records support the bounded-run claim; they are not an independent process-monitor trace.

During the initial artifact read, round lifecycle metadata was still ADMITTED with final collection pending. This report certifies saved attempt consistency, not that later FINISHED records or result commits have already been verified. Those final metadata/commit checks can be appended without scientific execution.

## BIO-001 evidence and limits

Saved verdict is `INDEPENDENT_METADATA_17_FIELDS_PASS_WITH_LEGACY_COVERAGE_GAP`; `all_criteria_passed` is strict boolean true. Independent metadata has the frozen 17 fields, all matching protocol expectations. Baseline and anchor checks accept with empty errors and gap 0. The normal anchors report 111445 retained metadata rows, class counts 57831 single / 41759 dual / 11855 control, 105 single perturbations, median 495 and order-statistic indices 10 and 94. The selected values are good coverage 104507, single cells 57831, 131 distinct dual perturbations; per-single min/max/p10/p90 113/1960/241/874; the five smallest genes PLK4/HES7/ZBTB10/NIT1/CITED1 at 113/126/162/192/215; and the five largest KLF1/BAK1/CEBPE/UBASH3B/ETS2 at 1960/1457/1233/1202/1201.

The 17 ordered fixed `PLUS_ONE_...` controls match the protocol names exactly. Every saved `claimed.json` is the frozen author-result object with only its specified selected leaf incremented by one. Every corresponding new-checker artifact has `independent_accepted` false, `independent_rejected` true and nonempty integer-mismatch errors. Missing, duplicate or substituted controls cannot satisfy the fixed-name/count aggregate contract.

The 18 legacy cases (CLEAN plus those 17 controls) were reviewed as saved artifacts. Each command uses the exact-byte legacy snapshot, a new case-local `--result`, and a new case-local `--output`. Each command record agrees with the aggregate result, has exit 0, and has a persisted checker result structurally equal to parsed raw stdout. Each contains the six fixed checks, all strict boolean true, and verdict `INDEPENDENT_CHECK_MATCH`. Thus the observed legacy acceptance count of 17 mutated claims is supported by actual saved case evidence, rather than the earlier static prediction alone. The new checker rejects those same selected-field mutations.

This is a bounded coverage gap in the legacy metadata checker. It does not show that its six checked fields are incorrect, or establish biological mechanism, intervention generalization, expression coverage, or a comprehensive metadata audit. The 1.1 GB expression artifact was not obtained. Existing INCONCLUSIVE and EXPLORATORY_UNVERIFIED findings remain retained; no broad research status is upgraded.

## EARTH-003 evidence and limits

Saved verdict is `INDEPENDENT_ARCHIVED_CALENDAR_LAG_PASS`; `all_criteria_passed` is strict boolean true. The saved independent artifact reports 27 archived catalog events, 730 daily rows and 24 monthly rows. Its sufficient-statistic mapping agrees exactly with the aggregate result. There are exactly 26 lag fields: 20 numeric and six null months (2017-01, 2017-04, 2017-09, 2018-02, 2018-06, 2018-10). Baseline and anchor checks accept with empty errors; the reported maximum numeric gap is `1.3877787807814457e-17`, below the frozen `1e-12` tolerance.

Static code uses the frozen global-mean, adjacent, noncyclic Fraction formula `[N^2 A + N K E - (N+1) K^2] / [N K (N-K)]`, with null handling at K=0 or N. This reviewer checked the formula and saved consistency but did not recompute catalog statistics or lag values.

All 28 controls have the exact frozen names/order, strict `rejected` true, saved `semantic-check.json` acceptance false, and nonempty semantic errors agreeing with the aggregate result. Each saved full JSON/daily CSV/monthly CSV was compared to the frozen baseline with only its declared mutation; this verifies mutation identity without rerunning the scientific checker. The 20 numeric cases alter the designated lag by +0.01 and synchronize its CSV representation where applicable. The six null cases replace only the designated null by zero and synchronize CSV, producing semantic null errors.

`DAILY_MARCH23_TO24` changes exactly the two designated daily rows (2018-03-23 count/occurrence 1 to 0, 2018-03-24 0 to 1), preserving the other fields, result JSON and monthly CSV. Saved semantic errors identify all four daily count/occurrence mismatches. `MONTHLY_ONLY_MARCH_LAG_PLUS_001` preserves JSON/daily data and changes only March 2018 monthly CSV lag from `0.2584485407066052` to `0.26844854070660523`; saved errors identify both monthly-value and JSON/CSV cross-file mismatches. These are semantic rejection evidence, not merely changed-file hash rejection.

The legacy EARTH checker/bootstrap was not invoked by this experiment; its saved execution flag is false and the new code does not call or import it. This review does not infer completeness or future skill from 27 archived events. Original no-improvement/baseline limitations, catalog vintage and archived-hindcast scope remain; this is not a forecast or hazard claim.

## Raw outputs, warnings and evidence hashes

Both raw stdout documents equal their documented summary projections of the full result JSON. BIO exposes 17 fields, 17 new rejections and 17 legacy acceptances; EARTH exposes 26/20/6 lag counts and 28 rejections. Omitted detailed fields remain in full result and case artifacts; stdout is not misrepresented as the entire evidence record.

Both top-level stderr files are **nonempty (98 bytes)** and contain the Python runtime-location warning `Failed to find real location of C:\Users\Leon1\AppData\Local\Programs\Python\Python313\python.exe`. All 18 legacy-case stderr files retain the same warning. Saved exits are 0 with complete JSON artifacts; the warning is disclosed rather than described as empty stderr. No saved scientific traceback was observed.

| Artifact | SHA256 |
|---|---|
| BIO result.json | `6dedec5d2c40b7fd0291402a34943b8c27264787ce766709d1cbf74f699c346c` |
| BIO stdout.txt | `9bce76ef207981a8e0046b0fb432dec40f85089740cfa5e0f1612fee1a90c498` |
| EARTH result.json | `67ec8badcf485f74cb6114af4dc4cd4d680ab83aafbdd4e0da5394ab07be6d13` |
| EARTH stdout.txt | `86492c231bce3a686225200963fa2c1dbf3f9513190a8e3905123d720a276d86` |
| Both top-level stderr.txt | `8531d820d22f5cdadd3f00c00d592e13c211ecf2ec0fe113c1931848a5ccc97d` |

Source reading limitations remain disclosed in the frozen protocols/web trace: BIO GEO recaptcha, Science/PMC request failures and partial abstract/subscription-preview material; EARTH initial collection/FAQ request failures. Saved primary-source summaries and archived references support provenance within those limits. This review does not claim complete literature access, novelty, absence of retractions, independent licensing determination or fresh catalog completeness.

Artifact review blockers: **none**. Remaining coordinator work at review time: finalize lifecycle/evidence manifests, preserve this review, make local result commits and audit committed bytes. Publication/CI metadata may follow; no further scientific run is authorized by this report.
