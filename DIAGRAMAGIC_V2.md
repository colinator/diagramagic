# Diagramagic CLI/MCP Server Spec

A CLI and  MCP tool that lets LLMs create, view, and iteratively refine diagrams using svg++ markup.

---

## Part 1: svg++ Language

### What svg++ Is

svg++ is just SVG. Specifically: a valid svg++ document is a well-formed XML document where the vast majority of content is standard SVG 1.1 elements (`<rect>`, `<text>`, `<line>`, `<circle>`, `<path>`, `<g>`, `<style>`, `<defs>`, etc.) that any SVG renderer understands.

On top of this standard SVG, svg++ adds a small set of extensions in the `diag:` namespace:

- `<diag:diagram>` — root element (becomes `<svg>` in output)
- `<diag:flex>` — flexbox-inspired layout container
- `<diag:template>` / `<diag:instance>` — reusable components
- `diag:wrap`, `diag:max-width`, `diag:font-family`, `diag:font-path` — attributes on `<text>` for wrapping and font control
- `diag:background`, `diag:padding` — attributes on `<diag:diagram>` for canvas setup

**An LLM that knows SVG already knows 90% of svg++.** The `diag:` extensions handle the specific things that are painful in raw SVG: multi-line text wrapping, box-with-text layout, and reusable components. Everything else is just SVG.

The compiler strips all `diag:` elements and attributes, producing pure standards-compliant SVG output with no custom namespace remnants.

### Namespaces

A valid svg++ document binds both the default SVG namespace and a `diag:` prefix:

```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://diagramagic.ai/ns">
```

Namespace URI policy:
- The compiler should not hardcode a specific `diag:` URI.
- Any URI is accepted, as long as the root element is namespaced `diag:diagram` and all svg++ elements/attributes use that same namespace.
- Docs and examples should prefer `https://diagramagic.ai/ns`, but `https://example.com/diag` (and others) remain valid.

### Root Element: `<diag:diagram>`

One required root container. Becomes `<svg>` in output.

| Attribute | Default | Notes |
|-----------|---------|-------|
| `width`, `height` | auto | Auto-calculated from content bounds if omitted |
| `viewBox` | auto | Auto-calculated from content bounds if omitted |
| `diag:background` | `"white"` | Canvas fill. Use `"none"` for transparent |
| `diag:padding` | `0` | Padding around auto-calculated content bounds (pixels) |
| `diag:font-family` | `"sans-serif"` | Default font for all descendants |
| `diag:font-path` | none | Path to `.ttf`/`.ttc` for exact metrics |

All other attributes are preserved on the output `<svg>`.

### Layout Element: `<diag:flex>`

Flexbox-inspired container. Positions children vertically (column) or horizontally (row). Compiles to a `<g>` with positioned children and an optional background `<rect>`.

| Attribute | Default | Notes |
|-----------|---------|-------|
| `x`, `y` | `0` | Position. Use on top-level flex only; omit on nested flex (parent handles layout) |
| `width` | auto | Auto = max child width (column) or sum of child widths (row) |
| `direction` | `"column"` | `"column"` stacks vertically, `"row"` arranges horizontally |
| `gap` | `0` | Space between children on main axis (pixels) |
| `padding` | `0` | Inner padding on all sides (pixels) |
| `background-class` | none | CSS class for auto-generated background `<rect>` |
| `background-style` | none | Inline style for auto-generated background `<rect>` |
| `id` | none | Element ID for MCP `update` and `render` focus |

Children can be other `<diag:flex>` elements, `<text>` elements, standard SVG elements, or `<diag:instance>` elements.

**Column layout:** children stack top to bottom. Container height = padding + sum(child heights) + gaps + padding.

**Row layout:** children arrange left to right. Container height = padding + max(child height) + padding.

### Text Wrapping

Standard SVG `<text>` elements, enhanced with `diag:` attributes:

| Attribute | Default | Notes |
|-----------|---------|-------|
| `diag:wrap` | `"false"` | Set `"true"` to enable automatic line wrapping |
| `diag:max-width` | container width | Override wrap width for this text element |
| `diag:font-family` | inherited | Font family name |
| `diag:font-path` | inherited | Path to `.ttf`/`.ttc` for exact metrics |

