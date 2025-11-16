# svg++ v0.1 Specification
*A minimal flexbox-inspired diagram language that compiles to pure SVG*
*"Text in → Text out" reference for humans and LLMs*

---

# 1. Purpose

svg++ is a tiny, deterministic, XML-based language used to describe diagrams. It is intended to be:

- **LLM-friendly** (simple, predictable syntax)
- **Human-readable**
- **Human-editable**
- **Machine-expandable** into plain, standards-compliant **SVG 1.1**

The system operates strictly as:

```
svg++ input → svg++ compiler → raw SVG output
```

There is **no requirement for file formats**, comments, or metadata—just **text in, text out**.

---

# 2. Core Principles

1. **svg++ is XML** – all constructs use XML syntax and may mix with normal SVG elements.
2. **All svg++ features live in the `diag:` namespace** – e.g. `<diag:flex>`, `<diag:diagram>`, `diag:wrap="true"`.
3. **Output contains no `diag:` elements or attributes** – they are replaced by standard SVG nodes such as `<g>`, `<rect>`, `<text>`, `<tspan>`.
4. **Layout is deterministic** – identical svg++ input always produces identical SVG output.
5. **v0.1 scope is intentionally small** – one root element (`<diag:diagram>`), one layout primitive (`<diag:flex>`), wrapped text opt-in on `<text>`, and everything else is plain SVG. Templates, expressions, style inheritance, and auto-arrows are reserved for future versions.

---

# 3. Syntax Summary (v0.1)

## 3.1 Namespaces

A valid svg++ document binds the `diag:` prefix, for example:

```xml
xmlns:diag="https://example.com/diag"
```

This prefix identifies svg++ semantic elements and attributes.

## 3.2 Root Element: `<diag:diagram>`

There must be exactly one top-level svg++ container.

```xml
<diag:diagram
  xmlns="http://www.w3.org/2000/svg"
  xmlns:diag="https://example.com/diag"
  width="400"
  height="200"
  viewBox="0 0 400 200"
>
  <!-- children -->
</diag:diagram>
```

**Allowed contents**

- Any number of svg++ layout elements (`<diag:flex>`)
- Any number of normal SVG elements (`<rect>`, `<text>`, `<line>`, `<g>`, `<style>`, …)

**Optional attributes**

| Attribute | Meaning |
| --- | --- |
| `width` | Output SVG width |
| `height` | Output SVG height |
| `viewBox` | Output SVG viewBox string |

All other attributes are preserved and applied to the output `<svg>` element.

---

# 4. Layout Element: `<diag:flex>`

`<diag:flex>` is a flexbox-inspired layout container that positions its children vertically (`direction="column"`) or horizontally (`direction="row"`).

## 4.1 Example (column stack)

```xml
<diag:flex
  x="20" y="60"
  width="150"
  direction="column"
  gap="6"
  padding="10"
  background-class="box"
>
  <text class="title" diag:wrap="false">User</text>
  <text class="body"  diag:wrap="false">id: Int</text>
  <text class="body"  diag:wrap="false">name: String</text>
</diag:flex>
```

## 4.2 Attributes

| Attribute | Required | Type | Default | Meaning |
| --- | --- | --- | --- | --- |
| `x` | yes | number | — | Top-left X position |
| `y` | yes | number | — | Top-left Y position |
| `width` | no | number | auto | See layout semantics |
| `direction` | no | `column` \| `row` | `column` | Main axis direction |
| `gap` | no | number | `0` | Space between children on the main axis |
| `padding` | no | number | `0` | Padding on all sides |
| `background-class` | no | string | none | CSS class applied to auto background `<rect>` |
| `background-style` | no | string | none | Inline style applied to auto background `<rect>` |

Other attributes are preserved but ignored by svg++ semantics.

---

# 5. Text With Wrapping

svg++ uses standard SVG `<text>` elements, enhanced with two attributes:

| Attribute | Type | Meaning |
| --- | --- | --- |
| `diag:wrap` | `"true"` / `"false"` | Whether to wrap text lines |
| `diag:max-width` | number | Optional per-text override of container width |
| `diag:font-family` | string | Optional default font family (inheritable, defaults to `sans-serif`) |
| `diag:font-path` | string | Optional local `.ttf` path for precise metrics (inheritable) |

