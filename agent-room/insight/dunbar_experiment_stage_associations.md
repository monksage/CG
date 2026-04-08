# Dunbar Context Model — Related Work & Associations

Last updated: 2026-03-25

---

## 1. Context Degradation Under Length ("Lost in the Middle")

**Liu et al. (2024)** — "Lost in the Middle: How Language Models Use Long Contexts"
Stanford / UW. Published in Transactions of the Association for Computational Linguistics (TACL), vol. 12.

LLM performance follows a U-shaped curve by position: accuracy is highest when relevant information is at the start or end of context, and drops 30%+ when placed in the middle. Holds even for models explicitly trained on long context. Tested on multi-document QA and key-value retrieval.

**Relevance to Dunbar:** Provides a mechanistic explanation for why full-source context (Experiment 07, S1 = 2018 lines) produces worse results than Dunbar (S3 = 80 lines). Full source scatters relevant information across positions; Dunbar concentrates it at depth 0.

- Paper: https://aclanthology.org/2024.tacl-1.9/
- arXiv: https://arxiv.org/abs/2307.03172

---

**Chroma (2025)** — Context Rot research

Tested 18 frontier models (GPT-4.1, Claude Opus 4, Gemini 2.5). Every model degrades at every context length increment — not just near the limit. Three compounding mechanisms: lost-in-the-middle effect, attention dilution (quadratic pairwise relationships), and distractor interference (semantically similar but irrelevant content actively misleads the model).

**Relevance to Dunbar:** "Distractor interference" maps directly to the pattern-copying mechanism observed in Experiments 06–07. Code that is semantically similar to the task but implements it suboptimally (e.g., `get_rescaled` in Exp 07, `main()` in Exp 06) is the worst kind of distractor — it is relevant enough to anchor on, but wrong enough to degrade output.

- Summary: https://www.morphllm.com/context-rot

---

**Context Length Alone Hurts LLM Performance Despite Perfect Retrieval (2025)**

Even when a model can perfectly retrieve all evidence (100% exact match recitation), performance still degrades substantially as input length increases. Tested on GSM8K (math), MMLU (QA), and HumanEval (code). Up to 17% drop for Mistral and 20% for Llama under 30K filler tokens, even with evidence placed right before the question.

**Relevance to Dunbar:** Shows that context reduction isn't just about helping the model *find* the right information — shorter context improves *reasoning quality* even when retrieval is perfect. Directly supports the Dunbar hypothesis: the benefit is not retrieval, it is forcing the model to think rather than copy.

- arXiv: https://arxiv.org/html/2510.05381v1

---

## 2. Descriptions > Raw Code (API Documentation Effect)

**AllianceCoder — Gu et al. (2025)** — "What to Retrieve for Effective Retrieval-Augmented Code Generation? An Empirical Study and Beyond"

Empirically tested what to retrieve for repo-level code generation. Key finding: providing in-context code and API documentation yields significant gains, but blindly retrieving similar code examples can *hurt* performance by up to 15%. AllianceCoder decomposes queries into sub-tasks and retrieves API descriptions for each.

**Relevance to Dunbar:** This is the closest published result to our Experiment 06–07 findings. AllianceCoder shows descriptions > raw similar code. Dunbar extends this: *structured summaries at graduated depth* > both raw code and flat descriptions.

- arXiv: https://www.alphaxiv.org/overview/2503.20589v1
- Referenced in: https://arxiv.org/html/2508.08322v1

---

**Selective Prompt Anchoring (Spa) — Tian et al. (2024)**

LLMs pay less attention to user prompts as more code tokens are generated ("attention dilution"). Spa amplifies attention to selected prompt tokens, improving Pass@1 by up to 12.9%. Demonstrates that LLMs exhibit misalignment between their attention and what a human programmer would focus on.

**Relevance to Dunbar:** Dunbar's graduated context achieves a similar effect architecturally: by removing code and keeping descriptions, the model's attention budget is spent on *intent and contracts* rather than on copying existing patterns. Dunbar is structural Spa.

