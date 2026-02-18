"""svg++ to SVG converter for the minimal spec in PROJECTSPEC.md."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import shlex
import shutil
import subprocess
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from diagramagic._diagramagic_resvg import measure_svg as _measure_svg
except Exception as exc:  # pragma: no cover - native dependency required
    raise RuntimeError(
        "diagramagic requires the bundled resvg extension; ensure Cargo is available "
        "and reinstall the package."
    ) from exc

try:  # pragma: no cover - optional while native module is being upgraded
    from diagramagic._diagramagic_resvg import render_svg as _render_svg
except Exception:  # pragma: no cover - fallback path
    _render_svg = None

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

GRAPH_MAX_NODES = 2000
GRAPH_MAX_EDGES = 8000


class FocusNotFoundError(ValueError):
    """Raised when a requested focus id does not exist in rendered SVG."""


class DiagramagicSemanticError(ValueError):
    """Structured semantic error with stable code for CLI mapping."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return self.message


@dataclass
class _ArrowSpec:
    from_id: str
    to_id: str
    slot_id: str
    label: Optional[str]
    label_size: float
    label_fill: str
    passthrough_attrs: Dict[str, str]


@dataclass
class _AnchorSpec:
    anchor_id: str
    x: Optional[float]
    y: Optional[float]
    relative_to: Optional[str]
    side: str
    offset_x: float
    offset_y: float


@dataclass
class _GraphNodeSpec:
    node_id: str
    source_node: ET.Element
    rendered: ET.Element
    width: float
    height: float


@dataclass
class _GraphEdgeSpec:
    from_id: str
    to_id: str
    label: Optional[str]
    label_size: float
    label_fill: str
    passthrough_attrs: Dict[str, str]


@dataclass
class _GraphvizEdgeLayout:
    points: List[Tuple[float, float]]
    label_pos: Optional[Tuple[float, float]]


@dataclass
class _GraphvizLayoutResult:
    node_positions: Dict[str, Tuple[float, float]]
    edge_layouts: List[_GraphvizEdgeLayout]


@dataclass
class _GraphExpansionState:
    non_graph_ids: Set[str]
    taken_ids: Set[str]
    seen_graph_node_ids: Set[str]
    graph_counter: int = 0


@dataclass
class _ClassStyleRule:
    class_name: str
    declarations: Dict[str, str]


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


def diagramagic(
    svgpp_source: str,
    shared_template_sources: Optional[List[str]] = None,
    *,
    source_path: Optional[Path] = None,
    _include_stack: Optional[List[Path]] = None,
    _include_depth: int = 0,
    _max_include_depth: int = 10,
) -> str:
    """Convert svg++ markup to plain SVG."""
    try:
        root = ET.fromstring(svgpp_source)
    except ET.ParseError as exc:
        line, column = getattr(exc, "position", (None, None))
        location = (
            f" at line {line}, column {column}" if line is not None and column is not None else ""
        )
        raise ValueError(
            "Failed to parse svg++ input. Ensure XML entities like &, <, > are escaped "
            f"(use &amp;, &lt;, &gt;){location}"
        ) from exc
    diag_ns = _namespace_of(root.tag)
    if not diag_ns:
        raise ValueError("Input does not contain a diag namespace root element")

    diag_font_paths = _collect_font_paths(root, diag_ns)
    original_width = root.get("width")
    original_height = root.get("height")
    diagram_padding_str = root.get(_qual(diag_ns, "padding"))
    diagram_padding = _parse_length(diagram_padding_str, 0.0)
    if diagram_padding is None or diagram_padding < 0:
        diagram_padding = 0.0

    templates = {}
    if shared_template_sources:
        templates.update(_collect_templates_from_sources(shared_template_sources, diag_ns))
    templates.update(_collect_templates(root, diag_ns))
    if templates:
        _expand_instances_in_tree(root, diag_ns, templates)
    include_base = source_path.parent if source_path is not None else Path.cwd()
    has_includes = _expand_includes_in_tree(
        root,
        diag_ns,
        include_base=include_base,
        shared_template_sources=shared_template_sources,
        include_stack=_include_stack or [],
        include_depth=_include_depth,
        max_include_depth=_max_include_depth,
    )
    if has_includes:
        _ensure_unique_ids(root)
    class_style_rules = _collect_class_style_rules(root)
    _expand_graphs_in_tree(root, diag_ns, class_style_rules)
    anchor_specs = _collect_anchors(root, diag_ns)
    arrow_specs = _collect_arrows(root, diag_ns)

    svg_root = ET.Element(_q("svg"))
    _copy_svg_attributes(root, svg_root, diag_ns)

    root_font_family, root_font_path = _font_family_info(root, diag_ns, class_style_rules)
    for child in root:
        rendered, _, _, bbox = _render_node(
            child,
            diag_ns,
            wrap_width_hint=None,
            inherited_family=root_font_family,
            inherited_path=root_font_path,
            class_style_rules=class_style_rules,
        )
        if rendered is not None:
            svg_root.append(rendered)

    if arrow_specs or anchor_specs:
        _emit_arrows(svg_root, arrow_specs, anchor_specs)

    _apply_resvg_bounds(svg_root, original_width, original_height, diag_font_paths, diagram_padding)
    _apply_background_rect(root, svg_root, diag_ns)

    return _pretty_xml(svg_root)


def _expand_graphs_in_tree(
    root: ET.Element, diag_ns: str, class_style_rules: List[_ClassStyleRule]
) -> None:
    state = _graph_expansion_state(root, diag_ns)

    def _walk(node: ET.Element, *, inside_graph: bool) -> None:
        new_children: List[ET.Element] = []
        for child in list(node):
            if child.tag is ET.Comment:
                new_children.append(child)
                continue
            ns = _namespace_of(child.tag)
            local = _local_name(child.tag)
            if ns == diag_ns and local == "graph":
                if inside_graph:
                    raise DiagramagicSemanticError(
                        "E_GRAPH_NESTED_UNSUPPORTED",
                        "diag:graph cannot be nested inside another diag:graph in v1",
                    )
                state.graph_counter += 1
                rendered_graph = _expand_single_graph(
                    child,
                    diag_ns,
                    state,
                    class_style_rules=class_style_rules,
                    graph_index=state.graph_counter,
                )
                new_children.append(rendered_graph)
                continue
            _walk(child, inside_graph=inside_graph or (ns == diag_ns and local == "graph"))
            new_children.append(child)
        node[:] = new_children

    _walk(root, inside_graph=False)


def _graph_expansion_state(root: ET.Element, diag_ns: str) -> _GraphExpansionState:
    non_graph_ids: Set[str] = set()
    taken_ids: Set[str] = set()

    def _walk(node: ET.Element, *, inside_graph: bool) -> None:
        node_id = node.get("id")
        if node_id:
            taken_ids.add(node_id)
            ns = _namespace_of(node.tag)
            local = _local_name(node.tag)
            if not (inside_graph and ns == diag_ns and local == "node"):
                non_graph_ids.add(node_id)
        for child in list(node):
            if child.tag is ET.Comment:
                continue
            ns = _namespace_of(child.tag)
            local = _local_name(child.tag)
            child_inside_graph = inside_graph or (ns == diag_ns and local == "graph")
            _walk(child, inside_graph=child_inside_graph)

    _walk(root, inside_graph=False)
    return _GraphExpansionState(
        non_graph_ids=non_graph_ids,
        taken_ids=taken_ids,
        seen_graph_node_ids=set(),
    )


