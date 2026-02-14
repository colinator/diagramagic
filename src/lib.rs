use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use pyo3::types::{PyDict, PyList};
use resvg::tiny_skia;
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

#[pyfunction]
#[pyo3(signature = (svg_text, scale=1.0, font_paths=None))]
fn render_svg<'py>(
    py: Python<'py>,
    svg_text: &str,
    scale: f32,
    font_paths: Option<Vec<String>>,
) -> PyResult<&'py PyBytes> {
    let png = render_internal(svg_text, scale, font_paths).map_err(|e| {
        PyValueError::new_err(e.to_string())
    })?;
    Ok(PyBytes::new(py, &png))
}

#[pymodule]
fn _diagramagic_resvg(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(measure_svg, m)?)?;
    m.add_function(wrap_pyfunction!(render_svg, m)?)?;
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
    #[error("invalid scale: {0} (must be > 0)")]
    InvalidScale(f32),
    #[error("unable to compute render size from SVG")]
    MissingSize,
    #[error("failed to allocate raster surface")]
    SurfaceAlloc,
    #[error("failed to encode PNG")]
    EncodePng,
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

fn render_internal(
    svg_text: &str,
    scale: f32,
    font_paths: Option<Vec<String>>,
) -> Result<Vec<u8>, MeasureError> {
    if scale <= 0.0 {
        return Err(MeasureError::InvalidScale(scale));
    }

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

    let fit_to = usvg::FitTo::Zoom(scale);
    let pixmap_size = fit_to
        .fit_to(rtree.size.to_screen_size())
        .ok_or(MeasureError::MissingSize)?;

    let mut pixmap = tiny_skia::Pixmap::new(pixmap_size.width(), pixmap_size.height())
        .ok_or(MeasureError::SurfaceAlloc)?;

    let rendered = resvg::render(
        &rtree,
        fit_to,
        tiny_skia::Transform::default(),
        pixmap.as_mut(),
    );
    if rendered.is_none() {
        return Err(MeasureError::MissingSize);
    }

    pixmap.encode_png().map_err(|_| MeasureError::EncodePng)
}
