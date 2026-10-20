"""Matplotlib renderer: scene primitives -> 512x512 PNG (pixels for verifiers) and SVG.

Domains compile their scenes into a short list of drawing primitives; this module draws
them in a given style. Coordinates are image pixels, x to the right and y downward.
Rendering is deterministic for a given scene, style and library version.
"""
from __future__ import annotations

import io
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import patches  # noqa: E402
from PIL import Image  # noqa: E402

from .styles import Style, hex_rgb  # noqa: E402

CANVAS = 512
DPI = 100
matplotlib.rcParams["svg.hashsalt"] = "eduassetverify"


# --------------------------------------------------------------------------- shapes

def star_points(cx, cy, size, points=5, inner=0.4):
    r_out, r_in = 0.5 * size, 0.5 * size * inner
    pts = []
    for i in range(2 * points):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / points
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def heart_points(cx, cy, size, n=80):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    x = 16 * np.sin(t) ** 3
    y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
    k = size / 34.0
    return list(zip(cx + k * x, cy - k * y + 0.05 * size))


def triangle_points(cx, cy, size, direction="up"):
    r = 0.5 * size
    base = {"up": -90, "down": 90, "left": 180, "right": 0}[direction]
    return [(cx + r * math.cos(math.radians(base + 120 * i)),
             cy + r * math.sin(math.radians(base + 120 * i))) for i in range(3)]


def diamond_points(cx, cy, size):
    r = 0.5 * size
    return [(cx, cy - r), (cx + 0.75 * r, cy), (cx, cy + r), (cx - 0.75 * r, cy)]


def arrow_points(cx, cy, size, direction="up"):
    s = size
    up = [(-0.1, 0.45), (-0.1, -0.02), (-0.3, -0.02), (0.0, -0.5),
          (0.3, -0.02), (0.1, -0.02), (0.1, 0.45)]
    rot = {"up": 0, "right": 90, "down": 180, "left": 270}[direction]
    a = math.radians(rot)
    out = []
    for x, y in up:   # rotate clockwise on screen (y down)
        out.append((cx + s * (x * math.cos(a) - y * math.sin(a)),
                    cy + s * (x * math.sin(a) + y * math.cos(a))))
    return out


def object_bbox(category: str, cx: float, cy: float, size: float) -> list[float]:
    """Axis-aligned box of a drawn object, used for localization ground truth."""
    h = 0.5 * size
    return [cx - h, cy - h, cx + h, cy + h]


# --------------------------------------------------------------------------- drawing

def _poly(ax, pts, fc, ec, lw, z=3):
    ax.add_patch(patches.Polygon(pts, closed=True, facecolor=fc, edgecolor=ec, linewidth=lw,
                                 joinstyle="round", zorder=z))


def _draw_object(ax, prim: dict, style: Style):
    cat, cx, cy, s = prim["category"], prim["cx"], prim["cy"], prim["size"]
    ec, lw = style.outline, style.line_width * 0.8
    fc = style.object_color(cat)
    if cat == "apple":
        ax.add_patch(patches.Rectangle((cx - 0.04 * s, cy - 0.52 * s), 0.08 * s, 0.22 * s,
                                       facecolor="#5d4037", edgecolor=ec, linewidth=lw * 0.6, zorder=2))
        ax.add_patch(patches.Ellipse((cx + 0.15 * s, cy - 0.40 * s), 0.30 * s, 0.14 * s, angle=-30,
                                     facecolor="#1b5e20", edgecolor=ec, linewidth=lw * 0.6, zorder=2))
        ax.add_patch(patches.Circle((cx, cy + 0.06 * s), 0.42 * s, facecolor=fc, edgecolor=ec,
                                    linewidth=lw, zorder=3))
    elif cat == "star":
        _poly(ax, star_points(cx, cy, s), fc, ec, lw)
    elif cat == "fish":
        tail = [(cx - 0.22 * s, cy), (cx - 0.5 * s, cy - 0.24 * s), (cx - 0.5 * s, cy + 0.24 * s)]
        _poly(ax, tail, fc, ec, lw, z=2)
        ax.add_patch(patches.Ellipse((cx + 0.08 * s, cy), 0.80 * s, 0.48 * s, facecolor=fc,
                                     edgecolor=ec, linewidth=lw, zorder=3))
        # tail fill again on top: the body outline no longer cuts the fish in two
        ax.add_patch(patches.Polygon(tail, closed=True, facecolor=fc, edgecolor="none", zorder=3.5))
        ax.add_patch(patches.Circle((cx + 0.30 * s, cy - 0.06 * s), 0.06 * s, facecolor="#ffffff",
                                    edgecolor=ec, linewidth=lw * 0.5, zorder=4))
    elif cat == "heart":
        _poly(ax, heart_points(cx, cy, s), fc, ec, lw)
    elif cat == "flower":
        for i in range(5):
            a = math.radians(-90 + 72 * i)
            ax.add_patch(patches.Circle((cx + 0.27 * s * math.cos(a), cy + 0.27 * s * math.sin(a)),
                                        0.2 * s, facecolor=fc, edgecolor=ec, linewidth=lw * 0.7, zorder=3))
        ax.add_patch(patches.Circle((cx, cy), 0.15 * s, facecolor="#ffffff", edgecolor=ec,
                                    linewidth=lw * 0.7, zorder=4))
    elif cat == "ball":
        ax.add_patch(patches.Circle((cx, cy), 0.44 * s, facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3))
        for th1, th2 in ((200, 340), (20, 160)):
            ax.add_patch(patches.Arc((cx, cy), 0.62 * s, 0.62 * s, theta1=th1, theta2=th2,
                                     edgecolor="#ffffff", linewidth=max(2.0, 0.05 * s), zorder=4))
    elif cat == "square":
        ax.add_patch(patches.Rectangle((cx - 0.4 * s, cy - 0.4 * s), 0.8 * s, 0.8 * s, facecolor=fc,
                                       edgecolor=ec, linewidth=lw, zorder=3))
    elif cat == "circle":
        ax.add_patch(patches.Circle((cx, cy), 0.42 * s, facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3))
    elif cat == "triangle":
        _poly(ax, triangle_points(cx, cy, s), fc, ec, lw)
    elif cat == "arrow":
        _poly(ax, arrow_points(cx, cy, s, prim.get("direction", "up")), fc, ec, lw)
    else:
        raise ValueError(f"unknown object category {cat!r}")


