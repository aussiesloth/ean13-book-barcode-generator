#!/usr/bin/env python3
"""
EAN-13 Book Barcode Generator

A small, offline desktop app for generating print-ready EAN-13 barcodes,
with book/ISBN-focused validation and GS1-compliant nominal dimensions.

No third-party Python packages are required.
"""

from __future__ import annotations

import re
import struct
import sys
import zlib
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Tkinter is required. On Debian/Ubuntu install it with: sudo apt install python3-tk"
    ) from exc

APP_NAME = "EAN-13 Book Barcode Generator"
APP_VERSION = "1.0.0"

# GS1 nominal EAN-13 dimensions at 100% magnification.
X_NOMINAL_MM = 0.330
BAR_HEIGHT_NOMINAL_MM = 22.85
GUARD_HEIGHT_NOMINAL_MM = 24.50
TOTAL_HEIGHT_NOMINAL_MM = 25.93
HRI_TOP_NOMINAL_MM = 23.18
HRI_HEIGHT_NOMINAL_MM = 2.75
LEFT_QUIET_MODULES = 11
RIGHT_QUIET_MODULES = 7
SYMBOL_MODULES = 95
TOTAL_MODULES = LEFT_QUIET_MODULES + SYMBOL_MODULES + RIGHT_QUIET_MODULES

L_PATTERNS = {
    "0": "0001101", "1": "0011001", "2": "0010011", "3": "0111101", "4": "0100011",
    "5": "0110001", "6": "0101111", "7": "0111011", "8": "0110111", "9": "0001011",
}
G_PATTERNS = {
    "0": "0100111", "1": "0110011", "2": "0011011", "3": "0100001", "4": "0011101",
    "5": "0111001", "6": "0000101", "7": "0010001", "8": "0001001", "9": "0010111",
}
R_PATTERNS = {
    "0": "1110010", "1": "1100110", "2": "1101100", "3": "1000010", "4": "1011100",
    "5": "1001110", "6": "1010000", "7": "1000100", "8": "1001000", "9": "1110100",
}
PARITY = {
    "0": "LLLLLL", "1": "LLGLGG", "2": "LLGGLG", "3": "LLGGGL", "4": "LGLLGG",
    "5": "LGGLLG", "6": "LGGGLL", "7": "LGLGLG", "8": "LGLGGL", "9": "LGGLGL",
}

# Simple built-in 5x7 bitmap digits used only for PNG human-readable text.
# SVG uses vector text. This keeps PNG generation dependency-free.
FONT_5X7 = {
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
}


def clean_digits(value: str) -> str:
    """Remove common ISBN/EAN formatting while rejecting other characters."""
    value = value.strip()
    if not value:
        return ""
    if re.search(r"[^0-9\s-]", value):
        raise ValueError("Use digits only (spaces and hyphens are also accepted).")
    return re.sub(r"[\s-]", "", value)


def ean13_check_digit(first12: str) -> str:
    if len(first12) != 12 or not first12.isdigit():
        raise ValueError("Check-digit calculation requires exactly 12 digits.")
    weighted = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(first12))
    return str((10 - weighted % 10) % 10)


def normalize_ean(value: str, require_isbn_prefix: bool = True) -> tuple[str, str]:
    """Return (13-digit EAN, status message). Accepts 12 or 13 digits."""
    digits = clean_digits(value)
    if len(digits) not in (12, 13):
        raise ValueError("Enter 12 digits (to calculate the check digit) or a complete 13-digit EAN/ISBN.")
    if require_isbn_prefix and not digits.startswith(("978", "979")):
        raise ValueError("Book/ISBN mode requires an ISBN prefix of 978 or 979.")

    if len(digits) == 12:
        check = ean13_check_digit(digits)
        return digits + check, f"Check digit calculated: {check}"

    expected = ean13_check_digit(digits[:12])
    if digits[-1] != expected:
        raise ValueError(f"Invalid check digit: entered {digits[-1]}, expected {expected}.")
    return digits, "Check digit valid"


def encode_ean13(ean: str) -> str:
    """Encode a validated 13-digit EAN into the 95 barcode modules."""
    if len(ean) != 13 or not ean.isdigit():
        raise ValueError("EAN-13 encoding requires 13 digits.")
    parity = PARITY[ean[0]]
    left = "".join(
        (L_PATTERNS if p == "L" else G_PATTERNS)[digit]
        for digit, p in zip(ean[1:7], parity)
    )
    right = "".join(R_PATTERNS[digit] for digit in ean[7:13])
    bits = "101" + left + "01010" + right + "101"
    if len(bits) != 95:
        raise AssertionError("Internal encoding error: EAN-13 must be 95 modules.")
    return bits


