# svg++ Agent Quick Reference

This cheat sheet summarizes the svg++ v0.1 primitives so agents (LLMs, scripts, etc.) can generate diagrams without rereading the full spec.

## Big Picture

svg++ is just SVG with a handful of extra `diag:` elements and attributes. Start every document with a `<diag:diagram>` root (it becomes a normal `<svg>` on output), then mix standard SVG nodes (`<rect>`, `<line>`, `<text>`, etc.) with svg++ helpers like `<diag:flex>` and `diag:wrap`. The renderer walks the tree, expands the `diag:` features into routed `<g>`, `<rect>`, `<text>` nodes, and leaves all plain SVG untouched.

## Complete Minimal Example

```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://diagramagic.ai/ns">
  <style>
    .card { fill:#f0f0f0; stroke:#333; stroke-width:1; }
    .title { font-size:14px; font-weight:bold; }
  </style>

  <diag:flex x="20" y="20" width="160" padding="12" gap="6"
             direction="column" background-class="card">
    <text class="title" diag:wrap="false">Hello</text>
    <text style="font-size:12px" diag:wrap="true">
      This text wraps automatically within the flex container.
    </text>
  </diag:flex>
</diag:diagram>
```

The diagram automatically sizes to fit your content—no need to specify `width`, `height`, or `viewBox`!

## Elements

- `<diag:diagram>` — root container. Accepts normal `<svg>` attributes (`width`, `height`, `viewBox`, styles), but **all are optional**—the renderer auto-calculates size and viewBox from content bounds. Optional `diag:font-family` / `diag:font-path` apply to all descendants. `diag:background` fills the canvas (defaults to white; use `none` to stay transparent). `diag:padding` adds symmetrical padding around content (defaults to 0).
- `<diag:flex>` — column/row layout block.
- `<diag:arrow>` — connector between two elements by `id`.
  - Required attributes: `from`, `to` (element or anchor ids).
  - Optional attributes: `label`, `label-size`, `label-fill`, standard SVG stroke/presentation attributes (`stroke`, `stroke-width`, `stroke-dasharray`, etc.), and optional `marker-end`/`marker-start`.
  - Endpoints are chosen automatically via center-line intersection with each target bbox.
- `<diag:anchor>` — invisible named coordinate point.
  - Required: `id`.
  - Position mode: absolute (`x` + `y`) or relative (`relative-to` + optional `side="top|bottom|left|right|center"`).
  - Optional offsets: `offset-x`, `offset-y`.
- `<diag:include>` — include another svg++ file as a compiled sub-diagram.
  - Required: `src` (resolved relative to the including file).
  - Optional: `x`, `y`, `scale`, `id`.
  - Included content is opaque in v1; no cross-boundary ID references.
- `<diag:graph>` — automatic node/edge layout for flowcharts and dependency graphs.
  - Child elements: `<diag:node>` and `<diag:edge>` only.
  - `diag:node` requires `id`; supports `width`, `min-width`, `padding`, `gap`, `background-class`, `background-style`.
  - `diag:edge` requires `from` + `to` (same-graph node ids); supports arrow-like stroke/label attributes.
  - Layout attrs on graph: `direction="TB|BT|LR|RL"`, `node-gap`, `rank-gap`, optional `x`/`y` (top-level only).
- `<diag:flex>` attributes: `x`, `y`, `width`, `direction="column|row"`, `gap`, `padding`, `background-class`, `background-style`.
- `<diag:flex>` children: other `<diag:flex>` nodes, `<text>`, and regular SVG elements.
- `<diag:flex>` width defaults to content width; column flexes wrap children vertically, row flexes lay them out horizontally.
- `<text>` — standard SVG text. Use `diag:wrap="true"` to enable wrapping.
  - Optional attributes: `diag:max-width` (override wrapping width per text node), `diag:font-family`, `diag:font-path` (inherit like CSS).
  - **Important**: Always specify `font-size` via CSS (`style` attribute or `<style>` block) for proper text measurement.

## Attribute Reference

