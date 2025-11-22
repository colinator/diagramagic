# diagramagic

svg++ reference renderer for humans and LLMs. Feed it svg++ input and it emits plain SVG—no runtime, no exotic format. What is "svg++"? Just something we made up here: it's simply svg plus a few additions to support text layout and templates.

## Installation

```bash
pip install diagramagic
```

**Note**: This package includes a Rust extension for accurate SVG measurement. During installation, the extension will be compiled from source, which requires the Rust toolchain:

```bash
# Install Rust (if not already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Then install diagramagic
pip install diagramagic
```

Installation typically takes 30-60 seconds while the Rust extension compiles.

## Quick Start

- **CLI**: `diagramagic input.svg++ > output.svg`
- **Library**: `from diagramagic import diagramagic`
- **Cheat sheet**: `diagramagic --cheatsheet` (or see `AGENTS.md`)
- **Full spec**: `PROJECTSPEC.md`
- **Tests**: `python tests/run_tests.py`

svg++ basics: wrap your document in `<diag:diagram>` with the `diag:` namespace, use `<diag:flex>` for layout, and `diag:wrap="true"` on `<text>` to wrap. Everything compiles to pure SVG 1.1.

Need reusable pieces? Define `<diag:template name="card">…</diag:template>` once, then drop `<diag:instance template="card">` wherever you need consistent cards or packets.

Output defaults to a white canvas; set `diag:background="none"` (or any color) on `<diag:diagram>` to change it.

Example:

```xml
<diag:diagram xmlns="http://www.w3.org/2000/svg"
              xmlns:diag="https://example.com/diag"
              width="300" height="160">
  <style>
    .card { fill:#fff; stroke:#999; rx:10; ry:10; }
    .title { font-size:16; font-weight:600; }
    .body { font-size:12; }
  </style>

  <diag:flex x="20" y="20" width="260" padding="14" gap="8" background-class="card">
    <text class="title" diag:wrap="false">Hello svg++</text>
    <text class="body" diag:wrap="true">
      This paragraph wraps to the flex width automatically.
    </text>
  </diag:flex>
</diag:diagram>
```