When `diag:wrap="true"`, text is broken into lines using font metrics and emitted as `<tspan>` elements. When false or omitted, text stays on one line.

Always specify `font-size` via CSS (`style` attribute or `<style>` block) for proper measurement.

### Templates

Define reusable components once, instantiate with different parameters.

**Definition** (must be direct children of `<diag:diagram>`):

```xml
<diag:template name="service-box">
  <diag:flex width="180" padding="10" gap="4" direction="column"
             background-class="card">
    <text class="title"><diag:slot name="name"/></text>
    <text class="desc" diag:wrap="true"><diag:slot name="description"/></text>
  </diag:flex>
</diag:template>
```

**Instantiation** (anywhere in the document):

```xml
<diag:instance template="service-box" x="30" y="50">
  <diag:param name="name">Auth Service</diag:param>
  <diag:param name="description">Handles OAuth2 flows and token validation.</diag:param>
</diag:instance>
```

- `<diag:slot name="..."/>` inside text elements marks where parameter values are inserted.
- `<diag:param name="...">` on instances provides the values.
- Attributes on `<diag:instance>` (like `x`, `y`, `background-class`) override the template's top-level element attributes.
- Missing parameters default to empty text.

### Mixing svg++ and Raw SVG

This is the key design point: **svg++ elements and raw SVG elements coexist freely.** Use `<diag:flex>` when you want automatic text layout and box sizing. Use raw SVG when you want precise control — lines, arrows, circles, paths, transforms, markers, gradients, anything SVG supports.

```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://diagramagic.ai/ns"
              diag:padding="20">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#555"/>
    </marker>
  </defs>
  <style>.card { fill:#f0f0f0; stroke:#333; stroke-width:1; rx:8; }</style>

  <!-- svg++ handles the box layout -->
  <diag:flex id="box-a" x="20" y="20" width="120" padding="8"
             background-class="card">
    <text style="font-size:14px">Service A</text>
  </diag:flex>

  <diag:flex id="box-b" x="250" y="20" width="120" padding="8"
             background-class="card">
    <text style="font-size:14px">Service B</text>
  </diag:flex>

  <!-- Raw SVG handles the arrow -->
  <line x1="140" y1="35" x2="250" y2="35" stroke="#555"
        marker-end="url(#arrow)"/>
</diag:diagram>
```

The compiler processes `<diag:flex>` into `<g>` groups, wraps text, and leaves the `<line>` untouched. The output is pure SVG.

### Grouping and Transforms with `<g>`

SVG's `<g>` element is your primary tool for positioning, scaling, and organizing diagram content. diagramagic passes `<g>` through untouched, so it works freely with svg++ elements inside.

**Positioning anything — including template instances:**

```xml
<g transform="translate(200, 50)">
  <diag:instance template="service-box">
    <diag:param name="name">Auth Service</diag:param>
    <diag:param name="description">Handles OAuth2 flows.</diag:param>
  </diag:instance>
</g>
```

**Scaling a subsection** (e.g., a detail inset at half size):

```xml
<g transform="translate(400, 300) scale(0.5)">
  <!-- This entire sub-diagram renders at 50% size -->
  <diag:flex width="300" padding="10" gap="6" direction="column"
             background-class="detail-panel">
    <text style="font-size:14px; font-weight:bold">Internals</text>
    <text style="font-size:12px" diag:wrap="true">
      Detailed view that becomes legible when zoomed in.
    </text>
  </diag:flex>
</g>
```

**Nested zoom / level-of-detail:** Use `<g>` with `scale()` to embed sub-diagrams that reveal detail at different zoom levels. A high-level architecture diagram might contain `<g transform="scale(0.3)">` groups with full internal diagrams inside each service box — invisible at overview zoom, readable when focused.

**Rotation** (e.g., angled labels):

```xml
<g transform="translate(100, 200) rotate(-45)">
  <text style="font-size:11px; fill:#666">diagonal label</text>
</g>
```

