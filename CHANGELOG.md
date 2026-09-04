# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-04

### Added
- Single-file, dependency-free browser app that runs entirely locally.
- EAN-13 encoding with ISBN-focused validation for `978` and `979` prefixes.
- Automatic EAN-13 check-digit calculation from 12 digits.
- Validation of complete 13-digit values.
- SVG export for vector-sharp book-cover artwork.
- High-resolution PNG export with integer-pixel barcode modules.
- White and transparent background options, with a safety warning for transparent output.
- 80% to 200% magnification control.
- 300, 600 and 1200 dpi PNG targets.
- Built-in preview and output-dimension reporting.
- Optional Python/Tkinter desktop implementation with no third-party packages.
- Known-value self-tests for EAN-13 encoding and physical dimensions.
- Example SVG and PNG output.