def guard_module(index: int) -> bool:
    """True if a symbol-module index belongs to start, centre, or end guard bars."""
    return index in {0, 2, 46, 48, 92, 94}


def hri_centres_modules() -> list[float]:
    """Horizontal centres for the 13 human-readable digits in total-module coordinates."""
    centres = [LEFT_QUIET_MODULES / 2.0]
    centres.extend(LEFT_QUIET_MODULES + 3 + 3.5 + 7 * i for i in range(6))
    centres.extend(LEFT_QUIET_MODULES + 3 + 42 + 5 + 3.5 + 7 * i for i in range(6))
    return centres


def svg_string(ean: str, magnification: float = 1.0, transparent: bool = False) -> str:
    bits = encode_ean13(ean)
    x_mm = X_NOMINAL_MM * magnification
    width_mm = TOTAL_MODULES * x_mm
    height_mm = TOTAL_HEIGHT_NOMINAL_MM * magnification
    bar_h = BAR_HEIGHT_NOMINAL_MM * magnification
    guard_h = GUARD_HEIGHT_NOMINAL_MM * magnification
    hri_y = HRI_TOP_NOMINAL_MM * magnification
    font_size = HRI_HEIGHT_NOMINAL_MM * magnification

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm:.4f}mm" height="{height_mm:.4f}mm" '
        f'viewBox="0 0 {width_mm:.6f} {height_mm:.6f}" shape-rendering="crispEdges">',
        f'  <title>EAN-13 {ean}</title>',
        f'  <desc>EAN-13 barcode generated by {APP_NAME} {APP_VERSION}</desc>',
    ]
    if not transparent:
        parts.append(f'  <rect x="0" y="0" width="{width_mm:.6f}" height="{height_mm:.6f}" fill="#ffffff"/>')

    symbol_x = LEFT_QUIET_MODULES * x_mm
    for i, bit in enumerate(bits):
        if bit == "1":
            h = guard_h if guard_module(i) else bar_h
            x = symbol_x + i * x_mm
            parts.append(f'  <rect x="{x:.6f}" y="0" width="{x_mm:.6f}" height="{h:.6f}" fill="#000000"/>')

    # Human-readable interpretation. Font choice is not required to be OCR-B;
    # GS1 permits a clearly legible alternative. Generic sans-serif remains vector text.
    centres = hri_centres_modules()
    for digit, centre_mod in zip(ean, centres):
        cx = centre_mod * x_mm
        parts.append(
            f'  <text x="{cx:.6f}" y="{hri_y + font_size * 0.88:.6f}" '
            f'font-family="Arial, Helvetica, sans-serif" font-size="{font_size:.6f}" '
            f'text-anchor="middle" fill="#000000" shape-rendering="geometricPrecision">{digit}</text>'
        )
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)


def write_png_rgba(path: Path, width: int, height: int, rgba: bytearray, pixels_per_metre: int) -> None:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    phys = struct.pack(">IIB", pixels_per_metre, pixels_per_metre, 1)
    rows = bytearray()
    stride = width * 4
    for y in range(height):
        rows.append(0)  # filter type 0
        start = y * stride
        rows.extend(rgba[start:start + stride])
    payload = signature + png_chunk(b"IHDR", ihdr) + png_chunk(b"pHYs", phys) + png_chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + png_chunk(b"IEND", b"")
    path.write_bytes(payload)


def fill_rect(buf: bytearray, width: int, height: int, x0: int, y0: int, x1: int, y1: int, rgba: tuple[int, int, int, int]) -> None:
    x0 = max(0, min(width, x0)); x1 = max(0, min(width, x1))
    y0 = max(0, min(height, y0)); y1 = max(0, min(height, y1))
    if x1 <= x0 or y1 <= y0:
        return
    pixel = bytes(rgba)
    row = pixel * (x1 - x0)
    for y in range(y0, y1):
        off = (y * width + x0) * 4
        buf[off:off + len(row)] = row


def draw_bitmap_digit(buf: bytearray, width: int, height: int, digit: str, centre_x: int, top_y: int, cell: int) -> None:
    pattern = FONT_5X7[digit]
    glyph_w = 5 * cell
    x_start = int(round(centre_x - glyph_w / 2))
    for row_idx, row in enumerate(pattern):
        for col_idx, on in enumerate(row):
            if on == "1":
                fill_rect(
                    buf, width, height,
                    x_start + col_idx * cell,
                    top_y + row_idx * cell,
                    x_start + (col_idx + 1) * cell,
                    top_y + (row_idx + 1) * cell,
                    (0, 0, 0, 255),
                )