| Attribute | Required? | Default | Units | Notes |
|-----------|-----------|---------|-------|-------|
| **diag:flex** | | | | |
| `x`, `y` | For top-level | `0` | pixels | Absolute position for top-level flex; omit for nested flex (parent handles layout) |
| `width` | No | auto | pixels | Auto = sum of child widths (row) or max child width (column) |
| `direction` | No | `"column"` | — | `"column"` stacks vertically, `"row"` horizontally |
| `gap` | No | `0` | pixels | Space between children along main axis |
| `padding` | No | `0` | pixels | Inner padding on all sides |
| `background-class` | No | none | — | CSS class for auto-generated background `<rect>` |
| `background-style` | No | none | — | Inline styles for background `<rect>` |
| **diag:arrow** | | | | |
| `from`, `to` | Yes | — | id string | Source/target element ids |
| `label` | No | none | text | Optional text centered at arrow midpoint |
| `label-size` | No | `10` | pixels | Label font size |
| `label-fill` | No | `#555` | color | Label text color |
| `marker-end`, `marker-start` | No | auto `marker-end` | marker URL | If omitted, default arrowhead is added to marker-end |
| stroke/presentation attrs | No | SVG defaults | SVG units | Passed through to emitted `<line>` |
| **diag:anchor** | | | | |
| `id` | Yes | — | id string | Anchor id in global id namespace |
| `x`, `y` | Absolute mode | — | pixels | Use both for absolute anchor mode |
| `relative-to` | Relative mode | — | id string | Target element id for relative anchor mode |
| `side` | No | `center` | — | `top`, `bottom`, `left`, `right`, `center` |
| `offset-x`, `offset-y` | No | `0` | pixels | Applied after base anchor position |
| **diag:include** | | | | |
| `src` | Yes | — | path string | Include file path (relative to including file) |
| `x`, `y` | No | `0` | pixels | Wrapper translation |
| `scale` | No | `1` | scalar | Uniform include scale (`> 0`) |
| `id` | No | none | id string | Assigned to emitted include wrapper `<g>` |
| **text** | | | | |
| `diag:wrap` | No | `"false"` | — | Set `"true"` to enable line wrapping |
| `diag:max-width` | No | container width | pixels | Override wrap width for this text element |
| `diag:font-family` | No | `"sans-serif"` | — | Inheritable font family name |
| `diag:font-path` | No | none | — | Path to `.ttf`/`.ttc` for exact metrics |
| **diag:diagram** | | | | |
| `width`, `height` | No | auto | pixels | Auto-calculated from content bounds if omitted |
| `viewBox` | No | auto | — | Auto-calculated from content bounds if omitted |
| `diag:background` | No | `"white"` | — | Canvas background; use `"none"` for transparent |
| `diag:padding` | No | `0` | pixels | Padding around auto-calculated content bounds |

## Positioning & Coordinates

- **For diagram margins: use `diag:padding`, NOT manual x/y offsets.** Instead of `<diag:flex x="24" y="20">`, use `<diag:diagram diag:padding="24">` with `<diag:flex>` (no x/y). This creates symmetrical margins automatically.
- **For vertical stacking: use nested column flex, NOT manual y-coordinates.** Flex containers auto-calculate their height based on content, so you can't predict where the next element should go. Wrap everything in a parent `<diag:flex direction="column" gap="16">` to let the layout engine handle spacing.
- **Top-level flex elements** (direct children of `<diag:diagram>`): Only use `x` and `y` for side-by-side elements at known positions, never for vertical stacks or margins.
- **Nested flex elements** (children of other flex containers): **omit `x` and `y`** — the parent positions children automatically using its layout algorithm (column stacks vertically, row arranges horizontally with gap/padding).
- SVG transforms compose naturally, so if you do specify `x`/`y` on a nested flex, it creates an offset relative to the parent's coordinate space (rarely needed).
- The diagram auto-sizes to fit all content—`width`, `height`, and `viewBox` are calculated automatically from content bounds (you can override by setting them explicitly on `<diag:diagram>` if needed).
- All numeric values are in **pixels** (SVG user units).

## Wrapping rules

- When `diag:wrap="true"`, text wraps to the flex container’s inner width (outer width minus padding) unless `diag:max-width` provides a smaller limit.
- Wrapping uses the actual font metrics (Pillow) for the chosen font; defaults to `sans-serif` if no font is provided.
- `diag:wrap="false"` (or omitted) keeps the text in a single line and measures width for layout but does not insert `tspan`s.

## Fonts

- Default `font-family` is `sans-serif`. Set `diag:font-family="Helvetica"` (or similar) on the root `<diag:diagram>` or any `<diag:flex>`/`<text>` to override.
- `diag:font-path` can point to a `.ttf`/`.ttc` file (relative paths allowed) for deterministic metrics.
- The renderer propagates font settings down the tree and writes `font-family` on each emitted `<text>`.

