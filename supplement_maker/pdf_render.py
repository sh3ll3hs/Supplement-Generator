"""Render a Job to PDF in the shop's CCC-style estimate layout.

All coordinates are PDF points measured from the TOP of a US Letter page (612 x 792),
taken from the 2018 Nissan Sentra estimate so the output lines up with it.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .model import Job, extended, money, hrs, num

PAGE_W, PAGE_H = letter
L, R = 21.6, 561.6                 # text block edges
BODY, SECT, SHOP = 8.02, 9.94, 11.98
PITCH = 13.55                      # row pitch for 8pt tables
LEGAL_PITCH = 13.3
BOTTOM = 728.0                     # last usable baseline above the footer
GRAY = 0.827


# ---------------------------------------------------------------- fonts
def resource_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / "supplement_maker" if base else Path(__file__).resolve().parent


def _find_tahoma():
    cands = []
    windir = os.environ.get("WINDIR", r"C:\Windows")
    cands.append((Path(windir) / "Fonts" / "tahoma.ttf", Path(windir) / "Fonts" / "tahomabd.ttf"))
    for d in ("/System/Library/Fonts/Supplemental", "/Library/Fonts", str(Path.home() / "Library/Fonts"),
              "/usr/share/fonts/truetype/msttcorefonts", "/usr/share/fonts/truetype/tahoma"):
        cands.append((Path(d) / "Tahoma.ttf", Path(d) / "Tahoma Bold.ttf"))
        cands.append((Path(d) / "tahoma.ttf", Path(d) / "tahomabd.ttf"))
    for reg, bold in cands:
        if reg.exists() and bold.exists():
            return reg, bold
    return None


_FONTS = None


def fonts():
    """Register fonts once. Returns (regular, bold, scale). Tahoma matches CCC output;
    the bundled DejaVu Sans is scaled so its widths come close when Tahoma is missing."""
    global _FONTS
    if _FONTS:
        return _FONTS
    t = _find_tahoma()
    try:
        if t:
            pdfmetrics.registerFont(TTFont("EstR", str(t[0])))
            pdfmetrics.registerFont(TTFont("EstB", str(t[1])))
            _FONTS = ("EstR", "EstB", 1.0)
            return _FONTS
    except Exception:
        pass
    fdir = resource_dir() / "fonts"
    pdfmetrics.registerFont(TTFont("EstR", str(fdir / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("EstB", str(fdir / "DejaVuSans-Bold.ttf")))
    _FONTS = ("EstR", "EstB", 0.88)
    return _FONTS


# ---------------------------------------------------------------- legal text
NOTICES = [
    'ANY PERSON WHO KNOWINGLY AND WITH INTENT TO INJURE, DEFRAUD, OR DECEIVE ANY INSURER FILES A STATEMENT OF CLAIM OR AN APPLICATION CONTAINING ANY FALSE, INCOMPLETE, OR MISLEADING INFORMATION IS GUILTY OF A FELONY OF THE THIRD DEGREE(FLORIDA STATUTES TITLE XLVI, CHAPTER 817.234). FAILURE TO USE THE INSURANCE PROCEEDS IN ACCORDANCE WITH THE SECURITY AGREEMENT,IF ANY, COULD BE A VIOLATION OF S. 812.014, FLORIDA STATUTES. IF YOU HAVE ANY QUESTIONS, CONTACT YOUR LENDING INSTITUTION. IF A CHARGE FOR SHOP SUPPLIES OR HAZARDOUS OR OTHER WASTE REMOVAL IS INCLUDED ON THIS ESTIMATE, PLEASE NOTE THE FOLLOWING: "THIS CHARGE REPRESENTS COSTS AND PROFITS TO THE MOTOR VEHICLE REPAIR FACILITY FOR MISCELLANEOUS SHOP SUPPLIES OR WASTE DISPOSAL." IF A CHARGE FOR NEW TIRES OR A NEW OR REMANUFACTURED LEAD-ACID BATTERY IS INCLUDED ON THIS ESTIMATE, PLEASE NOTE THE FOLLOWING: A $1.00 FEE FOR EACH NEW MOTOR VEHICLE TIRE SOLD AT RETAIL IS IMPOSED ON ANY PERSON ENGAGING IN THE BUSINESS OF MAKING RETAIL SALES OF NEW MOTOR VEHICLE TIRES WITHIN THE STATE OF FLORIDA. FLORIDA STATUTES TITLE XXIX CHAPTER 403.718. A $1.50 FEE FOR EACH NEW OR REMANUFACTURED LEAD-ACID BATTERY SOLD AT RETAIL IS IMPOSED ON ANY PERSON ENGAGING IN THE BUSINESS OF MAKING RETAIL SALES OF NEW OR REMANUFACTURED LEAD-ACID BATTERIES WITHIN THE STATE OF FLORIDA. FLORIDA STATUTES TITLE XXIX 403.7185.',
    'THIS ESTIMATE HAS BEEN PREPARED BASED ON THE USE OF CRASH PARTS SUPPLIED BY A SOURCE OTHER THAN THE MANUFACTURER OF YOUR MOTOR VEHICLE. THE AFTERMARKET CRASH PARTS USED IN THE PREPARATION OF THIS ESTIMATE ARE WARRANTED BY THE MANUFACTURER OR DISTRIBUTOR OF SUCH PARTS RATHER THAN THE MANUFACTURER OF YOUR VEHICLE.',
]
LEGEND = [
    ("", "Unless otherwise noted, labor times and part prices on this estimate are taken from published collision estimating guide data and from the supplier quotes listed on the Parts Supplier List, and the parts presented are OEM parts. OEM parts are manufactured by or for the vehicle's Original Equipment Manufacturer (OEM) according to OEM's specifications for U.S. distribution. OEM parts are available at OE/Vehicle dealerships or the specified supplier. OPT OEM (Optional OEM) or ALT OEM (Alternative OEM) parts are OEM parts that may be provided by or through alternate sources other than the OEM vehicle dealerships with discounted pricing. Asterisk (*) or Double Asterisk (**) indicates that the parts and/or labor data provided by third party sources of data may have been modified or may have come from an alternate data source. Tilde sign (~) items indicate Not-Included Labor operations. The symbol (<>) indicates the refinish operation WILL NOT be performed as a separate procedure from the other panels in the estimate. Non-Original Equipment Manufacturer aftermarket parts are described as Non OEM, A/M or NAGS. Used parts are described as LKQ, RCY, or USED. Reconditioned parts are described as Recond. Recored parts are described as Recore. NAGS Part Numbers and Benchmark Prices are provided by National Auto Glass Specifications. Pound sign (#) items indicate manual entries. Parts numbers and prices should be confirmed with the local dealership."),
    ("", "The following is a list of additional abbreviations or symbols that may be used to describe work to be done or parts to be repaired or replaced:"),
    ("SYMBOLS FOLLOWING PART PRICE:", "m=Mechanical component. s=Structural component. T=Miscellaneous Taxed charge category. X=Miscellaneous Non-Taxed charge category."),
    ("SYMBOLS FOLLOWING LABOR:", "D=Diagnostic labor category. E=Electrical labor category. F=Frame labor category. G=Glass labor category. M=Mechanical labor category. S=Structural labor category. (numbers) 1 through 4=User Defined Labor Categories."),
    ("OTHER SYMBOLS AND ABBREVIATIONS:", "Adj.=Adjacent. Algn.=Align. ALU=Aluminum. A/M=Aftermarket part. Blnd=Blend. BOR=Boron steel. CAPA=Certified Automotive Parts Association. CFC=Carbon Fiber. D&R=Disconnect and Reconnect. HSS=High Strength Steel. HYD=Hydroformed Steel. Incl.=Included. LKQ=Like Kind and Quality. LT=Left. MAG=Magnesium. Non-Adj.=Non Adjacent. NSF=NSF International Certified Part. O/H=Overhaul. Qty=Quantity. Refn=Refinish. Repl=Replace. R&I=Remove and Install. R&R=Remove and Replace. Rpr=Repair. RT=Right. SAS=Sandwiched Steel. Sect=Section. STS=Stainless Steel. Subl=Sublet. UHS=Ultra High Strength Steel. N=Note(s) associated with the estimate line. BAR=Bureau of Automotive Repair. EPA=Environmental Protection Agency. NHTSA=National Highway Transportation and Safety Administration. PDR=Paintless Dent Repair. VIN=Vehicle Identification Number."),
]


# ---------------------------------------------------------------- renderer
class Renderer:
    def __init__(self, job: Job, path: str | Path):
        self.job = job
        self.reg, self.bold, self.scale = fonts()
        self.c = canvas.Canvas(str(path), pagesize=letter)
        shop = job.shop()
        self.c.setTitle(f"{job.doc.title} - {job.customer.customer}".strip(" -"))
        self.c.setAuthor(shop["name"])
        self.page = 0
        self.warnings: list[str] = []

    # ---- primitives
    def font(self, size, bold=False):
        return (self.bold if bold else self.reg), size * self.scale

    def width(self, s, size=BODY, bold=False):
        f, sz = self.font(size, bold)
        return pdfmetrics.stringWidth(s, f, sz)

    def text(self, x, y, s, size=BODY, bold=False, align="l", maxw=None):
        s = "" if s is None else str(s)
        if not s:
            return
        if maxw is not None:
            s = self.fit(s, maxw, size, bold)
        f, sz = self.font(size, bold)
        self.c.setFont(f, sz)
        yy = PAGE_H - y
        if align == "l":
            self.c.drawString(x, yy, s)
        elif align == "r":
            self.c.drawRightString(x, yy, s)
        else:
            self.c.drawCentredString(x, yy, s)

    def underline(self, x, y, s, size=BODY, bold=False, align="l"):
        if not s:
            return
        w = self.width(s, size, bold)
        x0 = x if align == "l" else (x - w if align == "r" else x - w / 2)
        self.c.setLineWidth(0.5)
        self.c.line(x0, PAGE_H - y - 1.6, x0 + w, PAGE_H - y - 1.6)

    def fit(self, s, maxw, size=BODY, bold=False):
        if self.width(s, size, bold) <= maxw:
            return s
        while s and self.width(s + "…", size, bold) > maxw:
            s = s[:-1]
        return s + "…"

    def wrap(self, s, maxw, size=BODY, bold=False):
        words, lines, cur = str(s).split(), [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if cur and self.width(trial, size, bold) > maxw:
                lines.append(cur)
                cur = w
            else:
                cur = trial
            while self.width(cur, size, bold) > maxw and len(cur) > 1:   # very long single word
                cut = len(cur)
                while cut > 1 and self.width(cur[:cut], size, bold) > maxw:
                    cut -= 1
                lines.append(cur[:cut])
                cur = cur[cut:]
        if cur or not lines:
            lines.append(cur)
        return lines

    def hline(self, y, x0=L, x1=R, w=0.72, gray=0.0):
        self.c.setLineWidth(w)
        self.c.setStrokeGray(gray)
        self.c.line(x0, PAGE_H - y, x1, PAGE_H - y)
        self.c.setStrokeGray(0)

    # ---- page furniture
    def footer(self):
        j = self.job
        self.text(24.4, 743.9, j.printed())
        self.text(307.55, 743.9, j.doc.ro_number, align="c")
        self.text(558.1, 743.9, f"Page {self.page}", align="r")

    def title_block(self, y_title, y_rule, y_cust):
        j = self.job
        self.text(289.75, y_title, j.doc.title, SECT, True, "c")
        self.hline(y_rule, w=1.44)
        jobno = f"Job Number: {j.doc.job_number}".rstrip()
        jw = self.width(jobno, SECT, True)
        self.text(24.7, y_cust, f"Customer: {j.customer.customer}", SECT, True, maxw=555.9 - jw - 40 - 24.7)
        self.text(555.9, y_cust, jobno, SECT, True, "r")

    def new_page(self, running=True):
        if self.page:
            self.footer()
            self.c.showPage()
        self.page += 1
        if running:
            self.title_block(31.6, 37.1, 52.1)
            self.text(22.9, 67.1, self.job.vehicle.description(), maxw=R - 22.9)

    # ---- page 1
    def page_one(self):
        j, shop = self.job, self.job.shop()
        self.new_page(running=False)
        self.text(288.6, 35.0, shop["name"], SHOP, True, "c")
        y = 51.0
        for s in (f"{shop['street']}, {shop['city']}", f"Phone: {shop['phone']}",
                  f"FAX: {shop['fax']}" if shop.get("fax") else ""):
            if s:
                self.text(288.6, y, s, SECT, False, "c")
                y += 13.3
        if j.doc.workfile_id:
            self.text(433.9, 31.1, "Workfile ID:")
            self.text(558.0, 31.1, j.doc.workfile_id, align="r")

        self.title_block(113.5, 119.2, 134.0)
        if j.doc.written_by:
            self.text(290.65, 149.0, f"Written By: {j.doc.written_by}", align="c")

        c = j.customer
        grid = [
            (172.7, [("Insured:", c.insured or c.customer), ("Policy #:", c.policy), ("Claim #:", c.claim)]),
            (186.2, [("Type of Loss:", c.loss_type), ("Date of Loss:", c.loss_date), ("Days to Repair:", c.days_to_repair)]),
            (199.8, [("Point of Impact:", c.point_of_impact), None, None]),
        ]
        cols = [(24.4, 89.1, 118), (207.9, 272.6, 105), (380.6, 445.4, 115)]
        for y, cells in grid:
            for (lx, vx, vw), cell in zip(cols, cells):
                if cell:
                    self.text(lx, y, cell[0])
                    self.text(vx, y, cell[1], maxw=vw)

        self.text(24.4, 224.9, "Owner:", bold=True)
        self.text(202.6, 224.9, "Inspection Location:", bold=True)
        self.text(380.7, 224.9, "Insurance Company:", bold=True)
        self.text(24.4, 238.3, c.owner or c.customer, maxw=172)
        self.text(380.6, 238.3, c.insurer, maxw=178)
        for k, s in enumerate([shop["name"], shop["street"], shop["city"], "Repair Facility",
                               f"{shop['phone']} Business"]):
            self.text(202.6, 238.3 + k * 13.57, s, maxw=172)
        self.hline(308.2)

        v = j.vehicle
        self.text(290.7, 330.2, "VEHICLE", SECT, True, "c")
        self.text(24.4, 354.6, v.description(), maxw=R - 24.4)
        vgrid = [
            (374.5, [("VIN:", v.vin), ("Interior Color:", v.interior_color), ("Mileage In:", v.mileage_in), ("Vehicle Out:", v.vehicle_out)]),
            (388.1, [("License:", v.license), ("Exterior Color:", v.exterior_color), ("Mileage Out:", v.mileage_out), None]),
            (401.6, [("State:", v.state), ("Production Date:", v.production_date), ("Condition:", v.condition), ("Job #:", v.job_no)]),
        ]
        vcols = [(24.4, 62.1, 105), (170.0, 235.0, 105), (342.8, 399.8, 54), (456.1, 505.1, 56)]
        for y, cells in vgrid:
            for (lx, vx, vw), cell in zip(vcols, cells):
                if cell:
                    self.text(lx, y, cell[0])
                    self.text(vx, y, cell[1], maxw=vw)
        self.hline(417.2)

        opts = [o.strip() for o in j.options.splitlines() if o.strip()]
        if opts:
            max_rows = int((BOTTOM - 439.0) / PITCH) + 1
            rows = max(1, math.ceil(len(opts) / 4))
            if rows > max_rows:
                self.warnings.append(f"Only the first {max_rows * 4} vehicle options fit on page 1.")
                rows = max_rows
                opts = opts[: rows * 4]
            xs = [46.0, 180.9, 315.8, 451.0]
            for i, o in enumerate(opts):
                col, row = divmod(i, rows)
                heading = o.upper() == o and any(ch.isalpha() for ch in o)
                self.text(xs[col], 439.0 + row * PITCH, o, bold=heading, maxw=130)

    # ---- line items
    COLS = dict(line=37.75, sym=56.8, oper=126.7, desc=143.2, part=352.6, qty=385.9, ext=439.6,
                ptype=445.6, labor=499.2, cat=505.0, paint=558.6)
    DESC_W = 150.0

    def items_header(self):
        self.hline(87.7)
        self.text(37.65, 97.2, "Line", bold=True, align="c")
        self.text(126.65, 97.2, "Oper", bold=True, align="c")
        self.text(181.6, 97.2, "Description", bold=True)
        self.text(312.55, 97.2, "Part Number", bold=True, align="c")
        self.text(385.6, 97.2, "Qty", bold=True, align="r")
        self.text(439.1, 97.2, "Extended", bold=True, align="r")
        self.text(439.3, 107.9, "Price $", bold=True, align="r")
        self.text(498.7, 97.2, "Labor", bold=True, align="r")
        self.text(558.1, 97.2, "Paint", bold=True, align="r")
        self.hline(112.0)
        return 121.3

    def line_items(self):
        j, C = self.job, self.COLS
        show = j.output.show_prices
        self.new_page()
        y = self.items_header()
        prev = None   # baseline of the previous row's last line
        for n, ln in j.numbered():
            if ln.kind == "section":
                lines = self.wrap(ln.description.upper() if ln.description else "", R - C["sym"], BODY, True)
            else:
                lines = self.wrap(ln.description, self.DESC_W)
            need = (len(lines) - 1) * PITCH
            if y + need > BOTTOM:
                self.new_page()
                y = self.items_header()
                prev = None
            if ln.kind == "section" and prev is not None:
                self.hline(prev + 4.1, w=0.5, gray=GRAY)
            self.text(C["line"], y, str(n), align="c")
            if ln.kind == "section":
                for k, s in enumerate(lines):
                    self.text(C["sym"], y + k * PITCH, s, bold=True)
            else:
                self.text(C["sym"], y, ln.sym)
                self.text(C["oper"], y, ln.oper, align="c", maxw=24)
                for k, s in enumerate(lines):
                    self.text(C["desc"], y + k * PITCH, s)
                self.text(C["part"], y, ln.part_no, align="r", maxw=62)
                self.text(C["qty"], y, ln.qty, align="r", maxw=24)
                e = extended(ln)
                vals = [(C["labor"], fmt_hours(ln.labor)), (C["paint"], fmt_hours(ln.paint))]
                if show and e is not None:
                    vals.append((C["ext"], money(e)))
                for x, v in vals:
                    self.text(x, y, v, align="r", maxw=48)
                    if ln.changed and num(v) is not None:
                        self.underline(x, y, v, align="r")
                self.text(C["ptype"], y, ln.part_type)
                if num(ln.labor) is not None:
                    self.text(C["cat"], y, ln.labor_cat)
            prev = y + need
            y = prev + PITCH

        t = j.totals()
        if prev is None:
            prev = y - PITCH
        if prev + 4.0 + PITCH + 4.1 > BOTTOM + 6:
            self.new_page()
            prev = self.items_header() - PITCH
        self.hline(prev + 4.0)
        ys = prev + 13.5
        self.text(320.5, ys, "SUBTOTALS", bold=True, align="r")
        if show:
            self.text(439.4, ys, money(t.parts), bold=True, align="r")
        self.text(499.0, ys, hrs(t.labor_total_hours), bold=True, align="r")
        self.text(558.5, ys, hrs(t.paint_hours), bold=True, align="r")
        self.hline(ys + 4.1)
        return ys

    # ---- estimate totals
    def totals(self, y_sub):
        j = self.job
        t = j.totals()
        n = len(t.rows)
        height = 26.9 + 27.8 + (n - 1) * PITCH + 3 * PITCH + 4.1 + 13.55
        y0 = y_sub + 26.9
        if y0 - 26.9 + height > BOTTOM + 10:
            self.new_page()
            y0 = 97.7
        X0, X1 = 140.4, 556.2
        self.text(143.5, y0, "ESTIMATE TOTALS", SECT, True)
        self.hline(y0 + 4.9, X0, X1)
        hy = y0 + 14.3
        self.text(143.2, hy, "Category", bold=True)
        self.text(406.9, hy, "Basis", bold=True, align="r")
        self.text(493.5, hy, "Rate", bold=True, align="r")
        self.text(552.7, hy, "Cost $", bold=True, align="r")
        self.hline(y0 + 18.5, X0, X1)
        y = y0 + 27.8
        for cat, basis, rate, cost in t.rows:
            self.text(143.2, y, cat)
            if basis:
                self.text(407.0, y, basis, align="r")
                self.text(423.75, y, "@", align="c")
                self.text(493.2, y, rate, align="r")
            self.text(553.0, y, money(cost), align="r")
            y += PITCH
        y -= PITCH
        self.hline(y + 4.2, X0, X1)
        y += PITCH
        self.text(143.2, y, "Subtotal")
        self.text(552.7, y, money(t.subtotal), align="r")
        self.hline(y + 4.1, X0, X1)
        y += PITCH
        self.text(143.2, y, "Sales Tax")
        self.text(406.7, y, f"$ {money(t.taxable)}", align="r")
        self.text(423.75, y, "@", align="c")
        self.text(493.3, y, f"{j.rates.tax_rate:.4f} %", align="r")
        self.text(552.9, y, money(t.tax), align="r")
        self.hline(y + 4.1, X0, X1)
        y += PITCH
        self.text(143.2, y, "Grand Total", bold=True)
        self.text(552.6, y, money(t.grand), bold=True, align="r")
        self.hline(y + 4.1, X0, X1)

    # ---- disclosure pages
    def paragraphs(self, paras):
        self.new_page()
        y = 86.2
        width = 518.0
        for head, body in paras:
            block = ([head] if head else []) + self.wrap(body, width, SECT)
            if y + (len(block) - 1) * LEGAL_PITCH > BOTTOM:
                self.new_page()
                y = 86.2
            for s in block:
                self.text(23.3, y, s, SECT)
                y += LEGAL_PITCH
            y += LEGAL_PITCH

    # ---- parts supplier list
    def suppliers(self):
        sups = [s for s in self.job.suppliers if any(str(v).strip() for v in vars(s).values())]
        if not sups:
            return
        show = self.job.output.show_prices

        def head():
            self.text(289.8, 97.7, "PARTS SUPPLIER LIST", SECT, True, "c")
            self.text(43.05, 122.0, "Line", bold=True, align="c")
            self.text(67.6, 122.0, "Supplier", bold=True)
            self.text(229.5, 122.0, "Description", bold=True)
            self.text(558.1, 122.0, "Price", bold=True, align="r")
            self.hline(126.1)
            return 135.6

        self.new_page()
        y = head()
        for i, s in enumerate(sups):
            left = [x for x in (s.name, s.street, s.city, s.phone) if x.strip()]
            right = [x for x in (s.part_no, s.description, f"Quote: {s.quote}" if s.quote.strip() else "",
                                 f"Expires: {s.expires}" if s.expires.strip() else "") if x.strip()]
            nlines = max(len(left), len(right), 1)
            if y + (nlines - 1) * 13.5 > BOTTOM:
                self.new_page()
                y = head()
            self.text(43.1, y, s.line, align="c")
            for k, t in enumerate(left):
                self.text(67.6, y + k * 13.5, t, maxw=155)
            for k, t in enumerate(right):
                self.text(229.5, y + k * 13.5, t, maxw=250)
            p = num(s.price)
            if show and (p is not None or s.price.strip()):
                self.text(558.1, y, f"$ {money(p)}" if p is not None else s.price, align="r")
            last = y + (nlines - 1) * 13.5
            if i < len(sups) - 1:
                self.hline(last + 12.7)
                y = last + 12.7 + 9.5

    # ---- all
    def render(self):
        self.page_one()
        y_sub = self.line_items()
        if self.job.output.show_prices:
            self.totals(y_sub)
        if self.job.output.include_disclosures:
            self.paragraphs([("", p) for p in NOTICES])
            self.paragraphs(LEGEND)
        self.suppliers()
        self.footer()
        self.c.save()
        return self.warnings


def fmt_hours(s: str) -> str:
    v = num(s)
    if v is None:
        return (s or "").strip()
    return f"{v:.1f}"


def render_pdf(job: Job, path: str | Path) -> list[str]:
    """Write the PDF; returns a list of warnings (empty when everything fit)."""
    return Renderer(job, path).render()
