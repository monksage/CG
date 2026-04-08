# Decompose a Folder Into Graph Nodes

## Role

You are decomposing a multi-file Python project into graph nodes and loading them into CodeGraph.

## Objective

Read all files in `D:\tmp\unit_divide` (and subdirectories). Decompose the entire codebase into nodes and edges, load into CodeGraph, verify the graph is connected and Dunbar circles work.

## How to decompose

Work in three phases.

**Phase 1 — Survey.** Read every file. Understand the overall structure: what each file does, how files depend on each other, what's code and what's not. Decide what belongs in the graph and what doesn't.

**Phase 2 — Plan.** Produce a decomposition plan before making any API calls:
- List every node with its classification (contour/micro/config).
- For each micro, identify its parent.
- Map all call/use relationships — within files and across files. These become edges.
- If the codebase is large enough that doing this alone would be slow, identify which parts can be delegated to soldiers for parallel decomposition. Each soldier gets a module/file and clear boundaries.

**Phase 3 — Load.** Execute the plan via API. Create all nodes, then all edges. If you delegated decomposition to soldiers, consolidate their results and handle cross-module edges yourself.

## Node rules

- A node is the smallest unit of code containing at least one decision (if/try/loop with condition).
- No decision = micro. Inline into parent. No standalone micros with zero edges.
- Node names are verbs: `parse_image`, `compute_regression`, `render_gel_line`. What_do only.
- Clean code without imports. Imports in the `imports` field.
- Fill `accepts`, `returns`, `spec_ticket`, `spec_summary`, `tags`.
- Every contour node must have at least one edge after loading.
- You decide what is code, what is config, and what is not worth loading. Justify exclusions in the report.

## Context

CodeGraph API at `http://localhost:39051`. There are already nodes from previous experiments — do not delete them, add alongside.

```
POST /node              — create node
POST /edge              — add edge {source_id, target_id, edge_type}
GET  /node/{id}         — read node
GET  /graph             — all node ids + edges
GET  /context/{id}      — Dunbar circle context package
```

## Constraints

- Do not modify the original files in `D:\tmp\unit_divide`. Read only.
- Do not modify existing nodes in CodeGraph.
- Use `NO_PROXY=localhost,127.0.0.1` for all HTTP requests.
- Python 3.11+ assumed.

## Verification

1. `GET /graph` — new nodes and edges present. Edge count > 0.
2. Pick a leaf node. `GET /context/{id}` — verify depth 0 full, depth 1 summaries.
3. Pick the most connected node. `GET /context/{id}` — verify multiple Dunbar levels.
4. No standalone micro nodes (kind=micro with zero edges).
5. Node + edge counts match Phase 2 plan.

## Report

Write to `corporal_reports/codegraph_test_run_orders/04_decompose_folder_report.md`.

Include:
- Phase 1 survey: what each file is, what you included/excluded and why.
- Phase 2 plan: full node list + edge map.
- If you used soldiers: what you delegated, the prompts you gave them, what they returned.
- Graph stats: total nodes, edges, clusters, most connected node.
- Verification results with /context output samples.

## Subagent guidance

This is ~2200 lines across 13 Python files plus non-code files. If after Phase 1 you see independent modules that can be decomposed in parallel, spawn soldiers for them. Keep cross-module edge mapping to yourself. Each soldier prompt must include: which files to decompose, the node rules above, and the API details. Soldiers do not need to know about other modules — you stitch the graph together.
