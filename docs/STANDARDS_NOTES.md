# Standards and publishing notes

This project is intended to make standards-conscious EAN-13 artwork easy to create, but it is not a substitute for formal barcode verification.

## EAN-13 geometry used by the generator

At 100% / target size:

- X-dimension: 0.330 mm
- encoded symbol: 95 modules = 31.35 mm
- left quiet zone: 11 modules = 3.63 mm
- right quiet zone: 7 modules = 2.31 mm
- overall width: 113 modules = 37.29 mm
- normal bar height: 22.85 mm
- overall nominal height including human-readable interpretation: 25.93 mm

The app allows 80%–200% scaling, corresponding to an X-dimension of 0.264–0.660 mm.

Primary reference:

- GS1 General Specifications: https://ref.gs1.org/standards/genspecs/

## ISBN-specific guidance

The International ISBN Agency publishes the definitive ISBN Users' Manual and FAQs:

- https://www.isbn-international.org/content/isbn-users-manual/29

ISBN-specific presentation rules can go beyond the EAN-13 symbol geometry itself. In particular, some book-trade guidance calls for a human-readable formatted ISBN caption near the barcode. This generator supplies the EAN-13 symbol and its EAN human-readable digits; surrounding ISBN captioning can be added in the cover-layout application to meet the requirements of the relevant market, printer or distributor.

## Five-digit price add-on

Version 1.0.0 does not generate the optional five-digit book price supplement. This is deliberate: it is not normally required for Australian publishing and historically has been used principally in the US and Canadian book trade.

## Production cautions

Barcode scan performance depends on more than mathematically correct bar patterns. Avoid:

- non-uniform scaling;
- placing artwork inside the quiet zones;
- low contrast;
- putting transparent output over anything except solid white;
- raster resizing that blurs bar edges;
- very low-resolution export;
- print processes that significantly spread or break up fine bars.

Where a printer, distributor or retailer requires formal verification, use their specified process or an appropriate barcode verification service.
