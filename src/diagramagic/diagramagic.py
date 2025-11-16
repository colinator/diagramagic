"""svg++ to SVG converter for the minimal spec in PROJECTSPEC.md."""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from PIL import ImageFont
except ImportError:  # pragma: no cover - Pillow required via requirements
    ImageFont = None

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

DEFAULT_FONT_FAMILY = "sans-serif"
GENERIC_FONT_FALLBACKS = {
    "sans-serif": ["Helvetica", "Arial", "Liberation Sans", "DejaVu Sans"],
    "serif": ["Times New Roman", "Times", "Liberation Serif", "DejaVu Serif"],
    "monospace": [
        "Courier New",
        "Courier",
        "Liberation Mono",
        "DejaVu Sans Mono",
    ],
}


class _TextMeasurer:
    """Caches Pillow fonts and exposes width/line height helpers."""

    FONT_DIRS = [
        Path("/System/Library/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/Library/Fonts"),
        Path("~/Library/Fonts").expanduser(),
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path("C:/Windows/Fonts"),
    ]

    def __init__(self) -> None:
        self._font_cache: dict[Tuple[str, int], Optional["ImageFont.FreeTypeFont"]] = {}
        self._font_paths: dict[str, Optional[str]] = {}

    def font(
        self, size: float, family: Optional[str], explicit_path: Optional[str]
    ) -> Optional["ImageFont.ImageFont"]:
        if ImageFont is None:
            return None
        key_size = max(1, int(round(size)))
        if family is None:
            family = DEFAULT_FONT_FAMILY
        key_family = (explicit_path or family).lower()
        cache_key = (key_family, key_size)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        font: Optional["ImageFont.ImageFont"] = None
        candidates: List[str] = []
        if explicit_path:
            candidates.append(explicit_path)
        if family:
            family_key = family.lower()
            mapped_families = GENERIC_FONT_FALLBACKS.get(family_key, [family])
            for fam in mapped_families:
                resolved = self._locate_font(fam)
                if resolved:
                    candidates.append(resolved)
        candidates.append("DejaVuSans.ttf")

        for candidate in candidates:
            try:
                path, index = self._parse_font_candidate(candidate)
                font = ImageFont.truetype(path, key_size, index=index)
                break
            except OSError:
                continue
        if font is None:
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None

        self._font_cache[cache_key] = font
        return font

    def measure(
        self, text: str, size: float, family: Optional[str], explicit_path: Optional[str]
    ) -> float:
        font = self.font(size, family, explicit_path)
        if font is None:
            return _heuristic_width(text, size)
        try:
            length = font.getlength(text)
        except AttributeError:
            length = font.getsize(text)[0]
        return float(length)

    def line_height(
        self, size: float, family: Optional[str], explicit_path: Optional[str]
    ) -> float:
        _, _, line_height = self.metrics(size, family, explicit_path)
        return line_height

    def metrics(
        self, size: float, family: Optional[str], explicit_path: Optional[str]
    ) -> Tuple[float, float, float]:
        font = self.font(size, family, explicit_path)
        if font is None:
            ascent = 0.8 * size
            descent = 0.2 * size
            return ascent, descent, ascent + descent
        try:
            ascent, descent = font.getmetrics()
            ascent = float(ascent)
            descent = float(descent)
            try:
                internal_height_units = font.font.height
                units_per_em = font.font.units_per_EM
                if units_per_em:
                    internal_height = internal_height_units * (size / units_per_em)
                else:
                    internal_height = None
            except Exception:
                internal_height = None
            if not internal_height or internal_height <= 0:
                internal_height = ascent + descent
            line_height = float(internal_height)
            return ascent, descent, line_height
        except Exception:
            ascent = 0.8 * size
            descent = 0.2 * size
            return ascent, descent, ascent + descent

    def _locate_font(self, family: str) -> Optional[str]:
        key = family.lower()
        if key in self._font_paths:
            return self._font_paths[key]
        normalized = re.sub(r"[^a-z0-9]+", "", family, flags=re.IGNORECASE).lower()
        aliases = {normalized, normalized + "mt", normalized + "psmt"}
        best_match: Optional[Tuple[int, str]] = None
        for directory in self.FONT_DIRS:
            if not directory.exists():
                continue
            try:
                for glob in ("*.ttf", "*.ttc"):
                    for path in directory.rglob(glob):
                        stem = re.sub(
                            r"[^a-z0-9]+", "", path.stem, flags=re.IGNORECASE
                        ).lower()
                        if not normalized:
                            continue
                        match_score = None
                        if stem in aliases:
                            match_score = 0
                        elif stem.startswith(normalized):
                            match_score = 1
                        elif normalized in stem:
                            match_score = 2
                        if match_score is None:
                            continue
                        candidate = (
                            str(path)
                            if glob == "*.ttf"
                            else f"{path};0"
                        )
                        if (
                            best_match is None
                            or match_score < best_match[0]
                        ):
                            best_match = (match_score, candidate)
            except Exception:
                continue
        if best_match:
            resolved = best_match[1]
            self._font_paths[key] = resolved
            return resolved
        self._font_paths[key] = None
        return None

    @staticmethod
    def _parse_font_candidate(candidate: str) -> Tuple[str, int]:
        if ";" in candidate:
            path, idx = candidate.split(";", 1)
            try:
                return path, int(idx)
            except ValueError:
                return path, 0
        return candidate, 0


