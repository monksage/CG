# Dunbar Context Model — Experimental Validation

## What is Dunbar context

Contour Graph stores code as graph nodes in a database. Each node holds clean code, contracts (accepts/returns), and specifications at four levels of granularity inspired by Dunbar's social circles (5/15/50/150):

- **depth 0 (as_is):** full code + all specs. The node you're working on.
- **depth 1 (summary):** full description without code + contracts. Direct neighbors.
- **depth 2 (ticket):** 10-15 line summary. Neighbors of neighbors.
- **depth 3+ (name):** node id only. The name is chosen to be self-explanatory (e.g., `validate_jwt`, `subtract_nearby_background`).

An agent working on a node receives a context package assembled by the API: full detail on its target, decreasing detail with graph distance. The hypothesis is that this focused context is sufficient — and possibly superior — to giving the agent the full codebase.

## The concern

Observation from practice: LLM output quality appears to scale with input complexity. Simple input → simple output. Complex input → sophisticated output. If true, Dunbar's intentional context reduction would produce worse code than full-file access — agents would "dumb down" to match the apparent simplicity of summaries.

This concern was vital enough to test before building further infrastructure.

## Experiment 06 — Binary A/B test

**Setup:** Two Sonnet soldiers receive the same task: write `process_bulk_orders(orders, payment_method) -> dict` for a 900-line order processing system with 13 OOP design patterns (singleton, factory, strategy, observer, decorator, builder, state, iterator, proxy, chain of responsibility, adapter, template method, command).

- **Soldier A:** receives all 900 lines of source code.
- **Soldier B:** receives textual summaries + method contracts (accepts/returns). No code. Approximates Dunbar depth 1.

Both get the identical task description, word for word.

**Result:** Soldier B won 4 of 5 evaluation axes.

| Axis | Soldier A (full code) | Soldier B (Dunbar) |
|------|----------------------|-------------------|
| Edge cases | Handles validation + payment failure. No undo, no fraud, no state check. | Handles validation, payment failure, fraud detection, InvalidStateTransition, generic exceptions. |
| Infrastructure use | Uses 6/7 components. No EventBus. | Uses 6/7 components. No OrderHistory. Uses EventBus (fraud subscription). |
| Error recovery | Catches exception, records, continues. **Failed commands not undone** — orders left in CONFIRMED state with held warehouse reservations. | Catches RuntimeError, **calls pop_undo() to rollback**, distinguishes fraud from other failures, continues. |
| Report richness | 7 fields. | 8 fields including fraud_detected tracking. |
| Code sophistication | 54 lines, 4 decision points. | 94 lines, 9 decision points, 3 exception types. |

**Key finding:** Soldier A saw `main()` in the source, which processes orders without undo on failure. It copied this pattern. Soldier B, not seeing `main()`, designed its own error handling from architectural descriptions — and made better choices. Full code induced pattern copying; summaries forced architectural thinking.

**Token cost:** A used 14K tokens for 54 lines. B used 12K tokens for 94 lines. Better output with fewer tokens.

## Experiment 07 — Five-point gradient

**Setup:** Five Sonnet soldiers receive the same task: write `compare_lane_intensities(lane_ids, marker_kb) -> dict` for a gel electrophoresis analysis codebase (27 nodes, 33 edges in CodeGraph, ~1071 lines of source).

Context gradient from maximum to zero:

| Soldier | Context | Size |
|---------|---------|------|
| S1 | Full source files including superseded v0 monoliths | ~2018 lines |
| S2 | Trimmed code — only directly relevant nodes | ~300 lines |
| S3 | Dunbar /context API output (depth 0 code, depth 1 summaries, depth 2 tickets) | ~80 lines JSON |
| S4 | Node names + accepts/returns contracts only | ~20 lines |
| S5 | Zero context — just the function signature | 0 lines |

All receive identical task description. Compared on 5 axes (edge cases, domain awareness, integration quality, error recovery, code sophistication) scored 1-5.