def _expand_single_graph(
    graph_node: ET.Element,
    diag_ns: str,
    state: _GraphExpansionState,
    class_style_rules: List[_ClassStyleRule],
    *,
    graph_index: int,
) -> ET.Element:
    direction = (graph_node.get("direction") or "TB").strip().upper()
    if direction not in {"TB", "BT", "LR", "RL"}:
        raise DiagramagicSemanticError(
            "E_GRAPH_ARGS",
            f'diag:graph has invalid direction="{graph_node.get("direction")}"',
        )
    node_gap = _parse_graph_nonnegative_length(
        graph_node, "node-gap", 30.0, error_code="E_GRAPH_ARGS"
    )
    rank_gap = _parse_graph_nonnegative_length(
        graph_node, "rank-gap", 50.0, error_code="E_GRAPH_ARGS"
    )
    x = _parse_graph_number(graph_node, "x", 0.0, error_code="E_GRAPH_ARGS")
    y = _parse_graph_number(graph_node, "y", 0.0, error_code="E_GRAPH_ARGS")
    layout = (graph_node.get("layout") or "layered").strip().lower()
    routing = (graph_node.get("routing") or "auto").strip().lower()
    quality = (graph_node.get("quality") or "balanced").strip().lower()
    if layout not in {"layered", "circular", "radial"}:
        raise DiagramagicSemanticError(
            "E_GRAPH_ARGS",
            (
                f'diag:graph has invalid layout="{graph_node.get("layout")}" '
                '(supported in v2 phase 1: layered, circular, radial)'
            ),
        )
    if routing not in {"auto", "spline", "polyline", "ortho", "curved", "line"}:
        raise DiagramagicSemanticError(
            "E_GRAPH_ARGS",
            f'diag:graph has invalid routing="{graph_node.get("routing")}"',
        )
    if quality not in {"fast", "balanced", "high"}:
        raise DiagramagicSemanticError(
            "E_GRAPH_ARGS",
            f'diag:graph has invalid quality="{graph_node.get("quality")}"',
        )

    nodes: List[_GraphNodeSpec] = []
    node_by_id: Dict[str, _GraphNodeSpec] = {}
    edges: List[_GraphEdgeSpec] = []

    for child in list(graph_node):
        if child.tag is ET.Comment:
            continue
        ns = _namespace_of(child.tag)
        local = _local_name(child.tag)
        if ns != diag_ns:
            raise DiagramagicSemanticError(
                "E_GRAPH_CHILD_UNSUPPORTED",
                f"unsupported child <{local}> under <diag:graph>; only diag:node and diag:edge are allowed",
            )
        if local == "node":
            node_spec = _collect_graph_node(child, diag_ns, class_style_rules)
            if node_spec.node_id in node_by_id:
                raise DiagramagicSemanticError(
                    "E_GRAPH_DUPLICATE_NODE",
                    f'duplicate diag:node id "{node_spec.node_id}" in graph',
                )
            if node_spec.node_id in state.non_graph_ids:
                raise DiagramagicSemanticError(
                    "E_GRAPH_ID_COLLISION",
                    f'diag:node id "{node_spec.node_id}" collides with an existing non-graph element id',
                )
            if node_spec.node_id in state.seen_graph_node_ids:
                raise DiagramagicSemanticError(
                    "E_GRAPH_ID_COLLISION",
                    f'diag:node id "{node_spec.node_id}" collides with an id from another graph',
                )
            nodes.append(node_spec)
            node_by_id[node_spec.node_id] = node_spec
            continue
        if local == "edge":
            edges.append(_collect_graph_edge(child))
            continue
        if local == "graph":
            raise DiagramagicSemanticError(
                "E_GRAPH_NESTED_UNSUPPORTED",
                "diag:graph cannot be nested inside another diag:graph in v1",
            )
        raise DiagramagicSemanticError(
            "E_GRAPH_CHILD_UNSUPPORTED",
            f"unsupported child <diag:{local}> under <diag:graph>; only diag:node and diag:edge are allowed",
        )

    if len(nodes) > GRAPH_MAX_NODES or len(edges) > GRAPH_MAX_EDGES:
        raise DiagramagicSemanticError(
            "E_GRAPH_TOO_LARGE",
            (
                f"diag:graph exceeds configured limits: nodes={len(nodes)} "
                f"(max {GRAPH_MAX_NODES}), edges={len(edges)} (max {GRAPH_MAX_EDGES})"
            ),
        )

    for edge in edges:
        if edge.from_id == edge.to_id:
            raise DiagramagicSemanticError(
                "E_GRAPH_SELF_EDGE",
                f'diag:edge from="{edge.from_id}" to="{edge.to_id}" self-edges are not supported in v1',
            )
        if edge.from_id not in node_by_id:
            raise DiagramagicSemanticError(
                "E_GRAPH_UNKNOWN_NODE",
                f'diag:edge from="{edge.from_id}" references unknown node id in this graph (attribute: from)',
            )
        if edge.to_id not in node_by_id:
            raise DiagramagicSemanticError(
                "E_GRAPH_UNKNOWN_NODE",
                f'diag:edge to="{edge.to_id}" references unknown node id in this graph (attribute: to)',
            )

    for node_spec in nodes:
        state.seen_graph_node_ids.add(node_spec.node_id)

    graphviz_layout = _layout_graph_with_graphviz(
        nodes,
        edges,
        direction=direction,
        layout=layout,
        routing=routing,
        quality=quality,
        node_gap=node_gap,
        rank_gap=rank_gap,
    )
    if graphviz_layout is None:
        if layout != "layered":
            raise DiagramagicSemanticError(
                "E_GRAPHVIZ_UNAVAILABLE",
                f'diag:graph layout="{layout}" requires Graphviz ("dot" executable not found)',
            )
        layout_positions = _layout_graph(nodes, edges, direction, node_gap, rank_gap)
    else:
        layout_positions = graphviz_layout.node_positions

    group_attrs = {"transform": f"translate({_fmt(x)}, {_fmt(y)})"}
    graph_id = graph_node.get("id")
    if graph_id:
        if graph_id in state.taken_ids and graph_id not in state.non_graph_ids:
            # id may already be this graph element's own id from source tree
            pass
        group_attrs["id"] = graph_id
    rendered_graph = ET.Element(_q("g"), group_attrs)

    node_bboxes: Dict[str, Tuple[float, float, float, float]] = {}
    for node_spec in nodes:
        nx, ny = layout_positions[node_spec.node_id]
        node_bboxes[node_spec.node_id] = (
            nx,
            ny,
            nx + node_spec.width,
            ny + node_spec.height,
        )

    needs_default_marker = any(
        "marker-end" not in edge.passthrough_attrs and "marker-start" not in edge.passthrough_attrs
        for edge in edges
    )
    default_marker_id: Optional[str] = None
    if needs_default_marker:
        default_marker_id = _reserve_unique_id(
            state.taken_ids, f"diag-graph-arrow-default-{graph_index}"
        )
        defs = ET.SubElement(rendered_graph, _q("defs"))
        marker = ET.SubElement(
            defs,
            _q("marker"),
            {
                "id": default_marker_id,
                "viewBox": "0 0 10 10",
                "refX": "9",
                "refY": "5",
                "markerWidth": "6",
                "markerHeight": "6",
                "orient": "auto",
            },
        )
        ET.SubElement(marker, _q("path"), {"d": "M 0 0 L 10 5 L 0 10 z", "fill": "#555"})

    for idx, edge in enumerate(edges):
        from_bbox = node_bboxes[edge.from_id]
        to_bbox = node_bboxes[edge.to_id]
        p_from, p_to = _resolve_arrow_points(from_bbox, to_bbox)
        edge_points: Optional[List[Tuple[float, float]]] = None
        if graphviz_layout is not None and idx < len(graphviz_layout.edge_layouts):
            candidate = graphviz_layout.edge_layouts[idx].points
            if len(candidate) >= 2:
                edge_points = candidate
        if edge_points is None:
            edge_points = [p_from, p_to]

        attrs: Dict[str, str] = {}
        attrs.update(edge.passthrough_attrs)
        attrs.setdefault("stroke", "#555")
        attrs.setdefault("stroke-width", "1")
        attrs.setdefault("fill", "none")
        if (
            default_marker_id is not None
            and "marker-end" not in attrs
            and "marker-start" not in attrs
        ):
            attrs["marker-end"] = f"url(#{default_marker_id})"
        edge_points = _clip_graph_edge_points_to_nodes(edge_points, from_bbox, to_bbox)
        use_bezier = routing in {"curved", "spline"} or (
            routing == "auto" and layout == "layered"
        )
        attrs["d"] = _graph_points_to_path_d(edge_points, bezier=use_bezier)
        rendered_graph.append(ET.Element(_q("path"), attrs))

    for node_spec in nodes:
        nx, ny = layout_positions[node_spec.node_id]
        wrapper = ET.Element(
            _q("g"),
            {"id": node_spec.node_id, "transform": f"translate({_fmt(nx)}, {_fmt(ny)})"},
        )
        wrapper.append(node_spec.rendered)
        rendered_graph.append(wrapper)

    for idx, edge in enumerate(edges):
        if not edge.label:
            continue
        label_pos: Optional[Tuple[float, float]] = None
        if graphviz_layout is not None and idx < len(graphviz_layout.edge_layouts):
            label_pos = graphviz_layout.edge_layouts[idx].label_pos
        if label_pos is not None:
            _emit_graph_edge_label_at(rendered_graph, edge, label_pos)
        else:
            from_bbox = node_bboxes[edge.from_id]
            to_bbox = node_bboxes[edge.to_id]
            p_from, p_to = _resolve_arrow_points(from_bbox, to_bbox)
            _emit_graph_edge_label(rendered_graph, edge, p_from, p_to)

    return rendered_graph


def _expand_includes_in_tree(
    node: ET.Element,
    diag_ns: str,
    *,
    include_base: Path,
    shared_template_sources: Optional[List[str]],
    include_stack: List[Path],
    include_depth: int,
    max_include_depth: int,
) -> bool:
    found_include = False
    new_children: List[ET.Element] = []
    for child in list(node):
        ns = _namespace_of(child.tag)
        local = _local_name(child.tag)
        if ns == diag_ns and local == "include":
            expanded = _expand_single_include(
                child,
                diag_ns,
                include_base=include_base,
                shared_template_sources=shared_template_sources,
                include_stack=include_stack,
                include_depth=include_depth,
                max_include_depth=max_include_depth,
            )
            new_children.append(expanded)
            found_include = True
            continue
        found_include = _expand_includes_in_tree(
            child,
            diag_ns,
            include_base=include_base,
            shared_template_sources=shared_template_sources,
            include_stack=include_stack,
            include_depth=include_depth,
            max_include_depth=max_include_depth,
        ) or found_include
        new_children.append(child)
    node[:] = new_children
    return found_include