Think of `<g>` as the universal adapter: any time you need to position, scale, rotate, or logically group a set of elements — whether raw SVG or svg++ — wrap them in a `<g>`.

#### Known bug: `<g>` children are zero-height in flex

When a `<g>` element is a direct child of a `<diag:flex>`, the flex layout:
- **Does** position it in the flow (assigns a `translate()` like any other child)
- **Does NOT** measure its bounding box — treats it as zero-width, zero-height

This means the parent container won't grow to fit the `<g>`'s visual content. An embedded sub-diagram via `<g transform="scale(0.25)">` inside a flex will render correctly at the right position, but the flex box behind it will be too short.

**Current workaround:** Place an invisible spacer `<rect>` inside the flex to reserve the needed height, and position the `<g>` outside the flex at absolute coordinates calculated from the compiled output:

```xml
<!-- Inside the flex: spacer reserves visual space -->
<rect width="200" height="195" fill="none" stroke="none"/>

<!-- Outside the flex: <g> at absolute coordinates to overlap the spacer area -->
<g transform="translate(480, 995) scale(0.25)">
  <!-- sub-diagram content -->
</g>
```

This works but requires a compile-inspect-adjust cycle to get the absolute coordinates right.

**Root cause:** The flex layout engine measures direct children that are known primitives (`<rect>`, `<text>`, `<diag:flex>`, etc.) but does not descend into `<g>` elements to compute their aggregate bounding box.

**Fix:** The layout engine should compute the bounding box of `<g>` children by recursively measuring their contents and applying any `transform` attribute (translate, scale, rotate). This would let `<g>` elements participate naturally in flex sizing, eliminating the spacer workaround entirely. See Iteration 1 in the Implementation Plan.

### Complete Minimal Example

```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://diagramagic.ai/ns">
  <style>
    .card { fill:#f0f0f0; stroke:#333; stroke-width:1; rx:8; }
    .title { font-size:14px; font-weight:bold; }
  </style>

  <diag:flex x="20" y="20" width="160" padding="12" gap="6"
             direction="column" background-class="card">
    <text class="title">Hello</text>
    <text style="font-size:12px" diag:wrap="true">
      This text wraps automatically within the flex container.
    </text>
  </diag:flex>
</diag:diagram>
```

Auto-sizes to fit content. No `width`, `height`, or `viewBox` needed on the root.

---

## Part 2: MCP Server

### Design Principles

- **svg++ is the authoring language.** The LLM writes SVG with `diag:` extensions. Its deep SVG knowledge transfers directly — svg++ just removes the pain points (text wrapping, box layout, templates).
- **Document-level statefulness.** The tool holds named documents. No entity-level scene graph — the svg++ source *is* the state.
- **Visual feedback loop.** The LLM can render at any time, see the result via multimodal vision, and correct course. This is the primary quality lever.
- **Shared template library.** Common diagram components are available across all documents without re-definition.

### Operations

#### `create`

Create or replace a named document.

```json
{
  "op": "create",
  "args": {
    "name": "architecture",
    "source": "<diag:diagram xmlns=...>...</diag:diagram>"
  }
}
```

Returns: `{ "status": "created", "name": "architecture" }`

- `source` is svg++ markup (full `<diag:diagram>` document).
- If a document with this name already exists, it is replaced.
- Parses and validates the svg++ on creation; returns an error if malformed.

#### `render`

Render a document (or a region of it) to a PNG image.

```json
{
  "op": "render",
  "args": {
    "name": "architecture",
    "focus": "auth-subsystem",
    "padding": 20
  }
}
```

Returns: PNG image of the rendered diagram.

- `focus` (optional): an element `id` in the svg++. The viewport crops to that element's bounding box plus `padding`. Omit to render the full document.
- `padding` (optional, default 20): extra space around the focused element in pixels.
- Pipeline: svg++ → SVG (via diagramagic) → PNG (via rasterizer).
- If `focus` is provided and no matching `id` exists, return an error.
- Off-canvas, hidden, or very small focused elements are still valid: render the requested crop region; do not treat this as an error.