## Templates

Templates let you define reusable components and instantiate them with different parameters.

**Structure:**
1. Define once at document root: `<diag:template name="card">...</diag:template>`
2. The template body typically contains one top-level element (usually a `<diag:flex>`)
3. Use `<diag:slot name="title"/>` inside `<text>` elements as placeholders
4. Instantiate with `<diag:instance template="card" x="20" y="40">` plus `<diag:param>` children
5. Instance attributes (`x`, `y`, `background-class`, etc.) **override** the template's top-level element attributes

**Complete Template Example:**

```xml
<diag:template name="note">
  <diag:flex width="180" direction="column" padding="10" gap="4" background-class="card">
    <text class="title" diag:wrap="false"><diag:slot name="heading"/></text>
    <text class="body" diag:wrap="true"><diag:slot name="content"/></text>
  </diag:flex>
</diag:template>

<!-- Later in the document: -->
<diag:instance template="note" x="30" y="50">
  <diag:param name="heading">Task 1</diag:param>
  <diag:param name="content">Review the pull request and merge if tests pass.</diag:param>
</diag:instance>

<diag:instance template="note" x="30" y="150" background-class="highlight">
  <diag:param name="heading">Task 2</diag:param>
  <diag:param name="content">Deploy to staging environment.</diag:param>
</diag:instance>
```

The second instance overrides `background-class`, so it gets a different style while keeping the same structure.

## Arrows

Use arrows to connect rendered elements by id:

```xml
<diag:arrow from="auth" to="db" label="queries"/>
```

- `from` / `to` must reference element `id` attributes in the final diagram.
- `from` / `to` may reference either element ids or anchor ids.
- Endpoints are selected automatically via center-line intersection with each element bbox.
- If an endpoint is an anchor id, that endpoint uses the exact anchor coordinate.
- Optional arrow attrs: `label`, `label-size`, `label-fill`, plus standard SVG stroke/presentation attrs.
- If no marker attributes are specified, a default arrowhead is added to `marker-end`.

## Anchors

Use anchors to define precise named points:

```xml
<diag:anchor id="client_mid" relative-to="client_box" side="right" offset-x="8"/>
<diag:arrow from="client_mid" to="server_box" label="SYN"/>
```

- Anchors are invisible (no emitted SVG node).
- Position mode is either absolute (`x`+`y`) or relative (`relative-to` + optional `side`).
- Anchor ids share the global id namespace (duplicates are errors).

## Includes

Use includes to compose large diagrams from sub-files:

```xml
<diag:include src="subdiagram.svg++" x="280" y="120" scale="0.9"/>
```

- `src` is resolved relative to the current file.
- Include expansion happens at compile time (final SVG is flattened).
- In v1, do not reference included internal IDs from the parent.

## Graphs

Use `diag:graph` when the structure is node-and-edge oriented (flowchart, architecture, dependency graph).

```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://diagramagic.ai/ns"
              diag:padding="20">
  <style>
    .box { fill:#e8f4f8; stroke:#2980b9; stroke-width:1; rx:4; }
  </style>

  <diag:graph direction="TB" node-gap="28" rank-gap="44">
    <diag:node id="start" padding="10" background-class="box">
      <text style="font-size:13px">Start</text>
    </diag:node>
    <diag:node id="process" padding="10" background-class="box">
      <text style="font-size:13px">Process</text>
    </diag:node>
    <diag:node id="done" padding="10" background-class="box">
      <text style="font-size:13px">Done</text>
    </diag:node>

    <diag:edge from="start" to="process" label="step"/>
    <diag:edge from="process" to="done"/>
  </diag:graph>
</diag:diagram>
```

- Use `diag:graph` when topology/ranking is the hard part; do not use it as a substitute for full visual design.
- `diag:edge` impacts layout; `diag:arrow` does not.
- `diag:graph` cannot be nested in another `diag:graph` in v1.

## Common Patterns

**Stacked Cards (Vertical List):**
```xml
<!-- Outer flex uses x/y for top-level positioning -->
<diag:flex x="20" y="20" width="200" direction="column" gap="12">
  <!-- Nested flex elements omit x/y - parent handles layout -->
  <diag:flex width="200" padding="10" background-class="card">
    <text diag:wrap="true">First item in the list</text>
  </diag:flex>
  <diag:flex width="200" padding="10" background-class="card">
    <text diag:wrap="true">Second item</text>
  </diag:flex>
</diag:flex>
```

