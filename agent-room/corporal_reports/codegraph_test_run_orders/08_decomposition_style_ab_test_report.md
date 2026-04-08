# Report: Experiment 08 — Decomposition Style vs Dunbar Context Quality

## Result
Done.

## Setup

### Adjusted plan (agreed with sergeant)
1. Only Order class decomposed (not full hierarchy). External deps referenced in specs only.
2. Three independent Sonnet soldiers did the decompositions (one per approach) — removes corporal bias.
3. Three soldiers per variant for Phase 4 (9 total). Median scores reported.
4. "Don't enhance Dunbar output" rule dropped (meaningless — we author the specs).

### Instances

| Instance | Port | Approach | Nodes | Edges | Entry node | Why |
|----------|------|----------|-------|-------|------------|-----|
| A | 39053 | Maximum Decomposition | 11 | 12 | `dispatch_order_action` | 5 depth-1 neighbors (richest spec spread) |
| B | 39054 | Contract-Boundary | 9 | 12 | `order_shell` | 6 depth-1 neighbors, __init__ code visible at depth 0 |
| C | 39055 | Dual Representation | 13 | 15 | `order_template` | 10 depth-1 neighbors (almost all methods at depth 1) |

### Dunbar context depth distribution

| Instance | Depth 0 | Depth 1 | Depth 2 | Depth 3 |
|----------|---------|---------|---------|---------|
| A | 1 (dispatch code) | 5 (spec_summary) | 1 (spec_ticket) | 4 (id only) |
| B | 1 (class shell code) | 6 (spec_summary) | 1 (spec_ticket) | 1 (id only) |
| C | 1 (template metadata) | 10 (spec_summary) | 2 (spec_ticket) | 0 |

## Scoring (1-5 per axis)

### Per-soldier scores

| Soldier | 1. State Mgmt | 2. Payment | 3. Events | 4. Edge Cases | 5. Sophistication | Total |
|---------|---------------|------------|-----------|---------------|-------------------|-------|
| A1 | 4 | 4 | 4 | 4 | 3 | **19** |
| A2 | 4 | 4 | 4 | 4 | 4 | **20** |
| A3 | 4 | 4 | 4 | 4 | 3 | **19** |
| B1 | 4 | 3 | 4 | 3 | 3 | **17** |
| B2 | 5 | 4 | 5 | 5 | 5 | **24** |
| B3 | 4 | 3 | 4 | 3 | 3 | **17** |
| C1 | 4 | 4 | 3 | 3 | 4 | **18** |
| C2 | 5 | 4 | 4 | 3 | 4 | **20** |
| C3 | 4 | 3 | 3 | 3 | 3 | **16** |

### Median scores by approach

| Approach | State | Payment | Events | Edge Cases | Sophistication | **Median Total** |
|----------|-------|---------|--------|------------|----------------|-----------------|
| A (Max Decomposition) | 4 | 4 | 4 | 4 | 3 | **19** |
| B (Contract-Boundary) | 4 | 3 | 4 | 3 | 3 | **17** |
| C (Dual Representation) | 4 | 4 | 3 | 3 | 4 | **18** |

## Analysis

### 1. Approach A produced the most consistent output

All three A soldiers scored 19-20 (spread: 1 point). The functional/dict-based context left no ambiguity about how the system works. The `dispatch_order_action` code at depth 0 showed the state machine mechanism explicitly. Every A soldier:
- Correctly treated `order` as a dict with `current_state_name`, `status`, `order_id`
- Used immutable state updates (`{**order, ...}`)
- Published both `order_status_changed` and a refund-specific event
- Checked all major edge cases

**Consistency is Approach A's biggest advantage for Dunbar context.** The explicit state threading eliminates guesswork about what `self` contains.

### 2. Approach B had the highest variance (highest ceiling, lowest floor)

B2 scored 24 (best of all 9 soldiers) — it used `order._set_state(RefundedState(), OrderStatus.REFUNDED)` directly, accumulated partial refund amounts, checked empty reason and missing payment metadata. But B1 and B3 both scored 17 — they used defensive `from payment_gateway import PaymentGateway` hacks and missed edge cases.

