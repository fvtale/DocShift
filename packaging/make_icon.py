"""Draws docshift.ico, the icon on the window and on DocShift.exe.

    python packaging/make_icon.py

Each size is drawn on its own rather than one large image scaled down: at 16
pixels a scaled-down drawing is a smudge. The .ico holds one PNG per size,
which every Windows since Vista reads.

The result is committed, and nothing in the build runs this. Run it again
after changing the drawing.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen, QPolygonF

SIZES = (16, 24, 32, 48, 64, 128, 256)
ICON = Path(__file__).resolve().parent.parent / "docshift" / "gui" / "docshift.ico"

# The window's own palette, from docshift/gui/style.py.
INK = QColor("#0b0b0f")  # the background
PAPER = QColor("#34343f")  # the page going in
ACCENT = QColor("#ff4d5a")  # the page coming out -- the title red
FOLD = QColor("#8b1e2d")  # the Convert button red


def draw(size: int) -> QImage:
    """Two sheets, the red one shifted off the grey one."""
    s = float(size)
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    painter.setBrush(INK)
    painter.drawRoundedRect(QRectF(0, 0, s, s), s * 0.2, s * 0.2)

    painter.setBrush(PAPER)
    painter.drawRoundedRect(QRectF(s * 0.16, s * 0.12, s * 0.46, s * 0.58), s * 0.05, s * 0.05)

    # The front sheet, its top-right corner folded down.
    x, y, w, h, fold = s * 0.38, s * 0.30, s * 0.46, s * 0.58, s * 0.16
    sheet = QPainterPath()
    sheet.moveTo(x, y)
    sheet.lineTo(x + w - fold, y)
    sheet.lineTo(x + w, y + fold)
    sheet.lineTo(x + w, y + h)
    sheet.lineTo(x, y + h)
    sheet.closeSubpath()
    # Outlined in the background colour, so it reads as a second sheet lying on
    # the first rather than one merged shape.
    painter.setPen(QPen(INK, max(1.0, s * 0.05)))
    painter.setBrush(ACCENT)
    painter.drawPath(sheet)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(FOLD)
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(x + w - fold, y),
                QPointF(x + w - fold, y + fold),
                QPointF(x + w, y + fold),
            ]
        )
    )
    painter.end()
    return image


def png(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def ico(images: dict[int, bytes]) -> bytes:
    """Pack PNGs into an .ico: a 6-byte header, a 16-byte entry per image, the PNGs."""
    header = struct.pack("<HHH", 0, 1, len(images))  # reserved, 1 = icon, count
    entries, blobs = [], []
    offset = len(header) + 16 * len(images)
    for size, data in images.items():
        edge = 0 if size >= 256 else size  # an .ico writes 256 as 0
        entries.append(struct.pack("<BBBBHHII", edge, edge, 0, 0, 1, 32, len(data), offset))
        blobs.append(data)
        offset += len(data)
    return header + b"".join(entries) + b"".join(blobs)


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _app = QGuiApplication(sys.argv[:1])
    ICON.write_bytes(ico({size: png(draw(size)) for size in SIZES}))
    print(f"wrote {ICON} ({ICON.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
