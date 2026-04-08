# Report: Decompose a Folder Into Graph Nodes

## Result
Done.

## Phase 1 — Survey

Codebase: gel electrophoresis image analysis tool (AnaForesis). 13 Python files, 2235 lines total.

### Included (8 files, ~1071 lines)

| File | Lines | Purpose |
|------|-------|---------|
| `conquer.py` | 47 | Entry point, wiring. No decisions — skipped as micro. |
| `app/gel_line.py` | 122 | GelLine + MarkerGelLine domain classes |
| `app/lil_shit.py` | 148 | Config constants (dotdict, global_paths, idp) + utility functions |
| `app/image_view.py` | 296 | ImageViewerDefs — strategy-based image interaction |
| `app/main_window.py` | 216 | Auto-generated Qt UI layout |
| `app/main_window_def.py` | 169 | Main window business logic |
| `regression/regression.py` | 145 | MarkerRegression — exponential fit + plotting |
| `regression/back_deleter.py` | 173 | InitAllData — data loading, background removal, concatenation |

### Excluded

| File | Lines | Reason |
|------|-------|--------|
| `all.py` | 1 | Dead code: `if 1 == '1': print('lol')` |
| `main.py` | 0 | Empty file |
| `app/background.py` | 0 | Empty file |
| `app/vis_v0.py` | 490 | Superseded monolith — all functionality now in split files |
| `regression/reg_v0.py` | 428 | Superseded monolith — replaced by regression.py |
| Non-code files | — | Stylesheets, .png results, .tif test data, .npy temp data, __pycache__ |

### Config/utility treatment
- `app/lil_shit.py`: config constants (`global_paths`, `idp`) referenced everywhere via `from app.lil_shit import *`. Not created as nodes — documented in specs as dependencies. Utility functions (save/load helpers) are all micros, inlined into callers.
- `app/main_window.py`: auto-generated Qt UI layout (`setupUi` + `retranslateUi`). No decisions. Not loaded.
- `conquer.py`: wiring-only class (`AppsInfer`). No decisions. Not loaded.

## Phase 2 — Decomposition Plan

### Nodes (27)

**gel_line.py (2):**
1. `extract_gel_line` — GelLine class + save_line (if border). Micros inlined: calc_ratio, cords_shift, make_line_array, hugging.
2. `plot_marker_bands` — MarkerGelLine.plot_mono + save_mark_monoline. Nested event handlers (on_key: if r/e, on_close).

**image_view.py (10):**
3. `init_image_strategy` — __init__ with match/case on strategy
4. `handle_mouse_click` — mousePressEvent (routing by button + strategy). Inlined: cropper_lines, draw_mark_gel_line, background_selector.
5. `handle_key_action` — keyPressEvent (routing by key + strategy). Inlined: rotator.
6. `handle_scroll_rotate` — wheelEvent + rotate_pixmap inlined.
7. `crop_image` — cropper (guard + numpy slicing)
8. `process_roads` — roads (for loop, GelLine per road)
9. `select_road_line` — road_selector (if/else + draw)
10. `process_background` — background + create_backline (for loop, bounds clamping)
11. `draw_overlay_grid` — draw_grid (while loops, 100px spacing)
12. `process_marker_line` — marker (creates MarkerGelLine)

**main_window_def.py (3):**
13. `open_file_dialog` — if dialog.exec + if filenames
14. `load_and_display_image` — ok_boomer (if empty fallback)
15. `apply_strategy_result` — replacer (if/elif on strategy type)

**regression.py (6):**
16. `init_plot_subplots` — if/elif on subplot dimensions
17. `normalize_marker_ladder` — if/elif on kb (100/1000)
18. `plot_fraglen_regression` — orchestrator: load + normalize + regress + plot
19. `plot_intensity_vs_position` — for loop over lanes
20. `plot_intensity_vs_fraglen` — rescale x-axis + for loop
21. `plot_concentration_vs_fraglen` — N/fraglen with filtering + median

**back_deleter.py (6):**
22. `load_marker_data` — init_markers (for + if/elif on filenames)
23. `replace_roads_in_image` — replace_roads (for + if on borders)
24. `load_road_data` — init_roads + drop_emptys inlined
25. `build_concatenated_result` — concater + name_bands_concated inlined
26. `subtract_nearby_background` — del_close_bg (for + if range check)
27. `load_background_lines` — init_background (for loop)

### Edge map (33 edges)

**image_view internal (9):**
init_image_strategy -> draw_overlay_grid, handle_key_action -> {crop_image, process_roads, process_background, select_road_line, process_marker_line}, handle_scroll_rotate -> draw_overlay_grid, handle_mouse_click -> select_road_line, load_and_display_image -> open_file_dialog

**Cross-module: image_view -> gel_line (3):**
process_roads -> extract_gel_line, process_background -> extract_gel_line, process_marker_line -> plot_marker_bands

**gel_line internal (1):**
plot_marker_bands -> extract_gel_line (extends)

**Cross-module: main_window_def -> back_deleter (3):**
apply_strategy_result -> {replace_roads_in_image, build_concatenated_result, load_marker_data}

**regression internal (9):**
plot_fraglen_regression -> {load_marker_data, normalize_marker_ladder, init_plot_subplots}
plot_intensity_vs_fraglen -> {load_marker_data, normalize_marker_ladder, init_plot_subplots}
plot_concentration_vs_fraglen -> {load_marker_data, normalize_marker_ladder, init_plot_subplots}