**Horizontal Timeline (Row Layout):**
```xml
<!-- Top-level row flex positions the timeline -->
<diag:flex x="20" y="40" direction="row" gap="20">
  <!-- Child flex elements auto-arranged horizontally by parent -->
  <diag:flex width="100" padding="8" direction="column" background-class="step">
    <text class="label">Step 1</text>
  </diag:flex>
  <diag:flex width="100" padding="8" direction="column" background-class="step">
    <text class="label">Step 2</text>
  </diag:flex>
  <diag:flex width="100" padding="8" direction="column" background-class="step">
    <text class="label">Step 3</text>
  </diag:flex>
</diag:flex>
```

**Note with Title and Body:**
```xml
<diag:flex x="40" y="60" width="220" padding="12" gap="8"
           direction="column" background-class="note">
  <text class="title" style="font-size:16px; font-weight:bold" diag:wrap="false">
    Important Notice
  </text>
  <text class="body" style="font-size:12px" diag:wrap="true">
    This is a longer paragraph that will wrap automatically within
    the container width. Perfect for documentation or explanatory text.
  </text>
</diag:flex>
```

**Multiple Separate Elements (Top-Level Manual Positioning):**
```xml
<!-- Top-level flex elements use absolute x/y positioning -->
<!-- First element at top-left -->
<diag:flex x="20" y="20" width="150" padding="10" background-class="box">
  <text>Box A</text>
</diag:flex>

<!-- Second element to the right (20 + 150 + 30 = 200) -->
<diag:flex x="200" y="20" width="150" padding="10" background-class="box">
  <text>Box B</text>
</diag:flex>

<!-- Third element below first (y = 20 + height of first + gap) -->
<diag:flex x="20" y="80" width="150" padding="10" background-class="box">
  <text>Box C</text>
</diag:flex>
```

## Using the CLI tool

**IMPORTANT: Common mistake to avoid!**

When you pass a **file** as input, diagramagic automatically writes the output file. Do NOT redirect stdout with `>` unless you use `--stdout`.

```bash
# ✅ CORRECT - file input (auto-writes to tcp.svg)
diagramagic compile tcp.svg++

# ✅ CORRECT - explicit output with --stdout
diagramagic compile tcp.svg++ --stdout > tcp.svg

# ✅ CORRECT - stdin to stdout
echo "<diag:diagram>...</diag:diagram>" | diagramagic compile > output.svg

# ❌ WRONG - this can corrupt the output if you're not careful!
diagramagic compile tcp.svg++ > tcp.svg
# ^ Status messages mix with file output and can corrupt tcp.svg
```

**Three ways to use diagramagic:**

1. **File input** (auto-generates output):
   ```bash
   diagramagic compile input.svg++
   # → Writes to input.svg automatically
   ```

2. **File input with --stdout** (for piping):
   ```bash
   diagramagic compile input.svg++ --stdout > output.svg
   # → Clean SVG to stdout, no status messages
   ```

3. **Stdin input** (must redirect output):
   ```bash
   diagramagic compile < input.svg++ > output.svg
   # or
   echo "<diag:diagram>...</diag:diagram>" | diagramagic compile > output.svg
   ```

## Tips for agents

- Always bind the `diag:` namespace: `xmlns:diag="https://diagramagic.ai/ns"` (preferred).
- Use column flexes for stacked cards, row flexes for timelines or step lists.
- Leverage `gap` to control spacing between items rather than inserting empty `<text>` nodes.
- For title+body graph nodes, prefer `diag:node gap="6"` to `gap="12"` for cleaner internal spacing.
- For nested layouts without explicit widths, the parent's available width is inherited automatically so wrapped text stays consistent.
- Keep styles in a `<style>` block in the root `<diag:diagram>`; normal CSS works for classes.
- Keep node content rich: favor title + supporting text over one-word boxes on complex diagrams.
- Treat `diag:graph` as scaffolding and keep using plain SVG/flex for section frames, legends, and annotation layers.
- If graph output is crowded, split into subgraphs with `diag:include` or use hybrid flex + arrow layouts.
- Quality gate before final output: no overlaps, no clipped/garbled text, and clear visual hierarchy at first glance.
- For a quick reference, run `diagramagic cheatsheet` to display this guide.
- For full agent operating guidance, run `diagramagic skill`.

For full semantics (grammar, examples, future extensions) see `PROJECTSPEC.md`.
