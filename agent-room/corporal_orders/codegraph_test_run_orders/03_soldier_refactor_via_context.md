# Refactor SignalProcessor Contour via Soldier Using /context

## Role

You are a corporal supervising a soldier who will refactor code through the CodeGraph API. You do not write code yourself in this task. You prepare the soldier's context, launch the soldier, and report results.

## Objective

Spawn a soldier subagent to refactor the SignalProcessor contour (8 nodes in CodeGraph). The soldier must:
1. Read context from CodeGraph API via `GET /context/{id}` — this is its only source of truth about the code.
2. Refactor the nodes: simplify logic, remove duplication, fix obvious problems.
3. Write changes back via `PUT /node/{id}`.

You are testing whether an agent can work productively through a graph API using Dunbar circle context.

## Your workflow

### Step 1 — Prepare soldier context

Call `GET http://localhost:39051/context/process_signal` to get the full Dunbar context package for the SignalProcessor cluster. This is what the soldier will work from.

The 8 SignalProcessor nodes are:
- `process_signal` (orchestrator, 6 outgoing edges)
- `preprocess_baseline`
- `find_dot_forward`
- `find_dot_reverse`
- `determine_dot_position`
- `check_exponential_rise`
- `remove_background`
- `create_signal_fit`

### Step 2 — Write soldier prompt

Spawn a soldier with the following structure:

1. **Role:** You are refactoring a signal processing contour. You work exclusively through the CodeGraph API.
2. **API:** CodeGraph at `http://localhost:39051`. Use `NO_PROXY=localhost,127.0.0.1`. Endpoints: `GET /node/{id}` to read, `PUT /node/{id}` to update, `GET /context/{id}` for neighbor context.
3. **Task:** Refactor the SignalProcessor contour — simplify logic, remove duplication, fix obvious problems. You decide what needs changing based on what you read.
4. **Context:** Include the full /context/process_signal output so the soldier has the Dunbar package. Also list all 8 node ids so it knows the scope.
5. **How to work:** Read each node via GET /node/{id}. Decide what to change. Update via PUT /node/{id} with improved code and updated specs. Update spec_ticket and spec_summary to reflect changes.
6. **Constraints:** Do not create new nodes. Do not delete nodes. Do not modify edges. Only update existing node code and specs. Do not touch nodes outside the 8 listed.
7. **Report back:** Return a detailed report of every change made and why. For each node: what was wrong, what you changed, what you left alone and why. If you found bugs, describe them. If you chose not to fix something, explain why.

### Step 3 — Evaluate

After the soldier returns, verify the changes:
1. `GET /node/{id}` for each of the 8 nodes — confirm code was updated.
2. `GET /context/process_signal` — confirm the context package still assembles correctly.
3. Read the soldier's report and include it in full in your own report.

## Constraints

- You do not write or modify code. The soldier does all code work.
- Do not give the soldier information about bugs or problems you know about. Let it discover issues from the code itself.
- Do not pre-read the nodes yourself beyond the /context call. The soldier should be the one doing deep reads.
- Use `NO_PROXY=localhost,127.0.0.1` for all HTTP requests.

## Verification

