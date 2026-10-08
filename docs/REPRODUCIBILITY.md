# Reproducibility contract

## Three distinct levels

1. **Functionality:** `python -m tools.reproduce demo` checks numerical assertions, one deterministic development history and two mocked runner observations. It uses no external service, writes no scientific data and is not evidence of a behavioral effect.
2. **Recorded-result reproduction:** `python -m tools.reproduce verify` checks the public scientific file hashes, recomputes locked primary statistics within the original 1e-12 tolerance and reproduces the secondary diagnostic report. The raw ledger and manifests are required. This does not obtain new model responses.
3. **Fresh hosted collection:** not performed, not promised and not part of CI. It would require an eligible hosted model snapshot, credentials, a paid request budget and explicit scientific authorization. Provider outputs can drift, and temperature zero does not guarantee identical repeats.

## Installation and offline resources

Use Python 3.11.9 in a fresh environment and install `requirements-public.lock` as shown in the READMEs. The original dependency files stay untouched because a regression test checks the scientific lock hash. The additional publication lock includes the packages needed by PDF inspection and plotting.

Run `python -m tools.prepare_resources` once while online. It downloads the exact revision and four files specified in [resources.json](resources.json), verifies every SHA-256 and creates a project-local default-revision alias. No weights or remote Python files are downloaded. The test wrapper supplies `HF_HOME`, `HF_HUB_CACHE` and `HF_HUB_OFFLINE=1` to its subprocess, so it does not depend on the author's personal Hugging Face cache.

For a machine without network access, prepare a clone elsewhere, then copy its `.cache/huggingface/` into the same relative location in the offline clone. Install the pinned Python packages from a locally prepared wheel directory. The cache is excluded from Git. The demo and primary-result verification themselves do not need tokenizer resources.

## Scientific inputs and analysis units

- Master seed: `20260804`; event count: 200; beta: 0.
- Formal N history seeds: `[14, 24, 5, 18, 22, 13, 1, 26]`; development seed: 1000.
- Histories use fixed action-count multisets, largest-remainder block allocation and SHA-256-derived NumPy PCG64 permutations. The seeds vary ordering/memory realization rather than the overall event composition.
- There are 6 development probes and 15 formal probes, all authored in English. N replays 3 deterministically selected formal probes per axis.
- E has 180 observations, producing 90 AB/BA pairs and 15 primary item units. Its denominator uses the three-decimal values the model actually saw.
- N has 576 observations, producing 288 AB/BA pairs and 8 primary seed units. Signed contrasts are averaged over six directions and their selected items before averaging seeds.
- Bootstrap repetitions: 5000. E resamples items within axes; N resamples seed and replay-item clusters. Results describe finite-grid sensitivity, not population coverage.
- Exact sign-flip tests enumerate the predefined units; zeros limit attainable resolution. Axis-wise tests use Holm correction. The separate engineering minimum effect size is 0.10 for both E and N in their respective units.
- The ledger has 836 recorded rows, including 80 development/stability rows excluded from inference. The stored ledger contains no error rows or technical retries.

See the original [protocol](../affective-sedimentation-csai-2026-sprint-final.zh.md), [configuration](../configs/sprint_20260810.yaml), [results](../reports/final_results.json) and [recorded deviations](../reports/deviations.md) for precise definitions and freeze history.

## Expected results and file integrity

Verification expects theta_E `0.26775524691778746`, p_E `0.015625`, theta_N `0.10416666666666666`, p_N `0.00390625` and the complete secondary report. Both primary gate suites pass; E axis-wise Holm rejections are `[false, false, false]`.

The raw SHA-256 is `13c9588a802a4980a75fdb27d1d71b61e3010fe7fd9c19cb54ceeaf8dff4ca87`. The sealed analysis hash is `3f4b63f49fdedba1e49c98ffcf41cd370d2f87fb72604086c18248c41c6eb9ed`. [publication_manifest.json](publication_manifest.json) records exact public scientific file bytes and the local source commit. The GitHub publication commit is separate from the historical scientific source commits recorded in the ledger and manifests.

The original freeze manifest intentionally retains two null fields and an older dependency hash. Later analysis hashes were sealed elsewhere; correcting the old manifest would change the experiment record. The safe verifier does not rewrite it. `.gitattributes` disables newline conversion for scientific files so a Windows/Linux checkout preserves hashes.

## Analysis exports and paper compilation

The safe verifier leaves all scientific artifacts unchanged. The original regression suite calls the analysis rebuild: protected result files finish with identical bytes, and two auxiliary `fig_theta_e.svg` / `fig_theta_n.svg` plots are generated and ignored. Run the suite in a disposable clone if temporary writes are unacceptable. Legacy commands such as `python -m tools.analysis_core rebuild`, `python -m tools.diagnostics` and the figure exporters write outputs. Use a disposable clone if you want to try them. `tools/export_locked_figures.py` consumes plot-ready data and diagnostics and wraps authored raster artwork; it does not regenerate the artistic source of every paper figure.

To compile a **copy** of the standalone paper source, use a TeX installation containing acmart and the required packages:

```sh
cd paper
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Font/package versions and PDF metadata can change bytes. Rebuilding the PDF is not a byte-identity promise. The preserved paper PDF has six pages; the old `reports/paper_pdf_sha256.txt` describes a different PDF revision and is retained as a historical record. The public manifest identifies the PDF actually shipped.

`python -m tools.r7_gate --quick --no-write` is a separate paper-readiness check, not the scientific regression suite. Citation verification, image resolution, submission checkboxes and fresh TeX logs can prevent it passing. Historical reports do not certify the current submission. The bylined paper and some older anonymous-submission notes describe different versions; the current paper source is authoritative for its actual layout.

## Updating the project

Make publication-tool/documentation changes on a new branch, run the quick-start checks and open a pull request. Do not edit protected scientific inputs or recompute history manifests to conceal a mismatch. Preserve the baseline and propose a separate experiment for scientific changes. When reporting failures, include sanitized commands/output, Python version, OS and the public commit SHA.