def _expand_single_include(
    include_node: ET.Element,
    diag_ns: str,
    *,
    include_base: Path,
    shared_template_sources: Optional[List[str]],
    include_stack: List[Path],
    include_depth: int,
    max_include_depth: int,
) -> ET.Element:
    src = (include_node.get("src") or "").strip()
    if not src:
        raise DiagramagicSemanticError("E_INCLUDE_ARGS", "diag:include requires non-empty src attribute")
    x = _parse_length(include_node.get("x"), 0.0)
    y = _parse_length(include_node.get("y"), 0.0)
    scale = _parse_length(include_node.get("scale"), 1.0)
    if x is None or y is None or scale is None or scale <= 0:
        raise DiagramagicSemanticError(
            "E_INCLUDE_ARGS",
            f'diag:include src="{src}" requires numeric x/y and scale > 0',
        )

    resolved = Path(src).expanduser()
    if not resolved.is_absolute():
        resolved = include_base / resolved
    try:
        resolved_norm = resolved.resolve()
    except OSError:
        resolved_norm = resolved.absolute()

    if include_depth >= max_include_depth:
        raise DiagramagicSemanticError(
            "E_INCLUDE_DEPTH",
            f"maximum include depth exceeded ({max_include_depth}) while resolving {resolved_norm}",
        )
    if resolved_norm in include_stack:
        chain = " -> ".join(str(p) for p in include_stack + [resolved_norm])
        raise DiagramagicSemanticError("E_INCLUDE_CYCLE", f"include cycle detected: {chain}")
    if not resolved_norm.exists():
        raise DiagramagicSemanticError("E_INCLUDE_NOT_FOUND", f"include file not found: {resolved_norm}")

    try:
        include_text = resolved_norm.read_text()
    except OSError as exc:
        raise DiagramagicSemanticError(
            "E_INCLUDE_NOT_FOUND", f"failed to read include file {resolved_norm}: {exc}"
        ) from exc

    try:
        parsed = ET.fromstring(include_text)
    except ET.ParseError as exc:
        line, col = getattr(exc, "position", (None, None))
        loc = f" at line {line}, column {col}" if line is not None and col is not None else ""
        raise DiagramagicSemanticError(
            "E_INCLUDE_PARSE", f"invalid include XML in {resolved_norm}{loc}: {exc}"
        ) from exc
    if _local_name(parsed.tag) != "diagram":
        raise DiagramagicSemanticError(
            "E_INCLUDE_ROOT", f'included file {resolved_norm} must use <diag:diagram> root'
        )

    compiled_svg = diagramagic(
        include_text,
        shared_template_sources=shared_template_sources,
        source_path=resolved_norm,
        _include_stack=include_stack + [resolved_norm],
        _include_depth=include_depth + 1,
        _max_include_depth=max_include_depth,
    )
    compiled_root = ET.fromstring(compiled_svg)

    wrapper_attrs = {"transform": f"translate({_fmt(x)} {_fmt(y)}) scale({_fmt(scale)})"}
    include_id = include_node.get("id")
    if include_id:
        wrapper_attrs["id"] = include_id
    wrapper = ET.Element(_q("g"), wrapper_attrs)
    for child in list(compiled_root):
        wrapper.append(deepcopy(child))
    return wrapper


def _collect_graph_node(
    node: ET.Element, diag_ns: str, class_style_rules: List[_ClassStyleRule]
) -> _GraphNodeSpec:
    node_id = (node.get("id") or "").strip()
    if not node_id:
        raise DiagramagicSemanticError("E_GRAPH_NODE_MISSING_ID", "diag:node requires non-empty id")

    width_attr = node.get("width")
    width_explicit = width_attr is not None
    width = _parse_graph_number(node, "width", None, error_code="E_GRAPH_ARGS")
    min_width = _parse_graph_nonnegative_length(
        node, "min-width", 0.0, error_code="E_GRAPH_ARGS"
    )
    padding = _parse_graph_nonnegative_length(node, "padding", 8.0, error_code="E_GRAPH_ARGS")
    gap = _parse_graph_nonnegative_length(node, "gap", 0.0, error_code="E_GRAPH_ARGS")
    for descendant in node.iter():
        if descendant is node:
            continue
        if descendant.tag is ET.Comment:
            continue
        if _namespace_of(descendant.tag) == diag_ns and _local_name(descendant.tag) == "graph":
            raise DiagramagicSemanticError(
                "E_GRAPH_NESTED_UNSUPPORTED",
                "diag:graph cannot be nested inside another diag:graph in v1",
            )

    flex_node = ET.Element(_qual(diag_ns, "flex"))
    flex_node.set("direction", "column")
    flex_node.set("padding", _fmt(padding))
    flex_node.set("gap", _fmt(gap))
    if width_explicit and width is not None:
        flex_node.set("width", _fmt(max(width, min_width)))
    elif min_width > 0:
        flex_node.set("width", _fmt(min_width))

    bg_class = node.get("background-class")
    if bg_class:
        flex_node.set("background-class", bg_class)
    bg_style = node.get("background-style")
    if bg_style:
        flex_node.set("background-style", bg_style)

    for child in list(node):
        flex_node.append(deepcopy(child))

    rendered, measured_width, measured_height, _ = _render_flex(
        flex_node,
        diag_ns,
        inherited_family=None,
        inherited_path=None,
        wrap_width_hint=None,
        class_style_rules=class_style_rules,
    )

    final_width = measured_width
    if width_explicit and width is not None:
        final_width = max(width, min_width)
    else:
        final_width = max(measured_width, min_width)

    control_attrs = {
        "id",
        "width",
        "min-width",
        "padding",
        "gap",
        "background-class",
        "background-style",
    }
    for key, value in node.attrib.items():
        if _namespace_of(key) is not None:
            continue
        if key in control_attrs:
            continue
        rendered.set(key, value)

    if not math.isclose(final_width, measured_width, abs_tol=1e-9):
        for child in list(rendered):
            if _local_name(child.tag) != "rect":
                continue
            if child.get("class") == bg_class or (bg_class is None and bg_style and child.get("style") == bg_style):
                child.set("width", _fmt(final_width))
                break

    return _GraphNodeSpec(
        node_id=node_id,
        source_node=node,
        rendered=rendered,
        width=final_width,
        height=measured_height,
    )


def _collect_graph_edge(node: ET.Element) -> _GraphEdgeSpec:
    from_id = (node.get("from") or "").strip()
    to_id = (node.get("to") or "").strip()
    if not from_id or not to_id:
        raise DiagramagicSemanticError(
            "E_GRAPH_ARGS",
            "diag:edge requires non-empty from and to attributes",
        )
    label = node.get("label")
    label_size = _parse_graph_number(node, "label-size", 10.0, error_code="E_GRAPH_ARGS")
    if label_size is None or label_size <= 0:
        raise DiagramagicSemanticError(
            "E_GRAPH_ARGS",
            f'diag:edge label-size must be > 0 (got {node.get("label-size")!r})',
        )
    label_fill = node.get("label-fill") or "#555"

    passthrough: Dict[str, str] = {}
    control_attrs = {"from", "to", "label", "label-size", "label-fill"}
    for key, value in node.attrib.items():
        if _namespace_of(key) is not None:
            continue
        if key in control_attrs:
            continue
        passthrough[key] = value

    return _GraphEdgeSpec(
        from_id=from_id,
        to_id=to_id,
        label=label,
        label_size=float(label_size),
        label_fill=label_fill,
        passthrough_attrs=passthrough,
    )


