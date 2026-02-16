# diagramagic

svg++ reference renderer built primarily for LLM-driven diagram authoring.

Humans can use it directly, but the design target is agent workflows that need deterministic, editable, text-first diagram generation.

Feed it svg++ input and it emits plain SVG: no runtime, no proprietary viewer.

What is svg++? It is standard SVG plus a small set of `diag:` layout/composition tags:
- flex layout (`diag:flex`)
- automatic graph layout (`diag:graph`, `diag:node`, `diag:edge`)
- reusable components (`diag:template`, `diag:instance`)
- compile-time composition (`diag:include`)
- connection helpers (`diag:arrow`, `diag:anchor`)
- wrapped text on native `<text>` (`diag:wrap="true"`)

## Why svg++

LLMs already have strong SVG muscle memory: tags, attributes, groups, styles, and transforms.

svg++ is intentionally LLM-first: keep the familiar SVG surface area, then add a few high-leverage primitives for the parts models usually get wrong in raw SVG:
- layout without manual coordinate math
- wrapped text that measures correctly
- graph placement/routing from node+edge intent
- reusable templates and compile-time includes

Result: prompts stay short, edits stay local, and the generated output remains portable plain SVG.

## Installation

```bash
pip install diagramagic
```

**Note**: This package includes a Rust extension for accurate SVG measurement. During installation, the extension will be compiled from source, which requires the Rust toolchain:

```bash
# Install Rust (if not already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Then install diagramagic
pip install diagramagic
```

Installation typically takes 30-60 seconds while the Rust extension compiles.

## Quick Start

- **Compile**: `diagramagic compile input.svg++`
- **Render PNG**: `diagramagic render input.svg++`
- **Library**: `from diagramagic import diagramagic`
- **Cheat sheet**: `diagramagic cheatsheet` (or see `AGENTS.md`)
- **Full spec**: `PROJECTSPEC.md`
- **Tests**: `python tests/run_tests.py`

svg++ basics: wrap your document in `<diag:diagram>` with the `diag:` namespace, use `<diag:flex>` for layout, and use `diag:wrap="true"` on `<text>` for multi-line text. Everything compiles to pure SVG 1.1.

Need reusable pieces? Define `<diag:template name="card">…</diag:template>` once, then drop `<diag:instance template="card">` wherever you need consistent cards or packets.

Output defaults to a white canvas; set `diag:background="none"` (or any color) on `<diag:diagram>` to change it.

## Workflow Loop

Typical authoring loop:

1. Write or edit `.svg++`
2. Compile to `.svg` with `diagramagic compile ...`
3. Render to `.png` with `diagramagic render ...`
4. Inspect output (human or agent)
5. Adjust source and repeat

## Claude Skill Install

If you use Claude Code skills, install this repo's `SKILL.md` like this:

```bash
mkdir -p ~/.claude/skills/diagramagic
cp SKILL.md ~/.claude/skills/diagramagic/SKILL.md
```

## svg++ Tags

New `diag:` elements currently supported:

- `<diag:diagram>` (root)
- `<diag:flex>` (row/column layout)
- `<diag:graph>` (auto node/edge layout)
- `<diag:node>` (graph node)
- `<diag:edge>` (graph edge)
- `<diag:arrow>` (general connector by id)
- `<diag:anchor>` (named connection point)
- `<diag:template>`, `<diag:instance>`, `<diag:slot>`, `<diag:param>` (templating)
- `<diag:include>` (compile-time sub-diagram include)

Text wrapping stays on standard SVG `<text>`:
- use `diag:wrap="true"` (and optional `diag:max-width`) on `<text>` for multi-line layout
- `diag:node` is a graph container, not a text primitive

Example:

```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://diagramagic.ai/ns"
              width="300" height="160">
  <style>
    .card { fill:#fff; stroke:#999; rx:10; ry:10; }
    .title { font-size:16; font-weight:600; }
    .body { font-size:12; }
  </style>

  <diag:flex x="20" y="20" width="260" padding="14" gap="8" background-class="card">
    <text class="title" diag:wrap="false">Hello svg++</text>
    <text class="body" diag:wrap="true">
      This paragraph wraps to the flex width automatically.
    </text>
  </diag:flex>
</diag:diagram>
```
