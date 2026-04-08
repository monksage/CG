# Flowing Features

Ideas that emerged during work and are worth preserving. Not committed to, not designed — just crystallized enough to not lose.

## AST-based edge ingestion

When a corporal decomposes a folder into graph nodes, the most expensive part is mapping call relationships across files. The corporal has to read every file, hold the whole picture, and manually trace who calls whom. This doesn't scale — at 2000+ lines the corporal's context starts to strain.

A lightweight AST parser (Python's ast.parse + ast.walk) can extract function calls, class inheritance, and imports mechanically. No LLM needed. The output is a raw call graph: function X calls Y, class A extends B, module M imports N. This is not a node graph — it's a structural skeleton. But it gives the corporal a head start: instead of "read all files and figure out the relationships", the task becomes "here are the proposed edges, review, correct, and load."

This could live as a CodeGraph endpoint — `POST /ingest` accepts a file or folder path, runs the AST pass, and returns suggested nodes (function boundaries) and edges (call relationships). The corporal reviews the suggestions, adjusts node boundaries (merging micros, splitting god functions), fills in specs, and loads. Automation of the mechanical part, human/agent judgment on the meaningful part.

Not a priority until manual decomposition proves to be the bottleneck. Orders 01-04 are testing that hypothesis.

## OOP as projection — classes are not nodes

Classes, like files, are a human abstraction. In runtime, OOP compiles to flat function calls with vtable dispatch. The graph doesn't need classes as a concept — it needs functions with explicit contracts.

Decomposition of OOP code means: unroll classes into standalone functions, make `self` state explicit in accepts/returns, express polymorphism as routing nodes with "alternative_to" edges, express inheritance as explicit calls to parent functions.

This is more expensive at decomposition time but produces a cleaner graph: all dependencies visible as edges, no hidden state in MRO or closures.

**Open question:** Framework-bound code (Qt, Django) expects objects with methods. GUI callbacks like `button.clicked.connect(self.on_click)` assume an object reference. Without `self`, you need closures or partial application, and you're fighting the framework's assumptions. This may mean that framework integration code stays as class-nodes (kind="class"), while business logic decomposes into functions. Not resolved — needs a real OOP codebase to test against.

**Principle (proposed, not in essence yet):** "Classes are projection, like files. At decomposition, agents unroll OOP patterns into explicit functions with contracts."

**Unsolved: framework-bound inheritance.** PyQt, Django, etc. require your code to exist as subclasses of their classes. `class MyWindow(QMainWindow)` — Qt's event loop calls overridden methods via virtual dispatch. You can extract business logic into function-nodes, but the glue class must remain a class. Proposed "shell" node type (thin class, only wiring) was rejected as too narrow — doesn't generalize to all OOP patterns.

**Deeper problem (raised by user):** If F = set of all valid functions and C = set of all valid classes, then allowing whole classes as nodes reduces the useful F (functions that could be reused) and promotes duplication. A class-node is a monolith that can't be partially reused. The point of the graph is granular reuse — class-nodes defeat that.

**class_shell + binds approach (detailed, not validated):** A class decomposes into: one node kind="class_shell" containing class declaration, inheritance, `__init__` with instance attributes. Methods become separate contour nodes with edge_type="binds" to the shell. Static methods and classmethod-turned-static become free contour nodes without binds. Builder sees "binds" → inserts code inside class body with correct indentation. "calls" without "binds" → places outside class.

Weaknesses identified:
1. `self` as implicit dependency — contracts can't express which attributes a method actually touches, only "self"
2. Method ordering in assembled class — cosmetic but matters for human projection
3. Micro methods with binds (e.g., one-line `return self._get_real().refund()`) — no parent to inline into, awkward as standalone nodes
4. Inheritance chain requires topological ordering through "extends" edges — builder complexity grows
5. Reusability: a method with binds is locked to its class. Extracting reusable logic into a separate free node is the agent's job at decomposition, not the graph's

**Status:** Open. class_shell + binds is a concrete proposal but not validated. Needs OOP decomposition + rebuild test (order planned).

## Claim-based agent liveness monitoring

Soldier 3 in order 04 ran for 10.7 minutes, consumed 62k tokens, and produced nothing useful — the corporal had already loaded the data manually. This is the "drone soldier" problem.

Solution from essence: claim with TTL. An agent that doesn't interact with the API within TTL (e.g., 600 seconds) gets auto-released. This is the same mechanism designed for node claims, applied to agent liveness. Coordinator tracks last API call timestamp per agent. No call within TTL = agent considered dead, task re-queued.

Not a separate service — a metric in the coordinator. Waiting for coordinator to exist before implementing.

## Context complexity hypothesis — VITAL, test immediately

Observation: LLM output quality scales with input complexity. When an agent reads a simple isolated function and is asked to write a companion function, it produces naive code (linear interpolation, no edge cases, zero-division bugs). When it reads a complex, well-engineered function, it produces correspondingly sophisticated code (multiple strategies, spline fitting, argument handling, edge cases, tests).

If true, this is a fundamental challenge for Contour Graph. Dunbar circles intentionally reduce context — depth 2 nodes show only spec_ticket (15 lines), depth 3+ show only the name. An agent working on a node sees a simplified, compressed view of the surrounding graph. If context complexity drives output quality, then the agent working from a Dunbar package will produce worse code than one reading the full codebase.

**Test design:** Same task, two soldiers. Soldier A receives the full 900-line OOP file and a task "add feature X". Soldier B receives a Dunbar context package from /context and the same task. Compare output quality: sophistication, edge case handling, consistency with surrounding code.

If Soldier A produces significantly better code, the small-contour hypothesis has a hole: granular context = granular (worse) output. The fix might be that spec_summary and spec_ticket need to convey not just what a node does, but the *level of engineering rigor* expected — essentially priming the agent's quality bar through specs, not through raw code volume.

**Status: TESTED. Hypothesis disproven — in the opposite direction.**

Experiments 06 and 07 both showed Dunbar context outperforms full code:
- Experiment 06 (A/B, OOP order system): Dunbar soldier won 4/5 axes. Full-code soldier copied `main()` error handling pattern without undo. Dunbar soldier designed undo from architectural understanding.
- Experiment 07 (5-level gradient, gel electrophoresis): Inverted U curve. Scores: full source 18/25, trimmed code 14/25, **Dunbar 23/25**, contracts-only 14/25. Dunbar soldier invented bp-grid interpolation (mathematically correct, absent from original code). Full-code soldier copied existing `get_rescaled` pattern (inferior approach).

**Mechanism:** Full code causes pattern copying. Dunbar summaries force architectural thinking. Less code + good summaries = better decisions. The LLM's quality doesn't scale with input complexity — it scales with input *focus*. Noise (dead code, irrelevant patterns, v0 monoliths) actively hurts.

**Implication:** Dunbar is not a compromise — it's the optimal context strategy. The architecture is validated. Spec quality matters more than code volume.

**Remaining questions:** Does the advantage hold at 10K+ lines? At what point does "full source" become so large that Sonnet can't process it at all? Does the inverted U shift for Opus vs Sonnet?
