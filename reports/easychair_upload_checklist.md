# EasyChair upload checklist — CSAI 2026 (human B3)

**Deadline:** 2026-08-10 (Asia/Shanghai). Composer does **not** submit; this file is the human upload runbook.

## Submission identity (must match PDF + form)

| Field | Value |
|---|---|
| **Title** | Affective Sedimentation: A Controlled Proof-of-Mechanism for History-Driven Behavioral Modulation in LLM Agents |
| **Track** | Track 11: Generative AI, Large Language Models and Foundation Model Architectures |
| **Conference** | CSAI 2026 — 10th International Conference on Computer Science and Artificial Intelligence |
| **Review mode** | Named — the conference asks for the byline on page 1, so the PDF is **not** anonymised |

## Submission PDF (upload this file)

| Check | Detail |
|---|---|
| **Path** | `paper/main.pdf` (**tracked in git**, not gitignored) |
| **Page count** | **6 pages** (within the 4–6 dual-column limit) |
| **SHA-256** | _(stale; re-hash at upload — the PDF has been rebuilt since the old lock)_ |
| **Lock file** | `reports/paper_pdf_sha256.txt` (single line, no trailing newline required) |
| **Byline OK** | `\documentclass[sigconf]{acmart}`; Zexian Xiong and Yan Li with affiliation and email on page 1; Yan Li carries `\authornote{Corresponding author.}` |
| **Metadata OK** | acmart writes no `/Author` key at all (verified 2026-08-09); `/Title` matches the paper title. The byline lives in the page-1 body, which is what EasyChair and reviewers see |
| **Bibliography OK** | Wei et al. pages `24824--24837` present in compiled PDF |

Re-verify SHA before upload:

```powershell
Get-FileHash -Algorithm SHA256 paper/main.pdf | Select-Object -ExpandProperty Hash
# Compare (case-insensitive) to reports/paper_pdf_sha256.txt
```

## EasyChair form fields (paste from `paper/AUTHOR_INFORMATION.md`)

- [ ] **Authors & order** — 1. Zexian Xiong, 2. Yan Li (confirm order before submit)
- [ ] **Corresponding author** — Yan Li; tick the EasyChair "corresponding author" box on her row so it matches the asterisk in the PDF
- [ ] **English names** — Zexian Xiong; Yan Li
- [ ] **Emails** — shyzx4@nottingham.edu.cn; sylvie.li@nottingham.edu.cn
- [ ] **Affiliation** — University of Nottingham Ningbo China for both (confirm official English string)
- [ ] **Abstract** — copy verbatim from `paper/AUTHOR_INFORMATION.md` (matches PDF abstract)
- [ ] **Keywords** — large language models; LLM agents; affective state; prompt interface; controlled pilot
- [ ] **COI / competing interests** — none declared (see author form)
- [ ] **ORCID** — add in form if available (optional locally)

## Pre-upload verification

- [ ] `python -m tools.verify_paper_numbers` passes (locked numerics unchanged)
- [ ] `pytest tests/sprint -q` — last known: **274 passed**
- [ ] No local filesystem paths or repo URLs inside PDF
- [ ] Title and abstract in EasyChair **exactly** match the PDF
- [ ] Author list and order in EasyChair match the PDF byline, with Yan Li flagged as corresponding

## Post-upload receipt (human saves)

| Slot | Path / note |
|---|---|
| EasyChair submission ID | _(paste here after upload)_ |
| Submission timestamp (Asia/Shanghai) | _(paste here)_ |
| Final uploaded PDF SHA-256 | _(re-hash `paper/main.pdf` at upload time; update if different from lock)_ |
| Screenshot / PDF receipt | `reports/easychair_receipt_YYYYMMDD.pdf` or `.png` _(create after upload)_ |
| Confirmation email | archive to `reports/` or local mail folder |

## Explicit do-not

- Do **not** type the corresponding-author asterisk into `\author{}`; it comes from `\authornote{}`.
- Do **not** re-run formal API collection or change locked estimands before/during upload.
- Do **not** push git tags/commits unless explicitly requested.

## Git freeze reference

- Branch: `sprint/csai-20260810`
- Working tree includes post-audit Method/Results wording rewrite + PDF reseal (SHA above)
- Prior baseline HEAD before this rewrite: `e6ae10f`
- Submission freeze tag: apply after human says **commit** → `paper-freeze-YYYYMMDD_HHMMSS`
