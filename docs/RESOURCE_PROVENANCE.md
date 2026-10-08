# Resource provenance and use conditions

The publication separates original experimental artifacts from third-party software and resources. Public availability is not a blanket permission to redistribute everything under one license.

| Resource | Origin and role | Use conditions / status |
|---|---|---|
| `sprint/`, original analysis/tests, publication utilities | Local CSAI3 project and publication work | Project code license awaits author selection. |
| `materials/` | Author-defined fictional probes and engineered action mapping | Research materials retain author rights; source attribution is preserved. |
| `data/raw/sprint_raw.jsonl` | Recorded synthetic scenarios and hosted A/B completions | Publication requires the author's confirmation; no credentials are included. Provider terms remain applicable. |
| `reports/`, `data/derived/` | Local analysis of the recorded ledger | Research data/results retain author rights. |
| `paper/main.tex`, `main.pdf`, `refs.bib`, figures | Author paper and locally supplied research artwork | Publication requires the author's rights confirmation; paper/figures retain author rights. No conference acceptance is asserted. |
| `paper/ACM-Reference-Format-unsrt.bst` | Local unsorted variant of the ACM bibliography style | Header explicitly declares public-domain status and names its original authors; header retained. |
| `Qwen/Qwen3-0.6B` tokenizer | Qwen Hugging Face repository, revision pinned in `resources.json` | Downloaded on demand; not redistributed in Git, no weights. Consult the upstream license and model card. |
| Python dependencies | Packages listed in the publication lock | Installed from package registries; each retains its own license. |

Non-neutral appraisal values are attributed to Gebhard and Kipp (2006), Table 2, as recorded in the original sources and [deviations](../reports/deviations.md). This is an engineered mapping and the probes are not validated human psychometric instruments. Bibliographic metadata and claim limitations are recorded in [the evidence table](../paper/LITERATURE_EVIDENCE.md); entries awaiting human review are not represented as verified.

The public package excludes internal model-handoff prompts/copies, most obsolete submission-operation notes, the local author form, concept art of uncertain distribution status, scratch scripts, environment/cache directories, private settings and local snapshots. These remain in the original workspace and its private backup. The historical EasyChair checklist is retained because the original paper-QA tests read it; it is not a current upload runbook. Historical local Git commits are preserved locally; the public repository starts with a selected, inspected snapshot rather than exposing every internal drafting revision.

No third-party paper PDFs, model weights or conference template PDFs are bundled. Publication approval covers only material for which the author owns or has the necessary distribution rights.
