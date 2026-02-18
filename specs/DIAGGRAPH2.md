# diag:graph Specification v2 (Graphviz Backend)

## Purpose

Power up `diag:graph` quality without exploding svg++ API surface.

v2 keeps the existing `diag:graph` / `diag:node` / `diag:edge` model, but delegates layout and edge routing to Graphviz when available. This gives multiple mature layouts "for free" and significantly better edge paths (fewer overlaps/crossings, better readability).

## Goals

1. Keep authoring model unchanged: users still declare nodes + edges.
2. Add multiple layout families with one small switch.
3. Improve edge routing quality materially vs v1 straight segments.
4. Preserve deterministic output.
5. Keep existing v1 behavior as fallback when Graphviz is unavailable.

## Non-Goals

1. Replacing all Graphviz tuning knobs in svg++ attributes.
2. Full Graphviz feature parity (ports, clusters, all node shapes, etc.) in v2.
3. Interactive/animated force simulation.

## Release Phasing

### Phase 1 (ship first)

- `layout`: `layered`, `circular`, `radial`
- `routing`: `auto`, `spline`, `polyline`, `ortho`, `curved`, `line`
- Graphviz backend + routed SVG edge paths

### Phase 2 (deferred)

- `layout`: `spring`, `force`, `force-large`
- Additional tuning for very dense graphs and large-network quality/perf tradeoffs

## Minimal API Additions

### `<diag:graph>` new optional attributes (v2)

| Attribute | Default | Values | Description |
|-----------|---------|--------|-------------|
| `layout` | `"layered"` | `"layered"`, `"circular"`, `"radial"` (v2 Phase 1); `"spring"`, `"force"`, `"force-large"` (Phase 2) | Layout family |
| `routing` | `"auto"` | `"auto"`, `"spline"`, `"polyline"`, `"ortho"`, `"curved"`, `"line"` | Edge routing style |
| `quality` | `"balanced"` | `"fast"`, `"balanced"`, `"high"` | Preset for Graphviz spacing/overlap tuning |

All existing v1 attributes remain valid: `direction`, `node-gap`, `rank-gap`, `x`, `y`, `id`.

### Graphviz mapping

| `layout` | Graphviz engine |
|----------|------------------|
| `layered` | `dot` |
| `spring` | `neato` |
| `force` | `fdp` |
| `force-large` | `sfdp` |
| `circular` | `circo` |
| `radial` | `twopi` |

`routing` maps to Graphviz `splines` attribute:
- `spline`, `polyline`, `ortho`, `curved`, `line` map directly.
- `auto` uses:
  - `spline` for `layered`
  - `polyline` for circular/radial (and spring/force in Phase 2)

Notes:
- Graphviz documents that `splines=ortho` in `dot` does not fully handle edge labels/ports; treat as best-effort in v2.
- For circular/radial layouts, overlap handling is controlled by Graphviz `overlap` settings.
- Force/spring overlap tuning is Phase 2 scope.

## Behavior and Compatibility

1. If `layout` is omitted, behavior should remain flowchart-friendly (`layered`).
2. Existing diagrams using v1 attrs continue to render.
3. `direction` maps to Graphviz `rankdir` for `layered` only.
4. `node-gap` and `rank-gap` map to Graphviz spacing attrs when supported:
   - `layered`: map to `nodesep` and `ranksep` (unit-converted).
   - `radial`: map `rank-gap` to `ranksep` best-effort.
   - Phase 2 engines (`spring`/`force`/`force-large`): treat as hints only.
5. If Graphviz is not installed, compile should either:
   - fall back to v1 internal layout (default), or
   - fail with `E_GRAPHVIZ_UNAVAILABLE` when strict mode is enabled.

## Arrow/Edge Quality Upgrade

v2 replaces v1 straight edge segments with routed paths from Graphviz output geometry.

