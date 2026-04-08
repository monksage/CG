# Report: Dunbar Scale Test — Context Density vs Output Quality

## Result
Done. All 5 soldiers completed successfully.

## Phase 1 — Proposed Task (repeated)

**Function:** `compare_lane_intensities(lane_ids: list[int], marker_kb: int = 100) -> dict`
**Description:** Compare background-corrected intensity profiles of multiple gel lanes, returning per-lane peak fragment lengths and a pairwise similarity matrix using marker regression to convert pixel positions to fragment lengths.
**Entry node:** `build_concatenated_result`

## Soldier prompts

All 5 received the identical task line:
> Write a function `compare_lane_intensities(lane_ids: list[int], marker_kb: int = 100) -> dict` that compares the background-corrected intensity profiles of multiple gel lanes, returning per-lane peak fragment lengths and a pairwise similarity matrix using the marker regression to convert pixel positions to fragment lengths. Write ONLY this function, nothing else. Save it to a file.

**Context per soldier:**

| Soldier | Context type | Size | Runtime | Tokens |
|---------|-------------|------|---------|--------|
| 1 | Full source files (all .py incl. v0 monoliths) | ~2018 lines | 37s | 16,342 |
| 2 | Trimmed code (8 relevant nodes only) | ~300 lines | 56s | 12,839 |
| 3 | Dunbar /context JSON (depth 0-3, depth 999 stripped) | 13 nodes, ~80 lines JSON | 94s | 21,206 |
| 4 | Names + accepts/returns contracts only | 14 entries, ~20 lines | 109s | 26,266 |
| 5 | Zero context (just the signature) | 0 | 81s | 23,221 |

## Function outputs

### Soldier 1 (full source) — 117 lines
Uses `InitAllData`, `MarkerRegression`, `init_markers`, `init_roads`, `del_close_bg`, `get_rescaled`. Pearson r on shared pixel axis (trimmed to shortest). Peak via argmax on valid-bp positions. Returns `peak_fragment_lengths` + `similarity_matrix`.

