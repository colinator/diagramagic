# svg++ Agent Quick Reference

This cheat sheet summarizes the svg++ v0.1 primitives so agents (LLMs, scripts, etc.) can generate diagrams without rereading the full spec.

## Big Picture

svg++ is just SVG with a handful of extra `diag:` elements and attributes. Start every document with a `<diag:diagram>` root (it becomes a normal `<svg>` on output), then mix standard SVG nodes (`<rect>`, `<line>`, `<text>`, etc.) with svg++ helpers like `<diag:flex>` and `diag:wrap`. The renderer walks the tree, expands the `diag:` features into routed `<g>`, `<rect>`, `<text>` nodes, and leaves all plain SVG untouched.

## Elements

- `<diag:diagram>` — root container. Set normal `<svg>` attributes (`width`, `height`, `viewBox`, styles). Optional `diag:font-family` / `diag:font-path` apply to all descendants. `diag:background` fills the canvas (defaults to white; use `none` to stay transparent).
- `<diag:flex>` — column/row layout block.
  - Attributes: `x`, `y`, `width` (total width), `direction="column|row"`, `gap`, `padding`, `background-class`, `background-style`.
  - Children: other `<diag:flex>` nodes, `<text>`, and regular SVG elements.
  - Width defaults to content width; column flexes wrap children vertically, row flexes lay them out horizontally.
- `<text>` — standard SVG text. Use `diag:wrap="true"` to enable wrapping.
  - Optional attributes: `diag:max-width` (override wrapping width per text node), `diag:font-family`, `diag:font-path` (inherit like CSS).

## Wrapping rules

- When `diag:wrap="true"`, text wraps to the flex container’s inner width (outer width minus padding) unless `diag:max-width` provides a smaller limit.
- Wrapping uses the actual font metrics (Pillow) for the chosen font; defaults to `sans-serif` if no font is provided.
- `diag:wrap="false"` (or omitted) keeps the text in a single line and measures width for layout but does not insert `tspan`s.

## Fonts

- Default `font-family` is `sans-serif`. Set `diag:font-family="Helvetica"` (or similar) on the root `<diag:diagram>` or any `<diag:flex>`/`<text>` to override.
- `diag:font-path` can point to a `.ttf`/`.ttc` file (relative paths allowed) for deterministic metrics.
- The renderer propagates font settings down the tree and writes `font-family` on each emitted `<text>`.

## Templates

- Define reusable fragments with `<diag:template name="card"> … </diag:template>` at the top of the document.
- Inside templates, use `<diag:slot name="body" />` within `<text>`/`<tspan>` to mark where instance values flow.
- Instantiate with `<diag:instance template="card">` plus `<diag:param name="body">…</diag:param>` children. Attributes on the instance (e.g. `x`, `y`, `background-class`, `diag:max-width`) override attributes on the template’s root nodes.
- Templates expand inline before layout, so the emitted nodes behave exactly like hand-authored svg++.

## Tips for agents

- Always bind the `diag:` namespace: `xmlns:diag="https://example.com/diag"` (or whatever binding the renderer expects).
- Use column flexes for stacked cards, row flexes for timelines or step lists.
- Leverage `gap` to control spacing between items rather than inserting empty `<text>` nodes.
- For nested layouts without explicit widths, the parent’s available width is inherited automatically so wrapped text stays consistent.
- Keep styles in a `<style>` block in the root `<diag:diagram>`; normal CSS works for classes.
- Need a quick conversion in a workflow? Run `diagramagic input.svg++ > output.svg` once the package is installed.

For full semantics (grammar, examples, future extensions) see `PROJECTSPEC.md`.