Example:

```xml
<text class="body" diag:wrap="true">
  This text is wrapped to the container’s width.
</text>
```

- When `diag:wrap="true"` the text content is processed into wrapped lines using font metrics, and the generated SVG uses `<tspan>` elements for each line.
- When `diag:wrap="false"` (or omitted) the text is treated as a single line and width is measured directly from font metrics.
- When `diag:font-family` or `diag:font-path` is supplied, the renderer measures text with that exact typeface. These attributes can be placed on `<text>`, any `<diag:flex>`, or the root `<diag:diagram>` to provide an inherited default.

---

# 6. Layout Semantics (v0.1)

This section defines how `<diag:flex>` expands into plain SVG.

## 6.1 General Strategy

1. Treat `<diag:flex>` as an invisible layout container.
2. Measure each child:
   - Wrapped text → perform line breaking.
   - Unwrapped text → measure ascent, descent, and width.
   - Shapes (`<rect>`, `<circle>`, `<path>`, …) → use explicit size attributes.
3. Compute child positions within the container.
4. Construct a `<g>` element:
   - Apply `transform="translate(x,y)"`.
   - Optionally insert a background `<rect>`.
   - Insert the positioned children.
5. Output that `<g>` in place of the original `<diag:flex>`.

## 6.2 Column Layout (`direction="column"`)

Let `CW` be the container width (explicit width or max child width), `P` the padding, and `G` the gap.

1. Compute each child’s layout width: `childWidth = diag:max-width ?? CW`.
2. Measure each child's height.
3. Position children: start `y0 = P`, assign `child.y = y0`, then increment by `child.height + G`.
4. Container height `CH = P + Σ(child.height) + G*(n-1) + P`.
5. If background requested, emit:

```xml
<rect
  x="0" y="0"
  width="{CW + 2*P}"
  height="{CH}"
  class="background-class"
  style="background-style"
/>
```

6. Wrap background and children in `<g transform="translate(x,y)">`.

## 6.3 Row Layout (`direction="row"`)

Row layout mirrors column layout:

- Children stack left to right.
- Width = `padding + Σ(childWidth) + gap*(n-1) + padding`.
- Height = `padding + max(childHeight) + padding`.

---

# 7. Text Measurement and Wrapping Semantics

## 7.1 Source Text Rules

- Content inside `<text>` is treated as raw text except:
  - Newlines (`\n`) become hard line breaks.
  - `<tspan>` children are preserved only when `diag:wrap="false"` in v0.1.

## 7.2 Wrapping Algorithm

1. Determine available width `W = diag:max-width ?? containerProvidedWidth`.
2. Break text into words using Unicode word boundaries.
3. Fit words into lines using measured word widths.
4. Determine line height via font metrics, or default to `1.2 × font-size` if unavailable.
5. Emit `<text>` containing one `<tspan>` per line:

```xml
<text ...>
  <tspan x="0" dy="0">First line…</tspan>
  <tspan x="0" dy="1.2em">Second line…</tspan>
  <!-- etc -->
</text>
```

---

# 8. Templates (Experimental)

Templates let you define reusable svg++ fragments and instantiate them elsewhere in the document.

- **Definition**: Declare `<diag:template name="card">…</diag:template>` at the top level. The body can contain any mix of svg++/SVG elements (e.g. `<diag:flex>`, `<text>`, shapes).
- **Slots**: Insert `<diag:slot name="title" />` inside `<text>` or `<tspan>` nodes to mark where instance values flow. Slots currently inject plain text.
- **Parameters**: An instance provides `<diag:param name="title">…</diag:param>` children. Each parameter’s text replaces the matching slot; missing parameters default to empty text.
- **Instantiation**: `<diag:instance template="card" x="40" y="80">…</diag:instance>` expands the template in place. Attributes on the instance override attributes on the template’s top-level nodes (e.g., `x`, `y`, `background-class`, `diag:max-width`).
- **Scope**: Templates must live directly under `<diag:diagram>`. Instances can appear anywhere ordinary svg++ nodes are allowed.

Example:

