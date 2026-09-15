"""Render the GhostWorld icons.

    python tools/make_icon.py --app launcher     # -> assets/ghostworld.ico (+ .png)
    python tools/make_icon.py --app editor       # -> assets/ghostworld-editor.ico (+ .png)
    python tools/make_icon.py --app launcher --variant glyph --png-dir <dir>

Two icons, on purpose — the two windows sit next to each other in the taskbar:

* **launcher / game**: the 👻 emoji glyph, on a night-coloured rounded square.
  Emoji, because that is what the product's face is, and Qt6 renders it in full
  colour (Qt5 renders Segoe UI Emoji as a flat outline).
* **editor**: drawn with QPainter, not an emoji — a 3×3 grid of wall blocks taken
  from the editor's own palette (`editor/palette.py`), with one cell empty and
  ringed in the selection accent. It says "I edit a map", and because it is drawn
  per size rather than downscaled, 16 px is designed rather than shrunk.

The .ico holds every size, each rendered at that size (never rescaled from a big
one). Requires PySide6 + Pillow, and a real Qt platform: `QT_QPA_PLATFORM=offscreen`
renders no glyphs at all.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

EMOJI = "\U0001F47B"  # 👻
FONT_FAMILY = "Segoe UI Emoji"

# Night palette taken from the map files (`colors.sky`), so icon and game agree.
TILE_TOP = (26, 28, 44)
TILE_BOTTOM = (74, 82, 104)
TILE_RADIUS = 0.22  # fraction of the tile side

# The editor's own wall palette (editor/palette.py) and its selection accent,
# laid out the way the icon draws them: 3×3, centre cell left empty.
EDITOR_GRID = [
    [(100, 100, 150), (50, 200, 100), (150, 50, 50)],
    [(160, 140, 60), None, (50, 150, 150)],
    [(139, 69, 19), (70, 130, 180), (100, 100, 150)],
]
# The 16/24 px frames use four fat blocks instead of nine thin ones.
EDITOR_GRID_2 = [
    [(100, 100, 150), (50, 200, 100)],
    [(160, 140, 60), None],
]
EDITOR_ACCENT = (0, 170, 255)

APPS = {"launcher": "ghostworld", "editor": "ghostworld-editor"}
SIZES = [16, 24, 32, 48, 64, 128, 256]
MASTER = 1024
SUPERSAMPLE = 4


def _qapp():
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    if app.platformName() == "offscreen":
        raise SystemExit("offscreen Qt renders nothing; run on the real platform")
    return app


def render_glyph(char: str = EMOJI, size: int = MASTER, family: str = FONT_FAMILY):
    """The emoji glyph alone, cropped to its ink."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter

    _qapp()
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    font = QFont(family)
    font.setPixelSize(int(size * 0.8))
    p.setFont(font)
    p.setPen(QColor(0, 0, 0))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, char)
    p.end()

    import numpy as np

    alpha = np.frombuffer(img.constBits(), np.uint8).reshape(size, size, 4)[..., 3]
    ys, xs = np.nonzero(alpha > 8)
    if len(xs) == 0:
        raise SystemExit(f"glyph {char!r} drew nothing in {family!r}")
    return img.copy(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))


def _tile(painter, ss: int) -> None:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainterPath

    grad = QLinearGradient(0, 0, 0, ss)
    grad.setColorAt(0.0, QColor(*TILE_TOP))
    grad.setColorAt(1.0, QColor(*TILE_BOTTOM))
    radius = ss * TILE_RADIUS
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, ss, ss), radius, radius)
    painter.fillPath(path, QBrush(grad))


