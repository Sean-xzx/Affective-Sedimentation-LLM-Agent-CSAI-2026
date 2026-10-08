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

- Fresh publication environment: 49 pinned packages, installed independently of the original virtual environment; four tokenizer files downloaded into a new project-local cache and SHA-256 verified.
- Publication suite in that environment: **276 passed in 95.50 seconds** (274 original tests plus two publication tests), with the tokenizer offline.
- Credential-free demo: PASS; two mock observations, zero live API attempts, numerical half-times 1/8/69.
- Read-only scientific reproduction: PASS; 56 protected files, all locked primary statistics and the full stored secondary diagnostic report.
- Documentation: PASS; 36 local links and matching bilingual executable examples and result values.
- Selected 91-file publication snapshot cloned into an independent directory: demo, scientific verification and documentation checks passed; tokenizer resources were independently prepared there. Its first full suite found one portability defect: the paper-QA tool crashed on the deliberately excluded local compile log. The non-scientific QA tool now reports that missing prerequisite as a failed paper gate, with one additional regression test. Final clean-copy result: **277 passed in 154.09 seconds** (274 baseline tests plus one QA-prerequisite test and two publication tests).
- Paper compiled in a separate disposable directory: all four documented TeX/BibTeX steps exited 0 and produced a six-page PDF. No shipped source or PDF was overwritten. The local TeX compiler is MiKTeX; the build explicitly disabled automatic package installation.
- Git credential authentication and the connected GitHub plugin both identify the intended owner, Sean-xzx. A pattern scan inspected 411 historical blobs and found no recognized credential patterns. This does not replace review of the selected publication contents.
- The author selected repository name `affective-sedimentation-llm-agent`, public visibility, MIT for code, and public distribution of the experiment ledger and authored paper/figures on 2026-10-08. Repository creation, push, remote clone and remote CI are pending; no upload is claimed yet.

## Explicitly outside the validated scope

- No live Qwen requests or paid operations were made. Availability and reproducibility of the historical hosted snapshot are unverified.
- Linux is a CI target until an actual remote run completes. macOS is not tested.
- The current paper is six pages, but paper-readiness checks and human citation/submission review are not claimed complete.
- No model training, new behavioral sampling or regenerated authored artwork is performed.
- Byte integrity of frozen data/code is distinct from statistical reproduction and from PDF recompilation.