Expected improvements:
1. Fewer edges crossing node bodies.
2. Better multi-edge separation.
3. Better overall path readability in dense graphs.

Rendering model:
1. Parse edge control points from Graphviz layout output.
2. Emit SVG `<path>` per edge (instead of always `<line>`).
3. Preserve existing edge styling passthrough (`stroke`, `stroke-width`, `stroke-dasharray`, markers, labels).
4. Preserve default marker behavior (`marker-end` auto when unspecified).

## Implementation Plan

### 1) Build a Graphviz layout adapter

Inputs:
- measured node sizes from existing `diag:node` rendering path
- graph edges + graph attrs

Steps:
1. Render each `diag:node` exactly as today to determine final width/height.
2. Generate DOT text with one node per `diag:node`.
3. Set node `width`/`height` from measured sizes (inches), `fixedsize=true`, and neutral visual attrs (layout-only).
4. Apply graph attrs from `layout` / `routing` / `quality` + mapped `direction` / spacing.
5. Run Graphviz CLI with selected engine and parse geometry output.

Recommended output format for parsing:
- `-Tplain` initially (simple, line-based, includes node positions/sizes and edge control points).
- Optionally move to `-Tjson`/`-Txdot_json` later for richer metadata.

### 2) Coordinate conversion

Graphviz `plain` units are inches with lower-left origin.

Adapter responsibilities:
1. Convert inches to px (`96 px / in`) consistently.
2. Convert origin/sign to svg++ coordinate system.
3. Normalize min-x/min-y to local graph coordinates.

### 3) Emit final SVG graph group

1. Place rendered node groups at Graphviz-computed centers.
2. Emit routed edge paths from control points.
3. Emit labels at Graphviz-provided label anchor when available; otherwise midpoint fallback.
4. Maintain current bounds computation for flex/root autosize.

### 4) Quality presets (minimal)

Suggested preset mapping:

- `fast`:
  - fewer iterations/default overlap handling
  - prioritize speed
- `balanced`:
  - current default
- `high`:
  - stronger overlap/crossing reduction where engine supports it
  - may be slower

Implementation can start with conservative mappings and refine empirically.

## Error Handling

New errors:

| Condition | Error Code | Detail |
|-----------|------------|--------|
| Graphviz executable not found | `E_GRAPHVIZ_UNAVAILABLE` | Include engine and install hint |
| Graphviz process exits non-zero | `E_GRAPH_LAYOUT_FAILED` | Include stderr tail |
| Graphviz output parse failure | `E_GRAPH_LAYOUT_PARSE` | Include output format + parse context |
| Unsupported `layout` value | `E_GRAPH_ARGS` | Include bad value |
| Unsupported `routing` value | `E_GRAPH_ARGS` | Include bad value |
| Unsupported `quality` value | `E_GRAPH_ARGS` | Include bad value |

All existing `E_GRAPH_*` v1 errors remain.

## Performance and Limits

1. Keep existing safety guardrails (`E_GRAPH_TOO_LARGE`) in place.
2. Add timeout for Graphviz invocation (e.g. 2-10s configurable).
3. Cache Graphviz adapter binary detection per process.
4. Ensure deterministic node/edge emission order in final SVG.

## Test Plan (Acceptance)

### Functional

1. `layout=layered` reproduces v1-ish flowchart quality with improved edges.
2. `layout=circular` produces clearly circular placement.
3. `layout=radial` produces concentric/radial ranks.
4. `routing=ortho` emits axis-aligned polylines (best-effort caveat accepted).

### Phase 2 functional (deferred)

1. `layout=spring` provides stable undirected network placement.
2. `layout=force` handles dense undirected-ish dependency graph better than v1.
3. `layout=force-large` handles large graphs with acceptable runtime.

### Compatibility

1. Existing v1 fixtures compile unchanged.
2. Graph in flex still contributes correct bounds.
3. ID semantics and arrow marker defaults unchanged.

### Failure paths

