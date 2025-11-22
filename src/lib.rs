use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use resvg::usvg;
use usvg::NodeExt;
use usvg_text_layout::{fontdb, TreeTextToPath};

#[pyfunction]
#[pyo3(signature = (svg_text, font_paths=None))]
fn measure_svg(
    py: Python,
    svg_text: &str,
    font_paths: Option<Vec<String>>,
) -> PyResult<PyObject> {
    let result = measure_internal(svg_text, font_paths).map_err(|e| {
        PyValueError::new_err(e.to_string())
    })?;

    let py_nodes = PyList::empty(py);
    for info in result.nodes {
        let dict = PyDict::new(py);
        dict.set_item("index", info.index)?;
        if let Some(id) = info.id {
            dict.set_item("id", id)?;
        }
        dict.set_item("kind", info.kind)?;
        dict.set_item("bbox", (info.left, info.top, info.right, info.bottom))?;
        py_nodes.append(dict)?;
    }

    let py_result = PyDict::new(py);
    if let Some(overall) = result.overall_bbox {
        py_result.set_item(
            "overall",
            (overall.left, overall.top, overall.right, overall.bottom),
        )?;
    } else {
        py_result.set_item("overall", py.None())?;
    }
    py_result.set_item("nodes", py_nodes)?;
    Ok(py_result.into())
}

#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pymodule]
fn _diagramagic_resvg(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(measure_svg, m)?)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    Ok(())
}

struct MeasureResult {
    overall_bbox: Option<Bounds>,
    nodes: Vec<NodeInfo>,
}

#[derive(Clone, Copy)]
struct Bounds {
    left: f64,
    top: f64,
    right: f64,
    bottom: f64,
}

impl Bounds {
    fn from_rect(rect: usvg::Rect) -> Self {
        Self {
            left: rect.x() as f64,
            top: rect.y() as f64,
            right: (rect.x() + rect.width()) as f64,
            bottom: (rect.y() + rect.height()) as f64,
        }
    }

    fn extend(&mut self, other: Bounds) {
        self.left = self.left.min(other.left);
        self.top = self.top.min(other.top);
        self.right = self.right.max(other.right);
        self.bottom = self.bottom.max(other.bottom);
    }
}

struct NodeInfo {
    index: usize,
    id: Option<String>,
    kind: String,
    left: f64,
    top: f64,
    right: f64,
    bottom: f64,
}

#[derive(thiserror::Error, Debug)]
enum MeasureError {
    #[error("failed to parse SVG: {0}")]
    Parse(String),
}

fn measure_internal(
    svg_text: &str,
    font_paths: Option<Vec<String>>,
) -> Result<MeasureResult, MeasureError> {
    let opt = usvg::Options::default();
    let mut db = fontdb::Database::new();
    db.load_system_fonts();
    if let Some(paths) = font_paths {
        for path in paths {
            if let Err(err) = db.load_font_file(&path) {
                eprintln!("warning: failed to load font {}: {}", path, err);
            }
        }
    }

    let mut rtree = usvg::Tree::from_data(svg_text.as_bytes(), &opt).map_err(|e| {
        MeasureError::Parse(format!("{:?}", e))
    })?;
    rtree.convert_text(&db);

    let mut overall: Option<Bounds> = None;
    let mut nodes = Vec::new();

    for (idx, node) in rtree.root.descendants().enumerate() {
        if let Some(bbox) = node.calculate_bbox().and_then(|r| r.to_rect()) {
            let bounds = Bounds::from_rect(bbox);
            if let Some(current) = &mut overall {
                current.extend(bounds);
            } else {
                overall = Some(bounds);
            }
            let kind = format!("{:?}", *node.borrow());
            let id_ref = node.id();
            nodes.push(NodeInfo {
                index: idx,
                id: if id_ref.is_empty() {
                    None
                } else {
                    Some(id_ref.to_string())
                },
                kind,
                left: bounds.left,
                top: bounds.top,
                right: bounds.right,
                bottom: bounds.bottom,
            });
        }
    }

    Ok(MeasureResult {
        overall_bbox: overall,
        nodes,
    })
}
