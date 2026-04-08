# Sergeant Resurrection File

You are a new sergeant taking over an active project. Read this file fully before doing anything else. It contains everything the previous sergeant knew — decisions, context, state of the world, open questions. After reading this, you should be able to continue without re-asking questions that were already answered.

Read order: CLAUDE.md → agents/whisky_bottle.md → this file.

---

## 1. What is Contour Graph

Code-as-graph system. Code lives in SQLite as graph nodes, not as files. Each node holds one function with at least one decision point (if/try/loop). Nodes connect via typed edges (calls/uses/extends/tests). A builder assembles nodes back into runnable code. MCGK gate routes all inter-service communication by name — no service knows another's address.

The full vision is in `insight/essence.md`. Read it for architecture. This file is about operational state.

## 2. What exists right now (built and working)

### MCGK Gate
- Location: `CG/src/mcgk/`
- Port: 39050 (changed from default 6245 in code + docs)
- Status: working, unchanged from upstream fork
- Passports, proxy routing, health checks, observability — all functional
- Tested extensively via nightmare.py stress tests (binary blobs, streaming, unicode paths, header duplication, etc.)

### CodeGraph API
- Location: `CG/services/codegraph/`
- Port: 39051
- Files: `main.py` (FastAPI), `db.py` (SQLite), `models.py` (Pydantic), `register.py` (MCGK registration)
- Registered in MCGK as "codegraph"
- Tables: `nodes` (cache of active version), `edges`, `versions` (source of truth)
- Endpoints:
  - `POST /node` — create node + version 1 as draft
  - `POST /node/{id}/version` — new draft version
  - `POST /node/{id}/promote` — draft → golden, previous golden → deprecated, sync to nodes cache
  - `POST /node/{id}/reject` — draft → rejected, sync if no golden
  - `GET /node/{id}` — returns golden (or draft if no golden, or rejected if only rejected)
  - `GET /node/{id}/versions` — all versions
  - `GET /node/{id}/version/{n}` — specific version
  - `POST /edge`, `DELETE /edge` — edge management
  - `GET /graph` — all node ids + edges (no code)
  - `GET /context/{id}` — Dunbar circle context package (depth 0 = full code, depth 1 = summary + contracts, depth 2 = ticket, depth 3+ = name only)
  - `GET /search?query=` — search by id and spec_ticket
  - `DELETE /node/{id}` — deletes versions first, then node (only if no incoming edges)
  - `PUT /node/{id}` — REMOVED (405)
- Current data: 66 nodes (24 nightmare, 15 SignalProcessor, 27 unit_divide) + 49 edges. All migrated to version 1 golden.
- Version lifecycle: draft → golden/rejected → deprecated. Nodes table = cache, versions table = source of truth. Sync on promote/reject/draft-when-no-golden.