_TEXT_MEASURER = _TextMeasurer()


def _q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"


def diagramagic(svgpp_source: str) -> str:
    """Convert svg++ markup to plain SVG."""
    root = ET.fromstring(svgpp_source)
    diag_ns = _namespace_of(root.tag)
    if not diag_ns:
        raise ValueError("Input does not contain a diag namespace root element")

    templates = _collect_templates(root, diag_ns)
    if templates:
        _expand_instances_in_tree(root, diag_ns, templates)

    svg_root = ET.Element(_q("svg"))
    _copy_svg_attributes(root, svg_root, diag_ns)

    root_font_family, root_font_path = _font_family_info(root, diag_ns)
    combined_bbox: Optional[Tuple[float, float, float, float]] = None
    for child in root:
        rendered, _, _, bbox = _render_node(
            child,
            diag_ns,
            wrap_width_hint=None,
            inherited_family=root_font_family,
            inherited_path=root_font_path,
        )
        if rendered is not None:
            svg_root.append(rendered)
        if bbox is not None:
            combined_bbox = _merge_bbox(combined_bbox, bbox)

    _apply_root_bounds(root, svg_root, combined_bbox)

    return _pretty_xml(svg_root)


def _render_node(
    node: ET.Element,
    diag_ns: str,
    wrap_width_hint: Optional[float],
    inherited_family: Optional[str],
    inherited_path: Optional[str],
) -> Tuple[
    Optional[ET.Element],
    float,
    float,
    Optional[Tuple[float, float, float, float]],
]:
    if node.tag is ET.Comment:
        return None, 0.0, 0.0, None

    ns = _namespace_of(node.tag)
    local = _local_name(node.tag)

    if ns == diag_ns and local == "flex":
        return _render_flex(
            node,
            diag_ns,
            inherited_family=inherited_family,
            inherited_path=inherited_path,
            wrap_width_hint=wrap_width_hint,
        )
    if ns == diag_ns:
        return None, 0.0, 0.0, None

    if local == "text":
        return _render_text(
            node,
            diag_ns,
            wrap_width_hint,
            inherited_family=inherited_family,
            inherited_path=inherited_path,
        )

    rendered = _render_generic_node(
        node,
        diag_ns,
        wrap_width_hint,
        inherited_family,
        inherited_path,
    )
    width, height, bbox = _measure_generic(node)
    return rendered, width, height, bbox


