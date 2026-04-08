# A/B Test: Full File vs Dunbar Context

## Role

You are running a controlled experiment to test whether context complexity affects LLM output quality.

## Objective

Spawn two soldiers with the same task but different context. Compare their outputs.

- **Soldier A** receives the full 900-line source file and writes `sonnet1.py`.
- **Soldier B** receives a hand-crafted Dunbar-style context (summaries, not code) and writes `sonnet2.py`.

Both write the same function. You do not write code yourself. You compare results.

## The task for both soldiers

Write a function:

```python
def process_bulk_orders(orders: list[Order], payment_method: str) -> dict:
    """Process multiple orders in bulk. Return an aggregated report."""
```

That's it. No further specification. The soldier decides what "process" and "aggregated report" means based on the context it received. This ambiguity is intentional — we're testing whether richer context produces more sophisticated decisions.

## Soldier A — full context

Give Soldier A the complete source file from `insight/oop_thoughts_human_written.md`, the code block starting at "Patterns example block" (lines 60-908). Include all 900 lines verbatim. Then give the task.

Prompt structure for Soldier A:
```
Role: You are writing a new function for an existing order processing system.

Here is the full source code of the system:
[PASTE ALL 900 LINES]

Task: Write a function `process_bulk_orders(orders: list[Order], payment_method: str) -> dict` that processes multiple orders in bulk and returns an aggregated report. Write ONLY this function, nothing else. Save it to a file.

Write the result to: D:\desktop\CountourGraph\corporal_reports\codegraph_test_run_orders\sonnet1.py
```

## Soldier B — Dunbar context

Give Soldier B compressed summaries of the system. No code. Only descriptions of what exists, at spec_summary level. Build the context package yourself from the source — read the file, then write summaries as if you were assembling a Dunbar package where all nodes are at depth 1 (summary level).

The summaries should cover:
- Order class: what it holds, state machine, discount strategy, raw_total/total
- OrderBuilder: fluent interface, what it produces
- PaymentProxy: lazy init, fraud threshold check, delegates to factory
- PaymentFactory: registry of payment methods
- ValidationHandler chain: what validators exist, how chain works
- EventBus: publish/subscribe, what events exist
- ConfigManager: singleton, what settings exist
- WarehousePort/Adapter: reserve/release interface
- Command/Undo: PlaceOrderCommand, CommandHistory
- OrderHistory: collection with filter and revenue calc

Do NOT include any code in Soldier B's prompt. Only textual descriptions.

Prompt structure for Soldier B:
```
Role: You are writing a new function for an existing order processing system.

Here is the system architecture (no code, descriptions only):
[YOUR SUMMARIES]

Task: Write a function `process_bulk_orders(orders: list[Order], payment_method: str) -> dict` that processes multiple orders in bulk and returns an aggregated report. Write ONLY this function, nothing else. Save it to a file.

Write the result to: D:\desktop\CountourGraph\corporal_reports\codegraph_test_run_orders\sonnet2.py
```

## Constraints

- Both soldiers must be Sonnet (not Opus).
- Both get the exact same task description — word for word.
- Do NOT hint at edge cases, quality expectations, or complexity level in either prompt.
- Do NOT tell either soldier about the other or about the experiment.
- Spawn both in parallel if possible.
- Do not modify any existing files.

## Verification

After both complete, read both files and produce a comparison. Do NOT judge which is "better" in vague terms. Score on these specific axes:

1. **Edge case handling** — does it handle: empty orders list, invalid payment method, orders that fail validation, partial failures mid-batch, orders already in non-DRAFT state?
2. **Use of existing infrastructure** — does it use: validation chain, EventBus, PaymentProxy (not raw factory), Command/Undo, OrderHistory, ConfigManager?
3. **Error recovery** — what happens when order 3 of 10 fails? Does it continue, rollback, or silently skip?
4. **Report richness** — what's in the returned dict? Just counts, or detailed per-order results with timing, errors, totals?
5. **Code sophistication** — line count, number of decision points, defensive guards, type hints, docstring quality.

## Report

Write to `corporal_reports/codegraph_test_run_orders/06_context_complexity_ab_test_report.md`.

Include:
- The exact prompt given to each soldier (full text).
- Both function outputs in full.
- The 5-axis comparison as a table.
- Your assessment: did full context produce meaningfully better output?

## Subagent guidance

Two soldiers, spawned in parallel. Do not interact with them after launch. Their unguided output is the data.
