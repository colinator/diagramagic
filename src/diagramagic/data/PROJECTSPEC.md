# svg++ Specification v1
*A small SVG extension language that compiles to plain SVG 1.1*

## 1. Purpose

svg++ is XML. It keeps normal SVG syntax and adds a small set of `diag:` elements/attributes for layout and composition.

Design goals:
- LLM-friendly and human-editable
- deterministic output
- no runtime format lock-in (always compiles to standard SVG)

Compilation model:

```
svg++ input -> compiler -> plain SVG output
```

## 2. Namespace

A valid document uses a `diag:` namespace and a `<diag:diagram>` root.

Canonical namespace URI is:

```xml
xmlns:diag="https://diagramagic.ai/ns"
```

The implementation accepts alternate `diag` namespace URIs, but canonical URI is recommended.

## 3. Supported svg++ Constructs

### 3.1 Root and Layout

- `<diag:diagram>`: root container; compiles to `<svg>`
- `<diag:flex>`: row/column layout container
- `<text diag:wrap="true">`: wrapped text on native SVG `<text>`

### 3.2 Reuse and Composition

- `<diag:template>`, `<diag:instance>`, `<diag:slot>`, `<diag:param>`: reusable templates
- `<diag:include src="...">`: compile-time inclusion of another svg++ document

### 3.3 Connectors

- `<diag:arrow from="..." to="...">`: connector between element/anchor ids
- `<diag:anchor>`: named coordinate for precise connector endpoints

### 3.4 Graph Layout

- `<diag:graph>`: automatic layered graph layout
- `<diag:node>`: graph node content container
- `<diag:edge>`: graph relationship + rendered edge

## 4. Element Semantics

### 4.1 `<diag:diagram>`

Attributes:
- SVG attrs like `width`, `height`, `viewBox` are optional
- `diag:background` (default white; `none`/`transparent` keeps transparency)
- `diag:padding` (default `0`)
- `diag:font-family`, `diag:font-path` (inherited defaults for text metrics)

Behavior:
- emits `<svg>`
- auto-calculates bounds/viewBox from rendered content when not explicitly set
- strips all `diag:*` attributes/elements from output

### 4.2 `<diag:flex>`

Attributes:
- `x`, `y` (default `0`)
- `width` (optional)
- `direction="column|row"` (default `column`)
- `gap` (default `0`)
- `padding` (default `0`)
- `background-class`, `background-style`

Behavior:
- compiles to `<g transform="translate(x,y)">...`
- column/row child placement with gap + padding
- optional auto background `<rect>`

### 4.3 Wrapped text (`<text>`)

Attributes:
- `diag:wrap="true|false"` (default `false`)
- `diag:max-width` (optional)
- `diag:font-family`, `diag:font-path` (optional, inheritable)

Behavior:
- `diag:wrap="true"` inserts wrapped `<tspan>` lines
- `diag:wrap="false"` preserves single-line text measurement

### 4.4 Templates

- Define at root via `<diag:template name="...">...</diag:template>`
- Instantiate via `<diag:instance template="...">` with `<diag:param>` children
- `<diag:slot name="..."/>` placeholders are text-substituted
- instance attributes override template top-level element attributes

### 4.5 `<diag:arrow>`

Attributes:
- required: `from`, `to`
- optional: `label`, `label-size`, `label-fill`, `label-rotate`, stroke/presentation attrs, marker attrs

Behavior:
- endpoints resolved by center-line/border intersection (or exact anchor points)
- if marker attrs omitted, default `marker-end` arrowhead is added
- `label-rotate` controls label orientation: `horizontal` (default), `follow`, `vertical`, or numeric degrees
- legacy `from-edge` / `to-edge` overrides are not supported

### 4.6 `<diag:anchor>`

Attributes:
- required: `id`
- absolute mode: `x` + `y`
- relative mode: `relative-to` + optional `side="top|bottom|left|right|center"`
- optional offsets: `offset-x`, `offset-y`

Behavior:
- anchors are semantic only (no visible emitted SVG node)
- usable as `diag:arrow` endpoints

### 4.7 `<diag:include>`

Attributes:
- required: `src`
- optional: `x`, `y`, `scale`, `id`