def _render_flex(
    node: ET.Element,
    diag_ns: str,
    inherited_family: Optional[str],
    inherited_path: Optional[str],
    wrap_width_hint: Optional[float],
) -> Tuple[ET.Element, float, float, Tuple[float, float, float, float]]:
    direction = node.get("direction", "column").strip().lower()
    gap = _parse_length(node.get("gap"), 0.0)
    padding = _parse_length(node.get("padding"), 0.0)
    width_attr = _parse_length(node.get("width"), None)
    target_total_width = width_attr if width_attr is not None else wrap_width_hint
    x = _parse_length(node.get("x"), 0.0)
    y = _parse_length(node.get("y"), 0.0)
    bg_class = node.get("background-class")
    bg_style = node.get("background-style")

    local_family, local_path = _font_family_info(node, diag_ns)
    combined_family = local_family or inherited_family
    combined_path = local_path or inherited_path

    child_entries: List[Tuple[ET.Element, float, float]] = []
    child_wrap_hint = None
    if target_total_width is not None:
        child_wrap_hint = max(target_total_width - 2 * padding, 0.0)
    for child in list(node):
        rendered, w, h, _ = _render_node(
            child,
            diag_ns,
            wrap_width_hint=child_wrap_hint,
            inherited_family=combined_family,
            inherited_path=combined_path,
        )
        if rendered is not None:
            child_entries.append((rendered, w, h))

    g = ET.Element(_q("g"), {"transform": f"translate({_fmt(x)}, {_fmt(y)})"})

    if direction == "row":
        width, height = _layout_row(
            g, child_entries, target_total_width, padding, gap
        )
    else:
        width, height = _layout_column(
            g, child_entries, target_total_width, padding, gap
        )

    if bg_class or bg_style:
        rect_attrs = {
            "x": "0",
            "y": "0",
            "width": _fmt(width),
            "height": _fmt(height),
        }
        if bg_class:
            rect_attrs["class"] = bg_class
        if bg_style:
            rect_attrs["style"] = bg_style
        g.insert(0, ET.Element(_q("rect"), rect_attrs))

    bbox = (x, y, x + width, y + height)
    return g, width, height, bbox


def _layout_column(
    container: ET.Element,
    children: List[Tuple[ET.Element, float, float]],
    target_total_width: Optional[float],
    padding: float,
    gap: float,
) -> Tuple[float, float]:
    max_child_width = max((w for _, w, _ in children), default=0.0)
    interior_target = (
        max(target_total_width - 2 * padding, 0.0)
        if target_total_width is not None
        else None
    )
    if interior_target is not None:
        interior_width = max(interior_target, max_child_width)
    else:
        interior_width = max_child_width
    y_cursor = padding
    for child, child_width, child_height in children:
        wrapper = ET.Element(
            _q("g"), {"transform": f"translate({_fmt(padding)}, {_fmt(y_cursor)})"}
        )
        wrapper.append(child)
        container.append(wrapper)
        y_cursor += child_height + gap
    if children:
        y_cursor -= gap
    interior_height = max(y_cursor - padding, 0.0)
    total_height = interior_height + 2 * padding
    total_width = interior_width + 2 * padding
    if target_total_width is not None:
        total_width = max(total_width, target_total_width)
    return total_width, total_height


def _layout_row(
    container: ET.Element,
    children: List[Tuple[ET.Element, float, float]],
    target_total_width: Optional[float],
    padding: float,
    gap: float,
) -> Tuple[float, float]:
    natural_width = sum((w for _, w, _ in children))
    if children:
        natural_width += gap * (len(children) - 1)
    interior_target = (
        max(target_total_width - 2 * padding, 0.0)
        if target_total_width is not None
        else None
    )
    if interior_target is not None:
        interior_width = max(interior_target, natural_width)
    else:
        interior_width = natural_width
    max_height = max((h for _, _, h in children), default=0.0)
    x_cursor = padding
    for child, child_width, child_height in children:
        wrapper = ET.Element(
            _q("g"), {"transform": f"translate({_fmt(x_cursor)}, {_fmt(padding)})"}
        )
        wrapper.append(child)
        container.append(wrapper)
        x_cursor += child_width + gap
    total_width = interior_width + 2 * padding
    if target_total_width is not None:
        total_width = max(total_width, target_total_width)
    total_height = max_height + 2 * padding
    return total_width, total_height


