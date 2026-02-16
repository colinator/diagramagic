# `diag:include` Specification v1

Minimal, high-leverage modular composition for svg++.

## Purpose

`diag:include` lets one svg++ document include another svg++ file as a compiled sub-diagram.  
The included file is compiled independently and embedded as one transformed `<g>` in the parent output.

This enables:

- Modular diagram composition
- Sub-agent workflows
- Large-diagram structuring with low cognitive overhead

## Design Principles

1. Minimal new concepts
2. No new layout primitives
3. Included content is opaque to the parent
4. No cross-boundary ID references
5. Deterministic behavior
6. Fail loudly and clearly

## Element Definition

Element name: `diag:include`

Required attributes:

- `src` (string): Path to another svg++ file

Optional attributes:

- `x` (number): X translation in px, default `0`
- `y` (number): Y translation in px, default `0`
- `scale` (number): Uniform scale, default `1`
- `id` (string): Optional ID for the emitted wrapper `<g>`

All numeric values are SVG user units (pixels).

## Behavior

### Compilation Model

When the compiler encounters `<diag:include .../>`:

1. Resolve and load `src`
   - `src` is resolved relative to the including file's directory
   - absolute paths are allowed
2. Parse and compile that file as an independent svg++ document
3. Require a `diag:diagram` root in the included source
4. Extract compiled root SVG children (not the outer `<svg>`)
5. Measure compiled content bounds
6. Wrap extracted content in one `<g>`
7. Apply `transform="translate(x,y) scale(scale)"`
8. Emit that group at the include site in parent output

The included diagram is opaque to the parent except as a measured block.

Include recursion rules:

- Cycle detection uses normalized resolved file paths
- Recommended max include depth in v1: `10`

### Layout Interaction

If `diag:include` appears inside `diag:flex`:

- It participates as a single child block
- Width/height are derived from included compiled bounds after `scale`
- Parent flex handles final placement

If `diag:include` is a direct child of `diag:diagram`:

- `x` and `y` are absolute coordinates in the parent diagram
- Omitted `x`/`y` default to `0`

Parent auto-sizing and `viewBox` calculations include transformed included bounds.

## ID Semantics

1. Included internal IDs are preserved as-is
2. No automatic namespacing/rewriting in v1
3. Cross-boundary references are invalid:
- Parent `diag:arrow` cannot target IDs defined only inside an include
- Included `diag:arrow` cannot target parent IDs
4. Any ID collision between parent and included output is an error

## Error Model

Use existing CLI-style `E_*` codes.

- `E_INCLUDE_NOT_FOUND`
- When `src` cannot be resolved/read
- Message includes `src` and resolved path attempt

- `E_INCLUDE_PARSE`
- When included file is not valid XML/svg++
- Message includes included filename and parse location if available

- `E_INCLUDE_ROOT`
- When included file does not have `diag:diagram` root

- `E_INCLUDE_CYCLE`
- When recursive include cycle is detected
- Message includes inclusion chain

- `E_INCLUDE_DEPTH`
- When include depth exceeds v1 maximum

- `E_INCLUDE_ID_COLLISION`
- When parent and included outputs contain duplicate IDs
- Message includes conflicting ID

- `E_INCLUDE_ARGS`
- Invalid include attributes (for example non-numeric `scale`, or `scale <= 0`)

No partial output is emitted on include failure.

## Transforms

Emitted structure:

```xml
<g id="optional_id" transform="translate(x,y) scale(scale)">
  ...compiled included children...
</g>
```

Only uniform scaling is supported in v1.

## CLI Behavior

During `diagramagic compile`:

- Includes resolve at compile time
- Output SVG is fully flattened
- No `diag:include` nodes remain in final SVG

During `diagramagic render` on svg++ input:

- Same include resolution behavior applies (compile step first, then render)

## Non-Goals (Deferred)

Not in v1:

- `width`/`height` fit semantics
- Clipping
- Automatic background rectangles
- `expose-ids` or cross-boundary referencing
- ID namespacing/rewriting
- Include caching
- Partial/incremental compilation

## Sub-Agent Workflow Pattern

1. Sub-agent generates `subdiagram.svg++`
2. Main diagram includes it:

```xml
<diag:include src="subdiagram.svg++" x="300" y="120" scale="0.8"/>
```

3. Main diagram stays small and readable while sub-diagram evolves independently

## Rationale

This v1 gives high leverage with low overhead:

- Strong modularity
- Reuse of sub-diagrams
- Better context control for LLM agents
- No new layout model complexity

It intentionally avoids fragile cross-file coupling and advanced sizing semantics.

## Acceptance Tests (v1)

Minimum acceptance coverage:

1. Include as direct child of `diag:diagram` with default `x=0`, `y=0`, `scale=1`
2. Include with explicit `x`, `y`, `scale` produces expected wrapper transform
3. Include inside `diag:flex` contributes measured width/height correctly
4. Missing include file returns `E_INCLUDE_NOT_FOUND`
5. Invalid include XML/svg++ returns `E_INCLUDE_PARSE`
6. Included file without `diag:diagram` root returns `E_INCLUDE_ROOT`
7. Include cycle returns `E_INCLUDE_CYCLE` with chain context
8. ID collision between parent and included output returns `E_INCLUDE_ID_COLLISION`

## Fixture Generation (for Human Eyeball Review)

Add or refresh fixtures:

- `tests/fixtures/include_basic.svg++`
- `tests/fixtures/include_scaled.svg++`
- `tests/fixtures/include_in_flex.svg++`
- `tests/fixtures/include_cycle_error.svg++` (error fixture)

Generate outputs:

```bash
for f in tests/fixtures/include_*.svg++; do
  diagramagic compile "$f" -o "${f%.svg++}.svg" || true
  diagramagic render "$f" -o "${f%.svg++}.png" || true
done
```

Human eyeball checklist:

1. Included sub-diagram appears at expected position and scale
2. No visual clipping/regression in auto-size/viewBox
3. Include inside flex aligns with siblings and spacing rules
4. Error fixtures fail with expected `E_*` code and message

## LLM Guidance Updates (required when shipped)

Update agent-facing docs/resources:

1. `AGENTS.md` and `src/diagramagic/data/AGENTS.md`
: add a short `diag:include` section with one canonical example and constraints (`no cross-boundary refs`).
2. `src/diagramagic/data/diagramagic_patterns.md`
: add one full pattern that uses an included sub-diagram.
3. `src/diagramagic/data/diagramagic_prompt.txt`
: add one rule telling agents to use includes for large subgraphs instead of inlining huge trees.

## Implementation Checklist (v1)

- [x] Parse/validate `<diag:include>` attributes (`src`, numeric `x/y/scale`, `scale > 0`)
- [x] Resolve include paths relative to including file and enforce depth/cycle checks
- [x] Compile included sources recursively, extract child SVG nodes, compute bounds
- [x] Emit transformed wrapper `<g>` at include site and integrate bounds into layout/auto-size
- [x] Enforce ID collision detection across parent + included outputs
- [x] Add acceptance tests for all `E_INCLUDE_*` failures and success paths
- [x] Add/refresh include fixtures, render PNGs, perform human eyeball review
- [x] Update LLM guidance artifacts (`AGENTS`, patterns, prompt)

## Ready-to-Implement Gate

Spec is ready for implementation when:

- All checklist items above have concrete tasks in the implementation plan
- Acceptance tests are automated and passing
- Fixtures are regenerated and visually reviewed
