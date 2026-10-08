# Affective-Sedimentation-LLM-Agent-CSAI-2026

[简体中文](README.zh-CN.md) · **[Paper PDF](paper/main.pdf)** · [Architecture](docs/ARCHITECTURE.md) · [Validation](docs/VALIDATION.md)

**Accepted at CSAI 2026; not yet published.** The PDF is the repository manuscript, not a publisher link.

**All rights reserved.** Public viewing only; other uses require prior written permission, subject to existing legal, platform and earlier-license rights. See [RIGHTS.md](RIGHTS.md).

## Value

This project separates event memory from an externally computed slow affect state, then tests whether state injection changes an LLM agent's choices. It addresses a research problem: distinguishing state-channel effects from the memory text an agent receives. Explicit controls make that interface measurable without changing model weights.

## My contribution

**Zexian Xiong — first author.** Primarily responsible for mechanism design and validation, with involvement throughout the research. **Yan Li — supervisor, second author and corresponding author**, providing research guidance. The implementation, data collection, analysis and paper are presented as collaborative research outputs.

| My confirmed contribution | Concrete work | Evidence |
|---|---|---|
| Mechanism design | Proposed and designed affective sedimentation: a three-layer external controller maintaining slow P/A/D state | [Controller](sprint/dynamics.py), [paper](paper/main.pdf) |
| Mechanism validation | Participated in designing preregistered experiments, the active sensor control and the same-memory zero-state ablation to evaluate choice changes | [Frozen design](configs/sprint_20260810.yaml), [renderer](sprint/renderer.py), [results](reports/final_results.json) |

## Method

`Interaction events → fast/medium/slow P/A/D state → prompt metadata → A/B choice → paired analysis`

P/A/D represents valence, activation and perceived control. State is computed outside the model and supplied as background metadata that names no action. The key design choice is separating event memory from state, so each channel can be examined with explicit controls:

- **E — label control:** affect-labeled state versus numerically identical sensor metadata, without event memory.
- **N — state ablation:** history-derived state versus zero state, with identical event memory.

AB/BA option counterbalancing, fixed seeds, frozen materials and predefined gates constrain the comparisons. These experiments test the prompt interface; they do not isolate a unique causal effect of the three-layer recurrence. The shared implementation combines NumPy dynamics, deterministic seeded histories, a six-worker Qwen runner, resumable logs and SHA-256 provenance. These provide auditable experiment execution. See the [architecture](docs/ARCHITECTURE.md).

## Results and evidence

**756 formal observations**, plus 80 development/stability observations: **836 preserved ledger records**. Both primary gate suites pass on the frozen grid. CS denotes the counterbalanced choice score.

| Experiment | Formal observations | Recorded effect | One-sided sign-flip p |
|---|---:|---:|---:|
| E: affect-minus-sensor slope, CS per rendered-z | 180 | 0.2678 | 0.015625 |
| N: direction-corrected full-minus-zero CS | 576 | 0.1042 | 0.00390625 |

<details>
<summary>Exact stored effect values</summary>

E: `0.26775524691778746`; N: `0.10416666666666666`.

</details>

[Raw ledger](data/raw/sprint_raw.jsonl) · [Locked results](reports/final_results.json) · [Paper PDF](paper/main.pdf)

**Scope:** one Qwen snapshot and authored forced-choice probes. Nine of 15 E probes are saturated; none of the E axis-wise tests passes Holm correction. N's mean only narrowly exceeds the fixed 0.10 engineering threshold, and three of eight seed means fall below it. These results support a limited interface-level effect, not internal emotion, persistent personality or cross-model generality.

**Engineering evidence:** the recorded validation includes **277 passing tests** on Windows and Ubuntu with Python 3.11.9. The credential-free demo checks the numerical controller and two mock observations; it demonstrates functionality, not a new behavioral result. [Validation details](docs/VALIDATION.md).

## Quick start

**Only for rights holders and users with prior written permission.** Commands document the authors' procedure and grant no execution, reuse or modification permission.

Python **3.11.9** is verified on local Windows, Ubuntu 24.04.5 and Windows Server 2025; macOS is untested. No GPU, API key, model weights or paid requests are needed below. Internet is needed for installation and four tokenizer files (about 15 MB); allow several hundred MB for the environment. Tests take roughly 1–3 minutes locally.

```sh
git clone https://github.com/Sean-xzx/Affective-Sedimentation-LLM-Agent-CSAI-2026.git
cd Affective-Sedimentation-LLM-Agent-CSAI-2026
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

If PowerShell activation is blocked, use `.\.venv\Scripts\python.exe` instead of `python`. Then run:

```sh
python -m pip install -r requirements-public.lock
python -m tools.reproduce demo
python -m tools.reproduce verify
python -m tools.prepare_resources
python -m tools.reproduce test
python -m tools.check_publication
```

Success means every command exits 0: `Demo PASS`, numerical half-times **1/8/69**, two mock observations and `live_api_attempts=0`; `Verify PASS` reproduces the results above and checks 56 protected files; resource preparation verifies four tokenizer hashes; the suite reports **277 passed**. Tests can rebuild identical result files and generate ignored helper SVGs, so use a disposable clone if temporary writes are unacceptable.

## Configuration, structure and further reading

The [frozen config](configs/sprint_20260810.yaml) fixes 200-event histories, seed `20260804`, probes, budgets and the recorded model `qwen3.7-flash-2026-07-15`. [Resource metadata](docs/resources.json) pins `Qwen/Qwen3-0.6B` as a proxy tokenizer, not weights or a proven identical tokenizer for that hosted snapshot. Cache files stay in ignored `.cache/`. The publication lock supplies the complete test environment; historical dependency files remain unchanged.

`sprint/` implements state, histories, rendering and collection; `tools/` analyses the ledger and provides the safe entry points; `tests/` protects behavior; `data/` and `reports/` hold recorded evidence; `paper/` contains the manuscript and figures. See [Architecture](docs/ARCHITECTURE.md) for module relationships and [Reproducibility](docs/REPRODUCIBILITY.md) for seeds, units, offline resources, hashes and TeX requirements.

Live hosted collection was not rerun during publication and can incur charges. `.env.example` describes the optional `DASHSCOPE_API_KEY`; the adapter reads environment variables and does not load `.env` on import. Keep scientific code/data frozen. Run modules from the root and prepare the tokenizer before tests. Passing tests does not certify camera-ready paper readiness; historical PDF locks and submission notes may describe earlier revisions.

Questions, permission requests and authorized-run reports: [Issues](https://github.com/Sean-xzx/Affective-Sedimentation-LLM-Agent-CSAI-2026/issues). No unlicensed patches or functional changes are invited; include sanitized output, OS, Python version and commit SHA. No maintenance or hosted-service availability promise is made.

## Paper, sources and rights

Zexian Xiong and Yan Li, **Affective Sedimentation: A Controlled Proof-of-Mechanism for History-Driven Behavioral Modulation in an LLM Agent**. Cite the [manuscript](paper/main.pdf) and the repository commit used; no publication DOI is asserted. Non-neutral appraisal values are attributed to Gebhard and Kipp (2006), Table 2; see [references](paper/refs.bib), [literature evidence](paper/LITERATURE_EVIDENCE.md) and [resource provenance](docs/RESOURCE_PROVENANCE.md).

No open-source license is offered for this revision. [RIGHTS.md](RIGHTS.md) defines the permission policy and the limits arising from earlier MIT grants and GitHub platform rights. Third-party dependencies and resources retain their own terms.
