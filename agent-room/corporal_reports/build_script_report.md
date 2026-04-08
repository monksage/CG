# Report: Build Script — Graph to Runnable File

## Result
Done.

## What was built
`CG/services/codegraph/build.py` — 86-line CLI script that assembles CodeGraph nodes into a single .py file.

Usage: `python build.py --entry <node_id> [--output file.py]`

## Deviations from order
None.

## Verification

1. `python build.py --entry process_signal --output test_build.py` — **pass**. File produced (8 nodes: check_exponential_rise, create_signal_fit, determine_dot_position, find_dot_forward, find_dot_reverse, preprocess_baseline, process_signal, remove_background).

2. Output starts with collected imports, followed by node code in dependency order — **pass**. Import header: `import numpy as np`, `from model.Supply.utils import Statistic as stat`, `from model.Models.LMS import LMS, lmcoef`, `from model.Models.Linear import Linear`. Then code blocks in topological order (callees first).

3. `python -c "import ast; ast.parse(open('test_build.py').read())"` — **pass**.

4. `python build.py --entry load_marker_data --output test_build2.py` — **pass**. Single node (leaf, no outgoing edges).

5. Both outputs contain only reachable nodes — **pass**. process_signal: 8 nodes, load_marker_data: 1 node.

### Sample output (process_signal, first 30 lines)
```python
import numpy as np
from model.Supply.utils import Statistic as stat
from model.Models.LMS import LMS, lmcoef
from model.Models.Linear import Linear

# --- check_exponential_rise ---
def _has_exponential_rise(self, j, direction):
    for m in range(self.FRWRD):
        idx = j + m * direction
        if idx - 1 < 0 or idx + 2 >= len(self.data):
            return False
        ...
```

## Implementation notes

- **Imports**: parsed from each node's `imports` JSON field, deduplicated preserving first-seen order.
- **Topological sort**: Kahn's algorithm. Cycle remnants appended at end. Reversed so callees come before callers.
- **NO_PROXY**: set via `os.environ.setdefault` before any httpx calls.

## Open issues
None.
