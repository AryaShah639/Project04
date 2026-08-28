# Compliance Rules Reference — LM Compliance System

Every check implemented in the rules engine, with its legal basis under the
**Legal Metrology (Packaged Commodities) Rules, 2011** as amended (latest:
GSR 629(E) dt. 23-06-2017, in force from 01-01-2018).

---

## A. Mandatory declarations — Rule 6(1)

| # | Declaration | Provision | Check ID | Severity |
|---|---|---|---|---|
| 1 | Name & address of manufacturer; manufacturer **and** packer where different; importer for imported packages. Rule 10 requires the **complete** address (PIN code) | R6(1)(a), R10 | `MANUF_ADDR`, `MANUF_ADDR_PIN` | CRITICAL / MINOR |
| 2 | Country of origin / manufacture / assembly — **imported products only** | R6(1)(aa) | `COUNTRY_ORIGIN` | CRITICAL |
| 3 | Common or generic name of the commodity (brand name alone insufficient) | R6(1)(b) | `COMMON_NAME` | CRITICAL |
| 4 | Net quantity in standard unit of weight/measure, or number; SI symbols (g, kg, ml, l, cm, m, N/U); no "dozen/score/gross/great gross" | R6(1)(c), R8(5), R8(4) | `NET_QTY`, `NET_QTY_UNIT`, `NET_QTY_WORD` | CRITICAL / MAJOR |
| 5 | Month & year of manufacture / pre-packing / import (exempt: bidis, incense sticks, LPG cylinders — R6(1) proviso) | R6(1)(d) | `MFG_DATE` | CRITICAL |
| 6 | Best before / use-by date, month & year — for commodities that may become unfit for human consumption; expiry is checked against today | R6(1)(da) | `BEST_BEFORE` | MAJOR |
| 7 | Retail sale price as **MRP** — "Maximum/Max. retail price Rs. … (incl. of all taxes)" per the R2(m) illustrations; **single** MRP; rounded to nearest rupee / 50 paise | R6(1)(e), R2(m) | `MRP`, `MRP_KW`, `MRP_TAX`, `MRP_SINGLE`, `MRP_ROUNDING` | CRITICAL / MAJOR |
| 8 | Dimensions of commodity where sizes are relevant | R6(1)(f) | `DIMENSIONS` | INFO |
| 9 | Consumer care — name, address, telephone number, e-mail of the person/office to be contacted for complaints | R6(2) (as per GSR 385(E)/2015) | `CONSUMER_CARE` | CRITICAL |

## B. Font sizes, placement and manner

| Check | Provision | Engine behaviour | Severity |
|---|---|---|---|
| `FONT_SIZE` | R7(2) Table-I | Measured glyph height (mm, from OCR geometry at print DPI) vs. minimum by PDP area | MAJOR |
| `FONT_WIDTH` | R7(3) | Average letter/numeral width ≥ ⅓ of height (exceptions: "1", i, I, l) | MAJOR |
| `PDP_PLACEMENT` | R8(1) | Declarations on the principal display panel | — |
| `QTY_CLEAR_SPACE` | R8(1) proviso | Printed text within the clear zone around the quantity declaration (height above/below; 2× height left/right) | MINOR |
| `CONTRAST` | R9(1)(b) | Otsu contrast ratio of MRP/net-qty numerals vs. background: < 1.25 FAIL, < 1.5 WARN | MAJOR / MINOR |
| `LEGIBILITY` | R9(1)(a) | OCR confidence < 55% on declaration fields → verify physically | MINOR |
| `LANGUAGE` | R9(4) | Declarations in English or Hindi (Devanagari) | MINOR |

## C. Special markings & practices

| Check | Provision | Engine behaviour | Severity |
|---|---|---|---|
| `VEG_DOT` | R6(8) | Green (veg) / red-brown (non-veg) dot at top of PDP for soaps, shampoos, toothpastes, cosmetics, toiletries | MAJOR |
| `GM` | R6(7) | "GM" at top of PDP for genetically modified food | MAJOR |
| `STICKER` | R6(3) | Advisory — no sticker may alter declarations; only lower-MRP sticker permitted, not covering original MRP | INFO |
| `ECOMM` | R6(10) | E-commerce entities must display all declarations except month/year of manufacture | — |
| `STD_PACK` | R5 + Second Schedule | Non-standard pack sizes for scheduled commodities (tea, biscuits, milk powder, salt, sugar, detergents, edible oil — subset) | MINOR |

## D. Rule 7 Table-I — minimum height of numerals & letters

| PDP area (A) | Normal printing | Blown/formed/molded on container |
|---|---|---|
| A ≤ 50 cm² | 1.0 mm | 1.5 mm |
| 50 < A ≤ 100 cm² | 1.5 mm | 3.0 mm |
| 100 < A ≤ 500 cm² | 2.5 mm | 4.0 mm |
| 500 < A ≤ 2500 cm² | 4.0 mm | 6.0 mm |
| A > 2500 cm² | 6.0 mm | 6.0 mm |

**PDP area (R7(4))**: rectangular — height × width of the display side;
cylindrical — 40% of height × circumference; other shapes — 40% of total surface area.

## E. Exemptions (R3)

Chapter II does not apply to packages above 25 kg/25 L, cement/fertiliser bags above
50 kg, and packages meant for industrial or institutional consumers.

## F. Penalty reference — Legal Metrology Act, 2009

| Provision | Offence | Penalty |
|---|---|---|
| Sec. 35 | Contravention of s.18 (declarations on pre-packaged commodities) | Fine up to ₹25,000 (1st); ₹50,000 (2nd); ₹1,00,000 (3rd & subsequent) |
| Sec. 36(1) | Manufacturing/packing/selling **non-standard packages** (non-conforming declarations) | Fine up to ₹25,000 (1st); ₹50,000 (2nd); ₹50,000–₹1,00,000 or imprisonment up to 1 yr or both (subsequent) |
| Sec. 36(2) | Error in **net quantity** | Fine ₹10,000–₹50,000 (1st); up to ₹1,00,000 or imprisonment up to 1 yr or both (2nd & subsequent) |
| Sec. 39 | General contravention of rules | Fine up to ₹25,000 (1st); ₹50,000 (2nd); ₹1,00,000 (3rd & subsequent) |

---

*Sources: consumeraffairs.gov.in (Legal Metrology division); consolidated text of the
Legal Metrology (Packaged Commodities) Rules, 2011 with amendments
(`docs/LM_Packaged_Commodities_Rules_2011_consolidated.pdf` in this repository).*
