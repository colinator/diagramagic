"""Public API for diagramagic."""
from .diagramagic import FocusNotFoundError, diagramagic, render_png

__all__ = ["diagramagic", "render_png", "FocusNotFoundError"]