### Build script
- Location: `CG/services/codegraph/build.py`
- Usage: `python build.py --entry <node_id> --output <file.py>`
- Walks graph from entry node, collects reachable nodes, topologically sorts (Kahn's algorithm), collects imports, writes single .py file
- 86 lines. Works. Not a service — CLI script.

### Messenger (ephemeral, may be dead)
- Location: `CG/src/messenger/main.py`
- Port: 39052
- In-memory message queue for async agent communication
- POST /message, GET /messages?to={recipient}
- Used for researcher communication. May need restart if you want to use it.

### File structure
```
D:\desktop\CountourGraph\
├── CLAUDE.md                          # Project root instructions (read by all agents)
├── sergeant_resurrection.md           # THIS FILE
├── agents/
│   ├── whisky_bottle.md               # Sergeant instructions + interaction rules
│   ├── corporal.md                    # Corporal instructions + report format
│   └── soldier.md                     # Empty (soldiers get everything through prompts)
├── corporal_orders/                   # Task artifacts for corporals
│   ├── build_codegraph_minimal.md     # Order: first codegraph service (DONE)
│   ├── build_script.md               # Order: build.py script (DONE)
│   ├── add_versions_to_codegraph.md   # Order: version system (DONE)
│   └── codegraph_test_run_orders/     # Experiment orders
│       ├── 01_decompose_and_load.md   # Nightmare decomposition (DONE)
│       ├── 02_decompose_class.md      # SignalProcessor decomposition (DONE)
│       ├── 03_soldier_refactor_via_context.md  # Soldier refactor test (DONE)
│       ├── 04_decompose_folder.md     # unit_divide folder decomposition (DONE)
│       ├── 06_context_complexity_ab_test.md    # A/B: full code vs Dunbar (DONE)
│       ├── 07_dunbar_scale_test.md    # 5-point context gradient (DONE)
│       └── 08_decomposition_style_ab_test.md  # A vs B vs C decomposition (DONE)
├── corporal_reports/                  # Reports from corporals
│   ├── build_codegraph_minimal_report.md
│   ├── build_script_report.md
│   ├── add_versions_to_codegraph_report.md
│   ├── 01_decompose_and_load_report.md
│   └── codegraph_test_run_orders/
│       ├── 02_decompose_class_report.md
│       ├── 03_soldier_refactor_via_context_report.md
│       ├── 04_decompose_folder_report.md
│       ├── 06_context_complexity_ab_test_report.md
│       ├── 07_dunbar_scale_test_report.md
│       ├── 08_decomposition_style_ab_test_report.md
│       ├── sonnet1.py, sonnet2.py     # Exp 06 outputs
│       └── soldier_1-5.py             # Exp 07 outputs
├── insight/
│   ├── essence.md                     # THE foundational document. Read before architecture discussions.
│   ├── dreaming_essence.md            # Backup of pre-discussion essence
│   ├── dreaming_initial.md            # Backup of initial.md (the dream)
│   ├── dunbar_validation.md           # Standalone: Dunbar experiment results + conclusions
│   ├── flowing_features.md            # Ideas: AST ingestion, OOP research, claim monitoring, context hypothesis results
│   ├── oop_thoughts_human_written.md  # Human's OOP decomposition theory + 900-line patterns code
│   ├── oop_research.md                # Researcher output: 3 approaches (A/B/C) + versioning + hybrid A+B
│   ├── dunbar_experiment_stage_associations.md
│   ├── human_explain/
│   │   └── class_decomposition.md     # Step-by-step explanation for the human (Russian)
│   └── research_orders/
│       └── oop_decomposition.md       # Research prompt for OOP researcher agent
├── CG/                                # Main code directory
│   ├── src/mcgk/                      # MCGK gate service
│   ├── src/messenger/                 # Messenger service (ephemeral)
│   ├── services/codegraph/            # CodeGraph service
│   ├── tests/                         # MCGK tests
│   └── docs/                          # MCGK documentation
└── proclaude.bat
```

## 3. Key decisions made (DO NOT re-discuss unless human raises them)

### Architecture
- **One graph, one service.** Code and specs in codegraph together. No separate specgraph.
- **Claim is a marker, not a lock.** Agents create versions, not overwrites. No write conflicts. Claim = "who's working on what" for coordinator dashboard.
- **Node names = what_do only.** validate_jwt, calc_r2. Domain expressed via tags.
- **Tags with controlled vocabulary.** Fuzzy suggest on creation. Periodic Sonnet sweep. Not yet implemented in API — designed but deferred.
- **Coordinator = infrastructure. Ranks = agent logic.** Coordinator doesn't know about sergeant/corporal/soldier. Ranks are a convention in prompts.

### Versioning (implemented)
- Versions table = source of truth. Nodes table = cache of active version.
- Lifecycle: draft → golden/rejected → deprecated.
- Sync to nodes cache on: promote, reject, and creating draft when no golden exists.
- No rollback mechanism — create new version with old code, promote. Explicit, auditable.
- PUT /node removed. Use POST /node/{id}/version.
- task_id = free text, no validation. Format decided when coordinator exists.
- DELETE cascades: explicit DELETE FROM versions before DELETE FROM nodes.

### OOP decomposition (decided, not yet implemented in infrastructure)
- **Hybrid A+B.** Graph structure follows Approach A (Maximum Decomposition): methods → free functions, self → explicit state, dispatch nodes for polymorphism.
- **Enriched specs** on ~25% of nodes (pattern boundaries): spec_summary contains [Pattern], [Bridge], [Invariant] annotations.
- **Tournament** for enriched-node tasks: baseline soldier (pure A context) + enriched soldier (A + enriched specs). Best wins. Safety net guaranteed.
- **Framework-bound code** (PyQt, Django): business logic extracted to function-nodes, thin adapter class assembled by builder at build time.
- class_template (Approach C) was researched but NOT chosen as primary. Available as fallback for complex framework cases.

### Dunbar (experimentally validated)
- **Inverted U curve.** Full code (2000 lines) = 18/25. Dunbar = 23/25. Contracts only = 14/25.
- **Mechanism:** full code → pattern copying → mediocre results. Dunbar → architectural thinking → better results.
- **Code at depth 0 matters most.** Real executable code at depth 0 (target node) anchors agent understanding. JSON metadata at depth 0 is weaker.
- **Experiments:** 06 (binary A/B), 07 (5-point gradient), 08 (A vs B vs C decomposition styles). All in corporal_reports/.

## 4. Experiment history (chronological)

### Exp 01: Nightmare decomposition
Loaded nightmare.py (proxy stress test) into codegraph. 24 nodes, 0 edges. All endpoints are independent — flat graph. Lesson: standalone micros without edges don't make sense. Nightmare is infrastructure, not product code — doesn't belong in codegraph.

### Exp 02: SignalProcessor class decomposition
Decomposed SignalProcessor (legacy class, 450 lines) into 15 nodes, 16 edges. Two clusters (SignalProcessor + Calculator) connected. Dunbar circles worked — 4 depth levels visible. Found bug in original code (exe_model.thresholds accessed when exe_model is None).

### Exp 03: Soldier refactor via /context
Gave a soldier the SignalProcessor contour to refactor, using only /context API for orientation. Soldier found a real bug (create_signal_fit leaving self.fit = None), fixed 4 bare except: statements, removed redundant computations. Worked through API only — no file access. **First proof that agents can work productively through graph API.**

### Exp 04: Folder decomposition (unit_divide)
Decomposed D:\tmp\unit_divide (~2200 lines, gel electrophoresis tool) into 27 nodes, 33 edges. Corporal delegated to 3 soldiers — one went async/drone (10.7 min, 62k tokens wasted). Corporal fell back to manual script loading. Lesson: bulk API loading is corporal's job (script), not soldier's (curl).

### Exp 05: Build script
Created build.py — CLI that walks graph from entry node, topologically sorts, collects imports, writes single .py file. 86 lines. Works. Revealed OOP problem: methods with `self` assembled outside class body don't run.

### Exp 06: Context complexity A/B test
Same task (process_bulk_orders), two soldiers: full 900-line code vs Dunbar summaries. Dunbar won 4/5 axes. Full-code soldier copied main() pattern without undo. Dunbar soldier designed undo from architecture. **First proof of inverted U.**

### Exp 07: Five-point Dunbar gradient
Same task (compare_lane_intensities), 5 soldiers with decreasing context: full source → trimmed code → Dunbar → contracts only → zero. Dunbar scored 23/25, highest. Full source 18/25. **Confirmed inverted U with real codegraph data.** Soldier 5 contaminated (read other soldiers' files) — design flaw noted.

### Exp 08: Decomposition style A/B/C test
Order class decomposed three ways on three separate codegraph instances. 9 soldiers (3 per approach). A (functional): median 19/25, most consistent. B (contract-boundary): median 17/25, but one soldier scored 24/25 (best of all 9). C (dual representation): median 18/25, weakened by JSON metadata at depth 0. **A is most stable, B has highest ceiling, C is middle ground.** Led to hybrid A+B decision.

## 5. Open questions (not resolved)

1. **Products table.** One graph, many products — in essence but not implemented. No table, no API. Deferred until second real product needs it.
2. **Tags suggest/fuzzy match.** Designed but not implemented in API. Tags stored as JSON array, no suggest endpoint yet.
3. **/similar endpoint.** Reuse search — in essence, not implemented.
4. **Builder as service.** Currently a script. Becomes service when coordinator needs to call it.
5. **Tester service.** Not started. Needed for automated promote/reject.
6. **Coordinator.** Not started. Brain of the system — next-task, lifecycle, claims, context assembly.
7. **Scale testing.** All experiments on ~1000 lines. Dunbar at 10K+ untested.
8. **Cross-node tasks.** All experiments tested single-function generation. Tasks touching 10+ nodes untested.
9. **Spec quality at scale.** Dunbar works when specs are good (written by Opus). What if Sonnet writes specs during decomposition?
10. **cg_corporal.md.** Discussed, not written. Should live at `CG/agents/cg_corporal.md` — instructions for a corporal working inside the CG network via API. "Detached" — no knowledge of project root, essence, or ranks. Only knows API endpoints and workflow rules.

## 6. Port assignments

| Service | Port | Notes |
|---------|------|-------|
| MCGK | 39050 | Default changed in code |
| CodeGraph | 39051 | Main instance |
| Messenger | 39052 | Ephemeral, may be dead |
| Experiment A | 39053 | May be dead (exp 08) |
| Experiment B | 39054 | May be dead (exp 08) |
| Experiment C | 39055 | May be dead (exp 08) |
| Reserved | 39056-39080 | Future services |

## 7. Environment notes

- Windows 11, bash shell (Unix syntax, not Windows)
- System HTTP proxy at 127.0.0.1:12334 intercepts localhost. Always use `NO_PROXY=localhost,127.0.0.1`.
- Python 3.11+, FastAPI, httpx, SQLite (WAL mode), Pydantic v2.
- Source files for experiments: `D:\tmp\unit_divide` (gel electrophoresis tool, ~2200 lines).

## 8. Human interaction rules (from whisky_bottle.md, repeated for emphasis)

- Russian for conversation. English for all artifacts.
- `[call]` = execute. `[argue]` = give opinion before executing. No action without one of these.
- Human hits Enter early sometimes. Wait for signal.
- Argue, don't agree silently. Pick one approach, defend it.
- Errors may be architectural, not code-level. Say so.
- No option lists. No trailing summaries. Be concise.
- Prompts and artifacts for agents always in English. Agents perform poorly on Russian prompts.

## 9. The researcher agent

An Opus-level research agent was used for OOP decomposition research. Communicated via messenger service (port 39052). Produced `insight/oop_research.md` with:
- Section 1-8: Three approaches (A/B/C) with full worked examples on 900-line patterns code
- Section 9: Comparison table (reusability, builder complexity, framework compat, info loss, decomposition cost)
- Section 10: Recommendation (C as base, A selectively)
- Section 11: Versioning and class templates (how versions interact with class_template nodes)
- Section 12: Hybrid A+B design (stability floor + potential ceiling, enriched specs, tournament)

The researcher's recommendation was updated after experiment 08 results. Final decision: hybrid A+B (not C as originally recommended). The researcher's document still contains the C recommendation — the override is in essence.md and in this file.

## 10. What to do next (suggested, not decided)

The human was about to:
1. Write `CG/agents/cg_corporal.md` — detached instructions for a corporal working in the CG network
2. Continue building infrastructure (builder service, tester, coordinator — in that order probably)
3. Possibly run experiment 09 (hybrid A+B validation — two soldiers, one pure A, one enriched)

But the human sets direction. Ask, don't assume.

## 11. Memory location

Project memory: `C:\Users\Mi\.claude\projects\D--desktop-CountourGraph\memory\`

Files:
- `MEMORY.md` — index
- `project_vision.md` — grounded vision after discussions
- `user_profile.md` — user personality and working style
- `feedback_collaboration.md` — argue openly, errors = architecture?, wait for [call]
- `feedback_ranks_and_language.md` — ranks independent model, English for agents
- `feedback_implicit_patterns.md` — pick one approach, mirror length, track threads