```xml
<diag:template name="note">
  <diag:flex width="220" direction="column" padding="10" gap="6" background-class="card">
    <text class="title" diag:wrap="false"><diag:slot name="title" /></text>
    <text class="body" diag:wrap="true"><diag:slot name="body" /></text>
  </diag:flex>
</diag:template>

<diag:instance template="note" x="32" y="90">
  <diag:param name="title">Plan</diag:param>
  <diag:param name="body">Outline dependencies and assign owners.</diag:param>
</diag:instance>
```

Templates currently focus on text substitution; richer content slots (embedded SVG fragments, conditional sections) are reserved for a future release.

# 9. Full Example (svg++ Input → Pure SVG Output)

**svg++ input**

```xml
<diag:diagram
  xmlns="http://www.w3.org/2000/svg"
  xmlns:diag="https://example.com/diag"
  width="400"
  height="200"
  viewBox="0 0 400 200"
>
  <style>
    .box { fill:#f5f5f5; stroke:#333; stroke-width:1.5; rx:6; ry:6; }
    .title { font-size:14px; font-weight:600; }
    .body { font-size:12px; }
  </style>

  <diag:flex
    x="20" y="60"
    width="150"
    padding="10"
    gap="4"
    direction="column"
    background-class="box"
  >
    <text class="title" diag:wrap="false">User</text>
    <text class="body" diag:wrap="false">id: Int</text>
    <text class="body" diag:wrap="false">name: String</text>
  </diag:flex>
</diag:diagram>
```

**Resulting SVG (schematic)**

- Auto-generated `<g transform="translate(20,60)"> … </g>` containing measured `<text>` nodes.
- Optional background `<rect>` with class `box` sized to the layout bounds.
- No remaining `diag:` elements or attributes.

---

# 10. Grammar (Informal EBNF)

```ebnf
Diagram        ::= DiagDiagram

DiagDiagram    ::= <diag:diagram DiagDiagramAttrs>
                     DiagramContent*
                   </diag:diagram>

DiagDiagramAttrs ::= [ width = Number ]
                     [ height = Number ]
                     [ viewBox = String ]
                     (OtherAttrs)*

DiagramContent ::= FlexElement
                 | SvgElement          (* Any non-diag SVG element *)

FlexElement    ::= <diag:flex FlexAttrs>
                     DiagramContent*
                   </diag:flex>

FlexAttrs      ::= [ x = Number ]
                   [ y = Number ]
                   [ width = Number ]
                   [ direction = ("row" | "column") ]
                   [ gap = Number ]
                   [ padding = Number ]
                   [ background-class = String ]
                   [ background-style = String ]
                   (OtherAttrs)*

TextElement    ::= <text TextAttrs> TextContent* </text>

TextAttrs      ::= SvgTextAttrs*
                   [ diag:wrap = ("true" | "false") ]
                   [ diag:max-width = Number ]
                   (OtherAttrs)*
```

---

# 11. Versioning and Future Extensions

This document defines svg++ v0.1. Planned additions include:

- Templates: `<diag:template>` + `<diag:instance>`
- Arithmetic in attributes
- Auto arrows / routing
- Named variables / style inheritance
- Horizontal/vertical alignment refinements
- Layering and z-index
- Grid layout

Each future version will spell out added elements/attributes, backward compatibility guarantees, and strict version tagging.

---

# 12. Reference Implementation Notes (Optional)

A renderer typically implements:

- XML parser to build a DOM-like tree.
- Tree walker that handles `<diag:flex>`.
- Text measurement via font metrics (HarfBuzz, canvas APIs, platform APIs, etc.).
- Layout pass covering column/row placement, wrapping, and background generation.
- SVG emission: create a new XML tree with pure SVG nodes and strip all `diag:*` namespaces.

---

# 13. Summary

svg++ v0.1 defines a minimal, predictable, LLM-friendly diagram language:

- One root: `<diag:diagram>`
- One layout primitive: `<diag:flex>`
- Text wrapping via attributes on `<text>`
- Reusable snippets via `<diag:template>` + `<diag:instance>`
- Deterministic expansion into pure SVG
- Simple XML-based grammar ready for future extensions

This spec equips humans and LLMs to generate svg++ documents, parse them, implement renderers, and evolve the language further.
