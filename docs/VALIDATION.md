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
- Historical initial choice, since superseded: on 2026-10-08 the author selected the original repository name, public visibility and MIT for code, with public hosting of the ledger and authored paper/figures. The current policy offers no new open-source license; prior grants are addressed in [RIGHTS.md](../RIGHTS.md).

## Verified GitHub publication, 2026-10-08

- Public repository: [Sean-xzx/Affective-Sedimentation-LLM-Agent-CSAI-2026](https://github.com/Sean-xzx/Affective-Sedimentation-LLM-Agent-CSAI-2026), default branch `main`; the initial checked revision used MIT, while the current policy is all rights reserved with no new open-source grant. Owner, visibility and push permission were independently confirmed through Git credentials and the GitHub connector.
- Scientific publication checked at commit `d65cef45ef87cffbc35ee03f7e9f82463ec292dd`. Subsequent publication documentation and ignore-rule changes do not modify scientific code, data or artifacts.
- Remote tree: all 92 selected files present; downloaded file bytes match the local selected package. GitHub-rendered English and Chinese README pages include reciprocal links and the correct repository name. No README image assets are required; the demo output is shown as text.
- [GitHub Actions run](https://github.com/Sean-xzx/Affective-Sedimentation-LLM-Agent-CSAI-2026/actions/runs/37725321131): both jobs completed successfully with Python 3.11.9. Ubuntu 24.04.5: **277 passed in 54.85 seconds**. Windows Server 2025: **277 passed in 83.32 seconds**. Dependency installation, documentation, mock demo, locked statistics and pinned-tokenizer preparation also passed in both jobs.
- Independent clone fetched from GitHub into a new directory, with a newly created virtual environment and independently downloaded tokenizer cache: **277 passed in 70.49 seconds** on local Windows. All quick-start checks passed; `pip check` found no broken requirements.
- After the complete remote-clone suite, all 56 protected public files still matched their pre-publication SHA-256 values. Regression tests rebuild identical statistical artifacts and emit two auxiliary SVGs, which are excluded from the published package and ignored in Git.
- Latest documentation checks: **39 local links**, equivalent bilingual commands and recorded result values.
- The original workspace retains its history and internal files. A private pre-edit archive and Git bundle are outside the project and were not uploaded. Selected public history was also scanned for recognized credential/private-key patterns; no match was found. No private credentials, environment, backup or tokenizer cache were published.

## Repository name and rights-policy update, 2026-10-08

- The owner requested name `Affective-Sedimentation-LLM-Agent-CSAI-2026`, continued public visibility, all rights reserved and prior written permission for other uses. This supersedes the current MIT offering without purporting to revoke historical grants.
- The current MIT `LICENSE` file was removed; [RIGHTS.md](../RIGHTS.md) is a rights notice, not an open-source license. README contribution invitations and the reproduction guide's permission to make code changes were removed. Reproduction commands now require prior written permission.
- Access inspection before the update found only `Sean-xzx` with write/admin access, no other collaborators, no open pull requests and zero forks. The owner retains write access; public GitHub fork rights and previously acquired MIT rights cannot be excluded by this update.
- Scientific code, data, formulas, constants, manifests and paper bytes are unchanged. The original complete private snapshot is retained, and a new private Git-bundle/document snapshot preserves the state immediately before this update. Git history is preserved.

## Explicitly outside the validated scope

- No live Qwen requests or paid operations were made. Availability and reproducibility of the historical hosted snapshot are unverified.
- macOS, other Python versions and environments beyond those listed below are not tested.
- The current paper is six pages, but paper-readiness checks and human citation/submission review are not claimed complete.
- No model training, new behavioral sampling or regenerated authored artwork is performed.
- Byte integrity of frozen data/code is distinct from statistical reproduction and from PDF recompilation.
