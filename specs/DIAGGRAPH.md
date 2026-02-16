# diag:graph Specification v1

## Purpose

`diag:graph` enables automatic node-and-edge layout inside svg++ diagrams. The agent declares nodes and edges; the layout engine computes all positions and edge routes. Zero coordinate math required.

This is the single most common diagram type (flowcharts, architecture diagrams, dependency graphs, pipelines) and the one where agents fail hardest with raw SVG due to manual position calculation.

## Design Principles

1. Zero coordinate math for the agent.
2. Nodes are styled using existing svg++ primitives (flex-like content, CSS classes).
3. Edges reuse the visual model of `diag:arrow` (labels, stroke attributes, arrowheads).
4. One layout algorithm in v1: layered/hierarchical (Sugiyama-style). Covers DAGs, flowcharts, trees, pipelines.
5. Cycles are handled automatically (reversed internally for layout, drawn in original direction).
6. Composes with the rest of svg++ — a `diag:graph` can live inside flex, alongside other elements, or as the entire diagram.
7. Deterministic output for identical input (stable tie-breaking).

## Element Definitions

### `<diag:graph>`

Container that triggers automatic layout of its child nodes and edges.

**Optional attributes:**

| Attribute | Default | Description |
|-----------|---------|-------------|
| `direction` | `"TB"` | Layout direction: `"TB"` (top-to-bottom), `"BT"`, `"LR"`, `"RL"` |
| `node-gap` | `30` | Minimum horizontal gap between nodes in the same rank (pixels) |
| `rank-gap` | `50` | Minimum gap between ranks along the layout direction (pixels) |
| `x` | `0` | X position (top-level only; omit inside flex) |
| `y` | `0` | Y position (top-level only; omit inside flex) |
| `id` | — | Optional ID for the emitted wrapper group |

`diag:graph` emits a `<g>` wrapper containing all positioned nodes and routed edges.

Scope and nesting (v1):

- `diag:graph` cannot be nested inside another `diag:graph`
- Nested graph usage returns `E_GRAPH_NESTED_UNSUPPORTED`

ID semantics:

- `diag:node id` values are in the global document ID namespace within the same compiled document boundary (same namespace as other SVG/diag element IDs).
- Duplicate IDs between graph nodes and any other document element are compile errors.
- Emitted node wrappers preserve node IDs as-is.
- Node IDs must be globally unique across the entire compiled document (not just within one graph).
- Include boundaries remain opaque in v1. IDs inside an included document are not referenceable from the parent document (consistent with `diag:include` v1 constraints).

Children and order (v1):

- Direct children of `diag:graph` must be `diag:node` or `diag:edge`.
- `diag:node` and `diag:edge` may be interleaved in source order.
- Validation and layout are performed after collecting all child nodes and edges in input order.
- Any other direct child element is an error: `E_GRAPH_CHILD_UNSUPPORTED`.

### `<diag:node>`

A node in the graph. Behaves like a `<diag:flex direction="column">` internally — it can contain `<text>`, nested `<diag:flex>`, and other SVG elements. The layout engine determines its position; the node determines its own size from its content.

**Required attributes:**

| Attribute | Description |
|-----------|-------------|
| `id` | Unique identifier. Referenced by edges. |

**Optional attributes:**

| Attribute | Default | Description |
|-----------|---------|-------------|
| `width` | auto | Exact outer width in pixels. Auto = sized to content. |
| `padding` | `8` | Inner padding (pixels) |
| `background-class` | — | CSS class for the auto-generated background rect |
| `background-style` | — | Inline styles for the background rect |
| `min-width` | `0` | Minimum width (pixels) |

**Children:** `<text>`, `<diag:flex>`, standard SVG elements. Same content model as `<diag:flex>`.

Rendering model (v1):

- A node is rendered using the existing flex-style content model (column-style container with optional background rect).
- `diag:graph` introduces graph layout only; it does not introduce a second independent node layout engine.
- Width resolution happens before graph layout positioning:
  - If `width` is specified: `node_outer_width = max(width, min-width)`.
  - If `width` is omitted: `node_outer_width = max(content_width, min-width)`.

### `<diag:edge>`

A directed edge between two nodes. Affects layout (establishes rank ordering) and renders as a line with optional label and arrowhead.

**Required attributes:**

| Attribute | Description |
|-----------|-------------|
| `from` | ID of the source node |
| `to` | ID of the target node |

**Optional attributes:**

