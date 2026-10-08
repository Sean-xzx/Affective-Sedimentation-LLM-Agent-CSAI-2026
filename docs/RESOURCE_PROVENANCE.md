# Resource provenance and use conditions

The publication separates original experimental artifacts from third-party software and resources. Public availability is not a blanket permission to redistribute everything under one license.

| Resource | Origin and role | Use conditions / status |
|---|---|---|
| `sprint/`, original analysis/tests, publication utilities | Local CSAI3 project and publication work | All rights reserved under the current policy; no new open-source license grant. Other use requires prior written permission, subject to earlier grants. See [rights and permissions](../RIGHTS.md). |
| `materials/` | Author-defined fictional probes and engineered action mapping | Research materials retain author rights; other use requires prior written permission. Source attribution is preserved. |
| `data/raw/sprint_raw.jsonl` | Recorded synthetic scenarios and hosted A/B completions | The author authorized public hosting of this ledger; no downstream reuse or modification permission is granted by its availability. Prior grants and provider terms remain applicable. No credentials are included. |
| `reports/`, `data/derived/` | Local analysis of the recorded ledger | Research data/results retain author rights; other use requires prior written permission. |
| `paper/main.tex`, `main.pdf`, `refs.bib`, figures | Author paper and locally supplied research artwork | The author confirmed ownership and authorized public hosting; paper/figures retain author rights and other use requires prior written permission. The authors confirm CSAI 2026 acceptance; the paper is not yet published. The repository PDF is the supplied manuscript, not a publisher-hosted version. |
| `paper/ACM-Reference-Format-unsrt.bst` | Local unsorted variant of the ACM bibliography style | Header explicitly declares public-domain status and names its original authors; header retained. |
| `Qwen/Qwen3-0.6B` tokenizer | [Qwen repository](https://huggingface.co/Qwen/Qwen3-0.6B), revision pinned in `resources.json` | Upstream metadata declares Apache-2.0. Downloaded on demand; not redistributed in Git, no weights. Consult the upstream license and model card. |
| Python dependencies | Packages listed in the publication lock | Installed from package registries; each retains its own license. |

Non-neutral appraisal values are attributed to Gebhard and Kipp (2006), Table 2, as recorded in the original sources and [deviations](../reports/deviations.md). This is an engineered mapping and the probes are not validated human psychometric instruments. Bibliographic metadata and claim limitations are recorded in [the evidence table](../paper/LITERATURE_EVIDENCE.md); entries awaiting human review are not represented as verified.

The public package excludes internal model-handoff prompts/copies, most obsolete submission-operation notes, the local author form, concept art of uncertain distribution status, scratch scripts, environment/cache directories, private settings and local snapshots. These remain in the original workspace and its private backup. The historical EasyChair checklist is retained because the original paper-QA tests read it; it is not a current upload runbook. Historical local Git commits are preserved locally; the public repository starts with a selected, inspected snapshot rather than exposing every internal drafting revision.

No third-party paper PDFs, model weights or conference template PDFs are bundled. The owner's approval of public hosting is not a permission grant to downstream users. The current policy is subject to GitHub platform rights, earlier licenses and independent third-party terms as explained in [RIGHTS.md](../RIGHTS.md).
