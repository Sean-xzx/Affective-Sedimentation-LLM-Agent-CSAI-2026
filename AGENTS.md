# CSAI3 Sprint Agent Contract

## Working root

This directory (`CSAI3`) is the **only** implementation root for the CSAI 2026 sprint.

- Source of truth: `affective-sedimentation-csai-2026-sprint-final.zh.md`
- Clean rewrite in-place. Do **not** copy, symlink, import, or transplant code from sibling folders (`CSAI`, `CSAI2`, `Projects/affective-sedimentation`, etc.).
- Prior projects may be read for design memory only; any reused idea must be re-implemented here under this protocol.

## Language policy (mandatory)

CSAI is an international venue. **All project deliverables must be English-only.**

| Artifact | Language |
|---|---|
| Paper (`paper/`), abstracts, figure/table labels, captions | English |
| Code, identifiers, comments, docstrings, tests | English |
| Prompts, renderers, probes, options, memory strings | English |
| Configs, manifests, logs, reports, commit messages | English |
| Materials CSVs and analysis outputs | English |

Exceptions:

- The Chinese protocol file `*.zh.md` may remain as an **internal planning** source of truth.
- Chat with the author may be Chinese; every file written into this repo that ships with the paper or experiment must still be English.

Do not mix Chinese into prompts, probe text, or the submission PDF.

## Role

Cursor is an implementer and code-review assistant, not a research-design decision maker.

1. Do not change formulas, state endpoints, seeds, probe assignments, thresholds, call budgets, or the fixed `D → E → N` order.
2. Do not run or repair any old `generate_corpus.py`.
3. Do not introduce LangChain, AutoGen, CrewAI, or MetaGPT.
4. Do not use DeepSeek (or any second model) as a formal scorer.
5. Never write API keys, headers, or `.env` contents into logs or commits.
6. Each task: propose a diff plan, edit only allowlisted files, run specified tests, then stop for human review.
7. On design ambiguity: stop and report; do not “optimize” the experiment.
8. Stop immediately at attempt-budget or failure thresholds.
9. Before every protocol re-audit / vulnerability pass: Git checkpoint only — `git add -A` (respect `.gitignore`; never stage `.env`), commit if needed as `backup: pre-audit YYYYMMDD_HHMMSS`, then `git tag pre-audit-YYYYMMDD_HHMMSS`. Do not use folder copies under `backups/` or `git stash`.
10. After every such audit: return both (a) the Composer task list and (b) a human progress-confirmation card (including the Git tag / short SHA to verify).

## Sprint package target

```text
AGENTS.md
configs/sprint_20260810.yaml
materials/sprint_probes.csv
materials/action_map.csv
sprint/
  schema.py
  dynamics.py
  histories.py
  renderer.py
  provider_qwen.py
  manifest.py
  runner.py
  analysis.py
tests/sprint/
paper/
data/raw/
data/derived/
reports/
```

Production sprint code target: ≤ 1000 non-empty Python lines. No GUI, database, web service, plugin system, or general agent framework.

## Task header (every Cursor task)

```text
You are implementing exactly one bounded task from
affective-sedimentation-csai-2026-sprint-final.zh.md.

Before editing:
1. Read AGENTS.md and the named protocol sections.
2. List the exact files you will edit and the tests you will run.
3. Stop if the protocol and repository disagree.

During editing:
- Do not change scientific constants, manifests, budgets, thresholds, or frozen files.
- Do not call APIs unless this task explicitly authorizes the exact call block.
- Preserve unrelated user changes.

After editing:
1. Run only the specified tests plus the existing regression suite.
2. Summarize the diff, test output, remaining risk, and API attempts used.
3. Stop; do not start the next task automatically.
```
