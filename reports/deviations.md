# Protocol Deviations (CSAI 2026 Sprint)

## §2.3 OCC–PAD source page numbers

**Decision:** Per-action `source_page` values use `GebhardKipp2006_table2:<emotion>` for OCC listener labels and `protocol_s2.3_engineered:Neutral` for the engineered neutral event.

**Reason:** The sprint repository does not contain the full v4 protocol OCC–PAD snapshot with original printed page numbers. Sibling project folders were consulted for design memory only (per `AGENTS.md`); they provide Gebhard & Kipp (2006) Table 2 coordinates but not recoverable PDF page indices for each of the ten sprint actions.

**Impact:** The appraisal mapping remains an **engineered appraisal mapping** as stated in protocol §2.3. Paper claims must not treat PAD coordinates as independently validated psychometric scales. Coordinates and listener labels are frozen in `materials/action_map.csv`; `listener_vector = PAD * intensity` is recomputed in code and checked against protocol display vectors at `<1e-12`.

**Frozen table hash:** `ed00da0e3ceb6bc2436539621fe91d9b87390bed11303eb818f2566277be6fcf` (SHA-256 of canonical JSON excluding per-row `source_hash`).

## §3.1 Offline probe token counting vs agent snapshot

**Decision:** Offline high/low token-balance checks use `tokenizer_load_id: Qwen/Qwen3-0.6B`. The manifest `tokenizer` field remains the formal agent snapshot identifier `qwen3.7-flash-2026-07-15`.

**Reason:** The sprint agent snapshot `qwen3.7-flash-2026-07-15` is API-only in this repository window; no exact public Hugging Face tokenizer bundle for that snapshot was available for deterministic offline counting. The closest loadable Qwen3-family tokenizer is frozen as `Qwen/Qwen3-0.6B`.

**Impact:** Probe token-length parity (absolute ≤3, relative ≤10%) is enforced against the frozen Qwen3 proxy tokenizer, not against a verified byte-identical snapshot tokenizer. Counts may differ slightly from live DashScope tokenization if Alibaba ships snapshot-specific vocabulary changes. Author probe review must still meet the proxy gate before stability/API calls; any live mismatch will be logged at runtime but does not relax the pre-registered parity rule on the frozen proxy.

## Sprint manifest null hash fields and dependency lock drift

**Decision:** `sprint_manifest.json` records `analysis_code_hash: null` and `randomization_manifest_hash: null` at the scientific freeze. Post-freeze, `reports/randomization_manifest.json` seals the interleaved schedule and `file_sha256`; `analysis_code_hash` is sealed in `reports/final_results.json` and `reports/paper_number_lock.json`.

**Reason:** The sprint manifest was written before blind decode and before the analysis-code hash pipeline was finalized; rewriting that file would violate the frozen-manifest protocol.

**Impact:** Paper and integrity reports cite the analysis-code prefix from `paper_number_lock.json` / `final_results.json`, not from `sprint_manifest.json`. The manifest retains the pre-paper `dependency_lock_hash` (`2624c9c341d5b4c751f191c0bf9290e64b16fceda8f3b8d039a283a8b4d9dce7`); after matplotlib was pinned for figure export, the live lock hash is `c902457b38b3fc7ff010108cd4e0a12d3e0d6eebde80055453467c2ed00950ac`. Do not rewrite `sprint_manifest.json` to reconcile either hash field.
