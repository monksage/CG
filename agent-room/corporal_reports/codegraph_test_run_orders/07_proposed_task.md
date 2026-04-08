# Phase 1 — Proposed Task

## Function signature

```python
def compare_lane_intensities(
    lane_ids: list[int],
    marker_kb: int = 100,
) -> dict:
```

## One-sentence description

Compare the background-corrected intensity profiles of multiple gel lanes, returning per-lane peak fragment lengths and a pairwise similarity matrix using the marker regression to convert pixel positions to fragment lengths.

## Entry node for /context

`build_concatenated_result` — this node sits at the intersection of marker loading, road loading, background subtraction, and image assembly. Its Dunbar neighborhood at depth 1 includes: `load_marker_data`, `load_road_data`, `subtract_nearby_background`, `apply_strategy_result`. At depth 2: `load_background_lines`, all plotting nodes, `replace_roads_in_image`.

## Why this task is a good test

A **well-informed soldier** would:
- Know that lanes are "roads" stored as monolines (per-row pixel averages) in `monoline_dir_path`, loaded via `load_road_data` which returns borders+monos dicts keyed by string lane id.
- Know that background subtraction requires `load_background_lines` to find nearby background columns, then averages them and subtracts (clamped to 0) — the `subtract_nearby_background` pattern.
- Know that pixel→fragment-length conversion uses `normalize_marker_ladder` (normalizes by max, then exponential regression `func_exp`) and `load_marker_data` for band coordinates.
- Know that the system uses numpy arrays, that monolines are 1D intensity arrays indexed by pixel row, and that the existing rescaling pattern filters values outside [50, 1000] as None.
- Produce a function that loads real data paths, handles the 100/1000 marker distinction, and outputs a similarity matrix using the actual data structures.

A **poorly-informed soldier** would:
- Not know what a "monoline" is, what "roads" are, or how background correction works in this codebase.
- Invent generic signal processing (e.g., scipy peak detection on arbitrary arrays) instead of using the existing background subtraction and marker regression pipeline.
- Guess at data structures and file formats rather than using the existing loading functions.
- Produce a function that is technically correct but incompatible with the actual codebase — different assumptions about inputs, different data flow.

The gap between these two is wide enough to discriminate between context levels, but the task is domain-specific enough that "zero context" will produce something fundamentally different from "full context."