def _draw_fig_shape(ax, prim: dict, style: Style):
    kind, cx, cy, s = prim["shape"], prim["cx"], prim["cy"], prim["size"]
    fc = style.figure_colors[prim["color"] % len(style.figure_colors)]
    ec, lw = style.outline, style.line_width * 0.8
    if kind == "circle":
        ax.add_patch(patches.Circle((cx, cy), 0.45 * s, facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3))
    elif kind == "square":
        ax.add_patch(patches.Rectangle((cx - 0.42 * s, cy - 0.42 * s), 0.84 * s, 0.84 * s, facecolor=fc,
                                       edgecolor=ec, linewidth=lw, zorder=3))
    elif kind == "diamond":
        _poly(ax, diamond_points(cx, cy, s), fc, ec, lw)
    elif kind.startswith("triangle_"):
        _poly(ax, triangle_points(cx, cy, s, kind.split("_", 1)[1]), fc, ec, lw)
    else:
        raise ValueError(f"unknown figure shape {kind!r}")


def _texture(style: Style) -> np.ndarray:
    rng = np.random.default_rng(7)  # one fixed grain per style: texture is style, not content
    base = np.array(hex_rgb(style.background), dtype=float)
    noise = rng.normal(0, 6, (CANVAS, CANVAS, 1))
    blot = Image.fromarray(rng.normal(128, 40, (16, 16)).clip(0, 255).astype(np.uint8))
    blot = np.asarray(blot.resize((CANVAS, CANVAS), Image.BICUBIC), dtype=float)[..., None]
    blot = (blot - 128.0) / 40.0 * 5.0
    return np.clip(base + noise + blot, 0, 255).astype(np.uint8)


def render(primitives: list[dict], style: Style, svg_out=None) -> np.ndarray:
    """Draw primitives; return an (H, W, 3) uint8 array. `svg_out` (path or binary file) gets the SVG."""
    rc = {"font.family": style.font_family, "path.snap": False}   # exact mirror symmetry, no pixel snapping
    if style.sketch:
        rc["path.sketch"] = (1.6, 60.0, 2.0)
    with matplotlib.rc_context(rc):
        fig = plt.figure(figsize=(CANVAS / DPI, CANVAS / DPI), dpi=DPI)
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_xlim(0, CANVAS)
        ax.set_ylim(CANVAS, 0)
        ax.axis("off")
        fig.patch.set_facecolor(style.background)
        ax.set_facecolor(style.background)
        if style.texture:
            ax.imshow(_texture(style), extent=(0, CANVAS, CANVAS, 0), zorder=0, interpolation="nearest")
        for p in primitives:
            kind = p["kind"]
            if kind == "wedge":
                fc = style.colored_fill if p["colored"] else style.plain_fill
                ax.add_patch(patches.Wedge((p["cx"], p["cy"]), p["r"], p["theta1"], p["theta2"],
                                           facecolor=fc, edgecolor=style.outline,
                                           linewidth=style.line_width, zorder=2))
            elif kind == "rect":
                fc = style.colored_fill if p["colored"] else style.plain_fill
                ax.add_patch(patches.Rectangle((p["x"], p["y"]), p["w"], p["h"], facecolor=fc,
                                               edgecolor=style.outline, linewidth=style.line_width,
                                               zorder=2))
            elif kind == "text":
                ax.text(p["x"], p["y"], p["text"], fontsize=p["size"] * 72.0 / DPI, ha="center",
                        va="center", color=style.text_color, zorder=5)
            elif kind == "object":
                _draw_object(ax, p, style)
            elif kind == "fig_shape":
                _draw_fig_shape(ax, p, style)
            elif kind == "line":
                ax.plot([p["x0"], p["x1"]], [p["y0"], p["y1"]], color=style.outline,
                        linewidth=style.line_width, linestyle=(0, (8, 6)) if p.get("dashed") else "-",
                        zorder=1, solid_capstyle="butt")
            else:
                raise ValueError(f"unknown primitive {kind!r}")
        fig.canvas.draw()
        rgb = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
        if svg_out is not None:
            fig.savefig(svg_out, format="svg", metadata={"Date": None, "Creator": None})
        plt.close(fig)
    return rgb


def png_bytes(rgb: np.ndarray) -> bytes:
    """PNG without any metadata chunk: the file carries pixels and nothing else."""
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG", optimize=True)
    return buf.getvalue()