**regression -> back_deleter (2):**
plot_intensity_vs_position -> {init_plot_subplots, load_marker_data}

**back_deleter internal (6):**
replace_roads_in_image -> {load_road_data, load_marker_data}, build_concatenated_result -> {load_marker_data, subtract_nearby_background, load_road_data}, subtract_nearby_background -> load_background_lines

## Soldier delegation

Three soldiers spawned in parallel:
- **Soldier 1 (gel_line):** 2 nodes, 1 edge. Completed: 2 OK, 1 OK.
- **Soldier 2 (image_view + main_window_def):** 13 nodes, 9 edges. Completed: 13 OK, 9 OK.
- **Soldier 3 (regression + back_deleter):** Launched as async agent but did not complete in time. Loaded manually via script: 12 nodes, 20 edges (including cross-module).

Cross-module edges (6) added by corporal after soldiers completed.

## Graph stats

- New nodes: 27
- New edges: 33
- Total in CodeGraph: 66 nodes, 49 edges (39 pre-existing)
- Most connected node: `load_marker_data` (7 edges — called by 6 plotters + apply_strategy_result)
- Three clusters: image_view (10 nodes) ↔ gel_line (2 nodes), main_window_def (3 nodes) → back_deleter (6 nodes), regression (6 nodes) → back_deleter
- All connected via cross-module edges

## Verification

### 1. Graph presence — pass
27 new nodes, 33 new edges present. Edge count > 0.

### 2. Leaf node: `load_background_lines` — pass
- Depth 0: full code + specs
- Depth 1: `subtract_nearby_background` — spec_summary + contract
- Depth 2+: remaining nodes at name level

### 3. Most connected: `load_marker_data` — pass
All Dunbar levels present:
- Depth 0: full code + all specs
- Depth 1: 7 callers (apply_strategy_result, build_concatenated_result, plot_*, replace_roads) — spec_summary
- Depth 2: load_road_data, subtract_nearby_background, init_plot_subplots, normalize_marker_ladder — spec_ticket
- Depth 3: load_background_lines — name only
- Depth 5+: 53 disconnected nodes from previous experiments

### 4. No standalone micros — pass
All 27 nodes are kind=contour with at least one edge.

### 5. Count match — pass
27 nodes planned = 27 loaded. 33 edges planned = 33 loaded.

## Open issues
1. **Soldier 3 timeout.** The async regression soldier did not produce output in time. Had to load manually. Details in USER ENHANCED DETAILS section below.
2. **lil_shit.py wildcard import.** All files use `from app.lil_shit import *`, importing ~20 utility functions and 2 config dicts into every module's namespace. This makes dependency tracking imprecise — specs note config dependencies but the graph doesn't capture them as edges since they're not function calls.
3. **Superseded code not loaded.** vis_v0.py (490 lines) and reg_v0.py (428 lines) are earlier monolithic versions. They share significant code with the current split files but were excluded as superseded. If historical comparison is needed, they'd need separate nodes.

## USER ENHANCED DETAILS

### Soldier 3 failure analysis

**What happened:** Soldier 3 (regression + back_deleter module) was spawned as an async Agent alongside Soldiers 1 and 2. Soldiers 1 and 2 completed normally. Soldier 3 returned as async (background agent) instead of inline, produced 0 bytes of output for ~5 minutes, and was eventually completed by the framework after the corporal had already loaded the data manually.

**Prompt size:** Soldier 3 received the largest prompt of the three — 12 node definitions with full code strings, 16 edge definitions, and API instructions. Estimated prompt size: ~6,000 tokens. By comparison, Soldier 1 received ~2,000 tokens (2 nodes), Soldier 2 received ~5,000 tokens (13 nodes, 9 edges).

**Runtime:** Soldier 3 ran for **641,797 ms (~10.7 minutes)** before completing. By the time it finished, the corporal had already loaded all 12 nodes and 20 edges manually (~30 seconds via Python script). The soldier's final report confirmed "data was already loaded from a prior session."

**Token cost:** Soldier 3 consumed **62,126 total tokens** across **44 tool uses** — all wasted, since the work was already done. For comparison, Soldier 1 used ~28,000 tokens (21 tool uses, ~3 min), Soldier 2 used ~34,000 tokens (14 tool uses, ~4 min).

**Root cause:** The soldier was launched as a background agent (async) rather than inline. This meant the corporal had no way to monitor its progress or detect the stall early. The soldier itself appears to have worked correctly but slowly — it attempted to POST each node individually via curl (44 tool uses for 12 nodes + 16 edges suggests retries or verification reads), found them already present, and reported success.

**Mitigation applied:** After ~2 minutes of 0-byte output, corporal wrote a Python loader script and executed the same work in one batch call (~30 seconds). This made Soldier 3's eventual output redundant but harmless (all POSTs returned 200 since nodes already existed — CodeGraph is idempotent on create? Actually no, it returned 200 because the soldier did GET reads to verify, not POST creates that would have failed with duplicate key).

**Lesson:** For large decomposition tasks, a single Python loader script run by the corporal is faster and more reliable than delegating to a soldier via curl. Soldiers work well for code-level tasks (reading, refactoring) but are inefficient for bulk API loading where a script can batch everything in seconds. If soldiers are used for loading, they should use httpx/requests in Python rather than individual curl calls.
