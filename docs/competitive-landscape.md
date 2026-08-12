# Automation and graph-tool landscape

> Reviewed 2026-08-12. Percentages below are our estimates against the same
> workflow stages; they are not metrics published by the compared projects.

AI Context Linker overlaps with code graphs and context graphs, but its boundary
is different: it prepares a minimal project-development briefing for cloud AI
without publishing source-code bodies.

| Project | Estimated automation after setup | Required AI during indexing | Default input surface | Main difference |
|---|---:|---:|---|---|
| [GitNexus](https://github.com/nxpatterns/gitnexus) | 90–95% | 0% for the structural graph; AI is used for optional wiki generation | Repository source code | Deep code graph and coding-agent integration |
| [CodeGraph](https://github.com/codegraph-ai/CodeGraph) | 90–95% | 0% in graph-only mode | Repository source code | Functions, imports, calls and PR blast radius |
| [Microsoft GraphRAG](https://microsoft.github.io/graphrag/index/overview/) | 85–95% | Required by the standard entity, relationship and summary pipeline | Supplied unstructured text | General LLM-built RAG graph and community summaries |
| [Graphiti](https://help.getzep.com/graphiti/getting-started/welcome) | 85–95% | Required in the normal episode-ingestion path | Text, messages and JSON episodes | Temporal agent memory with incremental updates |
| AI Context Linker V0.2 | 75–80% from a new local workspace; 100% from an approved manifest | 0% | Explicit metadata allowlist; zero source-code bodies | Human-reviewed, cloud-safe project briefing |

## Why not claim 100% end to end?

The mechanical refresh is fully scriptable after one-time configuration:

1. read allowlisted facts;
2. normalize and safety-check them;
3. calculate a deterministic snapshot hash;
4. compare against the previous approved manifest;
5. render Markdown and a derived graph;
6. atomically write the selected output directory.

The remaining work is intentional: a person chooses which projects and metadata
files may enter the publication surface, reviews material changes, and approves
the candidate manifest. Removing that gate would increase unattended automation
while weakening the product's central privacy claim.

Projects that report near-one-command automation usually make a different trade:
they index the full repository locally, or allow an LLM to extract graph facts
from supplied text. Those are valid designs for code intelligence and agent
memory. AI Context Linker optimizes for a smaller cloud publication boundary.

## Direction

The realistic target is **90% end-to-end workflow automation with one explicit
human approval gate**, plus **100% deterministic automation after a manifest has
been approved**. Optional AI enrichment may be added later, but it must remain
separate from confirmed facts and must never be required to build the bundle.
