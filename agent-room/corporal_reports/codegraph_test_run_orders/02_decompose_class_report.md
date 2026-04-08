# Report: Decompose Class Into Graph Nodes

## Result
Done.

## Phase 1 — Decomposition Plan

### Micros inlined

| Micro | Inlined into | Reason |
|-------|-------------|--------|
| `SignalProcessor.__init__` | `process_signal` | Only assigns attributes, no decisions |
| `SignalProcessor._empty_result` | `process_signal` | Returns literal `[0]*cycles`, no decisions |
| `_is_valid_forward_point` | `find_dot_forward` | Returns boolean expression, no branching |
| `_is_valid_backward_point` | `find_dot_reverse` | Same pattern |
| `_process_channel` | `process_line` | One if + one call, not testable alone |
| `_find_ct_values` | `calculate_cts` | One if + return, single caller |

### Contour nodes (15)

**SignalProcessor (8):**
1. `process_signal` — orchestrator (process + __init__ + _empty_result)
2. `preprocess_baseline` — linear baseline removal
3. `find_dot_forward` — forward onset scan (+ _is_valid_forward_point)
4. `find_dot_reverse` — backward onset scan (+ _is_valid_backward_point)
5. `determine_dot_position` — median/merge of forward+backward candidates
6. `check_exponential_rise` — convexity validation at candidate points
7. `remove_background` — baseline subtraction before dot
8. `create_signal_fit` — LMS curve fitting

**Calculator (6):**
9. `initialize_calculator` — __init__ with routing logic
10. `process_exe_line` — ExModeler-based processing
11. `process_line` — SignalProcessor-based processing (+ _process_channel)
12. `find_thresholds` — per-channel threshold computation
13. `calculate_cts` — CT calculation (+ _find_ct_values)
14. `find_intersection` — linear interpolation threshold crossing

**Standalone (1):**
15. `convert_row_to_column` — row-major to column-major reorder

### Edges (16)

```
process_signal ──calls──> preprocess_baseline
process_signal ──calls──> find_dot_forward
process_signal ──calls──> find_dot_reverse
process_signal ──calls──> determine_dot_position
process_signal ──calls──> remove_background
process_signal ──calls──> create_signal_fit
find_dot_forward ──calls──> check_exponential_rise
find_dot_reverse ──calls──> check_exponential_rise
initialize_calculator ──calls──> process_exe_line
initialize_calculator ──calls──> process_line
initialize_calculator ──calls──> convert_row_to_column
initialize_calculator ──calls──> calculate_cts
process_line ──calls──> process_signal
calculate_cts ──calls──> find_intersection
calculate_cts ──calls──> convert_row_to_column
find_thresholds ──uses──> initialize_calculator
```

## Graph structure after loading

- Total in CodeGraph: 39 nodes, 16 edges (24 pre-existing + 15 new)
- New nodes: 15, new edges: 16
- Most connected: `process_signal` (6 outgoing edges)
- Two clusters: SignalProcessor subgraph (8 nodes) connected to Calculator subgraph (6 nodes + 1 shared) via `process_line -> process_signal`
- Every new contour node has at least one edge. No standalone micros.

## Verification

### 1. Graph presence — pass
15 new nodes and 16 new edges present in `/graph`.

### 2. Leaf node: `determine_dot_position` — pass
- Depth 0: full code + all specs + contract ✓
- Depth 1: `process_signal` — spec_summary + accepts/returns ✓
- Depth 2: 6 nodes (create_signal_fit, find_dot_forward, find_dot_reverse, preprocess_baseline, process_line, remove_background) — spec_ticket only ✓
- Depth 3+: remaining nodes — id only ✓

### 3. Most connected: `process_signal` — pass
All three Dunbar levels present:
- Depth 0: full as_is (code + specs + contract)
- Depth 1: 7 direct neighbors with spec_summary + contract
- Depth 2: check_exponential_rise, initialize_calculator — spec_ticket only
- Depth 3: calculate_cts, convert_row_to_column, find_thresholds, process_exe_line — name only
- Depth 4: find_intersection — name only
- Depth 999: 24 disconnected nodes from previous experiment — name only

### 4. Count match — pass
15 nodes planned = 15 loaded. 16 edges planned = 16 loaded.

### 5. No standalone micros — pass
All nodes have kind "contour" and at least one edge.

## Open issues
1. **Bug in original code preserved.** `Calculator.__init__` accesses `exe_model.thresholds` unconditionally on line 317, but `exe_model` can be `None` (the `else` branch). This would crash at runtime. Preserved as-is per constraints — noted in the node's spec_summary.
2. **`_find_thresholds` is never called.** The method exists in Calculator but no code in the provided listing calls it. The `uses` edge to `initialize_calculator` is a data dependency (it reads `self.line` and `self.cycles`), not a call. Whoever calls it externally would need another edge.