#### `update`

Replace a fragment of an existing document by element id.

```json
{
  "op": "update",
  "args": {
    "name": "architecture",
    "element_id": "hyplora-card",
    "source": "<diag:flex id='hyplora-card' width='245' ...>...</diag:flex>"
  }
}
```

Returns: `{ "status": "updated", "name": "architecture", "element_id": "hyplora-card" }`

- Finds the element with the given `id` in the stored document and replaces it with the provided svg++ fragment.
- The replacement element should have the same `id`.
- Returns an error if the id is not found.
- Avoids re-emitting the entire document for small changes — critical for large diagrams.

#### `export`

Retrieve the processed SVG or the raw svg++ source.

```json
{
  "op": "export",
  "args": {
    "name": "architecture",
    "format": "svg"
  }
}
```

Returns: the SVG or svg++ source as a string.

- `format`: `"svg"` (default) returns processed pure-SVG output. `"svgpp"` returns the stored svg++ source as-is.

### Shared Template Library

The MCP server maintains a library of named templates that are available to all documents without explicit `<diag:template>` definitions.

#### `define_template`

Add a template to the shared library.

```json
{
  "op": "define_template",
  "args": {
    "name": "service-box",
    "source": "<diag:flex width='180' padding='10' gap='4' direction='column' background-class='card'><text class='title'><diag:slot name='name'/></text><text class='desc' diag:wrap='true'><diag:slot name='description'/></text></diag:flex>"
  }
}
```

Returns: `{ "status": "defined", "template": "service-box" }`

- Templates defined here are injected into every document before processing, as if they were `<diag:template>` elements at the top of the document.
- Document-local templates with the same name take precedence (local override).
- Templates persist for the lifetime of the MCP server session.
- Calling `define_template` with an existing name replaces the previous shared template.

#### `list_templates`

List all templates in the shared library.

```json
{
  "op": "list_templates",
  "args": {}
}
```

Returns: `{ "templates": ["service-box", "db-cylinder", "note-card"] }`

### Document Model

Each document is:
- A **name** (string, chosen by the LLM)
- The **svg++ source** (the latest version, incorporating any `update` calls)

The svg++ source is the single source of truth. No separate metadata layer, no entity registry.

#### Element IDs

For `update` and `render` focus to work, elements need `id` attributes. This is standard SVG practice:

```xml
<diag:flex id="auth-card" width="245" ...>
  ...
</diag:flex>
```

IDs are the LLM's own bookkeeping — the tool doesn't auto-assign or manage them.

### Workflow Example

A typical session creating a large codebase diagram:

```
 1. LLM: define_template("service-box", ...)
 2. LLM: define_template("db-node", ...)
 3. LLM: create("codebase", svg++ with high-level module boxes using templates)
 4. LLM: render("codebase")
 5. LLM: [sees the image] "The API box overlaps the DB box, let me fix spacing"
 6. LLM: update("codebase", element_id="api-section", adjusted fragment)
 7. LLM: render("codebase")
 8. LLM: [looks good] "Now let me add detail to the auth module"
 9. LLM: update("codebase", element_id="auth-module", expanded fragment with internals)
10. LLM: render("codebase", focus="auth-module")
11. LLM: [checks detail view] "Done."
12. LLM: export("codebase", format="svg") → user saves to file
```

---

## Part 3: CLI

The CLI is the primary interface for file-based workflows (including LLM agents using tool calls like `Write` + `Bash` + `Read`). The MCP server is a thin wrapper over the same functions.

### CLI Interface Change

**Current behavior:** `diagramagic file.svg++` compiles to SVG. No subcommands. The `--cheatsheet` flag prints the reference.

**New behavior:** Introduce subcommands for clarity and extensibility.

| Command | Description | Status |
|---------|-------------|--------|
| `diagramagic compile` | svg++ → SVG | Replaces current bare invocation |
| `diagramagic render` | SVG or svg++ → PNG | **New** |
| `diagramagic cheatsheet` | Print svg++ reference | Replaces `--cheatsheet` flag |
| `diagramagic patterns` | Print pattern examples | **New** |
| `diagramagic prompt` | Print LLM system prompt fragment | **New** |

