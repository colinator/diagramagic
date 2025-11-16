"""Generate SVG fixtures for every .svg++ file in the fixtures directory."""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
FIXTURE_DIR = TESTS_DIR / "fixtures"

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from diagramagic import diagramagic  # noqa: E402


def main() -> int:
    svgpp_files = sorted(FIXTURE_DIR.glob("*.svg++"))
    if not svgpp_files:
        print("No .svg++ fixtures found in", FIXTURE_DIR)
        return 1

    for svgpp_path in svgpp_files:
        svg_output = diagramagic(svgpp_path.read_text())
        svg_path = svgpp_path.with_suffix(".svg")
        svg_path.write_text(svg_output)
        print(f"Generated {svg_path.name} from {svgpp_path.name}")

    print(f"Converted {len(svgpp_files)} file(s). Output written next to inputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