def _render_text(
    node: ET.Element,
    diag_ns: str,
    wrap_width_hint: Optional[float],
    inherited_family: Optional[str],
    inherited_path: Optional[str],
) -> Tuple[
    ET.Element,
    float,
    float,
    Tuple[float, float, float, float],
]:
    wrap = node.get(_qual(diag_ns, "wrap"), "false").lower() == "true"
    max_width = node.get(_qual(diag_ns, "max-width"))
    if max_width is not None:
        wrap_width_hint = _parse_length(max_width, wrap_width_hint)

    font_size = _infer_font_size(node)
    font_family, font_path = _font_family_info(node, diag_ns)
    if not font_family:
        font_family = inherited_family
    if not font_path:
        font_path = inherited_path
    if not font_family:
        font_family = DEFAULT_FONT_FAMILY
    ascent, descent, line_height = _TEXT_MEASURER.metrics(
        font_size, font_family, font_path
    )

    if wrap and wrap_width_hint is not None:
        text_content = _gather_text(node)
        lines = _wrap_lines(
            text_content, wrap_width_hint, font_size, font_family, font_path
        )
        new_text = ET.Element(node.tag, _filtered_attrib(node.attrib, diag_ns))
        _apply_font_attribute(new_text, font_family)
        _ensure_text_baseline(new_text, ascent)
        new_text.text = None
        base_x = node.get("x", "0")
        first_tspan = True
        max_line_width = 0.0
        for line in lines:
            line_width = _estimate_text_width(line, font_size, font_family, font_path)
            max_line_width = max(max_line_width, line_width)
            attrs = {"x": base_x}
            attrs["dy"] = "0" if first_tspan else "1.2em"
            tspan = ET.SubElement(new_text, _q("tspan"), attrs)
            tspan.text = line
            first_tspan = False
        line_count = max(len(lines), 1)
        height = ascent + descent + (line_count - 1) * line_height
        width = wrap_width_hint if wrap_width_hint is not None else max_line_width
        bbox = _text_bbox(node, width, height, ascent)
        return new_text, width, height, bbox

    new_text = _clone_without_diag(node, diag_ns)
    _apply_font_attribute(new_text, font_family)
    _ensure_text_baseline(new_text, ascent)
    content = _gather_text(node)
    width = _estimate_text_width(content, font_size, font_family, font_path)
    line_count = 1
    height = ascent + descent + (line_count - 1) * line_height
    bbox = _text_bbox(node, width, height, ascent)
    return new_text, width, height, bbox


def _wrap_lines(
    text: str,
    width_limit: float,
    font_size: float,
    font_family: Optional[str],
    font_path: Optional[str],
) -> List[str]:
    words = re.split(r"(\s+)", text.strip())
    lines: List[str] = []
    current = ""
    for chunk in words:
        if not chunk:
            continue
        candidate = (current + chunk) if current else chunk
        if (
            _estimate_text_width(candidate.strip(), font_size, font_family, font_path)
            <= width_limit
        ):
            current = candidate
            continue
        if current:
            lines.append(current.strip())
        current = chunk.strip()
    if current:
        lines.append(current.strip())
    return lines or [""]


def _text_bbox(
    node: ET.Element, width: float, height: float, ascent: float
) -> Tuple[float, float, float, float]:
    x_val = _parse_length(node.get("x"), 0.0)
    x = x_val if x_val is not None else 0.0
    y_val = _parse_length(node.get("y"), 0.0)
    baseline = y_val if y_val is not None else 0.0
    top = baseline - ascent
    return x, top, x + width, top + height


def _measure_generic(
    node: ET.Element,
) -> Tuple[float, float, Optional[Tuple[float, float, float, float]]]:
    local = _local_name(node.tag)
    if local == "rect":
        width = _parse_length(node.get("width"), 0.0)
        height = _parse_length(node.get("height"), 0.0)
        x = _parse_length(node.get("x"), 0.0) or 0.0
        y = _parse_length(node.get("y"), 0.0) or 0.0
        return width, height, (x, y, x + width, y + height)
    if local == "circle":
        r = _parse_length(node.get("r"), 0.0)
        cx = _parse_length(node.get("cx"), 0.0) or 0.0
        cy = _parse_length(node.get("cy"), 0.0) or 0.0
        return 2 * r, 2 * r, (cx - r, cy - r, cx + r, cy + r)
    if local == "ellipse":
        rx = _parse_length(node.get("rx"), 0.0)
        ry = _parse_length(node.get("ry"), 0.0)
        cx = _parse_length(node.get("cx"), 0.0) or 0.0
        cy = _parse_length(node.get("cy"), 0.0) or 0.0
        return 2 * rx, 2 * ry, (cx - rx, cy - ry, cx + rx, cy + ry)
    if local == "line":
        x1 = _parse_length(node.get("x1"), 0.0)
        x2 = _parse_length(node.get("x2"), 0.0)
        y1 = _parse_length(node.get("y1"), 0.0)
        y2 = _parse_length(node.get("y2"), 0.0)
        min_x = min(x1, x2)
        max_x = max(x1, x2)
        min_y = min(y1, y2)
        max_y = max(y1, y2)
        return abs(x2 - x1), abs(y2 - y1), (min_x, min_y, max_x, max_y)
    return 0.0, 0.0, None