Bare invocation (`diagramagic file.svg++` with no subcommand) is **removed**. A subcommand is always required.
This is an intentional breaking change: no deprecation window, no compatibility alias, and no legacy fallback path.

### `diagramagic compile` — svg++ to SVG

Compile svg++ markup into pure SVG.

```bash
# File input → auto-writes output
diagramagic compile input.svg++
# → Writes input.svg

# Explicit output path
diagramagic compile input.svg++ -o output.svg

# Include shared template files
diagramagic compile input.svg++ --templates ./templates/*.svg++

# Stdout
diagramagic compile input.svg++ --stdout

# Stdin
echo "<diag:diagram>...</diag:diagram>" | diagramagic compile > output.svg
```

### `diagramagic render` — SVG or svg++ to PNG

Rasterize any SVG or svg++ file to PNG. Auto-detects the input type: if the file contains a `<diag:diagram>` root, it runs the svg++ compilation first; otherwise it renders the SVG directly.

```bash
# svg++ → SVG → PNG
diagramagic render input.svg++
# → Writes input.png

# Raw SVG → PNG (no svg++ compilation)
diagramagic render diagram.svg
# → Writes diagram.png

# Explicit output path
diagramagic render input.svg++ -o output.png

# Include shared template files
diagramagic render input.svg++ --templates ./templates/*.svg++

# Focus on a specific element by id
diagramagic render input.svg++ --focus auth-card
# → Crops to the bounding box of #auth-card, plus padding

# Control padding around focused element
diagramagic render input.svg++ --focus auth-card --padding 30

# Scale factor for higher resolution
diagramagic render input.svg++ --scale 2
```

| Flag | Default | Notes |
|------|---------|-------|
| `-o`, `--output` | `{stem}.png` | Output PNG path |
| `--focus` | none | Element `id` to crop viewport to |
| `--padding` | `20` | Extra pixels around focused element |
| `--scale` | `1` | Scale factor (2 = 2x resolution) |
| `--stdout` | false | Write PNG bytes to stdout |

**Implementation note:** uses the bundled resvg library (same one already used for text measurement). Adding a `render_svg` function alongside the existing `measure_svg` in the Rust binding gives PNG rendering with zero external dependencies.

Error handling:
- `--focus <id>` with no match returns a non-zero exit and clear error message.
- If the focused element exists but is off-canvas/hidden, rendering still succeeds for that viewport (useful for zoomed-in workflows).

### Shared Templates (CLI)

Templates can be shared across svg++ documents by passing template files via the `--templates` flag. Template files are regular svg++ files containing only `<diag:template>` definitions:

```xml
<!-- templates/cards.svg++ -->
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://diagramagic.ai/ns">
  <diag:template name="service-box">
    <diag:flex width="180" padding="10" gap="4" direction="column"
               background-class="card">
      <text class="title"><diag:slot name="name"/></text>
      <text class="desc" diag:wrap="true"><diag:slot name="description"/></text>
    </diag:flex>
  </diag:template>
</diag:diagram>
```

```bash
# Use shared templates when compiling or rendering
diagramagic compile diagram.svg++ --templates templates/*.svg++
diagramagic render diagram.svg++ --templates templates/*.svg++
```

Templates from `--templates` files are injected before processing, as if they were defined at the top of the document. Document-local templates with the same name take precedence (local override).

Template precedence and determinism:
- Shared templates from `--templates` are loaded left-to-right.
- If multiple shared templates define the same name, the last loaded shared definition wins.
- Document-local templates always override shared templates.

This is the CLI equivalent of the MCP server's `define_template` / `list_templates` operations — same concept, files instead of API calls.

### `diagramagic cheatsheet`

Print the svg++ quick reference (already implemented).

```bash
diagramagic cheatsheet
```

### `diagramagic patterns`

Print the pattern-oriented reference showing canonical svg++ diagram patterns. See "LLM Fluency" section.

