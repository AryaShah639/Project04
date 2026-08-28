"""Generates demo package labels (PIL, 300 DPI) and sample e-commerce listings for the demo database."""
import os
from PIL import Image, ImageDraw, ImageFont
from . import db

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

CAP_FACTOR = 1.35   # printed cap-height ≈ 0.73 x font size; scale so measured glyph heights hit targets
LINE_GAP = 0.45     # line spacing = font size x (1 + LINE_GAP) — realistic label leading

def _f(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)

def draw_label(path, W, H, blocks, bg=(255, 255, 255), header=None, dot=None, dpi=300.0):
    """blocks: list of (text, size_px, color, bold). header: (band_color, title, subtitle).
    dot: 'green' | 'red_brown' — veg/non-veg mark at top-right (Rule 6(8))."""
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    y = 14
    if header:
        color, title, sub = header
        d.rounded_rectangle([18, 12, W - 18, 120], radius=8, fill=color)
        d.text((36, 26), title, font=_f(44, True), fill=(255, 255, 255))
        if sub:
            d.text((36, 84), sub, font=_f(21, True), fill=(235, 225, 180))
        if dot == "green":
            d.ellipse([W - 86, 34, W - 34, 86], fill=(0, 128, 60), outline=(0, 90, 40), width=3)
        elif dot == "red_brown":
            d.ellipse([W - 86, 34, W - 34, 86], fill=(150, 40, 30), outline=(110, 25, 20), width=3)
        y = 132
    for b in blocks:
        text, size, color, bold = b[0], b[1], b[2], b[3]
        px = int(size * CAP_FACTOR)
        d.text((22, y), text, font=_f(px, bold), fill=color)
        y += px + max(6, int(px * LINE_GAP))
    img.save(path, dpi=(dpi, dpi))
    return path

def label_compliant_tea(path):
    """Fully compliant label: PDP ~10 x 7.6 cm = 76 cm² -> min font 1.5 mm (~17.7 px cap @300dpi)."""
    W, H = 1181, 900  # 10.0 x 7.6 cm @300dpi
    blocks = [
        ("NET WT. 500 g", 30, (20, 20, 20), True),
        ("Ingredients: 100% pure Darjeeling tea leaves.", 17, (60, 60, 60), False),
        ("Manufactured by: FreshLeaf Beverages Pvt. Ltd.,", 19, (20, 20, 20), False),
        ("Tea Garden Road, Darjeeling - 734101, West Bengal, India", 19, (20, 20, 20), False),
        ("Packed by: FreshLeaf Beverages Pvt. Ltd. (address as above)", 19, (20, 20, 20), False),
        ("Mfg. Date: 03/2026    Best Before: 24 months from mfg.", 20, (20, 20, 20), False),
        ("MRP Rs. 285.00 (incl. of all taxes)", 26, (150, 20, 20), True),
        ("Consumer Care: 1800-266-7788 | care@freshleaf.in", 19, (20, 20, 20), False),
        ("FreshLeaf House, Darjeeling - 734101, West Bengal", 19, (20, 20, 20), False),
        ("FSSAI Lic. No. 10012011000456", 16, (90, 90, 90), False),
    ]
    return draw_label(path, W, H, blocks, bg=(250, 246, 238),
                      header=((11, 61, 102), "FRESHLEAF", "PREMIUM DARJEELING TEA"))

def label_noncompliant_noodles(path):
    """Violations: no country of origin (imported), no consumer care, MRP w/o tax wording,
    non-SI unit 'gm', font sizes below Table-I minimum for 76 cm² (1.5 mm ≈ 17.7 px)."""
    W, H = 1181, 900
    blocks = [
        ("NET WT. 400 gm", 13, (30, 30, 30), True),           # TOO SMALL (needs >=1.5mm) + 'gm'
        ("Imported by: NoodleKing India Pvt. Ltd.", 14, (30, 30, 30), False),
        ("21 Trade Centre, Mumbai - 400001, India", 14, (30, 30, 30), False),
        ("Mfg: 05/2026", 14, (30, 30, 30), False),
        ("Best before: 6 months from mfg", 14, (30, 30, 30), False),
        ("MRP Rs. 82.50", 12, (160, 20, 20), True),           # TOO SMALL + no tax wording
        ("Ingredients: Wheat flour (74%), palm oil, salt, spices.", 13, (80, 80, 80), False),
        ("Taste the king of noodles!", 13, (90, 90, 90), False),
    ]
    return draw_label(path, W, H, blocks, bg=(255, 242, 230),
                      header=((180, 30, 30), "NOODLEKING", "INSTANT NOODLES - MASALA"))