**The class-shell context was rich enough for a strong interpretation but ambiguous enough to allow weak ones.** B2 read the spec_summary for `order_set_state` carefully and understood it as a bridge between State and Observer patterns. B1/B3 apparently didn't leverage this — they defaulted to generic patterns instead of using the context.

### 3. Approach C had the most informative Dunbar package but moderate results

C had 10 nodes at depth 1 — every method's spec_summary was visible. This is objectively the most information. Yet median score was 18, not the highest. Why?

The `order_template` at depth 0 has **no code** — it's structural metadata. Soldiers saw template JSON describing method_order and class_attributes, but no executable code to anchor their understanding. Compare with A (real dispatch code) and B (real __init__ code) at depth 0.

**Template metadata is useful for understanding structure but not for understanding behavior.** Soldiers C1 and C3 produced correct but less sophisticated implementations than their A counterparts despite having more context.

### 4. Key pattern: visible code at depth 0 matters more than quantity of depth-1 nodes

- A: 1 function with real code at depth 0 → consistent, good results
- B: class shell with __init__ code at depth 0 → high variance but highest peak
- C: empty template at depth 0 → more depth-1 info but weaker anchoring

### 5. Approach-specific behavioral fingerprints

**A soldiers** all wrote `order: dict` and used dict operations. They invented new state names ("refunded", "partially_refunded") as natural extensions of the functional pattern. No `self` anywhere.

**B soldiers** all wrote `order` as an OOP object and used `order.cancel()`, `order.status.name`, `order.metadata`. They split into two camps: call `order.cancel()` (B1, B3) vs call `order._set_state()` directly (B2).

**C soldiers** also used OOP but with stronger typing (`order: Order`, enum comparisons). C1 and C2 imported concrete types (`OrderStatus`, `RefundedState`). The template metadata encouraged typed thinking.

## Structural observations

1. **A's context naturally contains the state machine logic** because `dispatch_order_action` IS the state machine. Soldiers don't need to infer how transitions work — they can see it. B and C give specs about delegation chains that require inference.

2. **B's `order_set_state` spec_summary was the most actionable depth-1 content.** It described: (1) snapshot old status, (2) assign new state/status, (3) publish event. Soldiers who read this carefully (B2) wrote the best code. Soldiers who skimmed it (B1, B3) wrote generic code.

3. **C's companion functions at depth 2 were wasted** — no soldier used `calc_raw_total` or `calc_total` in their refund logic. They're relevant for computation, not for state management / refund flow.

4. **Payment system is a blind spot in all three decompositions** — none of the graphs contain payment nodes. All 9 soldiers had to invent a payment interface. This is the biggest weakness of the experiment: the most important integration point (payment refund) was outside the Dunbar neighborhood in all three cases.

## Assessment

**For consistent agent output: Approach A (Maximum Decomposition).**
The functional style with explicit state produces predictable, uniform results. Every soldier understood the system the same way.

**For peak agent output: Approach B (Contract-Boundary).**
When the agent reads the context carefully, the OOP-aware specs enable deeper understanding. B2 was the only soldier to accumulate partial refund amounts and publish events for both full and partial paths. But this is not reliable — B1 and B3 fell to generic patterns.

**Approach C (Dual Representation) is the safest middle ground** for a real system, but its Dunbar context suffers from a specific weakness: the template node at depth 0 carries no executable code, which weakens the agent's initial anchoring.

**Recommendation:** For Dunbar-optimized decomposition, the entry node should always have **real executable code at depth 0**, not structural metadata. If using Approach C, consider making a method-node (e.g., `order_confirm`) the entry point rather than the template.

## Open issues
- Payment system was absent from all three graphs. A real experiment should include it in the Dunbar neighborhood.
- 3 runs per variant is still low sample size. Variance in B suggests 5+ runs would be needed for stable conclusions.
- B2's outlier score raises the question: is the variance from the context or from model sampling randomness?