def _collect_templates(root: ET.Element, diag_ns: str) -> Dict[str, List[ET.Element]]:
    templates: Dict[str, List[ET.Element]] = {}
    new_children: List[ET.Element] = []
    for child in list(root):
        ns = _namespace_of(child.tag)
        local = _local_name(child.tag)
        if ns == diag_ns and local == "template":
            name = child.get("name")
            if not name:
                continue
            templates[name] = [deepcopy(elem) for elem in list(child)]
        else:
            new_children.append(child)
    root[:] = new_children
    return templates


def _expand_instances_in_tree(
    node: ET.Element,
    diag_ns: str,
    templates: Dict[str, List[ET.Element]],
) -> None:
    new_children: List[ET.Element] = []
    for child in list(node):
        ns = _namespace_of(child.tag)
        local = _local_name(child.tag)
        if ns == diag_ns and local == "instance":
            expanded = _instantiate_template(child, diag_ns, templates)
            for elem in expanded:
                _expand_instances_in_tree(elem, diag_ns, templates)
                new_children.append(elem)
        else:
            _expand_instances_in_tree(child, diag_ns, templates)
            new_children.append(child)
    node[:] = new_children


def _instantiate_template(
    instance: ET.Element,
    diag_ns: str,
    templates: Dict[str, List[ET.Element]],
) -> List[ET.Element]:
    template_name = instance.get("template")
    if not template_name:
        return []
    blueprint = templates.get(template_name)
    if not blueprint:
        return []
    params = _gather_template_params(instance, diag_ns)
    clones = [deepcopy(elem) for elem in blueprint]
    for clone in clones:
        for attr_key, attr_value in instance.attrib.items():
            if attr_key == "template":
                continue
            clone.set(attr_key, attr_value)
        _apply_template_params(clone, params, diag_ns)
    return clones


def _gather_template_params(node: ET.Element, diag_ns: str) -> Dict[str, str]:
    params: Dict[str, str] = {}
    for child in list(node):
        ns = _namespace_of(child.tag)
        local = _local_name(child.tag)
        if ns == diag_ns and local == "param":
            name = child.get("name")
            if not name:
                continue
            value = "".join(child.itertext())
            params[name] = value.strip()
    return params


def _apply_template_params(
    node: ET.Element, params: Dict[str, str], diag_ns: str
) -> None:
    children = list(node)
    for idx, child in enumerate(children):
        ns = _namespace_of(child.tag)
        local = _local_name(child.tag)
        if ns == diag_ns and local == "slot":
            name = child.get("name")
            value = params.get(name, "")
            parent = node
            parent.remove(child)
            if idx == 0:
                parent.text = (parent.text or "") + value
            else:
                prev = children[idx - 1]
                prev.tail = (prev.tail or "") + value
            continue
        _apply_template_params(child, params, diag_ns)


def _merge_bbox(
    current: Optional[Tuple[float, float, float, float]],
    new: Optional[Tuple[float, float, float, float]],
) -> Optional[Tuple[float, float, float, float]]:
    if new is None:
        return current
    if current is None:
        return new
    return (
        min(current[0], new[0]),
        min(current[1], new[1]),
        max(current[2], new[2]),
        max(current[3], new[3]),
    )


def _apply_root_bounds(
    src_root: ET.Element,
    svg_root: ET.Element,
    bbox: Optional[Tuple[float, float, float, float]],
) -> None:
    if bbox is None:
        return
    raw_min_x, raw_min_y, raw_max_x, raw_max_y = bbox
    min_x = min(0.0, raw_min_x)
    min_y = min(0.0, raw_min_y)
    max_x = max(0.0, raw_max_x)
    max_y = max(0.0, raw_max_y)
    width_needed = max(max_x - min_x, 0.0)
    height_needed = max(max_y - min_y, 0.0)
    if width_needed == 0.0 and height_needed == 0.0:
        return
    svg_root.set(
        "viewBox",
        f"{_fmt(min_x)} {_fmt(min_y)} {_fmt(width_needed)} {_fmt(height_needed)}",
    )
    _ensure_dimension(svg_root, "width", width_needed, src_root.get("width"))
    _ensure_dimension(svg_root, "height", height_needed, src_root.get("height"))


def _ensure_dimension(
    svg_root: ET.Element, attr: str, needed: float, original_value: Optional[str]
) -> None:
    if needed <= 0 and original_value:
        svg_root.set(attr, original_value)
        return
    numeric = _parse_length(original_value, None) if original_value else None
    if original_value is not None and numeric is not None and numeric >= needed:
        svg_root.set(attr, original_value)
    else:
        svg_root.set(attr, _fmt(max(needed, 0.0)))


