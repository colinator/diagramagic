# `diag:anchor` Specification v1 (Minimal)

Named, invisible coordinates for precise arrow endpoints and alignment.

## Purpose

`diag:anchor` defines a named point in diagram coordinate space.  
Other features, especially `diag:arrow`, can reference that point.

Anchors compile to coordinates only and emit no visible SVG nodes.

## Design Goals

1. Minimal surface area
2. No visible rendering side effects
3. Compile-time deterministic behavior
4. Compatible with existing layout/transform model
5. Useful for sequence/timeline-style diagrams

## Element

`diag:anchor`

Placement (v1):

- Allowed anywhere regular diagram elements are allowed (top-level or nested groups/flex content)
- Anchors are not rendered, but their coordinates resolve in final diagram coordinate space

## Attributes

Required:

- `id` (string): Unique identifier in document ID namespace

Position source (choose exactly one mode):

- Absolute mode:
  - `x` (number)
  - `y` (number)
- Relative mode:
  - `relative-to` (string, target element ID)
  - `side` (optional): `top | bottom | left | right | center` (default `center`)

Optional offsets (both modes):

- `offset-x` (number, default `0`)
- `offset-y` (number, default `0`)

All numeric values are SVG user units (pixels).

Validation:

- Exactly one position mode must be used:
  - absolute mode (`x` and `y`, no `relative-to`)
  - relative mode (`relative-to`, optional `side`, no `x`/`y`)

## Resolution Rules

### Absolute anchor

If `x` and `y` are provided and `relative-to` is absent:

- Base point is `(x, y)`
- Apply `offset-x`, `offset-y` after base point

### Relative anchor

If `relative-to` is provided:

- Resolve referenced target bbox after layout in final coordinate space
- Target may be any measurable emitted element/node ID in the same document scope
- Compute base point from `side`:
  - `top`: `(mid-x, min-y)`
  - `bottom`: `(mid-x, max-y)`
  - `left`: `(min-x, mid-y)`
  - `right`: `(max-x, mid-y)`
  - `center`: `(mid-x, mid-y)`
- Apply `offset-x`, `offset-y` after base point

If `side` is omitted, default to `center`.

## Rendering Behavior

- `diag:anchor` emits no SVG nodes
- Anchor definitions exist only in compiler symbol tables
- Parent/group transforms are reflected via resolved final-space bboxes

## ID Semantics

- Anchor IDs share the same namespace as element IDs
- Duplicate IDs are compile errors

## `diag:arrow` Interaction

`diag:arrow from` and `to` may reference either:

- element IDs (existing behavior), or
- anchor IDs

Endpoint rules:

- Anchor target: endpoint is exact anchor coordinate
- Element target: existing center-line/bbox intersection logic

Mixed case is valid:

- one endpoint anchor, one endpoint element

## Includes and Templates (v1 stance)

To stay minimal and consistent with current `diag:include` v1:

- Parent diagrams cannot reference anchors inside included files
- Included diagrams cannot reference parent anchors
- No cross-boundary anchor export/import in v1
- Template/instance behavior follows existing ID-collision rules in compiler
  - No new anchor-specific rewrite mechanism introduced in this spec
- Nested include/template boundaries do not change this rule: same-scope only

## Compilation Order

1. Expand templates
2. Resolve includes
3. Resolve layout and transformed bboxes
4. Resolve anchors
5. Emit arrows
6. Emit final SVG

## Error Model

Use `E_*` style codes:

- `E_ANCHOR_ARGS`
  - Invalid attribute combination (for example both absolute and relative mode, missing required position mode, non-numeric values)
- `E_ANCHOR_TARGET_NOT_FOUND`
  - `relative-to` references missing ID
- `E_ANCHOR_DUPLICATE_ID`
  - Anchor ID collides with existing element/anchor ID
- `E_ARROW_TARGET_NOT_FOUND`
  - Arrow `from`/`to` references unknown ID (element or anchor)
- `E_ANCHOR_TARGET_UNMEASURABLE`
  - `relative-to` exists but has no measurable bbox

No partial output on anchor-resolution failure.

## Minimal Examples

Absolute anchor:

```xml
<diag:anchor id="t1" x="100" y="200"/>
```

