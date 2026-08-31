"""Generates assets/dx7.ico, the application icon.

Pure standard library (zlib + struct), so building the icon needs no image
library and nothing extra in the build environment.

The mark is an FM sine wave on the design system's signal colour: it stays
legible at 16 px in the taskbar, where lettering would turn to mush. Shapes are
rendered at 4x and box-filtered down, which is what gives the smooth edges.

    python tools/make_icon.py

Re-run only when the icon design changes; assets/dx7.ico is committed.
"""

import math
import struct
import zlib
from pathlib import Path

# From static/tokens.css -- keep in sync with the design system.
SIGNAL = (0x2F, 0xE3, 0xC2)  # --ds-signal, the brand/action colour
INK = (0x0A, 0x0C, 0x0F)     # --ds-bg, near-black

SIZES = (16, 24, 32, 48, 64, 128, 256)
SS = 4  # supersampling factor


def _rounded_rect_mask(n, radius):
    """Coverage mask (0..1 per pixel) for a rounded square filling n x n."""
    mask = bytearray(n * n)
    r = radius
    for y in range(n):
        for x in range(n):
            # Distance into the nearest corner's circle, if we're in a corner.
            dx = 0.0
            dy = 0.0
            if x < r:
                dx = r - x - 0.5
            elif x >= n - r:
                dx = x + 0.5 - (n - r)
            if y < r:
                dy = r - y - 0.5
            elif y >= n - r:
                dy = y + 0.5 - (n - r)
            inside = (dx * dx + dy * dy) <= r * r if (dx or dy) else True
            mask[y * n + x] = 255 if inside else 0
    return mask


def _wave_mask(n):
    """Coverage mask for a two-cycle sine wave, stamped as overlapping discs."""
    mask = bytearray(n * n)
    # Just over one cycle, running nearly edge to edge: it reads as a waveform
    # passing through the tile. More cycles or a shorter span and the peaks
    # start looking like the letter W.
    thickness = n * 0.075
    amp = n * 0.19
    cycles = 1.25
    cy = n / 2.0
    x0, x1 = n * 0.10, n * 0.90
    steps = max(256, n * 4)
    t = thickness
    ti = int(math.ceil(t))

    for s in range(steps + 1):
        px = x0 + (x1 - x0) * s / steps
        py = cy - amp * math.sin(2.0 * math.pi * cycles * (px - x0) / (x1 - x0))
        cx_i, cy_i = int(px), int(py)
        for yy in range(cy_i - ti, cy_i + ti + 1):
            if not (0 <= yy < n):
                continue
            for xx in range(cx_i - ti, cx_i + ti + 1):
                if not (0 <= xx < n):
                    continue
                ddx = xx + 0.5 - px
                ddy = yy + 0.5 - py
                if ddx * ddx + ddy * ddy <= t * t:
                    mask[yy * n + xx] = 255
    return mask


def _downsample(mask, n, factor):
    """Box-filter an n x n mask down by `factor`, yielding coverage 0..255."""
    out_n = n // factor
    out = bytearray(out_n * out_n)
    area = factor * factor
    for y in range(out_n):
        for x in range(out_n):
            total = 0
            for dy in range(factor):
                row = (y * factor + dy) * n + x * factor
                for dx in range(factor):
                    total += mask[row + dx]
            out[y * out_n + x] = total // area
    return out


def _render_rgba(size):
    """The icon at `size` x `size`, as RGBA bytes."""
    hi = size * SS
    bg = _downsample(_rounded_rect_mask(hi, hi * 0.22), hi, SS)
    wave = _downsample(_wave_mask(hi), hi, SS)

    px = bytearray()
    for i in range(size * size):
        a = bg[i]
        if a == 0:
            px += b"\x00\x00\x00\x00"
            continue
        # Ink over signal, both clipped to the rounded-square silhouette.
        w = wave[i] / 255.0
        r = round(SIGNAL[0] * (1 - w) + INK[0] * w)
        g = round(SIGNAL[1] * (1 - w) + INK[1] * w)
        b = round(SIGNAL[2] * (1 - w) + INK[2] * w)
        px += bytes((r, g, b, a))
    return bytes(px)


def _png(size, rgba):
    """Minimal RGBA PNG encoder."""
    raw = b"".join(
        b"\x00" + rgba[y * size * 4:(y + 1) * size * 4] for y in range(size)
    )

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main():
    images = [(s, _png(s, _render_rgba(s))) for s in SIZES]

    # ICO container. PNG-compressed entries are supported by Windows Vista+ and
    # copied through verbatim by PyInstaller's resource packer.
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,  # 0 means 256
            0 if size >= 256 else size,
            0, 0, 1, 32, len(data), offset,
        )
        blobs += data
        offset += len(data)

    out = Path(__file__).resolve().parent.parent / "assets" / "dx7.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(header + entries + blobs)
    print(f"Wrote {out} ({out.stat().st_size:,} bytes, sizes {list(SIZES)})")


if __name__ == "__main__":
    main()
