"""Build script — assemble CodeGraph nodes into a single runnable .py file."""
from __future__ import annotations
import argparse, json, os, sys
import httpx

API = "http://localhost:39051"
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

def fetch_graph(c):
    r = c.get(f"{API}/graph"); r.raise_for_status(); d = r.json()
    return d["nodes"], d["edges"]

def fetch_node(c, nid):
    r = c.get(f"{API}/node/{nid}"); r.raise_for_status()
    return r.json()

def reachable(entry, edges):
    adj = {}
    for e in edges:
        adj.setdefault(e["source_id"], []).append(e["target_id"])
    visited, stack = set(), [entry]
    while stack:
        n = stack.pop()
        if n in visited: continue
        visited.add(n)
        stack.extend(adj.get(n, []))
    return visited

def topo_sort(nodes, edges):
    adj, in_deg = {}, {n: 0 for n in nodes}
    for e in edges:
        s, t = e["source_id"], e["target_id"]
        if s in nodes and t in nodes:
            adj.setdefault(s, []).append(t)
            in_deg[t] = in_deg.get(t, 0) + 1
    queue = sorted(n for n in nodes if in_deg[n] == 0)
    order = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for t in adj.get(n, []):
            in_deg[t] -= 1
            if in_deg[t] == 0: queue.append(t)
    order.extend(sorted(nodes - set(order)))  # cycle remnants
    order.reverse()  # callees before callers
    return order

def build(entry):
    client = httpx.Client(timeout=30)
    all_nodes, edges = fetch_graph(client)
    if entry not in all_nodes:
        print(f"Error: entry node '{entry}' not found", file=sys.stderr); sys.exit(1)
    nodes = reachable(entry, edges)
    order = topo_sort(nodes, edges)
    all_imports, code_blocks, seen = [], [], {}
    for nid in order:
        info = fetch_node(client, nid)
        for imp in json.loads(info.get("imports", "[]")):
            if imp not in all_imports: all_imports.append(imp)
        label = nid
        if nid in seen:
            seen[nid] += 1; label = f"{nid}_{seen[nid]}"
        else:
            seen[nid] = 1
        code_blocks.append(f"# --- {label} ---\n{info['code']}")
    parts = []
    if all_imports:
        parts.append("\n".join(all_imports)); parts.append("")
    parts.append("\n\n\n".join(code_blocks))
    return "\n".join(parts) + "\n"

def main():
    p = argparse.ArgumentParser(description="Build .py from CodeGraph nodes")
    p.add_argument("--entry", required=True)
    p.add_argument("--output", default=None)
    args = p.parse_args()
    result = build(args.entry)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(result, end="")

if __name__ == "__main__":
    main()
