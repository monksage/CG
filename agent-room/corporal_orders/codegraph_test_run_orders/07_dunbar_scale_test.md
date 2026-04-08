# Dunbar Scale Test — Context Density vs Output Quality

## Role

You are running a controlled experiment measuring how context density affects LLM output quality. This is a two-phase task. Complete Phase 1 and stop. Phase 2 begins only after you receive explicit confirmation.

## Background

CodeGraph API at `http://localhost:39051` contains nodes from a real codebase (gel electrophoresis image analysis tool). 27 nodes with 33 edges, covering: image processing, regression analysis, background deletion, gel line extraction. Use `NO_PROXY=localhost,127.0.0.1` for all requests.

## Phase 1 — Propose task (DO THIS FIRST, THEN STOP)

1. Explore the graph: `GET /graph` to see all nodes and edges.
2. Read a few central nodes via `GET /node/{id}` to understand the domain.
3. Pick an entry point node and call `GET /context/{id}` to see how Dunbar circles look in practice.
4. Design a task — one function that a soldier would write. The task must:
   - Be relevant to this codebase (not generic).
   - Require understanding of at least 3-4 neighboring nodes to do well.
   - Be ambiguous enough that context quality will affect the solution (not a mechanical transformation).
   - Be expressible in one sentence + a function signature.
5. Write the proposed task to `corporal_reports/codegraph_test_run_orders/07_proposed_task.md` with:
   - The function signature.
   - One sentence description.
   - Which entry node you'd use for /context.
   - Why this task is a good test (what would a well-informed soldier do differently than a poorly-informed one).

**STOP after writing the proposal. Do not proceed to Phase 2 until you receive confirmation.**

## Phase 2 — Run experiment (ONLY after confirmation)

Spawn 5 soldiers in parallel. Same task, same function signature, same one-sentence description. Different context:

### Soldier 1 — Full source files
Read the original source files from `D:\tmp\unit_divide` (the app/ and regression/ directories relevant to the task). Give the soldier all relevant source files concatenated. Raw code, no summaries.

### Soldier 2 — Trimmed code
Only the source code of the nodes directly relevant to the task. Read them via `GET /node/{id}` and include their full code. No nodes beyond immediate relevance. ~200-400 lines, not 2000.

### Soldier 3 — Dunbar context from API
Call `GET /context/{entry_node_id}` and pass the result as-is to the soldier. This is what CodeGraph actually provides: depth 0 = full code, depth 1 = spec_summary + contracts, depth 2 = spec_ticket, rest = names. Do not modify or enhance the output.

### Soldier 4 — Names + contracts only
For all relevant nodes: only node id (the name) + accepts + returns fields. No code, no summaries, no tickets. The absolute minimum structural information.

### Soldier 5 — Zero context
Only the function signature and the one-sentence description. Nothing about the codebase. The lower bound.

### Soldier rules (apply to all 5)
- All soldiers must be Sonnet.
- All receive the identical task description — word for word, same function signature, same one-sentence description.
- Do NOT hint at quality expectations, edge cases, or complexity.
- Do NOT tell any soldier about the experiment or other soldiers.
- Each soldier writes result to a separate file: `soldier_1.py` through `soldier_5.py` in `corporal_reports/codegraph_test_run_orders/`.

## Verification (Phase 2)

After all 5 complete, compare on these axes:

1. **Edge case handling** — guards, error handling, boundary conditions.
2. **Domain awareness** — does it use domain-specific logic appropriate to the codebase, or generic boilerplate?
3. **Integration quality** — would it work with the existing code? Compatible types, correct assumptions about data formats?
4. **Error recovery** — what happens on bad input?
5. **Code sophistication** — decision points, defensive guards, type hints, docstring quality.

Produce a comparison table (5 soldiers × 5 axes) with brief notes per cell.

## Report

Write to `corporal_reports/codegraph_test_run_orders/07_dunbar_scale_test_report.md`.

Include:
- Phase 1 proposal (repeated for completeness).
- The exact prompt given to each soldier (full text, including their context).
- All 5 function outputs in full.
- The 5×5 comparison table.
- Assessment: is there a clear pattern? Does more context = better output, or is there a sweet spot?
- Note any soldiers that timed out or failed.

## Subagent guidance

Phase 1: do it yourself. Phase 2: five soldiers, all parallel. Do not interact with them after launch.