| Attribute | Default | Description |
|-----------|---------|-------------|
| `label` | — | Text label displayed at edge midpoint |
| `label-size` | `10` | Label font size (pixels) |
| `label-fill` | `"#555"` | Label text color |
| `stroke` | `"#555"` | Edge line color |
| `stroke-width` | `1` | Edge line width |
| `stroke-dasharray` | — | Dash pattern (e.g., `"4 2"` for dashed) |
| `marker-end` | auto arrowhead | Custom marker URL |
| `marker-start` | — | Custom marker URL |

If no marker attributes are specified, a default arrowhead is added to `marker-end` (same behavior as `diag:arrow`).

Scope:

- `from` and `to` must reference `diag:node` IDs within the same `diag:graph`.
- `diag:edge` does not target arbitrary external element IDs in v1.

## Examples

### Minimal flowchart

```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://diagramagic.ai/ns"
              diag:padding="20">
  <style>
    .box { fill:#e8f4f8; stroke:#2980b9; stroke-width:1; rx:4; }
  </style>

  <diag:graph direction="TB" node-gap="30" rank-gap="50">
    <diag:node id="start" padding="10" background-class="box">
      <text style="font-size:14px">Start</text>
    </diag:node>
    <diag:node id="process" padding="10" background-class="box">
      <text style="font-size:14px">Process Data</text>
    </diag:node>
    <diag:node id="end" padding="10" background-class="box">
      <text style="font-size:14px">Done</text>
    </diag:node>

    <diag:edge from="start" to="process"/>
    <diag:edge from="process" to="end"/>
  </diag:graph>
</diag:diagram>
```

### Architecture diagram (left-to-right)

```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://diagramagic.ai/ns"
              diag:padding="20">
  <style>
    .svc { fill:#ffeaa7; stroke:#fdcb6e; stroke-width:1; rx:6; }
    .db  { fill:#dfe6e9; stroke:#636e72; stroke-width:1; rx:6; }
    .label { font-size:13px; }
  </style>

  <diag:graph direction="LR" node-gap="24" rank-gap="60">
    <diag:node id="client" padding="12" background-class="svc">
      <text class="label">Client</text>
    </diag:node>
    <diag:node id="api" padding="12" background-class="svc">
      <text class="label">API Gateway</text>
    </diag:node>
    <diag:node id="auth" padding="12" background-class="svc">
      <text class="label">Auth Service</text>
    </diag:node>
    <diag:node id="db" padding="12" background-class="db">
      <text class="label">Database</text>
    </diag:node>

    <diag:edge from="client" to="api" label="HTTPS"/>
    <diag:edge from="api" to="auth" label="verify"/>
    <diag:edge from="api" to="db" label="query"/>
    <diag:edge from="auth" to="db" label="lookup" stroke-dasharray="4 2"/>
  </diag:graph>
</diag:diagram>
```

### Multi-content nodes

```xml
<diag:node id="userService" width="180" padding="12" background-class="svc">
  <text style="font-size:15px; font-weight:bold" diag:wrap="false">User Service</text>
  <text style="font-size:11px; fill:#666" diag:wrap="true">Handles registration, login, profile management</text>
</diag:node>
```

### Graph inside a larger diagram

```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://diagramagic.ai/ns"
              diag:padding="20">
  <diag:flex width="700" direction="column" gap="16">
    <diag:flex width="700" padding="12" background-class="header">
      <text style="font-size:20px; font-weight:bold">System Architecture</text>
    </diag:flex>

    <diag:graph direction="LR" node-gap="20" rank-gap="50">
      <!-- nodes and edges here -->
    </diag:graph>
  </diag:flex>
</diag:diagram>
```

## Layout Algorithm (v1)

The v1 layout uses a layered/hierarchical approach:

1. **Cycle breaking.** Detect back-edges via DFS. Temporarily reverse them to produce a DAG. All edges render in their original direction regardless.
2. **Rank assignment.** Longest-path ranking. Each node gets a rank (integer layer). `direction` determines which axis ranks map to.
3. **Ordering.** Within each rank, order nodes to minimize edge crossings (median heuristic, single pass for v1).
4. **Positioning.** Assign coordinates: ranks spaced by `rank-gap`, nodes within a rank spaced by `node-gap`, centered per rank on the cross-axis.
5. **Edge routing.** Emit one straight segment per edge between node border intersection points (same border-intersection algorithm as `diag:arrow`). No waypoints, obstacle avoidance, or orthogonal routing in v1, including for edges that skip ranks.
6. **Label placement.** If `label` is present, place it at the segment midpoint and offset by `6px` along the left-hand normal of the directed edge vector (`(-dy, dx)` normalized). If edge length is `0`, place label exactly at midpoint.