```bash
diagramagic patterns
```

### `diagramagic prompt`

Print a short system prompt fragment suitable for inclusion in CLAUDE.md files or MCP server instructions. Gives LLMs the "golden rules" for effective svg++ usage.

```bash
diagramagic prompt
# Paste output into your project's CLAUDE.md
```

### CLI Error Handling (Agent-Friendly)

The CLI is primarily consumed by LLM agents. Error output must be deterministic, concise, and machine-actionable.

Requirements:
- No Python traceback by default.
- Emit one concise error summary line in text mode.
- Support structured errors via `--error-format json`.
- Use stable error codes so agents can branch on code instead of free-form text.
- Include a short actionable hint when possible.
- Full traceback/details are available only in debug mode (`--debug` or `DIAGRAMAGIC_DEBUG=1`).

Text mode example:
```text
error[E_PARSE_XML]: failed to parse input.svg++: mismatched tag at line 42, column 17
hint: check for an unclosed <diag:flex> near line 39
```

JSON mode example:
```json
{
  "ok": false,
  "code": "E_PARSE_XML",
  "message": "mismatched tag",
  "file": "input.svg++",
  "line": 42,
  "column": 17,
  "hint": "Check for an unclosed <diag:flex> near line 39.",
  "retryable": true
}
```

Minimum code taxonomy:
- `E_ARGS` — invalid CLI usage/flags
- `E_IO_READ` — input file missing/unreadable
- `E_IO_WRITE` — output path not writable
- `E_PARSE_XML` — malformed XML/svg++
- `E_SVGPP_SEMANTIC` — valid XML but invalid svg++ semantics
- `E_TEMPLATE` — template load/merge/validation failure
- `E_FOCUS_NOT_FOUND` — `--focus` id missing
- `E_RENDER` — rasterization failure
- `E_INTERNAL` — unexpected internal error

Exit code guidance:
- `2` usage/input errors (`E_ARGS`, `E_IO_READ`, `E_PARSE_XML`)
- `3` svg++ semantic/template errors (`E_SVGPP_SEMANTIC`, `E_TEMPLATE`)
- `4` render/focus errors (`E_FOCUS_NOT_FOUND`, `E_RENDER`, `E_IO_WRITE`)
- `1` internal/unclassified errors (`E_INTERNAL`)

### LLM Agent Workflow (CLI)

The full visual feedback loop using only CLI + filesystem tools:

```bash
# 1. LLM writes svg++ via its Write tool
# 2. Compile + render in one step
diagramagic render diagram.svg++ -o diagram.png

# 3. LLM reads the PNG via its Read tool (multimodal vision)
# 4. LLM sees issues, edits the svg++ via its Edit tool
# 5. Re-render
diagramagic render diagram.svg++ -o diagram.png

# 6. Looks good — export final SVG
diagramagic compile diagram.svg++ -o final.svg
```

For raw SVG workflows (no svg++ extensions needed):

```bash
# LLM writes raw SVG, renders to check it
diagramagic render sketch.svg -o sketch.png
```

---

### Non-Goals

- **Entity/relation scene graph.** No separate semantic model of nodes and edges. The svg++ source is the model.
- **Auto-layout of arbitrary graphs.** The LLM positions elements manually or uses `diag:flex`. Force-directed layout of large graphs is a different tool.
- **Spatial metadata querying.** The LLM already knows what it built (or can read the source via `export`).

### LLM Fluency: Patterns and Prompting

LLMs already know SVG well, but tend to fall back to manual-coordinate habits instead of reaching for svg++ features (flex nesting, templates, `<g>` grouping). The fix is prompting, not fine-tuning — the API surface is small enough that a few well-placed hints change behavior dramatically.

**Required deliverables:**

1. **`diagramagic_patterns.md`** — A pattern-oriented reference (not feature-oriented). Should contain 5 complete, working svg++ diagrams, each demonstrating a canonical pattern:
   - Full-page column flex layout (zero manual y-coordinates)
   - Card grid using templates
   - Nested flex (rows inside columns) for multi-column sections
   - Embedded sub-diagram via `<g transform="scale(...)">` (no spacer workaround)
   - Mixed raw SVG + flex (arrows/lines alongside auto-laid-out boxes)

