# Architecture

This is a small Python experiment, not a general agent framework. The scientific controller and recorded analysis remain unchanged in the public release.

## Inputs and deterministic construction

`schema.py` loads the frozen YAML and supplies boundaries, endpoints, numeric formatting and hash helpers. `materials/action_map.csv` stores OCC-style listener labels, PAD values and intensities. `histories.py` converts each action to its evaluation vector, distributes fixed counts across ten blocks, derives PCG64 seeds through SHA-256 and permutes each block. It also checks relaxed endpoint reachability through linear programming.

`dynamics.py` updates epsilon, m and s in that order. With beta fixed at zero, there is no slow-state feedback into the medium state. All histories have 200 events; the scientific comparisons use checkpoint 200. Numerical persistence after zero input is an engineering property, not a behavioral persistence measurement.

## Model interface and collection

`renderer.py` writes either affect metadata or parallel unlabeled sensor metadata. Event memory contains the last ten events and cumulative action counts. N pairs share identical memory; only rendered state differs. The request orders the role, optional memory, metadata, scenario, counterbalanced options and output instruction.

`manifest.py` validates the 21 probes, derives replay selections and seals materials. `runner.py` defines observation and attempt keys, constructs development/formal schedules, interleaves formal observations and manages six concurrent workers. A single writer appends JSONL records and checkpoints. Completed observations are not repeated on resume; attempt/failure limits can pause or stop a run. `provider_qwen.py` performs hosted requests and format checks. The public demo supplies a mock completion function instead, so it never constructs a live client.

## Recorded-data analysis

`tools/rand_manifest.py` supplies the randomization manifest and integrity checks. `tools/analysis_core.py` filters formal records, maps answer positions back to semantic high/low choices and averages AB/BA pairs to CS. E estimates 15 affect-minus-placebo endpoint slopes; N estimates 8 seed means of direction-signed Full-minus-Zero contrasts. Exact sign flips, bootstrap sensitivity and Holm correction are implemented there. `sprint/analysis.py` is a re-export interface.

`tools/diagnostics.py` is outside the sealed primary analysis hash set. It explains saturation, origin-side movement, direction contributions, dose-normalized sensitivity, attainable p-value floors, development repeat stability and exploratory development headroom. Its D1-D8 labels are distinct from the protocol's numerical gate labels. Development records never enter the formal E/N estimands.

## Artifacts and safe entry points

The original analysis can write reports, a table and basic SVGs. Figure exporters can overwrite graph files. Paper figures also include authored raster artwork, so all displayed artifacts are not produced solely by one script. The current paper includes `fig_E_items.pdf`, `fig_N_seeds.pdf`, `fig_E_grid.pdf` and `fig_N_dirseed.pdf`.

The public wrapper `tools/reproduce.py` offers only demo, read-only verification and tests. It does not offer a hosted-run switch. `tools/prepare_resources.py` downloads only four verified tokenizer files; `tools/check_publication.py` checks documentation links and bilingual examples. These publication tools do not join the sealed analysis hash set.