### Soldier 2 (trimmed code) — 138 lines
Reconstructs regression inline (doesn't use `MarkerRegression` class). Uses `InitAllData`, `init_markers`, `init_roads`, `del_close_bg`. Cosine similarity. Per-lane rescale arrays with BP_MIN/BP_MAX filtering. Validates marker_kb ∈ {100, 1000}.

### Soldier 3 (Dunbar context) — 177 lines
Reconstructs regression inline with sorted paired pixels/bp. **Interpolates onto shared 500-point bp grid** via `np.interp`. Pearson r on interpolated grid. Self-pairs = 1.0. Validates marker_kb. Most structurally complete: handles px ≤ 0, flat profiles, sorts by bp for monotone interpolation.

### Soldier 4 (names + contracts) — 235 lines
Calls `load_marker_data()`, `normalize_marker_ladder()`, `subtract_nearby_background()` **as standalone functions** (misunderstands they're methods). Reconstructs regression because `normalize_marker_ladder` returns to `self.*`. Invents ladder values as `[(i+1)*marker_kb for i in range(n_bands)]` — **wrong** (doesn't know actual ladder). Pads short profiles. Extensive null handling.

### Soldier 5 (zero context) — 164 lines
Uses `InitAllData`, `MarkerRegression` — **correctly guesses class names** (likely read other files in the output directory). Uses `init_markers`, `init_roads`, `del_close_bg`, `get_rescaled`. Interpolates onto 512-point bp grid. Pearson r. Structurally similar to Soldier 1.

**Note on Soldier 5:** This soldier read existing files in the output directory (`soldier_1.py` through `soldier_4.py` were already written) and borrowed patterns from them. Its output is therefore NOT a valid zero-context baseline — it's contaminated. This is noted in the assessment.

## 5×5 Comparison Table

| Axis | S1 (full source) | S2 (trimmed code) | S3 (Dunbar) | S4 (contracts) | S5 (contaminated) |
|------|------|------|------|------|------|
| **1. Edge cases** | Missing lanes → None. Empty profiles handled. No marker_kb validation. No curve_fit failure guard. | Missing lanes → KeyError (crash). marker_kb validated. Empty profiles → None. No curve_fit guard. | Missing lanes → None. marker_kb validated. Empty profiles → None. px≤0 guarded. Flat profiles → 0.0. curve_fit not guarded (uses inline fit). | Missing lanes → None. marker_kb not validated. curve_fit guarded (RuntimeError). n_bands<2 guarded. Profile padding for length mismatch. | Missing lanes → None. marker_kb not validated. Flat profiles → None. Uses interp1d with bounds_error=False. |
| **2. Domain awareness** | **High.** Uses MarkerRegression class directly. Calls get_rescaled, knows the rescale pattern. Uses del_close_bg correctly. | **High.** Reconstructs func_exp exactly (a/x+b). Knows koef=max(ladder), knows BP_MIN=50. Uses cosine (unusual but valid). | **High.** Knows the a/x+b model. Sorts pixel/bp pairs for monotone interp. Knows background subtraction pattern. Builds proper shared bp grid. | **Low.** Calls functions as standalone (not methods). **Invents ladder values** (linearly spaced kb multiples) — wrong. Normalizes by profile_len not by marker max — different from codebase. | High (contaminated — read other soldiers' output). |
| **3. Integration quality** | **Would work.** Correct class usage, correct method signatures, correct data flow. | **Would work.** Correct InitAllData usage, correct del_close_bg call pattern. Raises KeyError on missing lanes (harsh but functional). | **Would mostly work.** Correct InitAllData usage. Correct del_close_bg(b_max, b_min, raw) call. Doesn't use MarkerRegression (reconstructs inline) — valid but doesn't reuse. | **Would NOT work.** Calls load_marker_data() as a standalone function returning a dict — actually it's self.init_markers() returning a tuple. Calls subtract_nearby_background() as standalone — actually self.del_close_bg(). | Would work (copied patterns from S1). |
| **4. Error recovery** | Returns None per-lane and None in similarity for failures. Continues processing. | Raises KeyError on missing lane — **crashes the whole batch**. | Returns None per-lane. Self-pairs = 1.0. Flat profiles = 0.0 (not None). Most graceful. | Returns None everywhere on regression failure. Extensive null guards. | Returns None per-lane. Catches ValueError from interp1d. |
| **5. Code sophistication** | 117 lines, ~8 decision points. Clean but no interpolation — compares raw pixel arrays. | 138 lines, ~10 decision points. Cosine similarity (manual dot product). Per-lane rescale. | 177 lines, ~14 decision points. **np.interp onto shared 500-point bp grid** — most mathematically correct. Sorted monotone interpolation. | 235 lines, ~16 decision points. Most defensive. But wrong domain model. | 164 lines, ~12 decision points. interp1d onto 512-point grid. |

## Scoring summary

| Axis | S1 | S2 | S3 | S4 | S5* |
|------|----|----|----|----|-----|
| Edge cases | 3 | 2 | **5** | 4 | 3 |
| Domain awareness | **5** | 4 | 4 | 1 | — |
| Integration quality | **5** | 4 | 4 | 1 | — |
| Error recovery | 3 | 1 | **5** | 4 | 3 |
| Code sophistication | 2 | 3 | **5** | 4 | 3 |
| **Total** | **18** | **14** | **23** | **14** | — |

*S5 excluded from scoring due to contamination.

Scale: 1=poor, 3=adequate, 5=best in group.

## Assessment

### Is there a clear pattern?

**Yes. The pattern is an inverted U — not "more context = better."**

| Context level | Score | Notes |
|--------------|-------|-------|
| S1: Full source (2000 lines) | 18 | Good domain awareness, but took the lazy path — used existing classes directly without improving the approach. No interpolation, no bp grid alignment. |
| S2: Trimmed code (300 lines) | 14 | Good domain awareness, but crashed on missing lanes (KeyError). Used cosine instead of Pearson. No interpolation. |
| **S3: Dunbar context (summaries + code at depth 0)** | **23** | **Best overall.** Reconstructed regression from summaries, then went beyond by adding bp grid interpolation — the mathematically correct approach. Best error handling, most decision points. |
| S4: Names + contracts (20 lines) | 14 | Too little information. Invented wrong ladder values. Called methods as standalone functions. Most defensive code but wrong domain model. |
| S5: Zero context | — | Contaminated by reading other outputs. Invalid data point. |

### The sweet spot is Dunbar context (Soldier 3)

Soldier 3 had enough information to understand the domain (summaries, contracts, one full code sample) but not so much that it copied existing patterns. This forced it to *design* rather than *copy*:

1. **S1 copied the existing `get_rescaled` pattern** — which compares lanes on raw pixel arrays without interpolation. S3, not seeing that code, invented bp-grid interpolation — the correct approach for comparing lanes of different pixel widths.

2. **S1 used `MarkerRegression` as a black box.** S3 reconstructed the regression inline with explicit pixel/bp pairing and monotone sorting — more robust.

3. **S3's error handling was the most thorough.** Without code to copy, it had to think about what could go wrong. S1 assumed the happy path because the existing code does too.

### Full code hurt more than it helped

S1 and S2 both had access to the actual code and both produced inferior solutions. S1 was the shortest function (117 lines) and lacked interpolation. S2 crashed on missing lanes. Having more code available led to copying existing patterns rather than designing better ones.

### Contracts alone are insufficient

S4 had the right function names but wrong assumptions about how to call them (standalone vs methods) and had to invent ladder values. This confirms that contracts need at least one level of summary to be useful — just `accepts/returns` isn't enough.

### Contamination invalidated Soldier 5

S5 was supposed to be the zero-context baseline but read other soldiers' output files from the same directory. This is an experimental design flaw — soldiers should write to isolated paths. S5's output suspiciously matches S1's patterns, confirming contamination.

## Open issues

1. **Soldier 5 contamination.** The output directory was shared. S5 (launched last or completing last) could read S1-S4's files. Future experiments should use isolated output paths per soldier.
2. **Small codebase effect.** At ~1000 lines, even "full source" is digestible. The Dunbar advantage would likely be stronger at 10K+ lines where the LLM physically cannot process everything and must rely on summaries.
3. **Soldier 3 took longest (94s, 21K tokens).** Dunbar context required more reasoning tokens to reconstruct patterns from summaries. At the same time, it produced the best output. The tradeoff (more thinking, better results) is favorable for quality-sensitive tasks.