1. All 8 nodes still exist and are readable — pass/fail.
2. At least 3 nodes were modified by the soldier — pass/fail (if fewer, the soldier didn't engage meaningfully).
3. /context/process_signal still returns valid Dunbar packages — pass/fail.
4. Soldier report covers all 8 nodes with reasoning — pass/fail.

## Report

Write to `corporal_reports/codegraph_test_run_orders/03_soldier_refactor_via_context_report.md`.

Include these extra sections beyond standard format:

```
## Soldier prompt
The exact prompt you gave the soldier (full text).

## Soldier report
The soldier's full report as returned.

## Signal loss assessment
What the soldier missed, misunderstood, or interpreted differently from the original code. Did the Dunbar context give it enough information?
```

## Subagent guidance

One soldier. Give it the full task. Do not micromanage — the point is to see how it handles autonomous work through the API.

## Prolong order

Prompt:
       Role

       You are a soldier agent refactoring a signal processing contour. You work exclusively through the CodeGraph   
       API — you do NOT read files on disk.

       API

       CodeGraph is running at http://localhost:39051. When making HTTP requests, always use
       NO_PROXY=localhost,127.0.0.1 (set via environment or pass --noproxy '*' to curl).

       Endpoints:
       - GET /node/{id} — read a node (full code + specs + edges)
       - PUT /node/{id} — update a node (send only fields you want to change)
       - GET /context/{id} — Dunbar circle context package for neighbor awareness

       Task

       Refactor the SignalProcessor contour — simplify logic, remove duplication, fix obvious problems. You decide   
       what needs changing based on what you read from the API.

       Scope — 8 nodes

       These are the only nodes you may touch:
       1. process_signal (orchestrator)
       2. preprocess_baseline
       3. find_dot_forward
       4. find_dot_reverse
       5. determine_dot_position
       6. check_exponential_rise
       7. remove_background
       8. create_signal_fit

       Dunbar context (from GET /context/process_signal)

       This is what the graph looks like from the orchestrator's perspective:

       Depth 0 — full code (process_signal):
       class SignalProcessor:
           FRWRD = 3
           BCK_CT = 3
           BACK_THRES_PERCENT_FORWARD = 0.05
           BACK_THRES_PERCENT_BACKWARD = 0.04
           DIBKTOL = 15
           DOT_WINDOW = 10
           SIGDOT_OFFSET = 8
           MAX_INDEX = 39

           def __init__(self, data, cycles):
               self.data = np.array(data)
               self.cycles = cycles
               self.signal_found = False
               self.dot = None
               self.forwards = []
               self.backwards = []
               self.fit = None

           def process(self):
               if len(self.data) == 0:
                   return [0] * self.cycles, [0] * self.cycles
               self._preprocess()
               self._find_dot_forward()
               self._find_dot_reverse()
               if not self._determine_dot_position():
                   return [0] * self.cycles, [0] * self.cycles
               self._remove_background()
               self._create_fit()
               return self.data.tolist(), self.fit.tolist()

       Depth 1 — summaries of direct neighbors:
       - preprocess_baseline: Baseline removal using first 6 points. Linear model from stat.xl(cycles)[:6] and       
       self.data[:6]. Subtracts slope*x, adds abs(intercept), shifts minimum to zero. Guards data < 6.
       - find_dot_forward: Forward onset scan. Savitzky-Golay smoothing, derivative max. Loop 5 to MAX_INDEX-FRWRD.  
       Rolling average, delta check (dI >= d_avg + 0.05*(d_max-d_avg) AND d_avg >= 0 AND dI >= 15). Exponential rise 
       check. Appends to self.forwards.
       - find_dot_reverse: Backward onset scan. Same smoothing. Start from argmax-5, backward to dy_max-4. Reversed  
       thresholds (0.04). Appends to self.backwards.
       - determine_dot_position: Merges forward/backward candidates. Forwards: median. If backwards overshoot,       
       averages. Fallback: backwards max. Returns bool.
       - remove_background: Background subtraction. Guards dot None/<=0. Linear fit on [dot-10, dot), subtracts,     
       zeros pre-dot. try/except silently.
       - create_signal_fit: LMS curve fitting. sigdot = min(39, dot+8). Fits LMS, splices fit[:sigdot] +
       data[sigdot:]. Fallback: data.copy().
       - process_line: (Calculator node, not in scope) Standard line processing, calls SignalProcessor.process() per 
       channel.

       Depth 2 — tickets only:
       - check_exponential_rise: Validates exponential rise at candidate onset. Checks FRWRD=3 consecutive points.   
       Forward: increasing differences (convexity). Backward: reverse. Returns False on any failure.
       - initialize_calculator: Calculator init, not in scope.

       How to work

       1. Read each of the 8 nodes via GET /node/{id}. Study the actual code.
       2. Identify problems: duplication, bugs, unclear logic, missing guards, silent exceptions, etc.
       3. For each node you decide to change: update via PUT /node/{id} with improved code AND updated spec_ticket   
       and spec_summary.
       4. Do NOT change accepts/returns/tags/kind/language — only code, spec_ticket, spec_summary.

       Constraints

       - Do NOT create new nodes.
       - Do NOT delete nodes.
       - Do NOT modify edges.
       - Do NOT touch nodes outside the 8 listed above.
       - Preserve the algorithmic intent — this is refactoring, not rewriting.

       Report

       When done, return a detailed report covering ALL 8 nodes:
       - For each node: what was wrong (if anything), what you changed, what you left alone and why.
       - If you found bugs, describe them.
       - If you chose not to fix something, explain why.
       - Summary: how many nodes modified, key improvements made.