def paint_glyph_tile(glyph, size: int, variant: str):
    """The emoji on the tile (or bare, for `variant == "glyph"`)."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter

    ss = size * SUPERSAMPLE
    out = QImage(ss, ss, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    fill = 0.94
    if variant == "tile":
        # Small frames spend their pixels on the silhouette, not on padding.
        fill = 0.86 if size <= 24 else 0.72
        _tile(p, ss)

    box = ss * fill
    scale = min(box / glyph.width(), box / glyph.height())
    w, h = glyph.width() * scale, glyph.height() * scale
    p.drawImage(QRectF((ss - w) / 2, (ss - h) / 2, w, h), glyph)
    p.end()
    return out if ss == size else out.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def paint_editor(size: int):
    """A grid of wall blocks with one cell selected — drawn, not scaled down."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen

    ss = size * SUPERSAMPLE
    out = QImage(ss, ss, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing, True)
    _tile(p, ss)

    # Two rows below 24 px: four fat blocks beat nine thin ones at that size.
    n = 2 if size <= 24 else 3
    spec = EDITOR_GRID_2 if n == 2 else EDITOR_GRID
    margin = ss * (0.09 if n == 3 else 0.085)
    inner = ss - 2 * margin
    gap = ss * (0.05 if n == 3 else 0.06)
    block = (inner - gap * (n - 1)) / n
    radius = block * 0.18

    for row in range(n):
        for col in range(n):
            rgb = spec[row][col]
            if rgb is None:
                continue  # the selected cell shows the tile through it
            x = margin + col * (block + gap)
            y = margin + row * (block + gap)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(*rgb))
            p.drawRoundedRect(QRectF(x, y, block, block), radius, radius)

    sel_row = sel_col = 1          # centre cell of the 3×3, bottom-right of the 2×2
    x = margin + sel_col * (block + gap)
    y = margin + sel_row * (block + gap)
    if n == 3:
        # A ring reads as "this cell is selected" once there are pixels for it.
        ring = block + gap
        pen = QPen(QColor(*EDITOR_ACCENT))
        pen.setWidthF(max(1.0, ss * 0.035))
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(x - gap / 2, y - gap / 2, ring, ring), radius * 1.4, radius * 1.4)
    else:
        # At 16 px a 1 px ring is invisible: fill the cell with the accent instead.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(*EDITOR_ACCENT))
        p.drawRoundedRect(QRectF(x, y, block, block), radius, radius)
    p.end()
    return out if ss == size else out.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def build_frame(app: str, size: int, variant: str, glyph=None):
    return paint_editor(size) if app == "editor" else paint_glyph_tile(glyph, size, variant)


def save_qimage(img, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(path)):
        raise SystemExit(f"could not write {path}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--app", choices=sorted(APPS), default="launcher")
    ap.add_argument("--variant", choices=["tile", "glyph"], default="tile",
                    help="launcher only: tile = on the night square, glyph = bare emoji")
    ap.add_argument("--ico", default=None)
    ap.add_argument("--png-dir", default=None, help="also write <dir>/<name>-<size>.png")
    ap.add_argument("--sprite", default=None, help="also write this single 256 px PNG")
    ap.add_argument("--emoji", default=EMOJI, help="launcher glyph override")
    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    name = APPS[args.app]
    ico_path = Path(args.ico) if args.ico else root / "assets" / f"{name}.ico"
    if args.app == "editor" and args.variant != "tile":
        print("editor 图标是画出来的（方块网格），没有透明版", file=sys.stderr)
        return 2

    glyph = render_glyph(args.emoji) if args.app == "launcher" else None
    frames = {s: build_frame(args.app, s, args.variant, glyph) for s in SIZES}

    from PIL import Image

    def to_pil(img):
        return Image.frombytes("RGBA", (img.width(), img.height()),
                               img.constBits().tobytes(), "raw", "BGRA")

    pil = {s: to_pil(im) for s, im in frames.items()}
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    # Every size is rendered by us and handed over verbatim (`append_images`), so
    # Pillow never rescales; small frames stay BMP/DIB, the 256 frame is a PNG.
    pil[256].save(
        str(ico_path),
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=[pil[s] for s in SIZES if s != 256],
    )
    print(f"{ico_path}  ({ico_path.stat().st_size / 1024:.0f} KiB, {len(SIZES)} sizes)")

    sprite = Path(args.sprite) if args.sprite else root / "assets" / f"{name}.png"
    save_qimage(build_frame(args.app, 256, args.variant, glyph), sprite)

    if args.png_dir:
        out = Path(args.png_dir)
        out.mkdir(parents=True, exist_ok=True)
        for size in (256, 512, 1024):
            save_qimage(build_frame(args.app, size, args.variant, glyph), out / f"{name}-{size}.png")
        print(f"pngs -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