- arXiv: https://arxiv.org/html/2408.09121

---

## 3. Graph-Based Code Representation for LLMs

**CodexGraph — Liu et al. (2024)** — "Bridging Large Language Models and Code Repositories via Code Graph Databases"
Published at NAACL 2025.

Builds a property graph of code where nodes = symbols (MODULE, CLASS, FUNCTION, METHOD, FIELD, GLOBAL_VARIABLE) and edges = relationships (CONTAINS, HAS_METHOD, INHERITS, USES, CALLS). LLM agent queries the graph via Cypher. Evaluated on CrossCodeEval, SWE-bench, EvoCodeBench.

**Relevance to Dunbar:** CodexGraph uses a similar node-edge model but retrieves *raw code* from nodes. Contour Graph stores code + graduated specs at each node. CodexGraph answers "what code exists" — Contour Graph answers "what does this code do and how does it relate to its neighbors."

- arXiv: https://arxiv.org/html/2408.03910v2
- NAACL: https://aclanthology.org/2025.naacl-long.7.pdf

---

**Code-Craft (HCGS) — Hierarchical Graph-Based Code Summarization (2025)**

Builds a code graph (files → classes → functions), then generates structured summaries per node using an LLM (Claude Haiku 3.5). Bottom-up traversal: higher-level summaries inherit context from constituent components. Used for context retrieval.

**Relevance to Dunbar:** Most structurally similar to Contour Graph. Key differences: (1) HCGS summarizes for *retrieval* — Contour Graph summarizes for *agent consumption during generation*; (2) HCGS uses uniform summary depth — Contour Graph uses graduated depth (as_is / summary / ticket / name) based on graph distance; (3) HCGS does not test whether summaries produce better generated code than raw code — our Experiments 06–07 do.

- arXiv: https://arxiv.org/html/2504.08975

---

**GraphCodeAgent — Dual-Graph Retrieval-Augmented Code Generation (2025)**

Uses two graphs: a Requirement Graph (NL → concepts) and a Structural-Semantic Code Graph (code elements + relationships). ReAct-style agent does multi-hop traversal. Ablation shows 12.2pp drop when graph traversal is removed.

**Relevance to Dunbar:** Validates graph-based code retrieval. GraphCodeAgent focuses on *retrieval precision* — Contour Graph focuses on *abstraction level of retrieved context*.

- Summary: https://www.emergentmind.com/topics/graphcodeagent

---

**Knowledge Graph Based Repository-Level Code Generation (2025)**

Retrieves a two-hop subgraph from the target node and passes nodes + edges to the LLM as context for generation. Close to Dunbar depth 1–2 in structure.

**Relevance to Dunbar:** Shares the two-hop subgraph retrieval pattern. Does not experiment with abstraction levels (code vs. summary vs. contract). Does not report an inverted-U quality curve.

- arXiv: https://arxiv.org/html/2505.14394v1

---

**LocAgent — Graph-Guided LLM Agents for Code Localization (2025)**

Graph-based code indexing with function-level node granularity. Tested subgraph rendering formats: tree-based format outperforms JSON, Graphviz DOT, and raw text. Including all entity attributes consistently *hurts* performance — noise from irrelevant attributes degrades localization.

**Relevance to Dunbar:** Confirms that *less information per node improves agent performance* — directly supports the Dunbar spec graduation principle (depth 2 = ticket, depth 3 = name only).

- arXiv: https://arxiv.org/html/2503.09089v1

---

## 4. Context Engineering Frameworks

**ACE — Agentic Context Engineering (2025)** — Zhang et al.

Treats contexts as evolving "playbooks" that accumulate and refine strategies. Identifies two failure modes: *brevity bias* (dropping domain insights for concise summaries) and *context collapse* (iterative rewriting erodes details over time). On AppWorld leaderboard, matches top production agent using a smaller open-source model.

**Relevance to Dunbar:** Brevity bias is the risk at Dunbar depth 3+ (name only). Context collapse is the risk if specs are auto-generated and iteratively refined without quality control. ACE validates that structured context curation beats raw context dumping.

