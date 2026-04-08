# Build Script — Graph to Runnable File

## Role

You are writing a build script that assembles code from CodeGraph nodes into a single runnable Python file.

## Objective

Create `CG/services/codegraph/build.py` — a CLI script that:
1. Takes an entry node id as argument.
2. Walks the graph from that node, collecting all reachable nodes via edges.
3. Assembles their code into one .py file with proper import header and topological ordering.
4. Writes the result to stdout or a specified output file.

Usage: `python build.py --entry process_signal --output built.py`

## How it should work

1. `GET /graph` from CodeGraph API to get all edges.
2. Starting from the entry node, follow all outgoing edges recursively to collect the full set of reachable nodes.
3. `GET /node/{id}` for each collected node to get code and imports.
4. Topologically sort nodes by edges — callees before callers. If cycles exist, break them arbitrarily.
5. Collect all `imports` fields from all nodes into a deduplicated set. This is the import header.
6. Handle name collisions: if two nodes have the same id (shouldn't happen, but guard it), append `_2`, `_3` etc.
7. Write: import header, then blank line, then each node's code in topological order, separated by two blank lines.

## Context

CodeGraph API at `http://localhost:39051`.

```
GET /graph              — returns all node ids + edges
GET /node/{id}          — returns full node (code, imports, specs, edges)
```

Nodes store clean code without imports. The `imports` field is a JSON array of import strings like `["import numpy as np", "from datetime import datetime"]`. These are external dependencies. Inter-node dependencies are expressed as edges, not imports — the build script resolves them by putting all code in one file.

## Constraints

- Pure Python script. Only stdlib + httpx for API calls.
- No frameworks, no templates, no Jinja.
- Under 100 lines.
- Use `NO_PROXY=localhost,127.0.0.1` when making HTTP requests.
- Do not modify any existing files. Create only `build.py`.

## Verification

1. `python build.py --entry process_signal --output test_build.py` — should produce a file.
2. The output file starts with collected imports, followed by node code in dependency order.
3. `python -c "import ast; ast.parse(open('test_build.py').read())"` — the output must be valid Python (parseable AST). It does not need to run — external dependencies may be missing. But it must be syntactically correct.
4. `python build.py --entry load_marker_data --output test_build2.py` — different entry point, different subset of nodes.
5. Both outputs contain only nodes reachable from the entry, not the entire graph.

## Report

Write to `corporal_reports/build_script_report.md`.

Include: how you handled imports, the topological sort approach, sample output for `--entry process_signal` (first 30 lines), and verification results.

## Subagent guidance

This is under 100 lines. Do it yourself.