Behavior:
- resolves and compiles included svg++ recursively at compile time
- emits one transformed `<g>` wrapper with included compiled children
- includes flatten into final output (no `diag:include` remains)
- depth/cycle checks are enforced

v1 constraints:
- include depth limit: `10`
- include cycles are errors
- ID collisions after expansion are errors
- design intent is opaque include boundaries; avoid cross-boundary references

### 4.8 `<diag:graph>`, `<diag:node>`, `<diag:edge>`

`diag:graph` attributes:
- `direction="TB|BT|LR|RL"` (default `TB`)
- `node-gap` (default `30`)
- `rank-gap` (default `50`)
- `x`, `y` (default `0`)
- optional `id`

`diag:graph` child grammar (v1):
- direct children must be `diag:node` or `diag:edge`
- nested `diag:graph` is not supported

`diag:node`:
- required: `id`
- optional: `width`, `min-width`, `padding`, `gap`, `background-class`, `background-style`
- content model follows flex-style content rendering

`diag:edge`:
- required: `from`, `to` (same-graph node ids)
- optional: label attrs (`label`, `label-size`, `label-fill`, `label-rotate`) + standard stroke/presentation attrs + markers
- `label-rotate` values match `diag:arrow`: `horizontal` (default), `follow`, `vertical`, or numeric degrees
- self-edges are not supported in v1

Layout algorithm (v1):
1. DFS back-edge cycle breaking (temporary reversal)
2. longest-path rank assignment
3. median-based per-rank ordering (stable tie-break)
4. rank/node spacing via `rank-gap` and `node-gap`
5. one straight line segment per edge

Graph guardrails (current defaults):
- max nodes per graph: `2000`
- max edges per graph: `8000`
- if exceeded: `E_GRAPH_TOO_LARGE`

## 5. ID and Scope Rules

- IDs are globally unique within the compiled document tree
- duplicate IDs are semantic errors
- graph node IDs participate in global ID uniqueness checks
- anchors share the same ID namespace as elements

## 6. Compilation Order (High-level)

1. parse XML + namespace detection
2. expand templates (`diag:template` / `diag:instance`)
3. expand includes (`diag:include`) with cycle/depth checks
4. enforce unique IDs after include expansion
5. expand graphs (`diag:graph` -> emitted groups/lines/labels)
6. collect anchors/arrows
7. render tree to pure SVG nodes
8. resolve and emit `diag:arrow`
9. compute bounds/viewBox/width/height and apply diagram background

## 7. Error Model

CLI exposes stable `E_*` codes.

Common families:
- Parse/args/runtime:
  - `E_ARGS`, `E_PARSE_XML`, `E_INTERNAL`, `E_FOCUS_NOT_FOUND`
- Semantic fallback:
  - `E_SVGPP_SEMANTIC` (for uncoded semantic `ValueError`s)
- Include:
  - `E_INCLUDE_ARGS`, `E_INCLUDE_NOT_FOUND`, `E_INCLUDE_PARSE`, `E_INCLUDE_ROOT`, `E_INCLUDE_CYCLE`, `E_INCLUDE_DEPTH`, `E_INCLUDE_ID_COLLISION`
- Graph:
  - `E_GRAPH_ARGS`, `E_GRAPH_NODE_MISSING_ID`, `E_GRAPH_UNKNOWN_NODE`, `E_GRAPH_DUPLICATE_NODE`, `E_GRAPH_ID_COLLISION`, `E_GRAPH_CHILD_UNSUPPORTED`, `E_GRAPH_SELF_EDGE`, `E_GRAPH_NESTED_UNSUPPORTED`, `E_GRAPH_TOO_LARGE`

## 8. Non-goals in v1

- orthogonal edge routing / waypoints
- graph clusters/subgraphs
- graph port constraints
- self-edge rendering for `diag:edge`
- multiple graph layout algorithms
- interactive/animated layout

## 9. References

Feature-specific v1 specs:
- `specs/DIAGANCHOR.md`
- `specs/DIAGINCLUDE.md`
- `specs/DIAGGRAPH.md`

Agent-oriented quick reference:
- `AGENTS.md`

This file is the consolidated overview; feature specs above contain deeper per-feature details and acceptance criteria.
