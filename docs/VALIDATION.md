# Validation evidence

This file records measured checks and their limits, not a support promise.

## Local baseline, 2026-10-08

- Platform: Windows, Python 3.11.9.
- Original scientific regression suite: **274 passed in 69.40 seconds**.
- Original `tools.verify_paper_numbers`: all locked fields matched rebuilt results within tolerance.
- Recorded ledger: 836 rows, 756 formal observations, no logged errors or retries.
- A fresh isolated Python environment installed all dependencies from the original requirements plus missing publication packages. A new tokenizer cache was downloaded independently of the author's cache.
- An initial offline test run failed because a pinned tokenizer snapshot had no default-revision cache alias. The publication resource-preparation tool explicitly creates that alias after integrity checks; subsequent results are recorded below.
- Core Python, frozen configuration/materials, raw data, primary/secondary analysis and paper files are protected by a pre-edit SHA-256 inventory.

## Publication checks

Publication demo, read-only reproduction, independent-cache regression tests, selected-release-clone checks and remote CI are pending execution. This section will be updated with actual results before publication.

## Explicitly outside the validated scope

- No live Qwen requests or paid operations were made. Availability and reproducibility of the historical hosted snapshot are unverified.
- Linux is a CI target until an actual remote run completes. macOS is not tested.
- The current paper is six pages, but paper-readiness checks and human citation/submission review are not claimed complete.
- No model training, new behavioral sampling or regenerated authored artwork is performed.
- Byte integrity of frozen data/code is distinct from statistical reproduction and from PDF recompilation.