2. **System prompt fragment** — A short block (5-10 lines) designed for inclusion in CLAUDE.md files or MCP server instructions. Golden rules like:
   - Always start with a full-page column flex
   - Template any element used 3+ times
   - Use `<g transform>` for positioning groups, not manual x/y
   - Nest flex (row inside column) instead of calculating coordinates
   - Use `diag:wrap` on every multi-word text element

The patterns file ships alongside the cheatsheet via `diagramagic patterns`. The system prompt fragment is available via `diagramagic prompt`.

### Future Considerations

Things we explicitly defer:

- **Multi-document composition.** Importing one document into another (e.g., a detail diagram embedded in an overview).
- **Collaboration.** Multiple agents/sessions accessing the same documents. Falls out naturally from the document model if needed.
- **Diff/history.** Version stack per document for undo or comparison.
- **Auto-arrows/routing.** Connections that automatically route between named elements, avoiding overlaps. High value but significant implementation complexity.

---

## Implementation Plan

### Iteration 1: CLI foundation + LLM fluency

The goal is a solid CLI with visual feedback and good LLM ergonomics. No MCP server yet.

#### 1a. Fix `<g>` bounding box in flex layout

The flex layout engine currently treats `<g>` children as zero-width, zero-height (see "Known bug" in Part 1). Fix the layout engine to recursively compute the bounding box of `<g>` elements, accounting for `transform` attributes (translate, scale, rotate).

This is a change to the Python layout code (`src/diagramagic/diagramagic.py`). The bounding box calculation should handle:
- `<g>` containing rects, text, circles, lines, paths
- `<g>` containing nested `<g>` elements
- `transform="scale(...)"` and `transform="translate(...) scale(...)"` on the `<g>`

Rust changes are only needed for rasterization (`render_svg`) and optional future performance work.

After this fix, the spacer workaround for embedded sub-diagrams is no longer needed.

#### 1b. Add `diagramagic render` command

Add PNG rasterization to the CLI. Uses the bundled resvg library (already present for text measurement). Requires adding a `render_svg` function alongside the existing `measure_svg` in the Rust binding.

Key features:
- Auto-detect svg++ vs raw SVG input
- `--focus <id>` to crop viewport to a specific element
- `--scale <n>` for resolution control
- `--templates` flag for shared template files (same as `compile`)

#### 1c. CLI subcommand structure

Introduce subcommands: `compile`, `render`, `cheatsheet`, `patterns`, `prompt`. A subcommand is always required. See "CLI Interface Change" table in Part 3.

#### 1d. Shared templates via `--templates` flag

Add `--templates <glob>` to both `compile` and `render`. Template files are svg++ documents containing only `<diag:template>` definitions. Injected before processing; document-local templates override.

#### 1e. Write LLM fluency deliverables

1. **`diagramagic_patterns.md`** — 5 complete working svg++ diagrams (full-page flex, card grid, nested flex, embedded sub-diagram without spacer workaround, mixed raw SVG + flex). Ships as `diagramagic patterns`.
2. **System prompt fragment** — 5-10 line golden rules block. Ships as `diagramagic prompt`.

#### 1f. Agent-friendly CLI error UX

Implement the error model from "CLI Error Handling (Agent-Friendly)":
- Wrap compile/render execution paths so expected failures map to stable error codes.
- Add `--error-format {text,json}`.
- Add `--debug` (and `DIAGRAMAGIC_DEBUG=1`) to enable traceback output.
- Ensure all common failure paths return deterministic exit codes and actionable hints.

#### 1g. Namespace policy

Remove any requirement for a hardcoded namespace URI:
- Compiler accepts any `diag:` namespace URI present on the root namespaced `diag:diagram`.
- Cheatsheet/patterns/docs use `https://diagramagic.ai/ns` as the preferred example URI.
- Existing diagrams using `https://example.com/diag` continue to work unchanged.

