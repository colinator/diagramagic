from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from diagramagic import cli


class _StdoutCapture:
    def __init__(self) -> None:
        self._text = io.StringIO()
        self.buffer = io.BytesIO()

    def write(self, value: str) -> int:
        return self._text.write(value)

    def flush(self) -> None:
        pass

    def get_text(self) -> str:
        return self._text.getvalue()


class CLIAcceptanceTests(unittest.TestCase):
    @staticmethod
    def _png_size(blob: bytes) -> tuple[int, int]:
        # PNG IHDR width/height are big-endian u32 at fixed offsets.
        if len(blob) < 24 or blob[:8] != b"\x89PNG\r\n\x1a\n":
            raise AssertionError("not a PNG payload")
        width = int.from_bytes(blob[16:20], "big")
        height = int.from_bytes(blob[20:24], "big")
        return width, height

    def run_cli(self, argv: list[str], stdin_text: str = "") -> tuple[int, str, bytes, str]:
        stdout = _StdoutCapture()
        stderr = io.StringIO()
        stdin = io.StringIO(stdin_text)
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr), mock.patch("sys.stdin", stdin):
            code = cli.main(argv)
        return code, stdout.get_text(), stdout.buffer.getvalue(), stderr.getvalue()

    def test_requires_subcommand(self) -> None:
        code, _out, _png, err = self.run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("E_ARGS", err)
        self.assertIn("subcommand", err)

    def test_compile_file_writes_svg(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "input.svg++"
            src.write_text(
                """
<diag:diagram xmlns=\"http://www.w3.org/2000/svg\" xmlns:diag=\"https://example.com/diag\">
  <diag:flex width=\"160\" padding=\"10\" background-class=\"card\"><text style=\"font-size:12px\">Hello</text></diag:flex>
</diag:diagram>
""".strip()
            )
            code, out, _png, err = self.run_cli(["compile", str(src)])
            self.assertEqual(code, 0, err)
            target = Path(td) / "input.svg"
            self.assertTrue(target.exists())
            self.assertIn("Wrote", out)

    def test_render_svgpp_and_raw_svg(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            svgpp = Path(td) / "diagram.svg++"
            svgpp.write_text(
                """
<diag:diagram xmlns=\"http://www.w3.org/2000/svg\" xmlns:diag=\"https://example.com/diag\">
  <diag:flex width=\"120\" padding=\"8\"><text style=\"font-size:12px\">Ping</text></diag:flex>
</diag:diagram>
""".strip()
            )
            code, _out, _png, err = self.run_cli(["render", str(svgpp)])
            self.assertEqual(code, 0, err)
            self.assertTrue((Path(td) / "diagram.png").exists())

            raw = Path(td) / "raw.svg"
            raw.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect x="0" y="0" width="20" height="20"/></svg>')
            code, _out, _png, err = self.run_cli(["render", str(raw)])
            self.assertEqual(code, 0, err)
            self.assertTrue((Path(td) / "raw.png").exists())

    def test_render_stdout_and_scale(self) -> None:
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect x="0" y="0" width="40" height="20"/></svg>'
        code, _out, png1, err = self.run_cli(["render", "--text", svg, "--stdout"])
        self.assertEqual(code, 0, err)
        w1, h1 = self._png_size(png1)
        self.assertEqual((w1, h1), (40, 20))

        code, _out, png2, err = self.run_cli(["render", "--text", svg, "--stdout", "--scale", "2"])
        self.assertEqual(code, 0, err)
        w2, h2 = self._png_size(png2)
        self.assertEqual((w2, h2), (80, 40))

    def test_focus_missing_id_errors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "raw.svg"
            raw.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect id="ok" x="0" y="0" width="20" height="20"/></svg>')
            code, _out, _png, err = self.run_cli(["render", str(raw), "--focus", "missing"])
            self.assertEqual(code, 4)
            self.assertIn("E_FOCUS_NOT_FOUND", err)

    def test_focus_off_canvas_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "raw.svg"
            raw.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
                '<rect id="far" x="1000" y="1000" width="20" height="20"/></svg>'
            )
            code, _out, _png, err = self.run_cli(["render", str(raw), "--focus", "far", "--padding", "10"])
            self.assertEqual(code, 0, err)
            self.assertTrue((Path(td) / "raw.png").exists())

    def test_templates_precedence_last_shared_wins_and_local_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            t1 = Path(td) / "t1.svg++"
            t2 = Path(td) / "t2.svg++"
            diagram = Path(td) / "diagram.svg++"
            t1.write_text(
                """
<diag:diagram xmlns=\"http://www.w3.org/2000/svg\" xmlns:diag=\"https://example.com/diag\">
  <diag:template name=\"card\"><diag:flex width=\"100\" background-class=\"v1\"><text>one</text></diag:flex></diag:template>
</diag:diagram>
""".strip()
            )
            t2.write_text(
                """
<diag:diagram xmlns=\"http://www.w3.org/2000/svg\" xmlns:diag=\"https://example.com/diag\">
  <diag:template name=\"card\"><diag:flex width=\"100\" background-class=\"v2\"><text>two</text></diag:flex></diag:template>
</diag:diagram>
""".strip()
            )
            diagram.write_text(
                """
<diag:diagram xmlns=\"http://www.w3.org/2000/svg\" xmlns:diag=\"https://example.com/diag\">
  <diag:instance template=\"card\" />
</diag:diagram>
""".strip()
            )

            out_svg = Path(td) / "out.svg"
            code, _out, _png, err = self.run_cli([
                "compile", str(diagram), "-o", str(out_svg), "--templates", str(t1), str(t2)
            ])
            self.assertEqual(code, 0, err)
            text = out_svg.read_text()
            self.assertIn('class="v2"', text)

            local = Path(td) / "local.svg++"
            local.write_text(
                """
<diag:diagram xmlns=\"http://www.w3.org/2000/svg\" xmlns:diag=\"https://example.com/diag\">
  <diag:template name=\"card\"><diag:flex width=\"100\" background-class=\"local\"><text>local</text></diag:flex></diag:template>
  <diag:instance template=\"card\" />
</diag:diagram>
""".strip()
            )
            out_svg2 = Path(td) / "out2.svg"
            code, _out, _png, err = self.run_cli([
                "compile", str(local), "-o", str(out_svg2), "--templates", str(t1), str(t2)
            ])
            self.assertEqual(code, 0, err)
            self.assertIn('class="local"', out_svg2.read_text())

    def test_render_with_templates_for_svgpp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            template = Path(td) / "cards.svg++"
            diagram = Path(td) / "diagram.svg++"
            template.write_text(
                """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://example.com/diag">
  <diag:template name="card"><diag:flex width="120" padding="8"><text>templated</text></diag:flex></diag:template>
</diag:diagram>
""".strip()
            )
            diagram.write_text(
                """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://example.com/diag">
  <diag:instance template="card" />
</diag:diagram>
""".strip()
            )
            code, _out, _png, err = self.run_cli(
                ["render", str(diagram), "--templates", str(template)]
            )
            self.assertEqual(code, 0, err)
            self.assertTrue((Path(td) / "diagram.png").exists())

    def test_accepts_multiple_diag_namespace_uris(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "input.svg++"
            src.write_text(
                """
<diag:diagram xmlns=\"http://www.w3.org/2000/svg\" xmlns:diag=\"https://diagramagic.ai/ns\">
  <diag:flex width=\"120\" padding=\"8\"><text style=\"font-size:12px\">Hello</text></diag:flex>
</diag:diagram>
""".strip()
            )
            code, _out, _png, err = self.run_cli(["compile", str(src)])
            self.assertEqual(code, 0, err)
            self.assertTrue((Path(td) / "input.svg").exists())

    def test_error_format_json_shape(self) -> None:
        code, _out, _png, err = self.run_cli(["--error-format", "json"])
        self.assertEqual(code, 2)
        payload = json.loads(err)
        self.assertEqual(payload["code"], "E_ARGS")
        self.assertFalse(payload["ok"])

    def test_debug_traceback_gate(self) -> None:
        with mock.patch("diagramagic.cli.diagramagic", side_effect=RuntimeError("boom")):
            code, _out, _png, err = self.run_cli(["compile", "--text", "<diag:diagram xmlns='http://www.w3.org/2000/svg' xmlns:diag='x'></diag:diagram>"])
            self.assertEqual(code, 1)
            self.assertNotIn("Traceback", err)

        with mock.patch("diagramagic.cli.diagramagic", side_effect=RuntimeError("boom")):
            code, _out, _png, err = self.run_cli(["--debug", "compile", "--text", "<diag:diagram xmlns='http://www.w3.org/2000/svg' xmlns:diag='x'></diag:diagram>"])
            self.assertEqual(code, 1)
            self.assertIn("Traceback", err)

    def test_g_bbox_participates_in_flex_height(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "g.svg++"
            src.write_text(
                """
<diag:diagram xmlns=\"http://www.w3.org/2000/svg\" xmlns:diag=\"https://example.com/diag\">
  <diag:flex width=\"260\" padding=\"10\" gap=\"8\" background-class=\"box\">
    <g transform=\"scale(0.5)\">
      <rect x=\"0\" y=\"0\" width=\"300\" height=\"200\" fill=\"none\" stroke=\"#111\"/>
    </g>
    <text style=\"font-size:12px\">After group</text>
  </diag:flex>
</diag:diagram>
""".strip()
            )
            out = Path(td) / "g.svg"
            code, _stdout, _png, err = self.run_cli(["compile", str(src), "-o", str(out)])
            self.assertEqual(code, 0, err)
            root = ET.fromstring(out.read_text())
            rects = root.findall("{http://www.w3.org/2000/svg}rect")
            # first rect is diagram background if any; the flex background should be present and tall enough
            heights = [float(r.get("height", "0")) for r in rects]
            self.assertTrue(any(h > 110 for h in heights), heights)

    def test_arrow_emits_line_and_label(self) -> None:
        src = """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns">
  <diag:flex id="a" x="20" y="20" width="120" padding="8"><text style="font-size:12px">A</text></diag:flex>
  <diag:flex id="b" x="260" y="20" width="120" padding="8"><text style="font-size:12px">B</text></diag:flex>
  <diag:arrow from="a" to="b" label="queries" stroke="#E67E22"/>
</diag:diagram>
""".strip()
        code, out, _png, err = self.run_cli(["compile", "--text", src, "--stdout"])
        self.assertEqual(code, 0, err)
        root = ET.fromstring(out)
        lines = root.findall(".//{http://www.w3.org/2000/svg}line")
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].get("stroke"), "#E67E22")
        self.assertTrue((lines[0].get("marker-end") or "").startswith("url(#diag-arrow-default"))
        labels = root.findall(".//{http://www.w3.org/2000/svg}text")
        self.assertTrue(any((t.text or "").strip() == "queries" for t in labels))

    def test_arrow_edge_overrides_are_rejected(self) -> None:
        src = """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns">
  <diag:flex id="top" x="40" y="20" width="120" padding="8"><text style="font-size:12px">Top</text></diag:flex>
  <diag:flex id="bottom" x="40" y="220" width="120" padding="8"><text style="font-size:12px">Bottom</text></diag:flex>
  <diag:arrow from="top" to="bottom" from-edge="bottom" to-edge="top" label="down"/>
</diag:diagram>
""".strip()
        code, _out, _png, err = self.run_cli(["compile", "--text", src])
        self.assertEqual(code, 3)
        self.assertIn("E_SVGPP_SEMANTIC", err)

    def test_arrow_marker_collision_policy(self) -> None:
        src = """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns">
  <defs>
    <marker id="diag-arrow-default" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 z" fill="#000"/>
    </marker>
  </defs>
  <diag:flex id="a" x="20" y="20" width="120" padding="8"><text style="font-size:12px">A</text></diag:flex>
  <diag:flex id="b" x="260" y="20" width="120" padding="8"><text style="font-size:12px">B</text></diag:flex>
  <diag:arrow from="a" to="b"/>
</diag:diagram>
""".strip()
        code, out, _png, err = self.run_cli(["compile", "--text", src, "--stdout"])
        self.assertEqual(code, 0, err)
        root = ET.fromstring(out)
        line = root.find(".//{http://www.w3.org/2000/svg}line")
        self.assertEqual(line.get("marker-end"), "url(#diag-arrow-default-1)")
        markers = [m.get("id") for m in root.findall(".//{http://www.w3.org/2000/svg}marker")]
        self.assertIn("diag-arrow-default", markers)
        self.assertIn("diag-arrow-default-1", markers)

    def test_arrow_semantic_errors(self) -> None:
        src = """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns">
  <diag:flex id="a" x="20" y="20" width="120" padding="8"><text style="font-size:12px">A</text></diag:flex>
  <diag:arrow from="missing" to="a"/>
</diag:diagram>
""".strip()
        code, _out, _png, err = self.run_cli(["compile", "--text", src])
        self.assertEqual(code, 3)
        self.assertIn("E_SVGPP_SEMANTIC", err)

        bad_edge = """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns">
  <diag:flex id="a" x="20" y="20" width="120" padding="8"><text style="font-size:12px">A</text></diag:flex>
  <diag:flex id="b" x="260" y="20" width="120" padding="8"><text style="font-size:12px">B</text></diag:flex>
  <diag:arrow from="a" to="b" from-edge="diagonal"/>
</diag:diagram>
""".strip()
        code, _out, _png, err = self.run_cli(["compile", "--text", bad_edge])
        self.assertEqual(code, 3)
        self.assertIn("E_SVGPP_SEMANTIC", err)

    def test_arrow_contributes_to_bounds(self) -> None:
        no_arrow = """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns">
  <diag:flex id="a" x="20" y="20" width="120" padding="8"><text style="font-size:12px">A</text></diag:flex>
  <diag:flex id="b" x="260" y="20" width="120" padding="8"><text style="font-size:12px">B</text></diag:flex>
</diag:diagram>
""".strip()
        with_arrow = """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns">
  <diag:flex id="a" x="20" y="20" width="120" padding="8"><text style="font-size:12px">A</text></diag:flex>
  <diag:flex id="b" x="260" y="20" width="120" padding="8"><text style="font-size:12px">B</text></diag:flex>
  <diag:arrow from="a" to="b" stroke-width="24"/>
</diag:diagram>
""".strip()
        code, out1, _png, err = self.run_cli(["compile", "--text", no_arrow, "--stdout"])
        self.assertEqual(code, 0, err)
        code, out2, _png, err = self.run_cli(["compile", "--text", with_arrow, "--stdout"])
        self.assertEqual(code, 0, err)
        root1 = ET.fromstring(out1)
        root2 = ET.fromstring(out2)
        h1 = float(root1.get("height"))
        h2 = float(root2.get("height"))
        self.assertGreater(h2, h1)

    def test_arrow_auto_uses_centerline_intersection(self) -> None:
        src = """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns">
  <rect id="r1" x="0" y="0" width="100" height="100" fill="none" stroke="#111"/>
  <rect id="r2" x="200" y="0" width="100" height="100" fill="none" stroke="#111"/>
  <diag:arrow from="r1" to="r2" stroke="#111"/>
</diag:diagram>
""".strip()
        code, out, _png, err = self.run_cli(["compile", "--text", src, "--stdout"])
        self.assertEqual(code, 0, err)
        root = ET.fromstring(out)
        line = root.find(".//{http://www.w3.org/2000/svg}line")
        self.assertIsNotNone(line)
        self.assertAlmostEqual(float(line.get("x1")), 100.5, delta=0.01)
        self.assertAlmostEqual(float(line.get("y1")), 50.0, delta=0.01)
        self.assertAlmostEqual(float(line.get("x2")), 199.5, delta=0.01)
        self.assertAlmostEqual(float(line.get("y2")), 50.0, delta=0.01)

    def test_arrow_label_is_offset_and_not_upside_down(self) -> None:
        src = """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns">
  <rect id="a" x="20" y="20" width="120" height="40" fill="none" stroke="#111"/>
  <rect id="b" x="260" y="20" width="120" height="40" fill="none" stroke="#111"/>
  <diag:arrow from="a" to="b" label="L2R"/>
  <diag:arrow from="b" to="a" label="R2L" stroke="#c2410c"/>
</diag:diagram>
""".strip()
        code, out, _png, err = self.run_cli(["compile", "--text", src, "--stdout"])
        self.assertEqual(code, 0, err)
        root = ET.fromstring(out)
        labels = { (t.text or "").strip(): t for t in root.findall(".//{http://www.w3.org/2000/svg}text") if (t.text or "").strip() in {"L2R", "R2L"} }
        self.assertEqual(set(labels.keys()), {"L2R", "R2L"})

        # Label should be offset above the connecting line (line midpoint y is 40).
        self.assertLess(float(labels["L2R"].get("y")), 40.0)
        self.assertLess(float(labels["R2L"].get("y")), 40.0)

        # Reversed arrow label should remain readable (no upside-down ~180deg rotation).
        transform = labels["R2L"].get("transform", "")
        if transform.startswith("rotate("):
            angle_str = transform[len("rotate("):].split(" ", 1)[0]
            angle = float(angle_str)
            self.assertLessEqual(abs(angle), 90.0)

    def test_arrow_inside_transformed_group_uses_local_coords(self) -> None:
        src = """
<diag:diagram xmlns="http://www.w3.org/2000/svg" xmlns:diag="https://diagramagic.ai/ns">
  <g transform="scale(0.4)">
    <rect id="a" x="325" y="215" width="120" height="45" fill="none" stroke="#111"/>
    <rect id="b" x="325" y="290" width="120" height="45" fill="none" stroke="#111"/>
    <diag:arrow from="a" to="b" stroke="#555" stroke-width="1.2"/>
  </g>
</diag:diagram>
""".strip()
        code, out, _png, err = self.run_cli(["compile", "--text", src, "--stdout"])
        self.assertEqual(code, 0, err)
        root = ET.fromstring(out)

        groups = root.findall("{http://www.w3.org/2000/svg}g")
        scaled = next((g for g in groups if g.get("transform") == "scale(0.4)"), None)
        self.assertIsNotNone(scaled)

        line = scaled.find(".//{http://www.w3.org/2000/svg}line")
        self.assertIsNotNone(line)
        self.assertEqual(line.get("stroke"), "#555")
        self.assertEqual(line.get("stroke-width"), "1.2")
        self.assertAlmostEqual(float(line.get("x1")), 385.0, delta=0.01)
        self.assertAlmostEqual(float(line.get("y1")), 260.5, delta=0.01)
        self.assertAlmostEqual(float(line.get("x2")), 385.0, delta=0.01)
        self.assertAlmostEqual(float(line.get("y2")), 289.5, delta=0.01)

        top_level_lines = [child for child in list(root) if child.tag == "{http://www.w3.org/2000/svg}line"]
        self.assertEqual(top_level_lines, [])


if __name__ == "__main__":
    unittest.main()
