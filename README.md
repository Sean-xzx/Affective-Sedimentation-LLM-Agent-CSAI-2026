# Affective Sedimentation for LLM Agents

[简体中文](README.zh-CN.md) · **[Paper PDF](paper/main.pdf)** · [Reproduction details](docs/REPRODUCIBILITY.md) · [Architecture](docs/ARCHITECTURE.md)

> **Accepted at CSAI 2026 — not yet published.**
> [Read the repository manuscript (PDF)](paper/main.pdf). This links to the file in this repository, not a publisher page.

**Can accumulated interaction history influence an LLM agent's choices through an explicit affect-state interface?** This project investigates that question with a three-layer numerical controller and controlled behavioral comparisons.

Paper: **Affective Sedimentation: A Controlled Proof-of-Mechanism for History-Driven Behavioral Modulation in an LLM Agent** — Zexian Xiong and Yan Li.

## Research at a glance

- **Mechanism:** interaction events update fast, medium and slow P/A/D states. The controller computes these states outside the LLM, then supplies the resulting state and event memory in its prompt.
- **Controlled comparisons:** Experiment E tests affect labels against numerically identical sensor metadata. Experiment N tests history-derived state against zero state while holding event memory fixed.
- **Recorded evidence:** 756 formal observations and 80 development/stability observations are preserved with the code, manifests and analyses. Both primary gate suites pass on the frozen grid; none of the E axis-wise tests passes Holm correction.

The repository provides the controller, deterministic histories, fixed probes, Qwen adapter and recorded-result analysis. It is intended for developers studying agent-state interfaces and reproducible experiments. The first run uses a mock provider and requires no API key, GPU or paid model requests.