#### 1h. Test Coverage (Required)

Add automated tests for all Iteration 1 behavior:
- CLI command shape: subcommands required; bare invocation fails with `E_ARGS`.
- Render: SVG vs svg++ auto-detection, `--focus`, `--padding`, `--scale`, `--stdout`.
- Focus error handling: missing id -> `E_FOCUS_NOT_FOUND`; off-canvas/hidden focus renders successfully.
- Template loading/precedence: left-to-right shared template ordering, last shared wins, document-local override.
- Namespace policy: parser accepts multiple `diag:` URIs, including `https://example.com/diag` and `https://diagramagic.ai/ns`.
- Agent-friendly errors: text mode shape, JSON mode schema, stable error codes, exit-code mapping, debug traceback gating.
- `<g>` bounding-box fix: nested groups and transforms affect parent flex sizing correctly; no spacer workaround needed.

### Iteration 2: MCP server

Build the MCP server as a thin wrapper over the CLI/library functions from Iteration 1.

#### 2a. Core operations: `create`, `render`, `export`

Minimum viable MCP server. Document store (in-memory, name → svg++ source). `render` returns PNG via multimodal. `export` returns SVG or svg++ source string. The `--templates` equivalent is the shared template library (2c).

#### 2b. `update` operation

Find-and-replace an XML subtree by element `id`. This is deceptively complex to implement correctly: requires parsing the svg++ as XML, locating the element, replacing the subtree while preserving namespace declarations, and re-serializing cleanly. Consider using an XML library with round-trip fidelity rather than string manipulation. Defer this if it blocks shipping 2a — the LLM can always `create` with the full updated source as a fallback.

Minimum error-handling contract for `update`:
- Error when `element_id` is missing in the document.
- Error when replacement fragment is not well-formed XML.
- Error when replacement root `id` differs from `element_id` (to prevent accidental id drift).
- If duplicate ids exist, update the first document-order match in v1 and return a warning note; tighten later if needed.

#### 2c. Shared template library: `define_template`, `list_templates`

MCP equivalent of the CLI's `--templates` flag. Templates persist for the server session lifetime. Injected into every document before processing. Document-local templates override.

---

## Execution Checklist

Use this checklist to track implementation progress. Check items only when complete and verified.

- [x] Add and maintain this checklist in `DIAGRAMAGIC_V2.md`.
- [x] 1a. Fix `<g>` bounding box participation in flex layout (`src/diagramagic/diagramagic.py`).
- [x] 1b. Add `diagramagic render` command (svg++/SVG -> PNG, focus/padding/scale/stdout).
- [x] 1c. Switch CLI to required subcommands: `compile`, `render`, `cheatsheet`, `patterns`, `prompt`.
- [x] 1d. Add shared template loading via `--templates` for `compile` and `render`.
- [x] 1e. Add LLM fluency deliverables (`diagramagic_patterns.md`, prompt fragment) and wire CLI commands.
- [x] 1f. Implement agent-friendly CLI error UX (`E_*` codes, text/json format, debug-only tracebacks, exit mapping).
- [x] 1g. Enforce namespace policy (accept any `diag:` URI; docs prefer `https://diagramagic.ai/ns`).
- [x] 1h. Add automated tests for all Iteration 1 behavior (including error UX and precedence rules).
- [x] 1i. Update user-facing docs to match v2 CLI (`README.md`, `AGENTS.md`, bundled `src/diagramagic/data/*` copies).
- [x] 1j. Update PyPI release guide (`BUILDFORPYPI.md`) for current version and v2 CLI smoke checks.
- [x] 1k. Align Rust crate version in `Cargo.toml` with package release versioning policy.
- [x] 1l. Regenerate `tests/fixtures/*.svg` from current `*.svg++` inputs and add v2-specific visual fixtures where needed.
- [ ] 2a. Implement MCP core ops: `create`, `render`, `export`.
- [ ] 2b. Implement MCP `update` with the minimum error-handling contract.
- [ ] 2c. Implement MCP shared template library: `define_template`, `list_templates`.
