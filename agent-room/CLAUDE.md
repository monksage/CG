# Contour Graph

Code-as-graph system. Code lives in SQLite as graph nodes, not files. MCGK gate routes all inter-service communication by name.

## Key files

- `agents/corporal.md` — corporal-rank agent instructions. Read first if you are a corporal.
- `corporal_orders/` — task artifacts for corporal agents.

## Environment

This machine has a system-wide HTTP proxy (`http_proxy`). It intercepts localhost traffic. When running services or curl against localhost, set `NO_PROXY=localhost,127.0.0.1` to bypass it. Without this, httpx, curl, and other HTTP clients will fail to reach local services.

## Rules

- Do not modify files outside your assigned scope.
- Do not create files unless the task requires it.
- If something feels wrong architecturally, raise it — don't silently work around it.
- All agent prompts and artifacts are written in English.