Relative anchor:

```xml
<diag:anchor id="client_mid" relative-to="client_box" side="right"/>
```

Arrow to anchors:

```xml
<diag:arrow from="client_mid" to="server_mid" label="SYN"/>
```

Sequence-style points:

```xml
<diag:anchor id="c_t1" relative-to="client_lane" side="top" offset-y="100"/>
<diag:anchor id="s_t1" relative-to="server_lane" side="top" offset-y="100"/>
<diag:arrow from="c_t1" to="s_t1" label="SYN"/>
```

## Non-Goals (v1)

- Auto timeline generation
- Constraint solving
- Visible/debug anchor markers
- Anchor groups
- Runtime/dynamic repositioning

## Critique Summary

`diag:anchor` is high value, but only if kept strict and minimal.

What makes it strong:

- Tiny syntax
- Significant expressiveness for arrows and sequence diagrams
- No renderer/runtime complexity

Main risk:

- Scope creep into cross-file/template ID rewriting and export semantics

Recommendation:

- Implement this exact minimal version first
- Defer cross-boundary anchor export, automatic rewriting, and advanced anchor systems

## Acceptance Tests (v1)

Minimum acceptance coverage:

1. Absolute anchor (`x`,`y`) endpoint is used exactly by `diag:arrow`
2. Relative anchor (`relative-to` + `side`) resolves to correct bbox point
3. `offset-x` / `offset-y` are applied after base position resolution
4. Mixed endpoint case (anchor -> element and element -> anchor) renders correctly
5. Missing position mode returns `E_ANCHOR_ARGS`
6. Invalid mixed mode (absolute + relative together) returns `E_ANCHOR_ARGS`
7. Missing `relative-to` target returns `E_ANCHOR_TARGET_NOT_FOUND`
8. Duplicate anchor ID collision returns `E_ANCHOR_DUPLICATE_ID`

## Fixture Generation (for Human Eyeball Review)

Add or refresh fixtures:

- `tests/fixtures/anchor_absolute.svg++`
- `tests/fixtures/anchor_relative_sides.svg++`
- `tests/fixtures/anchor_offsets.svg++`
- `tests/fixtures/anchor_mixed_endpoints.svg++`

Generate outputs:

```bash
for f in tests/fixtures/anchor_*.svg++; do
  diagramagic compile "$f" -o "${f%.svg++}.svg" || true
  diagramagic render "$f" -o "${f%.svg++}.png" || true
done
```

Human eyeball checklist:

1. Arrow endpoints land on intended anchor points, not auto-picked element borders
2. Offsets visibly move endpoints in correct axis/direction
3. Rotated/scaled groups still produce expected anchor placement
4. Error fixtures fail with expected `E_*` code and message

## LLM Guidance Updates (required when shipped)

Update agent-facing docs/resources:

1. `AGENTS.md` and `src/diagramagic/data/AGENTS.md`
: add a short `diag:anchor` section with absolute + relative examples.
2. `src/diagramagic/data/diagramagic_patterns.md`
: add one sequence/timeline-style pattern using anchors for message lanes.
3. `src/diagramagic/data/diagramagic_prompt.txt`
: add one rule: use anchors when precise connection points matter; use plain arrows otherwise.

## Implementation Checklist (v1)

- [x] Add parser/validation for `diag:anchor` with strict position-mode rules
- [x] Store anchors in symbol table sharing global ID namespace with elements
- [x] Resolve anchors after layout+bbox pass and before global arrow emission
- [x] Extend arrow endpoint resolution to accept anchor IDs in `from`/`to`
- [x] Enforce same-scope boundary rules for template contexts (include cross-boundary rules remain tied to future `diag:include` implementation)
- [x] Add acceptance tests for absolute/relative/offset/mixed-endpoint behaviors
- [x] Add/refresh anchor fixtures, render PNGs, perform human eyeball review
- [x] Update LLM guidance artifacts (`AGENTS`, patterns, prompt)

## Ready-to-Implement Gate

Spec is ready for implementation when:

- Anchor validation and resolution order are encoded in tests
- All `E_ANCHOR_*`/`E_ARROW_TARGET_NOT_FOUND` cases are covered
- Fixtures and guidance updates are complete