Determinism:

- DFS starts from nodes in `diag:node` input order; adjacency iteration uses `diag:edge` input order.
- Disconnected components are processed in first-seen node order.
- When heuristics produce equal scores (rank ordering or crossing-reduction ties), preserve input order as the tie-breaker.

Direction mapping:

- `TB`: rank increases on `+y` (top to bottom), cross-axis is `x`.
- `BT`: rank increases on `-y` (bottom to top), cross-axis is `x`.
- `LR`: rank increases on `+x` (left to right), cross-axis is `y`.
- `RL`: rank increases on `-x` (right to left), cross-axis is `y`.

This algorithm handles trees, DAGs, pipelines, and cyclic graphs. It produces clean results for the 80% case without requiring a full Sugiyama implementation with dummy nodes and coordinate refinement.

## Layout Interaction

**Inside `diag:flex`:**
- The graph is measured after layout (total bounding box of all positioned nodes and edges).
- It participates as a single fixed-size child in flex layout.
- `x` and `y` should be omitted (parent flex handles positioning).

**As a direct child of `diag:diagram`:**
- `x` and `y` position the graph absolutely.
- Defaults to `(0, 0)` if omitted.

**Auto-sizing:**
- The graph's bounds are included in the parent diagram's auto-size and viewBox calculation.

## Interaction with `diag:arrow`

- `diag:edge` is the native edge primitive for `diag:graph`.
- `diag:arrow` remains available elsewhere in the document.
- In v1, `diag:arrow` may reference emitted graph node IDs when both are in the same compiled document boundary, but `diag:arrow` does not influence graph layout.
- `diag:include` opacity rules still apply: arrows do not cross include boundaries.
- `diag:edge` and `diag:arrow` are resolved in separate phases:
  1. graph layout + `diag:edge` emission
  2. global `diag:arrow` endpoint resolution and emission

## Compilation Phase Order (v1)

1. Expand templates/includes
2. Render/measure graph nodes
3. Compute graph layout (ranks/order/positions)
4. Emit `diag:edge` geometry and labels
5. Merge graph output into document tree
6. Run global `diag:arrow` resolution/emission
7. Compute final diagram bounds/viewBox

## Error Handling

| Condition | Error Code | Detail |
|-----------|-----------|--------|
| `<diag:edge>` references nonexistent node ID | `E_GRAPH_UNKNOWN_NODE` | Includes bad ID and which attribute (`from`/`to`) |
| `<diag:node>` without `id` | `E_GRAPH_NODE_MISSING_ID` | — |
| Duplicate graph node IDs | `E_GRAPH_DUPLICATE_NODE` | Includes duplicate ID |
| Graph node ID collides with external element ID | `E_GRAPH_ID_COLLISION` | Includes duplicate ID and scope |
| Unsupported direct child under `<diag:graph>` | `E_GRAPH_CHILD_UNSUPPORTED` | Includes child tag name |
| `<diag:edge>` where `from` equals `to` | `E_GRAPH_SELF_EDGE` | Self-edges are not supported in v1 |
| Invalid graph attribute value (`direction`, gaps, etc.) | `E_GRAPH_ARGS` | Includes attribute and invalid value |
| Nested `diag:graph` inside another graph | `E_GRAPH_NESTED_UNSUPPORTED` | Nested graphs are not supported in v1 |

Cycles are **not** errors. They are handled by the layout algorithm.

## Complexity Guardrail (v1, Optional)

- v1 does not require fixed graph-size limits.
- Implementations may define optional guardrails for operational safety (for example, max node/edge counts).
- If an implementation enables a guardrail and input exceeds it, return `E_GRAPH_TOO_LARGE` and include node/edge counts plus the configured limit(s).

## Non-Goals (Explicitly Deferred)

- **Orthogonal edge routing** (right-angle paths with waypoints)
- **Edge bend points / control points**
- **Subgraphs / clusters** (grouped nodes with a shared boundary)
- **Multiple layout algorithms** (force-directed, circular, etc.)
- **Rank constraints** (`rank="same"`, `rank="min"`)
- **Port specification** (which side of a node an edge connects to)
- **Self-edges**
- **Node shapes** (diamond, circle, etc. — use raw SVG inside the node if needed)
- **Interactive / animated layout**

