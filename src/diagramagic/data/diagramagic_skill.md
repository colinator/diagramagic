# diagramagic Agent Skill

Use this skill when producing or editing SVG diagrams with diagramagic.

## Required execution model

- You can run shell commands.
- You can read and write local files.
- You can view generated PNG images for visual feedback.

## Command contract

- Compile svg++ to SVG:
  - `diagramagic compile input.svg++`
  - `diagramagic compile input.svg++ -o output.svg`
- Render svg++ or SVG to PNG:
  - `diagramagic render input.svg++`
  - `diagramagic render input.svg -o output.png`
- Optional references:
  - `diagramagic cheatsheet`
  - `diagramagic patterns`
  - `diagramagic prompt`

## First step (mandatory per session)

Before the first diagram task in each session, run:

- `diagramagic cheatsheet`
- `diagramagic patterns`

Use those outputs as the authoritative syntax/pattern reference for the rest of the session.

## Working loop (required)

1. Create or edit `.svg++` source.
2. Run `diagramagic render ...` to generate a PNG.
3. Inspect the rendered image.
4. If incorrect, update source and render again.
5. Produce final SVG with `diagramagic compile ...` when done.

Do not stop at first compile success; iterate until the rendered result matches intent.

## svg++ rules to follow

- Use `<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns">`.
- Prefer flex layout over manual coordinates for vertical/horizontal stacks.
- Use `id` on elements that arrows or focus operations target.
- Use `<diag:arrow from="..." to="...">` for connectors.
- Keep non-`diag:` SVG attributes untouched unless intentionally changed.
- If topology/ranking is the core problem, use `<diag:graph>` + `<diag:node>`/`<diag:edge>` for structure.
- Treat `diag:graph` as scaffolding, not the full design: still use normal SVG/flex for titles, regions, legends, and contextual annotations.
- Keep graph nodes content-rich (title + supporting text) instead of single-token labels when detail matters.
- For title+body graph nodes, set `diag:node gap="6"` to `gap="12"` to avoid cramped text blocks.
- If graph layout is cluttered, split into multiple subgraphs with `diag:include` or use a hybrid flex + arrows composition.

## Quality bar

- Use the same attention to detail you would use in raw SVG (spacing, hierarchy, labels, visual grouping).
- Do not stop at “technically correct” topology; optimize for readability at first glance.
- After each render, check for overlaps, cramped labels, and ambiguous edge paths before finalizing.

## Error recovery policy

- Treat `E_*` failures as actionable input errors, not fatal crashes.
- For `E_ARGS`: fix command usage and retry.
- For `E_PARSE_XML`: fix malformed XML/escaping and retry.
- For `E_SVGPP_SEMANTIC`: fix svg++ structure/ids/templates and retry.
- For `E_FOCUS_NOT_FOUND`: fix focus id or remove `--focus` and retry.
- Only stop and ask for help after at least one concrete corrective attempt.

## Anti-patterns

- Do not use bare `diagramagic file.svg++` (subcommands are required).
- Do not write PNG with `compile`; use `render`.
- Do not treat `diag:graph` as a one-shot substitute for visual design.
- Do not assume output is correct without visual render checks.
