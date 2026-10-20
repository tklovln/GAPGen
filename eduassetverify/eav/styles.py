"""Visual styles.

A style changes appearance only, never scene content, so the same scene rendered in two
styles must receive the same verdict (the style-invariance test). Every style lists the
colors it uses; the independent raster validator relies on that palette, never on the
scene specification.

DEV styles appear in the development split and the in-domain / unseen-template / error-
combination test splits. UNSEEN styles appear only in the unseen-style test split.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Object categories shared by the counting and spatial domains.
COUNT_CATEGORIES = ["apple", "star", "fish", "heart", "flower", "ball"]
SHAPE_CATEGORIES = ["star", "square", "circle", "triangle", "heart"]
ALL_CATEGORIES = sorted(set(COUNT_CATEGORIES) | set(SHAPE_CATEGORIES) | {"arrow"})


@dataclass(frozen=True)
class Style:
    name: str
    role: str                  # "dev" or "unseen"
    background: str
    outline: str
    line_width: float          # px
    colored_fill: str          # colored fraction parts
    plain_fill: str            # uncolored fraction parts
    text_color: str
    object_colors: dict = field(default_factory=dict)   # category -> body color
    figure_colors: tuple = ()  # symmetry-figure elements
    font_family: str = "DejaVu Sans"
    sketch: bool = False       # hand-drawn wobble (matplotlib xkcd path effects)
    texture: bool = False      # paper-grain background

    def object_color(self, category: str) -> str:
        return self.object_colors[category]


_BASE_OBJECTS = {
    "apple": "#e53935", "star": "#fbc02d", "fish": "#1e88e5", "heart": "#ec407a",
    "flower": "#8e24aa", "ball": "#43a047", "square": "#00897b", "circle": "#fb8c00",
    "triangle": "#00acc1", "arrow": "#3949ab",
}
_PASTEL_OBJECTS = {
    "apple": "#f28b82", "star": "#fff176", "fish": "#81d4fa", "heart": "#f8bbd0",
    "flower": "#b39ddb", "ball": "#a5d6a7", "square": "#80cbc4", "circle": "#ffab91",
    "triangle": "#c5e1a5", "arrow": "#9fa8da",
}
_BRIGHT_OBJECTS = {
    "apple": "#ff5252", "star": "#ffd740", "fish": "#40c4ff", "heart": "#ff4081",
    "flower": "#e040fb", "ball": "#69f0ae", "square": "#64ffda", "circle": "#ff6e40",
    "triangle": "#b2ff59", "arrow": "#8c9eff",
}

DEV_STYLES = [
    Style("flat_blue", "dev", "#ffffff", "#212121", 2.5, "#42a5f5", "#ffffff", "#212121",
          _BASE_OBJECTS, ("#ef5350", "#42a5f5", "#66bb6a", "#ffa726")),
    Style("flat_orange", "dev", "#ffffff", "#212121", 2.5, "#ff9800", "#ffffff", "#212121",
          _BASE_OBJECTS, ("#ab47bc", "#26a69a", "#ffca28", "#5c6bc0")),
    Style("flat_green", "dev", "#fafafa", "#37474f", 3.0, "#66bb6a", "#ffffff", "#263238",
          _BASE_OBJECTS, ("#ec407a", "#29b6f6", "#9ccc65", "#ff7043")),
]

UNSEEN_STYLES = [
    Style("dark", "unseen", "#1a2238", "#e0e0e0", 2.5, "#ffca28", "#3a4466", "#f5f5f5",
          _BRIGHT_OBJECTS, ("#ff5252", "#40c4ff", "#69f0ae", "#ffd740")),
    Style("pastel_thick", "unseen", "#fffdf5", "#5d4037", 6.0, "#f48fb1", "#ffffff", "#4e342e",
          _PASTEL_OBJECTS, ("#ce93d8", "#80deea", "#c5e1a5", "#ffcc80")),
    Style("sketch", "unseen", "#ffffff", "#212121", 2.5, "#7e57c2", "#ffffff", "#212121",
          _BASE_OBJECTS, ("#ef5350", "#42a5f5", "#66bb6a", "#ffa726"), sketch=True),
    Style("paper", "unseen", "#eadcb8", "#3e2723", 2.5, "#26a69a", "#ffffff", "#3e2723",
          _BASE_OBJECTS, ("#d84315", "#1565c0", "#2e7d32", "#f9a825"), texture=True),
]

STYLES = {s.name: s for s in DEV_STYLES + UNSEEN_STYLES}


def hex_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