def export_png(path: Path, ean: str, magnification: float, target_dpi: int, transparent: bool) -> dict[str, float | int]:
    bits = encode_ean13(ean)
    x_mm = X_NOMINAL_MM * magnification

    # Integer pixels per module are essential for crisp bars. Choose the nearest
    # integer to the requested raster resolution, then embed a slightly adjusted
    # physical resolution so the intended GS1 dimensions remain exact.
    module_px = max(1, round(x_mm * target_dpi / 25.4))
    pixels_per_metre = max(1, round(module_px / x_mm * 1000.0))
    effective_dpi = pixels_per_metre * 0.0254

    width = TOTAL_MODULES * module_px
    height = max(1, round(TOTAL_HEIGHT_NOMINAL_MM * magnification * pixels_per_metre / 1000.0))
    if transparent:
        buf = bytearray(width * height * 4)
    else:
        buf = bytearray(b"\xff\xff\xff\xff" * (width * height))

    bar_h = round(BAR_HEIGHT_NOMINAL_MM * magnification * pixels_per_metre / 1000.0)
    guard_h = round(GUARD_HEIGHT_NOMINAL_MM * magnification * pixels_per_metre / 1000.0)
    symbol_x = LEFT_QUIET_MODULES * module_px
    for i, bit in enumerate(bits):
        if bit == "1":
            h = guard_h if guard_module(i) else bar_h
            x0 = symbol_x + i * module_px
            fill_rect(buf, width, height, x0, 0, x0 + module_px, h, (0, 0, 0, 255))

    desired_hri_px = max(7, round(HRI_HEIGHT_NOMINAL_MM * magnification * pixels_per_metre / 1000.0))
    cell = max(1, desired_hri_px // 7)
    hri_top = round(HRI_TOP_NOMINAL_MM * magnification * pixels_per_metre / 1000.0)
    for digit, centre_mod in zip(ean, hri_centres_modules()):
        centre_x = round(centre_mod * module_px)
        draw_bitmap_digit(buf, width, height, digit, centre_x, hri_top, cell)

    write_png_rgba(path, width, height, buf, pixels_per_metre)
    return {
        "width_px": width,
        "height_px": height,
        "module_px": module_px,
        "effective_dpi": effective_dpi,
        "width_mm": TOTAL_MODULES * x_mm,
        "height_mm": TOTAL_HEIGHT_NOMINAL_MM * magnification,
    }


def physical_dimensions(magnification: float) -> tuple[float, float, float]:
    x = X_NOMINAL_MM * magnification
    return TOTAL_MODULES * x, TOTAL_HEIGHT_NOMINAL_MM * magnification, x


def safe_filename(ean: str, magnification: float, ext: str) -> str:
    pct = int(round(magnification * 100))
    return f"ISBN_{ean}_EAN13_{pct}pct.{ext}"


class BarcodeApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.minsize(760, 560)
        self.geometry("850x640")

        self.ean_var = tk.StringVar()
        self.mag_var = tk.StringVar(value="100")
        self.dpi_var = tk.StringVar(value="600")
        self.bg_var = tk.StringVar(value="white")
        self.isbn_mode_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Enter an ISBN-13/EAN-13 above.")
        self.detail_var = tk.StringVar(value="100% nominal size: 37.29 × 25.93 mm")
        self.valid_ean: str | None = None

        self._build_ui()
        self.ean_var.trace_add("write", lambda *_: self.refresh_preview())
        self.mag_var.trace_add("write", lambda *_: self.refresh_preview())
        self.bg_var.trace_add("write", lambda *_: self.refresh_preview())
        self.isbn_mode_var.trace_add("write", lambda *_: self.refresh_preview())

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(5, weight=1)

        ttk.Label(outer, text="ISBN / EAN-13", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))
        entry = ttk.Entry(outer, textvariable=self.ean_var, font=("TkFixedFont", 14), width=28)
        entry.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(10, 0), pady=(0, 5))
        entry.focus_set()

        ttk.Checkbutton(outer, text="Book/ISBN mode — require 978 or 979 prefix", variable=self.isbn_mode_var).grid(
            row=1, column=1, columnspan=3, sticky="w", padx=(10, 0)
        )

        ttk.Label(outer, text="Magnification").grid(row=2, column=0, sticky="w", pady=(12, 0))
        mag = ttk.Spinbox(outer, from_=80, to=200, increment=5, textvariable=self.mag_var, width=8)
        mag.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(12, 0))
        ttk.Label(outer, text="%  (GS1 retail range: 80–200%)").grid(row=2, column=2, columnspan=2, sticky="w", padx=(6, 0), pady=(12, 0))

        ttk.Label(outer, text="PNG target resolution").grid(row=3, column=0, sticky="w", pady=(8, 0))
        dpi = ttk.Combobox(outer, textvariable=self.dpi_var, values=("300", "600", "1200"), width=8, state="readonly")
        dpi.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=(8, 0))
        ttk.Label(outer, text="dpi  (600 recommended)").grid(row=3, column=2, columnspan=2, sticky="w", padx=(6, 0), pady=(8, 0))

        ttk.Label(outer, text="Background").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Radiobutton(outer, text="White", value="white", variable=self.bg_var).grid(row=4, column=1, sticky="w", padx=(10, 0), pady=(8, 0))
        ttk.Radiobutton(outer, text="Transparent", value="transparent", variable=self.bg_var).grid(row=4, column=2, sticky="w", pady=(8, 0))

        preview_frame = ttk.LabelFrame(outer, text="Preview", padding=10)
        preview_frame.grid(row=5, column=0, columnspan=4, sticky="nsew", pady=(14, 10))
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(preview_frame, bg="#d9d9d9", highlightthickness=0, height=270)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self._draw_preview())

        ttk.Label(outer, textvariable=self.status_var, font=("TkDefaultFont", 10, "bold")).grid(row=6, column=0, columnspan=4, sticky="w")
        ttk.Label(outer, textvariable=self.detail_var).grid(row=7, column=0, columnspan=4, sticky="w", pady=(2, 0))
        ttk.Label(
            outer,
            text="Transparent exports are only barcode-safe when the entire barcode, including both quiet zones, sits over solid white.",
            wraplength=790,
        ).grid(row=8, column=0, columnspan=4, sticky="w", pady=(6, 0))

        buttons = ttk.Frame(outer)
        buttons.grid(row=9, column=0, columnspan=4, sticky="e", pady=(14, 0))
        self.svg_button = ttk.Button(buttons, text="Export SVG…", command=self.export_svg, state="disabled")
        self.svg_button.pack(side="left", padx=(0, 8))
        self.png_button = ttk.Button(buttons, text="Export PNG…", command=self.export_png_file, state="disabled")
        self.png_button.pack(side="left")

    def _magnification(self) -> float:
        try:
            pct = float(self.mag_var.get())
        except ValueError:
            raise ValueError("Magnification must be a number between 80 and 200.")
        if not 80 <= pct <= 200:
            raise ValueError("Magnification must be between 80% and 200%.")
        return pct / 100.0

    def refresh_preview(self) -> None:
        try:
            mag = self._magnification()
            width_mm, height_mm, x_mm = physical_dimensions(mag)
            self.detail_var.set(f"Output size: {width_mm:.2f} × {height_mm:.2f} mm   •   X-dimension: {x_mm:.3f} mm")
            ean, status = normalize_ean(self.ean_var.get(), self.isbn_mode_var.get())
            self.valid_ean = ean
            self.status_var.set(f"✓ {ean} — {status}")
            self.svg_button.configure(state="normal")
            self.png_button.configure(state="normal")
        except ValueError as exc:
            self.valid_ean = None
            if self.ean_var.get().strip():
                self.status_var.set(str(exc))
            else:
                self.status_var.set("Enter 12 digits to calculate the check digit, or a complete 13-digit number.")
            self.svg_button.configure(state="disabled")
            self.png_button.configure(state="disabled")
        self._draw_preview()

    def _draw_preview(self) -> None:
        c = self.canvas
        c.delete("all")
        if not self.valid_ean:
            c.create_text(c.winfo_width() / 2, c.winfo_height() / 2, text="Valid barcode preview will appear here", fill="#666666")
            return
        try:
            mag = self._magnification()
        except ValueError:
            return

        bits = encode_ean13(self.valid_ean)
        x_mm = X_NOMINAL_MM * mag
        w_mm = TOTAL_MODULES * x_mm
        h_mm = TOTAL_HEIGHT_NOMINAL_MM * mag
        margin = 28
        scale = min((c.winfo_width() - 2 * margin) / w_mm, (c.winfo_height() - 2 * margin) / h_mm)
        if scale <= 0:
            return
        x0 = (c.winfo_width() - w_mm * scale) / 2
        y0 = (c.winfo_height() - h_mm * scale) / 2

        # Preview always displays a white plate so quiet zones are visible.
        c.create_rectangle(x0, y0, x0 + w_mm * scale, y0 + h_mm * scale, fill="white", outline="#aaaaaa")
        module = x_mm * scale
        symbol_x = x0 + LEFT_QUIET_MODULES * module
        normal_h = BAR_HEIGHT_NOMINAL_MM * mag * scale
        guard_h = GUARD_HEIGHT_NOMINAL_MM * mag * scale
        for i, bit in enumerate(bits):
            if bit == "1":
                h = guard_h if guard_module(i) else normal_h
                bx = symbol_x + i * module
                c.create_rectangle(bx, y0, bx + module + 0.2, y0 + h, fill="black", outline="black")

        font_px = max(8, int(HRI_HEIGHT_NOMINAL_MM * mag * scale * 0.78))
        hri_y = y0 + (HRI_TOP_NOMINAL_MM * mag + HRI_HEIGHT_NOMINAL_MM * mag * 0.45) * scale
        for digit, centre_mod in zip(self.valid_ean, hri_centres_modules()):
            cx = x0 + centre_mod * module
            c.create_text(cx, hri_y, text=digit, font=("Arial", font_px), anchor="center", fill="black")

        if self.bg_var.get() == "transparent":
            c.create_text(x0 + 5, y0 + 5, text="Transparent export", anchor="nw", fill="#666666", font=("TkDefaultFont", 8))

    def _warn_transparent(self) -> bool:
        if self.bg_var.get() != "transparent":
            return True
        return messagebox.askokcancel(
            "Transparent background",
            "A transparent EAN-13 is safe only if the final cover beneath the entire barcode area is solid white. "
            "A coloured, textured or photographic background can destroy the required quiet zones and contrast.\n\n"
            "Continue with transparent export?",
        )

    def export_svg(self) -> None:
        if not self.valid_ean or not self._warn_transparent():
            return
        mag = self._magnification()
        path = filedialog.asksaveasfilename(
            title="Export EAN-13 as SVG",
            defaultextension=".svg",
            initialfile=safe_filename(self.valid_ean, mag, "svg"),
            filetypes=(("SVG vector image", "*.svg"), ("All files", "*.*")),
        )
        if not path:
            return
        Path(path).write_text(svg_string(self.valid_ean, mag, self.bg_var.get() == "transparent"), encoding="utf-8")
        messagebox.showinfo("Export complete", f"SVG saved:\n{path}\n\nFor book-cover work, SVG is the preferred master because the bars remain vector-sharp.")

    def export_png_file(self) -> None:
        if not self.valid_ean or not self._warn_transparent():
            return
        mag = self._magnification()
        dpi = int(self.dpi_var.get())
        path = filedialog.asksaveasfilename(
            title="Export EAN-13 as PNG",
            defaultextension=".png",
            initialfile=safe_filename(self.valid_ean, mag, "png"),
            filetypes=(("PNG image", "*.png"), ("All files", "*.*")),
        )
        if not path:
            return
        info = export_png(Path(path), self.valid_ean, mag, dpi, self.bg_var.get() == "transparent")
        messagebox.showinfo(
            "Export complete",
            f"PNG saved:\n{path}\n\n"
            f"Raster size: {info['width_px']} × {info['height_px']} px\n"
            f"Physical size: {info['width_mm']:.2f} × {info['height_mm']:.2f} mm\n"
            f"Module width: {info['module_px']} px\n"
            f"Embedded resolution: {info['effective_dpi']:.1f} dpi\n\n"
            "The embedded resolution may differ slightly from the selected target so every barcode module remains an exact integer number of pixels.",
        )


def run_self_tests() -> None:
    # Standard GS1 example and a well-known ISBN-13 example.
    assert ean13_check_digit("400638133393") == "1"
    assert normalize_ean("4006381333931", False)[0] == "4006381333931"
    assert ean13_check_digit("978030640615") == "7"
    assert normalize_ean("978-0-306-40615-7", True)[0] == "9780306406157"
    bits = encode_ean13("9780306406157")
    assert len(bits) == 95
    assert bits[:3] == "101" and bits[45:50] == "01010" and bits[-3:] == "101"
    w, h, x = physical_dimensions(1.0)
    assert abs(w - 37.29) < 1e-9 and abs(h - 25.93) < 1e-9 and abs(x - 0.330) < 1e-9
    print(f"{APP_NAME} {APP_VERSION}: all self-tests passed")


def main() -> None:
    if "--self-test" in sys.argv:
        run_self_tests()
        return
    app = BarcodeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
