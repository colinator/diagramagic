# svg++ Agent Quick Reference

This cheat sheet summarizes the svg++ v0.1 primitives so agents (LLMs, scripts, etc.) can generate diagrams without rereading the full spec.

## Big Picture

svg++ is just SVG with a handful of extra `diag:` elements and attributes. Start every document with a `<diag:diagram>` root (it becomes a normal `<svg>` on output), then mix standard SVG nodes (`<rect>`, `<line>`, `<text>`, etc.) with svg++ helpers like `<diag:flex>` and `diag:wrap`. The renderer walks the tree, expands the `diag:` features into routed `<g>`, `<rect>`, `<text>` nodes, and leaves all plain SVG untouched.

## Complete Minimal Example

```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://example.com/diag">
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
  - Attributes: `x`, `y`, `width` (total width), `direction="column|row"`, `gap`, `padding`, `background-class`, `background-style`.
  - Children: other `<diag:flex>` nodes, `<text>`, and regular SVG elements.
  - Width defaults to content width; column flexes wrap children vertically, row flexes lay them out horizontally.
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
diagramagic tcp.svg++

# ✅ CORRECT - explicit output with --stdout
diagramagic tcp.svg++ --stdout > tcp.svg

# ✅ CORRECT - stdin to stdout
echo "<diag:diagram>...</diag:diagram>" | diagramagic > output.svg

# ❌ WRONG - this can corrupt the output if you're not careful!
diagramagic tcp.svg++ > tcp.svg
# ^ Status messages mix with file output and can corrupt tcp.svg
```

**Three ways to use diagramagic:**

1. **File input** (auto-generates output):
   ```bash
   diagramagic input.svg++
   # → Writes to input.svg automatically
   ```

2. **File input with --stdout** (for piping):
   ```bash
   diagramagic input.svg++ --stdout > output.svg
   # → Clean SVG to stdout, no status messages
   ```

3. **Stdin input** (must redirect output):
   ```bash
   diagramagic < input.svg++ > output.svg
   # or
   echo "<diag:diagram>...</diag:diagram>" | diagramagic > output.svg
   ```

## Tips for agents

- Always bind the `diag:` namespace: `xmlns:diag="https://example.com/diag"` (or whatever binding the renderer expects).
- Use column flexes for stacked cards, row flexes for timelines or step lists.
- Leverage `gap` to control spacing between items rather than inserting empty `<text>` nodes.
- For nested layouts without explicit widths, the parent's available width is inherited automatically so wrapped text stays consistent.
- Keep styles in a `<style>` block in the root `<diag:diagram>`; normal CSS works for classes.
- For a quick reference, run `diagramagic --cheatsheet` to display this guide.

For full semantics (grammar, examples, future extensions) see `PROJECTSPEC.md`.