def _clone_without_diag(node: ET.Element, diag_ns: str) -> ET.Element:
    clone = deepcopy(node)
    for elem in clone.iter():
        keys = [k for k in elem.attrib if _namespace_of(k) == diag_ns]
        for key in keys:
            del elem.attrib[key]
    return clone


def _filtered_attrib(attrib, diag_ns: str):
    return {k: v for k, v in attrib.items() if _namespace_of(k) != diag_ns}


def _render_generic_node(
    node: ET.Element,
    diag_ns: str,
    wrap_width_hint: Optional[float],
    inherited_family: Optional[str],
    inherited_path: Optional[str],
) -> ET.Element:
    clone = ET.Element(node.tag, _filtered_attrib(node.attrib, diag_ns))
    if node.text:
        clone.text = node.text
    for child in list(node):
        child_rendered, _, _, _ = _render_node(
            child,
            diag_ns,
            wrap_width_hint=wrap_width_hint,
            inherited_family=inherited_family,
            inherited_path=inherited_path,
        )
        if child_rendered is not None:
            clone.append(child_rendered)
            child_rendered.tail = child.tail
    return clone


def _pretty_xml(element: ET.Element) -> str:
    try:
        for text_node in element.iter(_q("text")):
            if text_node.text:
                text_node.text = text_node.text.strip()
    except Exception:
        pass
    try:
        ET.indent(element, space="  ")
    except AttributeError:
        # Python <3.9 doesn't have ET.indent; fall back to raw serialization.
        pass
    return ET.tostring(element, encoding="unicode")


def _apply_font_attribute(elem: ET.Element, font_family: Optional[str]) -> None:
    if not font_family:
        return
    if "font-family" not in elem.attrib:
        elem.set("font-family", font_family)


def _ensure_text_baseline(elem: ET.Element, ascent: float) -> None:
    if elem.get("y") is None:
        elem.set("y", _fmt(ascent))


def _infer_font_size(node: ET.Element) -> float:
    if "font-size" in node.attrib:
        return _parse_length(node.attrib["font-size"], 16.0)
    style = node.get("style")
    if style:
        match = re.search(r"font-size:\s*([0-9.]+)", style)
        if match:
            return float(match.group(1))
    return 16.0


def _font_family_info(
    node: ET.Element, diag_ns: str
) -> Tuple[Optional[str], Optional[str]]:
    diag_font_path = node.get(_qual(diag_ns, "font-path"))
    if diag_font_path:
        diag_font_path = str(Path(diag_font_path).expanduser())
    diag_family = node.get(_qual(diag_ns, "font-family"))
    family = node.get("font-family") or diag_family
    if not family:
        style = node.get("style")
        if style:
            match = re.search(r"font-family:\s*([^;]+)", style)
            if match:
                family = match.group(1)
    if family:
        family = _strip_quotes(family.strip())
    return family, diag_font_path


def _gather_text(node: ET.Element) -> str:
    return "".join(node.itertext()).strip()


def _estimate_text_width(
    text: str,
    font_size: float,
    font_family: Optional[str],
    font_path: Optional[str],
) -> float:
    return _TEXT_MEASURER.measure(text, font_size, font_family, font_path)


def _heuristic_width(text: str, font_size: float) -> float:
    width = 0.0
    for ch in text:
        if ch.isspace():
            width += font_size * 0.33
        elif ch in "il":
            width += font_size * 0.3
        elif ch in "mwMW@#":
            width += font_size * 0.9
        else:
            width += font_size * 0.6
    return width


def _strip_quotes(value: str) -> str:
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _parse_length(value: Optional[str], default: Optional[float]) -> Optional[float]:
    if value is None:
        return default
    match = re.match(r"^-?\d+(?:\.\d+)?", value)
    if match:
        return float(match.group(0))
    return default


def _fmt(value: float) -> str:
    if math.isclose(value, round(value)):
        return str(int(round(value)))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _copy_svg_attributes(src: ET.Element, dest: ET.Element, diag_ns: str) -> None:
    for key, value in src.attrib.items():
        if _namespace_of(key) == diag_ns:
            continue
        dest.set(_local_name(key), value)


def _namespace_of(tag: str) -> Optional[str]:
    if tag is None:
        return None
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return None


def _local_name(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _qual(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


__all__ = ["diagramagic"]