## Acceptance Tests (v1)

Minimum acceptance coverage:

1. TB DAG layout with 4-6 nodes (golden SVG structure)
2. LR DAG layout with labels and stroke passthrough
3. BT and RL direction layouts map ranks to the correct axis/sign
4. Disconnected graph layout is stable and deterministic
5. Single cycle graph renders (cycle handling works, no error)
6. Unknown node reference returns `E_GRAPH_UNKNOWN_NODE`
7. Duplicate node ID returns `E_GRAPH_DUPLICATE_NODE` (or `E_GRAPH_ID_COLLISION` when external)
8. Unsupported direct child returns `E_GRAPH_CHILD_UNSUPPORTED`
9. Self-edge returns `E_GRAPH_SELF_EDGE`
10. Graph inside `diag:flex` contributes correct measured bounds
11. Determinism: same input yields stable node order/output across runs
12. If optional guardrails are enabled, oversized graph returns `E_GRAPH_TOO_LARGE`

## Fixture Generation (for Human Eyeball Review)

Add or refresh fixtures:

- `tests/fixtures/graph_tb_basic.svg++`
- `tests/fixtures/graph_lr_architecture.svg++`
- `tests/fixtures/graph_cycle.svg++`
- `tests/fixtures/graph_dense_small.svg++`
- `tests/fixtures/graph_in_flex.svg++`

Generate outputs:

```bash
for f in tests/fixtures/graph_*.svg++; do
  diagramagic compile "$f" -o "${f%.svg++}.svg" || true
  diagramagic render "$f" -o "${f%.svg++}.png" || true
done
```

Human eyeball checklist:

1. Node spacing matches `node-gap` / `rank-gap`
2. Direction modes (`TB`, `BT`, `LR`, `RL`) are visually correct
3. Edge labels are readable and offset from lines
4. Cyclic graph renders stably without collapsing overlap
5. Graph-in-flex respects parent spacing and overall bounds

## LLM Guidance Updates (required when shipped)

Update agent-facing docs/resources:

1. `AGENTS.md` and `src/diagramagic/data/AGENTS.md`
: add a dedicated `diag:graph` section with minimal syntax and one complete example.
2. `src/diagramagic/data/diagramagic_patterns.md`
: add at least two full patterns (`flowchart`, `service dependency graph`).
3. `src/diagramagic/data/diagramagic_prompt.txt`
: add one rule to prefer `diag:graph` over manual coordinates for graph-like tasks.
4. `src/diagramagic/data/diagramagic_skill.md`
: add one decision rule: if user asks for flowchart/architecture/dependency layout, start with `diag:graph`.

## Implementation Checklist (v1)

- [x] Parse/validate `diag:graph`, `diag:node`, `diag:edge` attributes, child element grammar, and IDs
- [x] Enforce scope constraints (same-graph edge targets, no nested graphs in v1)
- [x] Reuse existing node content renderer; measure node dimensions
- [x] Implement layered layout pipeline (cycle break, rank assign, order, position) with deterministic traversal/tie-break rules
- [x] Emit straight-segment edges + labels + marker defaults with stable tie-breaking
- [x] Integrate graph bounds into flex/root auto-size flow
- [x] Add acceptance tests for success/error/determinism paths
- [x] Optionally add operational guardrails (`E_GRAPH_TOO_LARGE`) if desired by implementation
- [x] Add/refresh graph fixtures, render PNGs, perform human eyeball review
- [x] Update LLM guidance artifacts (`AGENTS`, patterns, prompt, skill)

## Ready-to-Implement Gate

Spec is ready for implementation when:

- Compilation phase order is reflected in tests
- All required `E_GRAPH_*` failures listed above are covered (and `E_GRAPH_TOO_LARGE` if guardrails are enabled)
- Determinism and fixture visual review are complete

## Why This Feature

| Without `diag:graph` | With `diag:graph` |
|-----------------------|-------------------|
| Agent calculates every x/y coordinate | Agent declares nodes and relationships |
| Overlapping nodes on complex diagrams | Layout engine handles spacing |
| Manual arrow routing breaks on edits | Edges auto-route after layout |
| Flowcharts require ~3x more tokens | Flowcharts require only structure + style |
| Adding a node means repositioning everything | Adding a node means one `<diag:node>` + edges |

This is the feature that shifts svg++ from "SVG with better text wrapping" to "the right tool for any diagram an agent needs to produce."
