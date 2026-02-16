---
name: diagramagic
description: Generate and edit SVG diagrams using svg++ and the diagramagic CLI
allowed-tools: Bash(diagramagic *), Read, Write, Glob
---

# diagramagic — svg++ Diagram Skill

Diagramagic helps LLMs create better, larger diagrams more easily by keeping SVG familiar and adding minimal layout extensions.

You generate diagrams using svg++ (SVG with diag: layout extensions) and the
diagramagic CLI tool.

## Setup (first use per session)

Run these commands and use their output as your syntax reference:

- !`diagramagic cheatsheet`
- !`diagramagic patterns`

## Workflow (required)

1. Create or edit a `.svg++` file
2. Run `diagramagic render <file>.svg++` to generate PNG
3. View the PNG to verify correctness
4. If incorrect, fix the source and render again
5. When satisfied, run `diagramagic compile <file>.svg++` for final SVG

## Rules

- Use `<diag:diagram>` root with `xmlns="http://www.w3.org/2000/svg"` and `xmlns:diag="https://diagramagic.ai/ns"`
- Prefer `diag:flex` over manual coordinates for stacks/rows
- Use `diag:graph` for flowcharts and dependency diagrams (3+ connected nodes)
- Use `diag:wrap="true"` on `<text>` for multi-line text (wrapping is a text feature, not a `diag:node` feature)
- Use `diag:arrow` with `id`-tagged elements for connectors
- Use `diag:anchor` for precise named points (sequence diagrams, etc.)
- Use `diag:include` to compose large diagrams from sub-files
- Do NOT stop at first compile — iterate until the render matches intent

## Error Recovery

- `E_PARSE_XML`: fix malformed XML and retry
- `E_SVGPP_SEMANTIC`: fix svg++ structure/ids and retry
- `E_INCLUDE_ID_COLLISION`: rename conflicting ids between parent and included files
- `E_GRAPH_UNKNOWN_NODE`: ensure every `diag:edge from/to` id exists as a `diag:node` in the same graph
- `E_GRAPH_SELF_EDGE`: remove or redesign self-referential `diag:edge` (`from == to`)
- `E_GRAPH_TOO_LARGE`: split the graph into smaller sections or compose with `diag:include`
- Always attempt at least one fix before asking for help