**Start here:** [read the paper](paper/main.pdf) for the research, follow [Quick start](#quick-start) for the demo and result reproduction, or read [Architecture](docs/ARCHITECTURE.md) for the module relationships.

## Recorded results

The controller updates fast, medium and slow P/A/D states outside the model. Experiment E compares affect-labeled endpoints with numerically identical sensor metadata. Experiment N compares history-derived state with zero state while keeping event memory identical. The interpretive order is D (numerical checks), E, then N.

| Recorded quantity | Value |
|---|---:|
| Formal E observations | 180 |
| Formal N observations | 576 |
| Development/stability observations | 80 |
| Total ledger records | 836 |
| E effect, CS per rendered-z | 0.26775524691778746 |
| E one-sided sign-flip p | 0.015625 |
| N effect, direction-corrected CS | 0.10416666666666666 |
| N one-sided sign-flip p | 0.00390625 |

Both recorded primary gate suites pass. None of the E axis-wise tests passes Holm correction. These are results on a frozen finite grid, not population guarantees. Effects are asymmetric and activation-dominated; saturated probes, one model snapshot and a short collection window limit interpretation. The experiment provides no evidence of internal emotion or personality formation.

## Requirements

- Python **3.11.9** is verified on local Windows and in GitHub Actions on Ubuntu 24.04.5 and Windows Server 2025. macOS is untested.
- No GPU, database, model weights, API key or paid service is required for the demo and recorded-result analysis.
- Internet is needed to clone, install dependencies and fetch four proxy-tokenizer files for the full test suite. After resource preparation, the suite runs offline.
- Allow several hundred MB for the Python environment and about 15 MB for tokenizer resources. Local regression tests took about 1-3 minutes; timing varies by machine.
- Paper compilation additionally requires a TeX distribution containing `acmart`, `pdflatex` and `bibtex`; it is separate from statistical reproduction.

## Quick start

Clone this repository and enter its root:

```sh
git clone https://github.com/Sean-xzx/affective-sedimentation-llm-agent.git
cd affective-sedimentation-llm-agent
python -m venv .venv
```

Activate on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or on Linux/macOS:

```sh
source .venv/bin/activate
```

If PowerShell activation is restricted, use `.\.venv\Scripts\python.exe` in place of `python`; changing system execution policy is unnecessary. Then run:

```sh
python -m pip install -r requirements-public.lock
python -m tools.reproduce demo
python -m tools.reproduce verify
python -m tools.prepare_resources
python -m tools.reproduce test
python -m tools.check_publication
```

The demo uses a mock completion function and writes its two records only to a temporary directory. It does not send model requests or change the scientific ledger. Expected milestones:

```text
Demo PASS: numerical controller, history, renderer and mock runner.
verify_paper_numbers: all locked fields match rebuild within tolerance
Verify PASS: ... protected files, locked statistics and secondary diagnostics.
Tokenizer ready: Qwen/Qwen3-0.6B @ c1899de289a04d12100db370d81485cdf75e47ca
```

The demo reports unit-step half-times `epsilon=1`, `m=8`, `s=69`, two mock observations and `live_api_attempts=0`. Verification must reproduce the table above and exit with status 0. The test command runs the original scientific suite plus publication-interface tests. See [validation evidence](docs/VALIDATION.md) for the measured pass count and verification limits.

## Configuration and resources

The frozen [configuration](configs/sprint_20260810.yaml) defines the 200-event histories, seed `20260804`, model identifier, request settings, thresholds and budgets. Do not alter it to repair a result or dependency problem. [Action mappings](materials/action_map.csv) and [21 probes](materials/sprint_probes.csv) are also frozen.

The recorded model identifier is `qwen3.7-flash-2026-07-15`. The offline tokenizer is a **proxy**, `Qwen/Qwen3-0.6B`, not model weights or a verified byte-identical tokenizer for that hosted snapshot. [Resource metadata](docs/resources.json) pins its revision and SHA-256 values. Preparation places it in ignored `.cache/huggingface/`; the test wrapper resolves the default tokenizer name to the verified local snapshot and disables network access.

The original `requirements.txt` and `requirements.lock` are retained byte-for-byte because their hashes are part of the experiment. `requirements-public.lock` adds the missing publication/test dependencies, including `pypdf`, `pandas` and `seaborn`, without rewriting the historical lock.

`.env.example` documents the optional `DASHSCOPE_API_KEY`. The adapter reads environment variables; importing the package does not load `.env`. No quick-start command requires credentials. Hosted collection can incur charges and was **not** rerun or verified in this publication task. There is deliberately no live collection command in the quick start.

## Structure and entry points

```text
configs/                 Frozen experiment configuration
materials/               Action map and development/formal probes
sprint/                  Controller, histories, renderer, adapter and runner
tools/                   Analysis, diagnostics, safe reproduction and checks
tests/sprint/            Original scientific regression suite
tests/publication/       Safe-demo and release-integrity tests
data/raw/                Recorded immutable JSONL ledger
data/derived/            Recorded analysis summary
reports/                 Frozen manifests, statistics and diagnostics
paper/                   Paper source, bibliography and figure resources
docs/                    Architecture, provenance, resources and validation
.github/workflows/       Offline reproducibility CI
```

The action map feeds deterministic histories; `dynamics.py` computes slow state; `renderer.py` writes state and memory into the prompt. `runner.py` combines probes, schedules and the provider, then appends request records. `tools/analysis_core.py` reads the ledger and randomization manifest to compute E/N statistics. `sprint/analysis.py` re-exports those functions. Secondary diagnostics and plotting tools explain the response structure; the paper consumes selected figures. [The architecture guide](docs/ARCHITECTURE.md) describes this flow and the distinction between frozen analysis and secondary diagnostics.

## Reproduction and development

- `python -m tools.reproduce demo`: numerical and mock-runner functionality; no tokenizer download or credentials.
- `python -m tools.reproduce verify`: read-only byte-integrity, locked-statistic and secondary-diagnostic reproduction.
- `python -m tools.prepare_resources`: network download of pinned tokenizer resources only.
- `python -m tools.reproduce test`: original regression tests and publication tests, with an offline tokenizer cache.
- `python -m tools.check_publication`: local documentation links and bilingual command/result parity.
- [Detailed reproduction guide](docs/REPRODUCIBILITY.md): sampling, seeds, units, hashes, paper compilation and artifact limits.

Some legacy analysis/export commands write into `reports/` or `paper/figures/`. Use a disposable clone when experimenting with them. The safe commands above do not change frozen scientific bytes after completion. Original regression tests rebuild identical result files and create two ignored helper SVGs; use a disposable clone if you need a completely write-free checkout. Git attributes preserve scientific bytes across platforms, since even a line-ending change can invalidate a recorded hash.

Contributions and reproducibility reports are welcome through [Issues](https://github.com/Sean-xzx/affective-sedimentation-llm-agent/issues) and pull requests. Include your OS, Python version, command and sanitized failure output. Never include API keys, private `.env` contents or personal logs. Preserve the scientific constants, core code and recorded data; proposed scientific changes belong in a clearly separate experiment, not a silent change to this release. No maintenance or hosted-service availability promise is made.

## Known limitations and troubleshooting

- Run module commands from the repository root. A missing module usually indicates the wrong directory or inactive environment.
- If tests cannot load the tokenizer, run resource preparation first; do not replace the proxy or relax material gates. See the detailed guide for offline copying.
- The original freeze manifest contains two null hash fields and a historical dependency hash. [Recorded deviations](reports/deviations.md) explain where later analysis hashes were sealed; do not rewrite that manifest.
- Historical submission reports may refer to earlier paper versions. Current PDF bytes, citation review status and image resolution must be reviewed independently before a submission. The old PDF hash lock does not identify the current PDF.
- Passing regression tests does not certify publication readiness. Citation verification and submission steps remain human tasks. The paper QA gate can fail while scientific reproduction passes.
- Windows symlink warnings and the absence of PyTorch/TensorFlow are harmless for this tokenizer-only workflow. The tested Windows/Linux environments are listed above; other systems and language versions require separate verification.

## Use conditions, sources and citation

Project code is available under the [MIT License](LICENSE). The author has authorized public distribution of the experiment ledger and authored paper/figures; these research resources retain their authors' rights and are not automatically relicensed as code. Consult [resource provenance](docs/RESOURCE_PROVENANCE.md) for scope and third-party conditions.

The engineered appraisal map attributes non-neutral OCC-to-PAD values to Gebhard and Kipp (2006), Table 2; methodological and related-work references are in [refs.bib](paper/refs.bib) and the [evidence table](paper/LITERATURE_EVIDENCE.md). The repository distributes no third-party paper PDFs or model weights. The bundled bibliography style declares public-domain status in its header.

When referring to this experiment, cite the paper by Zexian Xiong and Yan Li, **Affective Sedimentation: A Controlled Proof-of-Mechanism for History-Driven Behavioral Modulation in an LLM Agent**, and include the repository commit used. The authors confirm acceptance at CSAI 2026; the paper has not yet been published. The [repository manuscript PDF](paper/main.pdf) is available above. No publication DOI is asserted.
