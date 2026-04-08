# Report: Refactor SignalProcessor Contour via Soldier Using /context

## Result
Done.

## What was built
No new artifacts. Soldier modified 7 of 8 SignalProcessor nodes in CodeGraph via the API (code + specs on 6, specs-only on 1, code + specs on 1 more with a bug fix).

## Deviations from order
None.

## Verification
1. All 8 nodes exist and readable (200) — **pass**
2. At least 3 nodes modified — **pass** (7 modified)
3. `/context/process_signal` returns valid Dunbar package — **pass** (depth 0 full, depth 1 summaries, depth 2 tickets, correct structure)
4. Soldier report covers all 8 nodes with reasoning — **pass**

## Soldier prompt

```
## Role
You are a soldier agent refactoring a signal processing contour. You work exclusively through the CodeGraph API — you do NOT read files on disk.

## API
CodeGraph is running at `http://localhost:39051`. When making HTTP requests, always use `NO_PROXY=localhost,127.0.0.1` (set via environment or pass `--noproxy '*'` to curl).

Endpoints:
- `GET /node/{id}` — read a node (full code + specs + edges)
- `PUT /node/{id}` — update a node (send only fields you want to change)
- `GET /context/{id}` — Dunbar circle context package for neighbor awareness

## Task
Refactor the SignalProcessor contour — simplify logic, remove duplication, fix obvious problems. You decide what needs changing based on what you read from the API.

## Scope — 8 nodes
These are the only nodes you may touch:
1. `process_signal` (orchestrator)
2. `preprocess_baseline`
3. `find_dot_forward`
4. `find_dot_reverse`
5. `determine_dot_position`
6. `check_exponential_rise`
7. `remove_background`
8. `create_signal_fit`

## Dunbar context (from GET /context/process_signal)
[Full context package included — depth 0 code, depth 1 summaries, depth 2 tickets for all 8 nodes plus neighbors]

## How to work
1. Read each of the 8 nodes via `GET /node/{id}`. Study the actual code.
2. Identify problems: duplication, bugs, unclear logic, missing guards, silent exceptions, etc.
3. For each node you decide to change: update via `PUT /node/{id}` with improved code AND updated spec_ticket and spec_summary.
4. Do NOT change accepts/returns/tags/kind/language — only code, spec_ticket, spec_summary.

## Constraints
- Do NOT create new nodes.
- Do NOT delete nodes.
- Do NOT modify edges.
- Do NOT touch nodes outside the 8 listed above.
- Preserve the algorithmic intent — this is refactoring, not rewriting.

## Report
When done, return a detailed report covering ALL 8 nodes.
```

## Soldier report

### Nodes Modified: 7 of 8

**1. `process_signal` — MODIFIED**
Extracted `_empty_result()` helper to deduplicate `[0] * self.cycles` in two return paths.

**2. `preprocess_baseline` — MODIFIED**
Removed redundant `stat.xl()` call (computed once, reused). Added explicit parentheses for clarity. Changed `min(self.data)` to `self.data.min()`.

**3. `find_dot_forward` — MODIFIED**
`except:` → `except Exception:`. Guard raised from `< 5` to `< 6`. Loop upper bound extracted to variable. Compound negated condition rewritten as positive skip. Threshold extracted to named variable.

**4. `find_dot_reverse` — MODIFIED**
Same fixes as find_dot_forward: `except Exception:`, guard to `< 6`, positive-skip condition, named threshold variable.

**5. `determine_dot_position` — MODIFIED (specs only)**
Code unchanged — already clean. Specs updated for consistency.

**6. `check_exponential_rise` — MODIFIED**
Extracted three named variables (`diff_curr`, `diff_next`, `diff_far`) replacing repeated array indexing expressions. Both branches now clearly readable.

**7. `remove_background` — MODIFIED**
`except:` → `except Exception:`. Extracted `x_all = stat.xl(self.cycles)` to avoid redundant call. Named `baseline` variable.

**8. `create_signal_fit` — MODIFIED**
**Bug fix:** Guard clause now sets `self.fit = self.data.copy()` before returning. Previously, if `self.dot` was None or out of bounds, `self.fit` remained `None`, causing `AttributeError` when `process()` called `self.fit.tolist()`. Also: `except:` → `except Exception:`, extracted `x_all`.

### Summary table

| Metric | Count |
|--------|-------|
| Nodes read | 8 |
| Nodes modified (code + specs) | 6 |
| Nodes modified (specs only) | 1 |
| Bugs fixed | 1 |
| Bare `except:` replaced | 4 |
| Redundant computations removed | 3 |
| Code duplication reduced | 1 |
| Readability improvements | 2 |

## Signal loss assessment

**What the soldier got right:**
- Found the real bug (`create_signal_fit` leaving `self.fit = None`) without being told about it.
- Correctly identified and fixed all 4 bare `except:` statements — a genuine safety issue.
- Identified redundant `stat.xl()` calls across 3 nodes.
- Appropriately chose NOT to change the unusual convexity check in `check_exponential_rise` (`data[idx-1] - data[idx+2]` instead of standard second derivative), correctly noting it as existing algorithmic intent and flagging it in specs.
- Respected the "refactor not rewrite" constraint — no behavioral changes except the bug fix.

**What the soldier missed:**
- Did not notice that `process_signal` stores class constants (FRWRD, BCK_CT, etc.) that are referenced by child nodes. This cross-node coupling is fine but worth noting in specs for someone working on a single node in isolation.
- The guard change from `< 5` to `< 6` in find_dot_forward/reverse is arguably a behavioral change, not just a refactor. The original code used `< 5` intentionally or not — the soldier assumed `< 6` was better based on preprocess_baseline's guard, but the Savitzky-Golay window of 19 actually needs at least 19 points to work, so even `< 6` is too permissive. The soldier improved correctness but didn't go far enough.
- Did not flag the `process_line` → `process_signal` cross-boundary call relationship. The soldier's scope was correctly limited to 8 nodes, but it could have noted the dependency in specs.

**Was Dunbar context sufficient?**
Yes. The depth-1 summaries gave the soldier enough to understand each node's role and dependencies. The depth-0 full code of process_signal showed the orchestration flow. The soldier correctly used `GET /node/{id}` for deep reads of each node — the Dunbar context served as orientation, not as a substitute for reading actual code.

The experiment succeeds: an agent working through the graph API was able to find a real bug, make meaningful refactoring improvements, and produce a coherent report — all from the API alone, with no file access.
