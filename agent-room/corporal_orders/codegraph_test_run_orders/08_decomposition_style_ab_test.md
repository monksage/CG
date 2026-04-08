# Experiment 08: Decomposition Style vs Dunbar Context Quality

## Role

You are running an experiment to determine which OOP decomposition style produces the best Dunbar context for agent work. This is the most complex experiment yet — three parallel graphs, three decompositions, three soldiers.

## Background

Read `D:\desktop\CountourGraph\insight\oop_research.md` — it describes three approaches to OOP decomposition:
- **A: Maximum Decomposition** — classes dissolved into free functions with explicit state threading. No `self`.
- **B: Contract-Boundary** — classes split along contract boundaries. `self` preserved for stateful methods. Class shells + bound methods.
- **C: Dual Representation** — every method is a node (with `self`), plus a class_template (JSON metadata) for reconstruction. Companion free functions for reusable logic.

Read `D:\desktop\CountourGraph\insight\oop_thoughts_human_written.md` — the "Patterns example block" at the end contains the 900-line source code with 13 OOP patterns. The `Order` class (lines 310-352 in that block) is the target.

## Objective

Decompose the Order class and its immediate dependencies three ways (A, B, C), load each into a separate CodeGraph instance, then give three soldiers the same task using Dunbar context from each graph. Compare output quality.

## Phase 1 — Setup three CodeGraph instances

Start three instances of CodeGraph on different ports with separate databases:

```
cd D:\desktop\CountourGraph\CG\services\codegraph

CODEGRAPH_PORT=39053 CODEGRAPH_DB_PATH=experiment_a.db python main.py &
CODEGRAPH_PORT=39054 CODEGRAPH_DB_PATH=experiment_b.db python main.py &
CODEGRAPH_PORT=39055 CODEGRAPH_DB_PATH=experiment_c.db python main.py &
```

Use `NO_PROXY=localhost,127.0.0.1` for all HTTP requests.

## Phase 2 — Decompose and load

Decompose the `Order` class **and all classes it interacts with** from the patterns code. Order depends on: OrderItem, OrderStatus, OrderState hierarchy (6 state classes), DiscountStrategy hierarchy (4 strategies), EventBus, NoDiscount. Include all of these — they form Order's Dunbar neighborhood.

### Instance A (port 39053) — Maximum Decomposition

Follow Approach A from oop_research.md:
- Every method becomes a free function with `state: OrderData` as first arg.
- `__init__` becomes `create_order() -> OrderData`.
- `OrderData` is a data-schema-node (no code, just typed schema).
- State pattern: dispatch node + transition functions.
- Strategy pattern: free functions, no classes.
- All edges explicit: `calls`, `reads_state`, `writes_state`, `implements`, `dispatches`.

### Instance B (port 39054) — Contract-Boundary

Follow Approach B from oop_research.md:
- Order splits into two contracts: "state management" and "order data."
- State classes stay as single nodes (small enough).
- Class-shell for Order with bound methods.
- Strategies become free functions (single-method classes).
- Edges: `calls`, `binds`, `implements`, `extends`.

### Instance C (port 39055) — Dual Representation

Follow Approach C from oop_research.md:
- class_template node for Order (JSON: name, bases, class_attributes, method_order).
- Every method is a separate node with `self` preserved.
- Companion free functions for `raw_total` and `total` (pure computations).
- Strategies: free functions (no template, too small).
- State classes: single nodes (no template, too small).
- Edges: `calls`, `member_of`, `implements`, `alias_of`.

For each instance: create all nodes via POST /node, create all edges via POST /edge. Fill spec_ticket and spec_summary for every node — these are what Dunbar will serve to the soldiers.

## Phase 3 — Get Dunbar context from each graph

For each instance, call `GET /context/{entry_node}` where entry_node is the most central Order-related node:
- Instance A: `GET http://localhost:39053/context/create_order` (or whichever is the Order orchestrator)
- Instance B: `GET http://localhost:39054/context/order_confirm` (or the most connected bound method)
- Instance C: `GET http://localhost:39055/context/order_confirm` (the method-node)

Pick the entry node that produces the richest Dunbar spread (most depth levels, most neighbors). You may try a few and choose the best.

Save each context package — you'll give it verbatim to the soldiers.

## Phase 4 — Run soldiers

Same task for all three:

```
Write a function `process_refund(order, reason: str, partial_amount: float | None = None) -> dict` that handles full or partial refunds for an order. It should validate the refund is possible, execute the refund through the payment system, update order state, notify via events, and return a detailed result dict. Write ONLY this function.
```

Three soldiers, each Sonnet, each gets:
- The task above (identical, word for word).
- The Dunbar context package from their respective CodeGraph instance (verbatim JSON from /context).
- NO other context. No source files. No summaries you wrote. Only what the API returned.

Soldiers write to:
- `corporal_reports/codegraph_test_run_orders/soldier_a.py`
- `corporal_reports/codegraph_test_run_orders/soldier_b.py`
- `corporal_reports/codegraph_test_run_orders/soldier_c.py`

Spawn all three in parallel.

## Phase 5 — Compare

Score on 5 axes (1-5 each):

1. **State management** — does it check current order state before refunding? Handle already-cancelled/already-refunded? Use state transitions correctly?
2. **Payment integration** — does it call refund through the payment system correctly? Handle payment failure?
3. **Event notification** — does it publish events via EventBus? Which events?
4. **Edge cases** — partial refund > total? Negative amount? None order? Order with no payment?
5. **Code sophistication** — decision points, type hints, error handling depth, return dict richness.

## Constraints

- Do not modify the main CodeGraph instance (port 39051). Use only experiment instances (39053-39055).
- All soldiers must be Sonnet.
- All soldiers get identical task text.
- Do not enhance Dunbar output — pass it as-is from the API.
- Kill all three experiment CodeGraph instances when done.

## Report

Write to `corporal_reports/codegraph_test_run_orders/08_decomposition_style_ab_test_report.md`.

Include:
- Node counts and edge counts per instance.
- The entry node chosen per instance and why.
- The actual /context output given to each soldier (or a representative summary if too long).
- All three function outputs in full.
- The 3×5 comparison table with scores.
- Assessment: which decomposition style produced the best Dunbar context for this task?
- Any structural observations: did one style's Dunbar package naturally contain more relevant information?

## Subagent guidance

Phase 1-3: do yourself. This requires understanding all three approaches and making consistent decomposition decisions. Phase 4: three soldiers in parallel. Phase 5: yourself.