def _layout_graph(
    nodes: List[_GraphNodeSpec],
    edges: List[_GraphEdgeSpec],
    direction: str,
    node_gap: float,
    rank_gap: float,
) -> Dict[str, Tuple[float, float]]:
    node_order = [node.node_id for node in nodes]
    order_index = {node_id: idx for idx, node_id in enumerate(node_order)}
    size_by_id = {node.node_id: (node.width, node.height) for node in nodes}

    outgoing: Dict[str, List[int]] = {node_id: [] for node_id in node_order}
    for idx, edge in enumerate(edges):
        outgoing[edge.from_id].append(idx)

    reversed_edges: Set[int] = set()
    state: Dict[str, int] = {node_id: 0 for node_id in node_order}

    def _dfs(node_id: str) -> None:
        state[node_id] = 1
        for edge_idx in outgoing[node_id]:
            target = edges[edge_idx].to_id
            if state[target] == 0:
                _dfs(target)
            elif state[target] == 1:
                reversed_edges.add(edge_idx)
        state[node_id] = 2

    for node_id in node_order:
        if state[node_id] == 0:
            _dfs(node_id)

    dag_edges: List[Tuple[str, str]] = []
    dag_outgoing: Dict[str, List[str]] = {node_id: [] for node_id in node_order}
    indegree: Dict[str, int] = {node_id: 0 for node_id in node_order}
    for idx, edge in enumerate(edges):
        if idx in reversed_edges:
            u, v = edge.to_id, edge.from_id
        else:
            u, v = edge.from_id, edge.to_id
        dag_edges.append((u, v))
        dag_outgoing[u].append(v)
        indegree[v] += 1

    queue: List[str] = [node_id for node_id in node_order if indegree[node_id] == 0]
    topo: List[str] = []
    cursor = 0
    while cursor < len(queue):
        u = queue[cursor]
        cursor += 1
        topo.append(u)
        for v in dag_outgoing[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    if len(topo) != len(node_order):
        topo = node_order[:]

    rank: Dict[str, int] = {node_id: 0 for node_id in node_order}
    for u in topo:
        base = rank[u]
        for v in dag_outgoing[u]:
            if rank[v] < base + 1:
                rank[v] = base + 1

    rank_to_nodes: Dict[int, List[str]] = {}
    for node_id in node_order:
        rank_to_nodes.setdefault(rank[node_id], []).append(node_id)

    max_rank = max(rank_to_nodes.keys(), default=0)
    for r in range(1, max_rank + 1):
        current_nodes = rank_to_nodes.get(r, [])
        if not current_nodes:
            continue
        prev_order_pos: Dict[str, int] = {}
        for pr in range(0, r):
            for idx, node_id in enumerate(rank_to_nodes.get(pr, [])):
                if node_id not in prev_order_pos:
                    prev_order_pos[node_id] = idx
        incoming_positions: Dict[str, float] = {}
        for node_id in current_nodes:
            preds = [u for (u, v) in dag_edges if v == node_id and rank[u] < r]
            if not preds:
                incoming_positions[node_id] = float("inf")
                continue
            pred_positions = sorted(prev_order_pos.get(p, order_index[p]) for p in preds)
            mid = len(pred_positions) // 2
            if len(pred_positions) % 2 == 1:
                median = float(pred_positions[mid])
            else:
                median = 0.5 * (pred_positions[mid - 1] + pred_positions[mid])
            incoming_positions[node_id] = median
        rank_to_nodes[r] = sorted(
            current_nodes,
            key=lambda node_id: (incoming_positions[node_id], order_index[node_id]),
        )

    cross_span_by_rank: Dict[int, float] = {}
    main_size_by_rank: Dict[int, float] = {}
    for r in range(0, max_rank + 1):
        members = rank_to_nodes.get(r, [])
        if direction in {"TB", "BT"}:
            cross_sizes = [size_by_id[n][0] for n in members]
            main_sizes = [size_by_id[n][1] for n in members]
        else:
            cross_sizes = [size_by_id[n][1] for n in members]
            main_sizes = [size_by_id[n][0] for n in members]
        span = sum(cross_sizes)
        if members:
            span += node_gap * (len(members) - 1)
        cross_span_by_rank[r] = span
        main_size_by_rank[r] = max(main_sizes, default=0.0)

    max_cross_span = max(cross_span_by_rank.values(), default=0.0)
    rank_main_origin: Dict[int, float] = {}
    cursor_main = 0.0
    for r in range(0, max_rank + 1):
        rank_main_origin[r] = cursor_main
        cursor_main += main_size_by_rank.get(r, 0.0) + rank_gap

    positions: Dict[str, Tuple[float, float]] = {}
    for r in range(0, max_rank + 1):
        members = rank_to_nodes.get(r, [])
        span = cross_span_by_rank.get(r, 0.0)
        cross_cursor = (max_cross_span - span) / 2.0
        for node_id in members:
            width, height = size_by_id[node_id]
            if direction in {"TB", "BT"}:
                x = cross_cursor
                y_base = rank_main_origin[r]
                y = y_base if direction == "TB" else -(y_base + height)
                positions[node_id] = (x, y)
                cross_cursor += width + node_gap
            else:
                y = cross_cursor
                x_base = rank_main_origin[r]
                x = x_base if direction == "LR" else -(x_base + width)
                positions[node_id] = (x, y)
                cross_cursor += height + node_gap

    return positions


def _emit_graph_edge_label(
    graph_group: ET.Element,
    edge: _GraphEdgeSpec,
    p_from: Tuple[float, float],
    p_to: Tuple[float, float],
) -> None:
    mid_x = (p_from[0] + p_to[0]) / 2.0
    mid_y = (p_from[1] + p_to[1]) / 2.0
    dx = p_to[0] - p_from[0]
    dy = p_to[1] - p_from[1]
    seg_len = math.hypot(dx, dy)
    if seg_len <= 1e-9:
        lx, ly = mid_x, mid_y
    else:
        nx = -dy / seg_len
        ny = dx / seg_len
        lx = mid_x + nx * 6.0
        ly = mid_y + ny * 6.0

    attrs = {
        "x": _fmt(lx),
        "y": _fmt(ly),
        "text-anchor": "middle",
        "font-size": _fmt(edge.label_size),
        "fill": edge.label_fill,
        "dominant-baseline": "alphabetic",
    }
    label = ET.Element(_q("text"), attrs)
    label.text = edge.label
    graph_group.append(label)


def _emit_graph_edge_label_at(
    graph_group: ET.Element,
    edge: _GraphEdgeSpec,
    point: Tuple[float, float],
) -> None:
    attrs = {
        "x": _fmt(point[0]),
        "y": _fmt(point[1]),
        "text-anchor": "middle",
        "font-size": _fmt(edge.label_size),
        "fill": edge.label_fill,
        "dominant-baseline": "alphabetic",
    }
    label = ET.Element(_q("text"), attrs)
    label.text = edge.label
    graph_group.append(label)


def _graph_points_to_path_d(points: List[Tuple[float, float]], *, bezier: bool = False) -> str:
    if not points:
        return ""
    if bezier and len(points) >= 4:
        parts = [f"M {_fmt(points[0][0])} {_fmt(points[0][1])}"]
        i = 1
        while i + 2 < len(points):
            c1 = points[i]
            c2 = points[i + 1]
            end = points[i + 2]
            parts.append(
                "C "
                f"{_fmt(c1[0])} {_fmt(c1[1])} "
                f"{_fmt(c2[0])} {_fmt(c2[1])} "
                f"{_fmt(end[0])} {_fmt(end[1])}"
            )
            i += 3
        for x, y in points[i:]:
            parts.append(f"L {_fmt(x)} {_fmt(y)}")
        return " ".join(parts)
    parts = [f"M {_fmt(points[0][0])} {_fmt(points[0][1])}"]
    for x, y in points[1:]:
        parts.append(f"L {_fmt(x)} {_fmt(y)}")
    return " ".join(parts)


def _clip_graph_edge_points_to_nodes(
    points: List[Tuple[float, float]],
    from_bbox: Tuple[float, float, float, float],
    to_bbox: Tuple[float, float, float, float],
) -> List[Tuple[float, float]]:
    if len(points) < 2:
        return points

    adjusted = [*points]
    start_target = adjusted[1]
    end_source = adjusted[-2]
    start_center = _bbox_center(from_bbox)
    end_center = _bbox_center(to_bbox)
    start_clip = _ray_rect_intersection(start_center, start_target, from_bbox)
    end_clip = _ray_rect_intersection(end_center, end_source, to_bbox)
    if start_clip is not None:
        adjusted[0] = start_clip
    if end_clip is not None:
        adjusted[-1] = end_clip

    return adjusted


def _layout_graph_with_graphviz(
    nodes: List[_GraphNodeSpec],
    edges: List[_GraphEdgeSpec],
    *,
    direction: str,
    layout: str,
    routing: str,
    quality: str,
    node_gap: float,
    rank_gap: float,
) -> Optional[_GraphvizLayoutResult]:
    dot_path = shutil.which("dot")
    if not dot_path:
        return None
    engine_by_layout = {
        "layered": "dot",
        "circular": "circo",
        "radial": "twopi",
    }
    engine = engine_by_layout[layout]
    splines = _graphviz_splines_for_routing(layout=layout, routing=routing)
    dot_text = _build_graphviz_dot(
        nodes=nodes,
        edges=edges,
        direction=direction,
        layout=layout,
        splines=splines,
        quality=quality,
        node_gap=node_gap,
        rank_gap=rank_gap,
    )
    try:
        proc = subprocess.run(
            [dot_path, f"-K{engine}", "-Tplain"],
            input=dot_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=5.0,
        )
    except subprocess.TimeoutExpired as exc:
        raise DiagramagicSemanticError(
            "E_GRAPH_LAYOUT_FAILED",
            f'graph layout timed out for layout="{layout}"',
        ) from exc
    except OSError as exc:
        raise DiagramagicSemanticError(
            "E_GRAPH_LAYOUT_FAILED",
            f'failed to execute Graphviz for layout="{layout}": {exc}',
        ) from exc
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip()
        if len(detail) > 240:
            detail = detail[:240] + "..."
        raise DiagramagicSemanticError(
            "E_GRAPH_LAYOUT_FAILED",
            f'Graphviz failed for layout="{layout}": {detail or "unknown error"}',
        )
    return _parse_graphviz_plain_layout(proc.stdout, nodes, edges)


def _build_graphviz_dot(
    *,
    nodes: List[_GraphNodeSpec],
    edges: List[_GraphEdgeSpec],
    direction: str,
    layout: str,
    splines: str,
    quality: str,
    node_gap: float,
    rank_gap: float,
) -> str:
    nodesep_in = max(0.02, node_gap / 96.0)
    ranksep_in = max(0.02, rank_gap / 96.0)
    lines: List[str] = ["digraph G {"]
    lines.append(f'  graph [splines="{splines}"];')
    if layout == "layered":
        lines.append(f'  graph [rankdir="{direction}", nodesep="{nodesep_in:.4f}", ranksep="{ranksep_in:.4f}"];')
    elif layout == "radial":
        lines.append(f'  graph [ranksep="{ranksep_in:.4f}", overlap="false"];')
    else:
        lines.append('  graph [overlap="false"];')
    if quality == "fast":
        lines.append('  graph [pack="false"];')
    elif quality == "high":
        lines.append('  graph [pack="true", packmode="array_u"];')
    lines.append('  node [shape="box", fixedsize="true", margin="0"];')
    for node in nodes:
        width_in = max(0.01, node.width / 96.0)
        height_in = max(0.01, node.height / 96.0)
        node_id = _dot_quote(node.node_id)
        lines.append(f'  {node_id} [width="{width_in:.4f}", height="{height_in:.4f}"];')
    for edge in edges:
        u = _dot_quote(edge.from_id)
        v = _dot_quote(edge.to_id)
        lines.append(f"  {u} -> {v};")
    lines.append("}")
    return "\n".join(lines)


def _dot_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _graphviz_splines_for_routing(*, layout: str, routing: str) -> str:
    if routing == "auto":
        return "spline" if layout == "layered" else "polyline"
    mapping = {
        "spline": "spline",
        "polyline": "polyline",
        "ortho": "ortho",
        "curved": "curved",
        "line": "line",
    }
    return mapping[routing]


def _parse_graphviz_plain_layout(
    plain_text: str,
    nodes: List[_GraphNodeSpec],
    edges: List[_GraphEdgeSpec],
) -> _GraphvizLayoutResult:
    lines = [ln.strip() for ln in plain_text.splitlines() if ln.strip()]
    if not lines or not lines[0].startswith("graph "):
        raise DiagramagicSemanticError(
            "E_GRAPH_LAYOUT_PARSE",
            "unexpected Graphviz plain output: missing graph header",
        )
    header = shlex.split(lines[0])
    if len(header) < 4:
        raise DiagramagicSemanticError(
            "E_GRAPH_LAYOUT_PARSE",
            "unexpected Graphviz plain output: malformed graph header",
        )
    try:
        graph_height_in = float(header[3])
    except ValueError as exc:
        raise DiagramagicSemanticError(
            "E_GRAPH_LAYOUT_PARSE",
            "unexpected Graphviz plain output: invalid graph dimensions",
        ) from exc

    node_positions_center: Dict[str, Tuple[float, float, float, float]] = {}
    parsed_edges: List[_GraphvizEdgeLayout] = []
    for line in lines[1:]:
        if line == "stop":
            break
        parts = shlex.split(line)
        if not parts:
            continue
        kind = parts[0]
        if kind == "node":
            if len(parts) < 6:
                raise DiagramagicSemanticError(
                    "E_GRAPH_LAYOUT_PARSE",
                    "unexpected Graphviz plain output: malformed node line",
                )
            node_id = parts[1]
            try:
                x_in = float(parts[2])
                y_in = float(parts[3])
                w_in = float(parts[4])
                h_in = float(parts[5])
            except ValueError as exc:
                raise DiagramagicSemanticError(
                    "E_GRAPH_LAYOUT_PARSE",
                    f'unexpected Graphviz plain output: invalid numeric node data for "{node_id}"',
                ) from exc
            node_positions_center[node_id] = (x_in, y_in, w_in, h_in)
        elif kind == "edge":
            if len(parts) < 4:
                raise DiagramagicSemanticError(
                    "E_GRAPH_LAYOUT_PARSE",
                    "unexpected Graphviz plain output: malformed edge line",
                )
            try:
                n = int(parts[3])
            except ValueError as exc:
                raise DiagramagicSemanticError(
                    "E_GRAPH_LAYOUT_PARSE",
                    "unexpected Graphviz plain output: invalid edge point count",
                ) from exc
            expected_min = 4 + 2 * n
            if len(parts) < expected_min:
                raise DiagramagicSemanticError(
                    "E_GRAPH_LAYOUT_PARSE",
                    "unexpected Graphviz plain output: truncated edge points",
                )
            coords = parts[4 : 4 + 2 * n]
            points: List[Tuple[float, float]] = []
            for i in range(0, len(coords), 2):
                try:
                    px_in = float(coords[i])
                    py_in = float(coords[i + 1])
                except ValueError as exc:
                    raise DiagramagicSemanticError(
                        "E_GRAPH_LAYOUT_PARSE",
                        "unexpected Graphviz plain output: invalid edge point value",
                    ) from exc
                points.append(
                    (
                        px_in * 96.0,
                        (graph_height_in - py_in) * 96.0,
                    )
                )
            label_pos: Optional[Tuple[float, float]] = None
            remaining = parts[expected_min:]
            if len(remaining) >= 3:
                # plain format includes label text + x/y when label exists.
                try:
                    lx_in = float(remaining[1])
                    ly_in = float(remaining[2])
                    label_pos = (lx_in * 96.0, (graph_height_in - ly_in) * 96.0)
                except ValueError:
                    label_pos = None
            parsed_edges.append(_GraphvizEdgeLayout(points=points, label_pos=label_pos))

    node_top_left: Dict[str, Tuple[float, float]] = {}
    min_x = 0.0
    min_y = 0.0
    first_point = True

    for node in nodes:
        if node.node_id not in node_positions_center:
            raise DiagramagicSemanticError(
                "E_GRAPH_LAYOUT_PARSE",
                f'Graphviz output missing node "{node.node_id}"',
            )
        x_in, y_in, w_in, h_in = node_positions_center[node.node_id]
        cx = x_in * 96.0
        cy = (graph_height_in - y_in) * 96.0
        w = w_in * 96.0
        h = h_in * 96.0
        tlx = cx - w / 2.0
        tly = cy - h / 2.0
        node_top_left[node.node_id] = (tlx, tly)
        if first_point:
            min_x, min_y = tlx, tly
            first_point = False
        else:
            min_x = min(min_x, tlx)
            min_y = min(min_y, tly)

    for edge_layout in parsed_edges:
        for px, py in edge_layout.points:
            min_x = min(min_x, px)
            min_y = min(min_y, py)
        if edge_layout.label_pos is not None:
            min_x = min(min_x, edge_layout.label_pos[0])
            min_y = min(min_y, edge_layout.label_pos[1])

    if min_x < 0 or min_y < 0:
        shift_x = -min_x if min_x < 0 else 0.0
        shift_y = -min_y if min_y < 0 else 0.0
        for node_id, (x, y) in list(node_top_left.items()):
            node_top_left[node_id] = (x + shift_x, y + shift_y)
        for edge_layout in parsed_edges:
            edge_layout.points = [(x + shift_x, y + shift_y) for (x, y) in edge_layout.points]
            if edge_layout.label_pos is not None:
                edge_layout.label_pos = (
                    edge_layout.label_pos[0] + shift_x,
                    edge_layout.label_pos[1] + shift_y,
                )

    if len(parsed_edges) < len(edges):
        raise DiagramagicSemanticError(
            "E_GRAPH_LAYOUT_PARSE",
            (
                "unexpected Graphviz plain output: edge count mismatch "
                f"(got {len(parsed_edges)}, expected at least {len(edges)})"
            ),
        )
    return _GraphvizLayoutResult(
        node_positions=node_top_left,
        edge_layouts=parsed_edges[: len(edges)],
    )


def _parse_graph_nonnegative_length(
    node: ET.Element,
    attr: str,
    default: float,
    *,
    error_code: str,
) -> float:
    value = _parse_graph_number(node, attr, default, error_code=error_code)
    assert value is not None
    if value < 0:
        raise DiagramagicSemanticError(
            error_code,
            f'{_tag_desc(node)} attribute "{attr}" must be >= 0 (got {node.get(attr)!r})',
        )
    return float(value)


def _parse_graph_number(
    node: ET.Element,
    attr: str,
    default: Optional[float],
    *,
    error_code: str,
) -> Optional[float]:
    raw = node.get(attr)
    if raw is None:
        return default
    parsed = _parse_length(raw, None)
    if parsed is None:
        raise DiagramagicSemanticError(
            error_code,
            f'{_tag_desc(node)} attribute "{attr}" must be numeric (got {raw!r})',
        )
    return float(parsed)


def _tag_desc(node: ET.Element) -> str:
    ns = _namespace_of(node.tag)
    local = _local_name(node.tag)
    if ns is None:
        return f"<{local}>"
    return f"<diag:{local}>"


def _reserve_unique_id(existing: Set[str], base: str) -> str:
    if base not in existing:
        existing.add(base)
        return base
    idx = 1
    while True:
        candidate = f"{base}-{idx}"
        if candidate not in existing:
            existing.add(candidate)
            return candidate
        idx += 1


def _ensure_unique_ids(root: ET.Element) -> None:
    seen: Dict[str, ET.Element] = {}
    for node in root.iter():
        node_id = node.get("id")
        if not node_id:
            continue
        if node_id in seen:
            raise DiagramagicSemanticError(
                "E_INCLUDE_ID_COLLISION",
                f'duplicate id "{node_id}" found after include expansion',
            )
        seen[node_id] = node


def render_png(
    svg_text: str,
    *,
    scale: float = 1.0,
    focus_id: Optional[str] = None,
    padding: float = 20.0,
    font_paths: Optional[List[str]] = None,
) -> bytes:
    render_input = svg_text
    if focus_id:
        render_input = _apply_focus_crop(svg_text, focus_id, padding)
    return bytes(_render_svg(render_input, scale, font_paths or []))


def _apply_focus_crop(svg_text: str, focus_id: str, padding: float) -> str:
    root = ET.fromstring(svg_text)
    measurement = _measure_svg(svg_text, [])
    nodes = measurement.get("nodes") or []

    matched_bbox: Optional[Tuple[float, float, float, float]] = None
    element_exists = False
    for node in root.iter():
        if node.get("id") == focus_id:
            element_exists = True
            break

    for node in nodes:
        if node.get("id") == focus_id:
            bbox = node.get("bbox")
            if bbox and len(bbox) == 4:
                matched_bbox = (bbox[0], bbox[1], bbox[2], bbox[3])
                break

    if not element_exists:
        raise FocusNotFoundError(f'focus id "{focus_id}" not found')

    if matched_bbox is None:
        # Exists but has no measurable bbox (e.g. display:none). Rendering still succeeds.
        return svg_text

    left, top, right, bottom = matched_bbox
    pad = max(padding, 0.0)
    view_x = left - pad
    view_y = top - pad
    view_w = max((right - left) + 2 * pad, 1.0)
    view_h = max((bottom - top) + 2 * pad, 1.0)

    root.set("viewBox", f"{_fmt(view_x)} {_fmt(view_y)} {_fmt(view_w)} {_fmt(view_h)}")
    root.set("width", _fmt(view_w))
    root.set("height", _fmt(view_h))
    return ET.tostring(root, encoding="unicode")


def _render_node(
    node: ET.Element,
    diag_ns: str,
    wrap_width_hint: Optional[float],
    inherited_family: Optional[str],
    inherited_path: Optional[str],
    class_style_rules: List[_ClassStyleRule],
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
            class_style_rules=class_style_rules,
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
            class_style_rules=class_style_rules,
        )

    rendered = _render_generic_node(
        node,
        diag_ns,
        wrap_width_hint,
        inherited_family,
        inherited_path,
        class_style_rules,
    )
    width, height, bbox = _measure_rendered_node(rendered)
    return rendered, width, height, bbox


def _render_flex(
    node: ET.Element,
    diag_ns: str,
    inherited_family: Optional[str],
    inherited_path: Optional[str],
    wrap_width_hint: Optional[float],
    class_style_rules: List[_ClassStyleRule],
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

    local_family, local_path = _font_family_info(node, diag_ns, class_style_rules)
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
            class_style_rules=class_style_rules,
        )
        if rendered is not None:
            child_entries.append((rendered, w, h))

    g_attrs = {"transform": f"translate({_fmt(x)}, {_fmt(y)})"}
    consumed = {"x", "y", "width", "direction", "gap", "padding", "background-class", "background-style"}
    for key, value in node.attrib.items():
        if _namespace_of(key) == diag_ns:
            continue
        local_key = _local_name(key)
        if local_key in consumed:
            continue
        g_attrs[local_key] = value
    g = ET.Element(_q("g"), g_attrs)

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
    class_style_rules: List[_ClassStyleRule],
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

    font_size = _infer_font_size(node, class_style_rules)
    font_family, font_path = _font_family_info(node, diag_ns, class_style_rules)
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


def _measure_rendered_node(
    rendered: ET.Element,
) -> Tuple[float, float, Optional[Tuple[float, float, float, float]]]:
    scratch_svg = ET.Element(_q("svg"))
    scratch_svg.append(deepcopy(rendered))
    measurement = _measure_svg(ET.tostring(scratch_svg, encoding="unicode"), [])
    overall = measurement.get("overall")
    if not overall:
        return 0.0, 0.0, None
    left, top, right, bottom = overall
    return right - left, bottom - top, (left, top, right, bottom)


def _collect_templates_from_sources(
    template_sources: List[str], diag_ns: str
) -> Dict[str, List[ET.Element]]:
    templates: Dict[str, List[ET.Element]] = {}
    for source in template_sources:
        parsed = ET.fromstring(source)
        if _namespace_of(parsed.tag) != diag_ns or _local_name(parsed.tag) != "diagram":
            raise ValueError("Template source must use the same diag namespace and <diag:diagram> root")
        templates.update(_collect_templates(parsed, diag_ns))
    return templates


def _collect_arrows(root: ET.Element, diag_ns: str) -> List[_ArrowSpec]:
    arrows: List[_ArrowSpec] = []
    parent_by_node: Dict[ET.Element, ET.Element] = {}
    for parent in root.iter():
        for child in list(parent):
            parent_by_node[child] = parent

    arrow_nodes = [
        node
        for node in root.iter()
        if _namespace_of(node.tag) == diag_ns and _local_name(node.tag) == "arrow"
    ]
    for index, node in enumerate(arrow_nodes):
        if _namespace_of(node.tag) != diag_ns or _local_name(node.tag) != "arrow":
            continue

        from_id = (node.get("from") or "").strip()
        to_id = (node.get("to") or "").strip()
        if not from_id:
            raise ValueError("diag:arrow requires non-empty 'from' attribute")
        if not to_id:
            raise ValueError("diag:arrow requires non-empty 'to' attribute")

        if node.get("from-edge") is not None or node.get("to-edge") is not None:
            raise ValueError("diag:arrow no longer supports from-edge/to-edge; use automatic center-line routing")

        label = node.get("label")
        label_size = _parse_length(node.get("label-size"), 10.0) or 10.0
        label_fill = node.get("label-fill") or "#555"

        passthrough_attrs: Dict[str, str] = {}
        control_attrs = {
            "from",
            "to",
            "label",
            "label-size",
            "label-fill",
        }
        for key, value in node.attrib.items():
            if _namespace_of(key) is not None:
                continue
            if key in control_attrs:
                continue
            passthrough_attrs[key] = value

        slot_id = f"diag-arrow-slot-{index}"
        arrows.append(
            _ArrowSpec(
                from_id=from_id,
                to_id=to_id,
                slot_id=slot_id,
                label=label,
                label_size=label_size,
                label_fill=label_fill,
                passthrough_attrs=passthrough_attrs,
            )
        )
        parent = parent_by_node.get(node)
        if parent is not None:
            replacement = ET.Element(_q("g"), {"data-diag-arrow-slot": slot_id})
            children = list(parent)
            insert_at = children.index(node)
            parent.remove(node)
            parent.insert(insert_at, replacement)
        elif node is root:
            raise ValueError("diag:arrow cannot be the document root element")

    return arrows


def _collect_anchors(root: ET.Element, diag_ns: str) -> List[_AnchorSpec]:
    anchors: List[_AnchorSpec] = []
    for node in root.iter():
        if _namespace_of(node.tag) != diag_ns or _local_name(node.tag) != "anchor":
            continue

        anchor_id = (node.get("id") or "").strip()
        if not anchor_id:
            raise ValueError("diag:anchor requires non-empty 'id' attribute")

        x = _parse_length(node.get("x"), None)
        y = _parse_length(node.get("y"), None)
        relative_to = (node.get("relative-to") or "").strip() or None
        side = (node.get("side") or "center").strip().lower()
        offset_x = _parse_length(node.get("offset-x"), 0.0) or 0.0
        offset_y = _parse_length(node.get("offset-y"), 0.0) or 0.0

        has_abs = x is not None or y is not None
        has_rel = relative_to is not None
        if has_abs and has_rel:
            raise ValueError(
                f'diag:anchor id="{anchor_id}" cannot combine absolute (x/y) and relative-to modes'
            )
        if not has_abs and not has_rel:
            raise ValueError(
                f'diag:anchor id="{anchor_id}" requires either x/y or relative-to'
            )
        if has_abs and (x is None or y is None):
            raise ValueError(
                f'diag:anchor id="{anchor_id}" absolute mode requires both x and y'
            )
        if side not in {"top", "bottom", "left", "right", "center"}:
            raise ValueError(
                f'diag:anchor id="{anchor_id}" side must be one of top|bottom|left|right|center'
            )

        anchors.append(
            _AnchorSpec(
                anchor_id=anchor_id,
                x=x,
                y=y,
                relative_to=relative_to,
                side=side,
                offset_x=offset_x,
                offset_y=offset_y,
            )
        )

    return anchors


def _emit_arrows(svg_root: ET.Element, arrows: List[_ArrowSpec], anchors: List[_AnchorSpec]) -> None:
    svg_text = ET.tostring(svg_root, encoding="unicode")
    measurement = _measure_svg(svg_text, [])
    nodes = measurement.get("nodes") or []
    bbox_by_id: Dict[str, Tuple[float, float, float, float]] = {}

    for node in nodes:
        node_id = node.get("id")
        bbox = node.get("bbox")
        if not node_id or not bbox:
            continue
        if node_id in bbox_by_id:
            raise ValueError(f'duplicate id "{node_id}" found while resolving diag:arrow endpoints')
        bbox_by_id[node_id] = (bbox[0], bbox[1], bbox[2], bbox[3])

    seen_ids: Dict[str, int] = {}
    for node in svg_root.iter():
        node_id = node.get("id")
        if not node_id:
            continue
        seen_ids[node_id] = seen_ids.get(node_id, 0) + 1

    anchor_counts: Dict[str, int] = {}
    for anchor in anchors:
        anchor_counts[anchor.anchor_id] = anchor_counts.get(anchor.anchor_id, 0) + 1
    for anchor_id, count in anchor_counts.items():
        if count > 1:
            raise ValueError(f'diag:anchor id="{anchor_id}" is duplicated')
        if seen_ids.get(anchor_id, 0) > 0:
            raise ValueError(f'diag:anchor id="{anchor_id}" collides with an existing element id')

    anchor_points: Dict[str, Tuple[float, float]] = {}
    for anchor in anchors:
        if anchor.relative_to:
            if seen_ids.get(anchor.relative_to, 0) == 0:
                raise ValueError(
                    f'diag:anchor id="{anchor.anchor_id}" relative-to="{anchor.relative_to}" id not found'
                )
            if seen_ids.get(anchor.relative_to, 0) > 1:
                raise ValueError(
                    f'diag:anchor id="{anchor.anchor_id}" relative-to="{anchor.relative_to}" is duplicated'
                )
            target_bbox = bbox_by_id.get(anchor.relative_to)
            if target_bbox is None:
                raise ValueError(
                    f'diag:anchor id="{anchor.anchor_id}" relative-to="{anchor.relative_to}" has no measurable bbox'
                )
            px, py = _anchor_point_from_bbox(target_bbox, anchor.side)
        else:
            assert anchor.x is not None and anchor.y is not None
            px, py = anchor.x, anchor.y
        anchor_points[anchor.anchor_id] = (px + anchor.offset_x, py + anchor.offset_y)

    default_marker_id: Optional[str] = None
    parent_by_node: Dict[ET.Element, ET.Element] = {}
    slot_nodes: Dict[str, ET.Element] = {}
    for parent in svg_root.iter():
        for child in list(parent):
            parent_by_node[child] = parent
        slot_id = parent.get("data-diag-arrow-slot")
        if slot_id:
            slot_nodes[slot_id] = parent

    for arrow in arrows:
        from_anchor = anchor_points.get(arrow.from_id)
        to_anchor = anchor_points.get(arrow.to_id)

        from_bbox: Optional[Tuple[float, float, float, float]] = None
        to_bbox: Optional[Tuple[float, float, float, float]] = None
        if from_anchor is None:
            if seen_ids.get(arrow.from_id, 0) == 0:
                raise ValueError(f'diag:arrow from="{arrow.from_id}" id not found')
            if seen_ids.get(arrow.from_id, 0) > 1:
                raise ValueError(f'diag:arrow from="{arrow.from_id}" is duplicated')
            from_bbox = bbox_by_id.get(arrow.from_id)
            if from_bbox is None:
                raise ValueError(f'diag:arrow from="{arrow.from_id}" has no measurable bbox')

        if to_anchor is None:
            if seen_ids.get(arrow.to_id, 0) == 0:
                raise ValueError(f'diag:arrow to="{arrow.to_id}" id not found')
            if seen_ids.get(arrow.to_id, 0) > 1:
                raise ValueError(f'diag:arrow to="{arrow.to_id}" is duplicated')
            to_bbox = bbox_by_id.get(arrow.to_id)
            if to_bbox is None:
                raise ValueError(f'diag:arrow to="{arrow.to_id}" has no measurable bbox')

        if from_anchor is not None and to_anchor is not None:
            p_from, p_to = from_anchor, to_anchor
        elif from_anchor is not None and to_bbox is not None:
            p_from = from_anchor
            p_to = _point_on_bbox_toward(to_bbox, from_anchor)
        elif to_anchor is not None and from_bbox is not None:
            p_from = _point_on_bbox_toward(from_bbox, to_anchor)
            p_to = to_anchor
        else:
            assert from_bbox is not None and to_bbox is not None
            p_from, p_to = _resolve_arrow_points(from_bbox, to_bbox)

        target_container = slot_nodes.get(arrow.slot_id, svg_root)
        local_from, local_to = p_from, p_to
        if target_container is not svg_root:
            ctm = _container_ctm(target_container, parent_by_node)
            inv = _invert_affine(ctm)
            if inv is not None:
                local_from = _apply_affine(inv, p_from)
                local_to = _apply_affine(inv, p_to)
            else:
                target_container = svg_root

        line_attrs = {
            "x1": _fmt(local_from[0]),
            "y1": _fmt(local_from[1]),
            "x2": _fmt(local_to[0]),
            "y2": _fmt(local_to[1]),
        }
        line_attrs.update(arrow.passthrough_attrs)
        line_attrs.setdefault("stroke", "#555")
        line_attrs.setdefault("stroke-width", "1")

        if "marker-end" not in line_attrs and "marker-start" not in line_attrs:
            if default_marker_id is None:
                default_marker_id = _ensure_default_arrow_marker(svg_root)
            line_attrs["marker-end"] = f"url(#{default_marker_id})"

        line = ET.Element(_q("line"), line_attrs)
        target_container.append(line)

        if arrow.label:
            _emit_arrow_label(target_container, arrow, local_from, local_to)

    for node in slot_nodes.values():
        if "data-diag-arrow-slot" in node.attrib:
            del node.attrib["data-diag-arrow-slot"]


def _ensure_default_arrow_marker(svg_root: ET.Element) -> str:
    existing_ids = {node.get("id") for node in svg_root.iter() if node.get("id")}
    marker_id = "diag-arrow-default"
    if marker_id in existing_ids:
        marker_id = "diag-arrow-default-1"
        idx = 1
        while marker_id in existing_ids:
            idx += 1
            marker_id = f"diag-arrow-default-{idx}"

    defs = svg_root.find(_q("defs"))
    if defs is None:
        defs = ET.Element(_q("defs"))
        svg_root.insert(0, defs)

    marker = ET.Element(
        _q("marker"),
        {
            "id": marker_id,
            "viewBox": "0 0 10 10",
            "refX": "9",
            "refY": "5",
            "markerWidth": "6",
            "markerHeight": "6",
            "orient": "auto",
        },
    )
    ET.SubElement(marker, _q("path"), {"d": "M 0 0 L 10 5 L 0 10 z", "fill": "#555"})
    defs.append(marker)
    return marker_id


def _resolve_arrow_points(
    from_bbox: Tuple[float, float, float, float],
    to_bbox: Tuple[float, float, float, float],
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    centerline = _resolve_arrow_points_centerline(from_bbox, to_bbox)
    if centerline is not None:
        return centerline

    candidates = ["right", "left", "bottom", "top", "center"]
    from_edges = candidates
    to_edges = candidates

    best: Optional[Tuple[float, int, Tuple[float, float], Tuple[float, float]]] = None
    tie_break_order = {name: idx for idx, name in enumerate(candidates)}
    for fe in from_edges:
        for te in to_edges:
            p1, p2 = _arrow_points_for_edges(from_bbox, to_bbox, fe, te)
            dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            tie = tie_break_order[fe] * 10 + tie_break_order[te]
            if best is None or dist < best[0] - 1e-9 or (
                math.isclose(dist, best[0], abs_tol=1e-9) and tie < best[1]
            ):
                best = (dist, tie, p1, p2)

    assert best is not None
    return best[2], best[3]


def _resolve_arrow_points_centerline(
    from_bbox: Tuple[float, float, float, float],
    to_bbox: Tuple[float, float, float, float],
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    c1 = _bbox_center(from_bbox)
    c2 = _bbox_center(to_bbox)
    if math.isclose(c1[0], c2[0], abs_tol=1e-9) and math.isclose(c1[1], c2[1], abs_tol=1e-9):
        return None
    p1 = _ray_rect_intersection(c1, c2, from_bbox)
    p2 = _ray_rect_intersection(c2, c1, to_bbox)
    if p1 is None or p2 is None:
        return None
    return p1, p2


def _ray_rect_intersection(
    origin: Tuple[float, float],
    toward: Tuple[float, float],
    bbox: Tuple[float, float, float, float],
) -> Optional[Tuple[float, float]]:
    ox, oy = origin
    tx, ty = toward
    dx = tx - ox
    dy = ty - oy
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return None

    left, top, right, bottom = bbox
    candidates: List[Tuple[float, float, float]] = []

    if abs(dx) > 1e-12:
        for x in (left, right):
            t = (x - ox) / dx
            if t <= 1e-12:
                continue
            y = oy + t * dy
            if top - 1e-9 <= y <= bottom + 1e-9:
                candidates.append((t, x, y))

    if abs(dy) > 1e-12:
        for y in (top, bottom):
            t = (y - oy) / dy
            if t <= 1e-12:
                continue
            x = ox + t * dx
            if left - 1e-9 <= x <= right + 1e-9:
                candidates.append((t, x, y))

    if not candidates:
        return None

    t, x, y = min(candidates, key=lambda item: item[0])
    del t
    return (x, y)


def _arrow_points_for_edges(
    from_bbox: Tuple[float, float, float, float],
    to_bbox: Tuple[float, float, float, float],
    from_edge: str,
    to_edge: str,
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    if from_edge == "center" and to_edge == "center":
        return _bbox_center(from_bbox), _bbox_center(to_bbox)
    if from_edge == "center":
        p1 = _bbox_center(from_bbox)
        p2 = _nearest_point_on_edge(to_bbox, to_edge, p1)
        return p1, p2
    if to_edge == "center":
        p2 = _bbox_center(to_bbox)
        p1 = _nearest_point_on_edge(from_bbox, from_edge, p2)
        return p1, p2

    seg1 = _edge_segment(from_bbox, from_edge)
    seg2 = _edge_segment(to_bbox, to_edge)
    return _closest_points_on_segments(seg1[0], seg1[1], seg2[0], seg2[1])


def _emit_arrow_label(
    svg_root: ET.Element,
    arrow: _ArrowSpec,
    p_from: Tuple[float, float],
    p_to: Tuple[float, float],
) -> None:
    dx = p_to[0] - p_from[0]
    dy = p_to[1] - p_from[1]
    seg_len = max(math.hypot(dx, dy), 1e-9)
    mid_x = (p_from[0] + p_to[0]) / 2.0
    mid_y = (p_from[1] + p_to[1]) / 2.0

    # Pick the normal that points more upward in screen coordinates to keep labels off the line.
    n1 = (dy / seg_len, -dx / seg_len)
    n2 = (-dy / seg_len, dx / seg_len)
    nx, ny = n1 if n1[1] <= n2[1] else n2
    # Keep labels close to the line, but never directly on top of it.
    # Baseline placement plus a small normal offset gives a cleaner, lighter gap.
    label_offset = max(2.0, arrow.label_size * 0.25)
    lx = mid_x + nx * label_offset
    ly = mid_y + ny * label_offset

    angle = math.degrees(math.atan2(dy, dx))
    # Keep text orientation readable (never upside-down).
    if angle > 90.0:
        angle -= 180.0
    elif angle < -90.0:
        angle += 180.0
    attrs = {
        "x": _fmt(lx),
        "y": _fmt(ly),
        "text-anchor": "middle",
        "font-size": _fmt(arrow.label_size),
        "fill": arrow.label_fill,
        "dominant-baseline": "alphabetic",
    }
    if abs(angle) >= 15.0:
        attrs["transform"] = f"rotate({_fmt(angle)} {_fmt(lx)} {_fmt(ly)})"
    text = ET.Element(_q("text"), attrs)
    text.text = arrow.label
    svg_root.append(text)


def _bbox_center(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    left, top, right, bottom = bbox
    return (left + right) / 2.0, (top + bottom) / 2.0


def _anchor_point_from_bbox(
    bbox: Tuple[float, float, float, float], side: str
) -> Tuple[float, float]:
    left, top, right, bottom = bbox
    mid_x = (left + right) / 2.0
    mid_y = (top + bottom) / 2.0
    if side == "top":
        return (mid_x, top)
    if side == "bottom":
        return (mid_x, bottom)
    if side == "left":
        return (left, mid_y)
    if side == "right":
        return (right, mid_y)
    return (mid_x, mid_y)


def _point_on_bbox_toward(
    bbox: Tuple[float, float, float, float], toward: Tuple[float, float]
) -> Tuple[float, float]:
    center = _bbox_center(bbox)
    point = _ray_rect_intersection(center, toward, bbox)
    if point is not None:
        return point
    return center


def _edge_segment(
    bbox: Tuple[float, float, float, float], edge: str
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    left, top, right, bottom = bbox
    if edge == "left":
        return (left, top), (left, bottom)
    if edge == "right":
        return (right, top), (right, bottom)
    if edge == "top":
        return (left, top), (right, top)
    if edge == "bottom":
        return (left, bottom), (right, bottom)
    raise ValueError(f"invalid edge for segment resolution: {edge}")


def _nearest_point_on_edge(
    bbox: Tuple[float, float, float, float], edge: str, point: Tuple[float, float]
) -> Tuple[float, float]:
    (x1, y1), (x2, y2) = _edge_segment(bbox, edge)
    px, py = point
    vx = x2 - x1
    vy = y2 - y1
    seg_len_sq = vx * vx + vy * vy
    if seg_len_sq <= 1e-12:
        return (x1, y1)
    t = ((px - x1) * vx + (py - y1) * vy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    return (x1 + t * vx, y1 + t * vy)


def _closest_points_on_segments(
    p1: Tuple[float, float],
    q1: Tuple[float, float],
    p2: Tuple[float, float],
    q2: Tuple[float, float],
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    # Standard closest-points algorithm for two 2D segments.
    x1, y1 = p1
    x2, y2 = q1
    x3, y3 = p2
    x4, y4 = q2

    ux, uy = x2 - x1, y2 - y1
    vx, vy = x4 - x3, y4 - y3
    wx, wy = x1 - x3, y1 - y3

    a = ux * ux + uy * uy
    b = ux * vx + uy * vy
    c = vx * vx + vy * vy
    d = ux * wx + uy * wy
    e = vx * wx + vy * wy

    denom = a * c - b * b
    s_n, s_d = 0.0, denom
    t_n, t_d = 0.0, denom

    if denom < 1e-12:
        s_n = 0.0
        s_d = 1.0
        t_n = e
        t_d = c
    else:
        s_n = b * e - c * d
        t_n = a * e - b * d
        if s_n < 0.0:
            s_n = 0.0
            t_n = e
            t_d = c
        elif s_n > s_d:
            s_n = s_d
            t_n = e + b
            t_d = c

    if t_n < 0.0:
        t_n = 0.0
        if -d < 0.0:
            s_n = 0.0
        elif -d > a:
            s_n = s_d
        else:
            s_n = -d
            s_d = a
    elif t_n > t_d:
        t_n = t_d
        if (-d + b) < 0.0:
            s_n = 0
        elif (-d + b) > a:
            s_n = s_d
        else:
            s_n = -d + b
            s_d = a

    sc = 0.0 if abs(s_n) < 1e-12 else s_n / s_d
    tc = 0.0 if abs(t_n) < 1e-12 else t_n / t_d

    c1 = (x1 + sc * ux, y1 + sc * uy)
    c2 = (x3 + tc * vx, y3 + tc * vy)
    return c1, c2


def _container_ctm(
    node: ET.Element, parent_by_node: Dict[ET.Element, ET.Element]
) -> Tuple[float, float, float, float, float, float]:
    lineage: List[ET.Element] = []
    cursor: Optional[ET.Element] = node
    while cursor is not None:
        lineage.append(cursor)
        cursor = parent_by_node.get(cursor)
    lineage.reverse()

    m = _identity_affine()
    for elem in lineage:
        transform = elem.get("transform")
        if not transform:
            continue
        m = _mul_affine(m, _parse_transform_affine(transform))
    return m


def _identity_affine() -> Tuple[float, float, float, float, float, float]:
    return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _mul_affine(
    m1: Tuple[float, float, float, float, float, float],
    m2: Tuple[float, float, float, float, float, float],
) -> Tuple[float, float, float, float, float, float]:
    # Composition m = m1 ∘ m2
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _apply_affine(
    m: Tuple[float, float, float, float, float, float], p: Tuple[float, float]
) -> Tuple[float, float]:
    a, b, c, d, e, f = m
    x, y = p
    return (a * x + c * y + e, b * x + d * y + f)


def _invert_affine(
    m: Tuple[float, float, float, float, float, float]
) -> Optional[Tuple[float, float, float, float, float, float]]:
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    inv_det = 1.0 / det
    ai = d * inv_det
    bi = -b * inv_det
    ci = -c * inv_det
    di = a * inv_det
    ei = -(ai * e + ci * f)
    fi = -(bi * e + di * f)
    return (ai, bi, ci, di, ei, fi)


def _parse_transform_affine(
    transform: str,
) -> Tuple[float, float, float, float, float, float]:
    m = _identity_affine()
    for fn, arg_text in re.findall(r"([a-zA-Z]+)\s*\(([^)]*)\)", transform):
        values = [
            float(chunk)
            for chunk in re.split(r"[,\s]+", arg_text.strip())
            if chunk
        ]
        name = fn.lower()
        if name == "matrix" and len(values) == 6:
            t = (values[0], values[1], values[2], values[3], values[4], values[5])
        elif name == "translate" and values:
            tx = values[0]
            ty = values[1] if len(values) > 1 else 0.0
            t = (1.0, 0.0, 0.0, 1.0, tx, ty)
        elif name == "scale" and values:
            sx = values[0]
            sy = values[1] if len(values) > 1 else sx
            t = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif name == "rotate" and values:
            angle = math.radians(values[0])
            cos_v = math.cos(angle)
            sin_v = math.sin(angle)
            if len(values) >= 3:
                cx = values[1]
                cy = values[2]
                t = _mul_affine(
                    _mul_affine((1.0, 0.0, 0.0, 1.0, cx, cy), (cos_v, sin_v, -sin_v, cos_v, 0.0, 0.0)),
                    (1.0, 0.0, 0.0, 1.0, -cx, -cy),
                )
            else:
                t = (cos_v, sin_v, -sin_v, cos_v, 0.0, 0.0)
        elif name == "skewx" and len(values) == 1:
            t = (1.0, 0.0, math.tan(math.radians(values[0])), 1.0, 0.0, 0.0)
        elif name == "skewy" and len(values) == 1:
            t = (1.0, math.tan(math.radians(values[0])), 0.0, 1.0, 0.0, 0.0)
        else:
            continue
        m = _mul_affine(m, t)
    return m


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
    min_x = raw_min_x
    min_y = raw_min_y
    max_x = raw_max_x
    max_y = raw_max_y
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


def _apply_resvg_bounds(
    svg_root: ET.Element,
    original_width: Optional[str],
    original_height: Optional[str],
    font_paths: List[str],
    diagram_padding: float = 0.0,
) -> None:
    svg_text = ET.tostring(svg_root, encoding="unicode")
    measurement = _measure_svg(svg_text, font_paths)
    overall = measurement.get("overall")
    if not overall:
        return
    left, top, right, bottom = overall
    min_x = left
    min_y = top
    width_needed = max(right - left, 0.0)
    height_needed = max(bottom - top, 0.0)
    if diagram_padding > 0:
        min_x -= diagram_padding
        min_y -= diagram_padding
        width_needed += 2 * diagram_padding
        height_needed += 2 * diagram_padding
    if width_needed == 0.0 and height_needed == 0.0:
        return
    svg_root.set(
        "viewBox",
        f"{_fmt(min_x)} {_fmt(min_y)} {_fmt(width_needed)} {_fmt(height_needed)}",
    )
    _ensure_dimension(svg_root, "width", width_needed, original_width)
    _ensure_dimension(svg_root, "height", height_needed, original_height)


def _apply_background_rect(
    src_root: ET.Element, svg_root: ET.Element, diag_ns: str
) -> None:
    raw_value = src_root.get(_qual(diag_ns, "background"))
    color = raw_value.strip() if raw_value else "#fff"
    if not color:
        color = "#fff"
    if color.lower() in {"none", "transparent"}:
        return

    min_x = 0.0
    min_y = 0.0
    width: Optional[float] = None
    height: Optional[float] = None

    view_box = svg_root.get("viewBox")
    if view_box:
        parts = re.split(r"[ ,]+", view_box.strip())
        if len(parts) >= 4:
            try:
                min_x = float(parts[0])
                min_y = float(parts[1])
                width = float(parts[2])
                height = float(parts[3])
            except ValueError:
                width = None
                height = None

    if width is None or height is None:
        width = _parse_length(svg_root.get("width"), None)
        height = _parse_length(svg_root.get("height"), None)
        min_x = 0.0
        min_y = 0.0

    if width is None or height is None:
        return

    rect_attrs = {
        "x": _fmt(min_x),
        "y": _fmt(min_y),
        "width": _fmt(width),
        "height": _fmt(height),
        "fill": color,
    }
    svg_root.insert(0, ET.Element(_q("rect"), rect_attrs))


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
    class_style_rules: List[_ClassStyleRule],
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
            class_style_rules=class_style_rules,
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


def _infer_font_size(node: ET.Element, class_style_rules: List[_ClassStyleRule]) -> float:
    if "font-size" in node.attrib:
        return _parse_length(node.attrib["font-size"], 16.0)
    style = node.get("style")
    if style:
        match = re.search(r"font-size:\s*([0-9.]+)", style)
        if match:
            return float(match.group(1))
    class_font_size = _class_style_value(node, class_style_rules, "font-size")
    if class_font_size:
        parsed = _parse_length(class_font_size, None)
        if parsed is not None:
            return float(parsed)
    return 16.0


def _font_family_info(
    node: ET.Element, diag_ns: str, class_style_rules: List[_ClassStyleRule]
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
    if not family:
        family = _class_style_value(node, class_style_rules, "font-family")
    if family:
        family = _strip_quotes(family.strip())
    return family, diag_font_path


def _collect_class_style_rules(root: ET.Element) -> List[_ClassStyleRule]:
    rules: List[_ClassStyleRule] = []
    for style_node in root.iter(_q("style")):
        css_text = "".join(style_node.itertext())
        if not css_text:
            continue
        for selector_text, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css_text, flags=re.MULTILINE):
            declarations: Dict[str, str] = {}
            for decl in body.split(";"):
                if ":" not in decl:
                    continue
                key, value = decl.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                if key and value:
                    declarations[key] = value
            if not declarations:
                continue
            selectors = [s.strip() for s in selector_text.split(",") if s.strip()]
            for selector in selectors:
                # Support simple class selectors like `.x` or `text.x`.
                for class_name in re.findall(r"\.([A-Za-z_][A-Za-z0-9_-]*)", selector):
                    rules.append(
                        _ClassStyleRule(class_name=class_name, declarations=declarations.copy())
                    )
    return rules


def _class_style_value(
    node: ET.Element, class_style_rules: List[_ClassStyleRule], prop: str
) -> Optional[str]:
    class_attr = node.get("class") or ""
    if not class_attr:
        return None
    class_names = set(part for part in class_attr.split() if part)
    if not class_names:
        return None
    resolved: Optional[str] = None
    for rule in class_style_rules:
        if rule.class_name in class_names and prop in rule.declarations:
            resolved = rule.declarations[prop]
    return resolved


def _collect_font_paths(node: ET.Element, diag_ns: str) -> List[str]:
    paths: set[str] = set()
    for elem in node.iter():
        diag_font_path = elem.get(_qual(diag_ns, "font-path"))
        if diag_font_path:
            paths.add(str(Path(diag_font_path).expanduser()))
    return sorted(paths)


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


__all__ = ["diagramagic", "render_png", "FocusNotFoundError"]