- arXiv: https://arxiv.org/abs/2510.04618

---

**Confucius Code Agent (CCA) — 2025**

Unified orchestrator with advanced context management, persistent note-taking for cross-session learning, and modular extensions. Achieves 59% Resolve@1 on SWE-Bench-Pro. Evaluates whether quality of context summarization affects downstream agent performance.

**Relevance to Dunbar:** CCA's finding that summarization quality affects agent performance directly supports our conclusion that spec_summary and spec_ticket quality are the most important node fields.

- arXiv: https://arxiv.org/pdf/2512.10398

---

**Context Engineering for Coding Agents — Martin Fowler / Thoughtworks (2025)**

Practical framework: rules (guardrails), skills (lazy-loaded context), tools (bash, search), memory files. Key insight: "Context engineering is curating what the model sees so that you get a better result." Recommends thinking strategically about which context interfaces are necessary per task.

**Relevance to Dunbar:** Dunbar is a formalization of this principle: instead of ad-hoc curation, graduated specs define a repeatable, graph-distance-based context strategy.

- Article: https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html

---

## 5. Code Repetition and Pattern Copying

**Code Copycat Conundrum (2025)** — "Demystifying Repetition in LLM-based Code Generation"

First empirical study of repetition in LLM code generation across 19 models and 3 benchmarks. Repetition is more severe in code than in natural language (rep-2: 9.1 vs 3.92 for text). Code cloning in training data causes models to learn and reproduce repetitive patterns. Proposes DeRep, a rule-based detection and mitigation technique.

**Relevance to Dunbar:** Documents the pattern-copying phenomenon at the token level. Our experiments show it at the *architectural* level: when given existing code, LLMs copy not just syntax but design decisions (e.g., no-undo error handling from `main()`, mathematically incorrect `get_rescaled`).

- arXiv: https://arxiv.org/html/2504.12608v1

---

## 6. Multi-Agent and Repo-Level Code Generation

**MASAI (2024)** — Modular Architecture for Software Engineering AI

Specialized sub-agents for planning, localization, code generation, testing. 28.3% resolution on SWE-Bench Lite.

**Relevance to Dunbar:** Each MASAI sub-agent has a scoped context — analogous to each Dunbar agent seeing only its graph neighborhood. MASAI scopes by *task type*; Dunbar scopes by *graph distance*.

- Referenced in: https://arxiv.org/html/2508.08322v1

---

**Anthropic — Building Effective Agents (2024)**

Recommends starting with single LLM calls + retrieval before adding agent complexity. Emphasizes tool documentation quality: "tools will likely be an important part of your agent... give just as much prompt engineering attention." Warns against unnecessary abstraction layers.

**Relevance to Dunbar:** Validates the importance of spec quality over system complexity. Dunbar's spec_summary and spec_ticket *are* the tool documentation for neighboring agents.

- Article: https://www.anthropic.com/research/building-effective-agents

---

## Summary: What Dunbar Adds

| Existing finding | Source | Dunbar extension |
|---|---|---|
| More context → worse performance | Liu et al., Chroma | Identifies *optimal* context level via inverted-U curve |
| API descriptions > similar code | AllianceCoder | Graduated specs (summary > ticket > name) by graph distance |
| Graph-based code indexing works | CodexGraph, HCGS, LocAgent | Stores specs at nodes, not just code; agents consume specs, not code |
| Less per-node detail can help | LocAgent | Formalizes via Dunbar depth levels (0–3+) |
| Context curation improves output | ACE, Fowler, CCA | Provides repeatable, distance-based curation strategy |
| LLMs copy patterns from code | Code Copycat | Shows copying at *design* level, not just syntax |

**Unique contributions not found in literature:**
1. Inverted-U quality curve across abstraction levels (not just context length)
2. Mechanism: "full code → pattern copying, summaries → architectural thinking"
3. Graduated spec depth tied to graph distance (Dunbar circles model)
4. Empirical evidence that summary-level context produces code *better* than original codebase