def label_partial_soap(path):
    """Violations: MRP not rounded (Rs. 45.99), low-contrast MRP, crowded quantity zone.
    Has green dot (veg)."""
    W, H = 1181, 900
    blocks = [
        ("NET WT. 150 g", 30, (20, 20, 20), True),
        ("Extra moisturising", 18, (70, 70, 70), False),       # crowds quantity clear-space (R8)
        ("Manufactured by: GlowCare Personal Care Ltd.,", 20, (20, 20, 20), False),
        ("Industrial Area Phase-II, Baddi - 173205, Himachal Pradesh", 20, (20, 20, 20), False),
        ("Mfg: 01/2026", 20, (20, 20, 20), False),
        ("MRP Rs. 45.99 (incl. of all taxes)", 26, (165, 165, 165), True),  # LOW CONTRAST on light bg
        ("Consumer Care: 1800-100-2200 | care@glowcare.in", 19, (20, 20, 20), False),
        ("GlowCare House, Baddi - 173205", 19, (20, 20, 20), False),
        ("Green dot mark: vegetarian product", 15, (90, 90, 90), False),
    ]
    return draw_label(path, W, H, blocks, bg=(235, 250, 240), dot="green",
                      header=((0, 100, 60), "GLOWCARE", "BATHING SOAP - NEEM & TULSI"))

def label_expired_milk(path):
    """Violation: 'Use by' date in the past (expired product)."""
    W, H = 1181, 900
    blocks = [
        ("NET VOLUME 500 ml", 30, (20, 20, 20), True),
        ("Packed by: DoodhMilk Dairy Pvt. Ltd.,", 20, (20, 20, 20), False),
        ("Dairy Road, Anand - 388001, Gujarat", 20, (20, 20, 20), False),
        ("Mfg: 07/2026", 20, (20, 20, 20), False),
        ("Use by: 15/07/2026", 20, (150, 20, 20), True),
        ("MRP Rs. 28.00 (incl. of all taxes)", 24, (150, 20, 20), True),
        ("Consumer Care: 1800-345-2233 | care@doodhmilk.in", 19, (20, 20, 20), False),
        ("Keep refrigerated below 4 degree C", 16, (90, 90, 90), False),
    ]
    return draw_label(path, W, H, blocks, bg=(238, 248, 255),
                      header=((30, 90, 170), "DOODHMILK", "TONED MILK - PASTEURISED"))

LISTING_COMPLIANT = """FreshLeaf Premium Darjeeling Tea - 500 g
Brand: FreshLeaf | Category: Tea
NET WT: 500 g
Manufactured by: FreshLeaf Beverages Pvt. Ltd., Tea Garden Road, Darjeeling - 734101, West Bengal, India
Packed by: FreshLeaf Beverages Pvt. Ltd. (address as above)
Mfg: 03/2026 | Best before: 24 months from manufacturing
MRP Rs. 285.00 (incl. of all taxes)
Consumer Care: 1800-266-7788, care@freshleaf.in
FSSAI Lic. No. 10012011000456"""

LISTING_NONCOMPLIANT = """NoodleKing Instant Noodles - Masala - 400 gm
Imported by NoodleKing India Pvt. Ltd., 21 Trade Centre, Mumbai - 400001
Mfg: 05/2026 | Best before: 6 months from packing
MRP Rs. 82.50
Price is exclusive of applicable taxes. Great taste guaranteed!"""

def generate_all():
    d = os.path.join(db.DATA_DIR, "samples")
    os.makedirs(d, exist_ok=True)
    out = {
        "compliant_tea": os.path.join(d, "compliant_tea.png"),
        "noncompliant_noodles": os.path.join(d, "noncompliant_noodles.png"),
        "partial_soap": os.path.join(d, "partial_soap.png"),
        "expired_milk": os.path.join(d, "expired_milk.png"),
    }
    label_compliant_tea(out["compliant_tea"])
    label_noncompliant_noodles(out["noncompliant_noodles"])
    label_partial_soap(out["partial_soap"])
    label_expired_milk(out["expired_milk"])
    return out