**Result:** Inverted U curve. Dunbar context (S3) scored highest.

| Context level | Score /25 |
|--------------|-----------|
| S1: Full source | 18 |
| S2: Trimmed code | 14 |
| **S3: Dunbar context** | **23** |
| S4: Contracts only | 14 |
| S5: Zero context | — (contaminated*) |

*S5 read other soldiers' output files from shared directory. Experimental design flaw — results invalid for S5.

**Key findings:**

1. **Full code → pattern copying.** S1 copied the existing `get_rescaled` function which compares lanes on raw pixel arrays without interpolation. This is the existing approach in the codebase, but it's mathematically incorrect for lanes of different pixel widths.

2. **Dunbar context → architectural design.** S3, not seeing `get_rescaled`, invented bp-grid interpolation: sort pixel/bp pairs for monotone interpolation, create a shared 500-point bp grid, interpolate all lanes onto it, then compare. This is the mathematically correct approach. It doesn't exist in the original codebase.

3. **S3 had the best error handling.** Without code to copy happy-path patterns from, it had to reason about what could go wrong: missing lanes → None, invalid marker_kb → validation, flat profiles → 0.0, pixel ≤ 0 → guard, unsorted bp pairs → sort before interp.

4. **Contracts alone are insufficient.** S4 had function names and signatures but called methods as standalone functions (wrong), invented ladder values (wrong), and built a domain model disconnected from reality. Summary-level descriptions are necessary to understand how components relate.

5. **Token efficiency.** S3 spent more tokens (21K) than S1 (16K) — summaries require more reasoning to reconstruct patterns. But the output quality justifies the cost. S4 spent the most tokens (26K) for the worst integration quality — too little context causes thrashing.

## Mechanism

The core finding across both experiments is the same:

**Full code causes pattern copying. Dunbar summaries force architectural thinking.**

When an LLM sees existing code, it anchors to existing patterns — even when those patterns are suboptimal. It copies method signatures, reuses data flows, follows the happy path. This is efficient but conservative: the output is never better than the input.

When an LLM sees architectural descriptions with contracts but without code, it must reconstruct the implementation from understanding. This is more expensive (more tokens, more reasoning) but produces solutions that can exceed the quality of the original codebase — because the LLM is designing, not copying.

The inverted U emerges because:
- Too little context (contracts only, zero) → the LLM doesn't understand the domain → wrong assumptions → bad code.
- Too much context (full source) → the LLM copies instead of thinking → adequate but unimaginative code.
- Focused context (Dunbar) → the LLM understands the domain but must think → best code.

## Implications for Contour Graph

1. **Dunbar is not a compromise — it is the optimal context strategy.** The architecture is validated.

2. **Spec quality matters more than code volume.** The difference between S3 (23/25) and S4 (14/25) is the difference between "summary + contracts" and "contracts only." Summaries carry the domain understanding that contracts alone cannot.

3. **spec_ticket and spec_summary are the most important fields in a node.** They are what neighboring agents actually consume. They must convey not just what a node does, but enough about the domain to enable good decision-making.

4. **Builder/tester loop validates correctness, not Dunbar.** An agent working from Dunbar context may produce better-designed code, but it may also have integration bugs (e.g., S3 didn't use MarkerRegression class, S6-B called LegacyWarehouseAdapter() without args). The build/test cycle catches these. Dunbar optimizes for design quality; testing optimizes for correctness. Both are needed.

## Open questions

- Does the inverted U hold at 10K+ lines? The advantage would likely be stronger — full source becomes unprocessable, Dunbar remains focused.
- Does the curve shift for Opus vs Sonnet? Opus may handle full context better due to larger effective reasoning capacity.
- What is the minimum spec quality for Dunbar to work? If specs are poorly written (by a weak decomposition agent), does the advantage disappear?
- How does Dunbar perform on tasks that require cross-cutting changes (touching 10+ nodes)? The current experiments tested single-function generation.