1. Missing Graphviz binary -> fallback or `E_GRAPHVIZ_UNAVAILABLE` (per mode).
2. Bad `layout`/`routing`/`quality` -> `E_GRAPH_ARGS`.
3. Corrupt/partial Graphviz output -> `E_GRAPH_LAYOUT_PARSE`.

### Determinism

1. Same input and version -> stable output.
2. Explicit test snapshots for `layered`, `circular`, `radial`.

## Fixtures to Add

1. `tests/fixtures/graph2_layered_flow.svg++`
2. `tests/fixtures/graph2_circular_deps.svg++`
3. `tests/fixtures/graph2_radial_hub.svg++`
4. `tests/fixtures/graph2_ortho_routing.svg++`

Phase 2 fixtures:

1. `tests/fixtures/graph2_spring_network.svg++`
2. `tests/fixtures/graph2_force_dense.svg++`
3. `tests/fixtures/graph2_force_large.svg++`

Generate:

```bash
for f in tests/fixtures/graph2_*.svg++; do
  diagramagic compile "$f" -o "${f%.svg++}.svg" || true
  diagramagic render "$f" -o "${f%.svg++}.png" || true
done
```

## Guidance Updates Required

1. `AGENTS.md` + `src/diagramagic/data/AGENTS.md`
   - add `layout`/`routing` quick reference and one example per layout family.
2. `src/diagramagic/data/diagramagic_patterns.md`
   - add 3 patterns: `layered`, `circular`, `radial`.
3. `SKILL.md` + `src/diagramagic/data/diagramagic_skill.md`
   - add decision rules for choosing layout family.
4. `src/diagramagic/data/diagramagic_prompt.txt`
   - add one-line selector heuristic:
     - flowchart => layered
     - hub/spoke => radial
     - cyclic peer network => circular (force in Phase 2)

## Implementation Checklist (v2)

- [x] Add parser support for `layout`, `routing`, `quality` on `diag:graph` (Phase 1 values only)
- [x] Implement Graphviz adapter (DOT generation + process invocation + output parse)
- [x] Keep v1 internal layout as fallback path
- [x] Map `direction`, `node-gap`, `rank-gap` to Graphviz attrs where supported
- [x] Emit routed SVG edge paths from Graphviz geometry
- [x] Preserve edge labels, markers, and passthrough styles
- [x] Add Graphviz-specific errors (`E_GRAPHVIZ_UNAVAILABLE`, `E_GRAPH_LAYOUT_FAILED`, `E_GRAPH_LAYOUT_PARSE`)
- [x] Add timeout + deterministic emission ordering
- [x] Add graph2 fixtures and PNG eyeball review
- [x] Add acceptance tests for each layout family and failure path
- [x] Update all agent-facing docs/patterns/skill guidance

## Phase 2 Checklist (deferred)

- [ ] Enable `layout=spring` (`neato`) with deterministic/stable settings
- [ ] Enable `layout=force` (`fdp`) and `layout=force-large` (`sfdp`)
- [ ] Add fixtures/tests for spring/force/force-large
- [ ] Tune quality presets for dense graph readability vs runtime
- [ ] Update guidance docs with when to prefer spring/force layouts

## Ready-to-Implement Gate

Spec is ready when:
1. `layout`/`routing`/`quality` semantics are frozen.
2. Fallback-vs-strict behavior for missing Graphviz is decided.
3. At least one parsed Graphviz output format is selected (`plain` recommended first).
4. Phase 1 acceptance fixtures for layered/circular/radial are committed.

## Research References

- Graphviz layout engines: https://graphviz.org/docs/layouts/
- Graphviz command-line usage (`-K`, `-T`): https://graphviz.org/doc/info/command.html
- Graphviz `plain` output format: https://graphviz.org/docs/outputs/plain/
- Graphviz `splines` attribute and ortho caveat: https://graphviz.org/docs/attrs/splines/
