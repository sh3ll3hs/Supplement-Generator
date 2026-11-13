"""Data model, defaults, JSON persistence and totals math for a supplement/estimate."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------- shops
SHOPS = {
    "Rescue Automotive": {
        "name": "RESCUE AUTOMOTIVE", "street": "10531 E Colonial Dr", "city": "Orlando, FL 32817",
        "phone": "(407) 658-9040", "fax": "",
    },
}
DEFAULT_SHOP = "Rescue Automotive"

TITLES = ["Supplement of Record 1", "Supplement of Record 2", "Supplement of Record 3",
          "Supplement of Record 4", "Supplement of Record 5", "Preliminary Estimate", "Estimate of Record"]
OPERATIONS = ["Repl", "Rpr", "R&I", "Refn", "Blnd", "O/H", "Subl", "Algn", "Add'l Labor", ""]
SYMBOLS = ["", "#", "*", "**"]
PART_TYPES = ["", "m", "s", "T", "X"]  # m=mechanical, s=structural, T/X misc taxed/non-taxed

# labor category code -> (label on totals, default rate key)
LABOR_CATS = {
    "":  "Body Labor",
    "M": "Mechanical Labor",
    "F": "Frame Labor",
    "S": "Structural Labor",
    "E": "Electrical Labor",
    "D": "Diagnostic Labor",
    "G": "Glass Labor",
}
LABOR_CAT_NAMES = {"": "Body", "M": "Mechanical", "F": "Frame", "S": "Structural",
                   "E": "Electrical", "D": "Diagnostic", "G": "Glass"}


# ---------------------------------------------------------------- dataclasses
@dataclass
class Doc:
    shop: str = DEFAULT_SHOP
    title: str = "Supplement of Record 1"
    workfile_id: str = ""
    ro_number: str = ""
    written_by: str = ""
    job_number: str = ""
    printed: str = ""          # blank -> current date/time at generation


@dataclass
class Customer:
    customer: str = ""
    insured: str = ""          # blank -> customer
    owner: str = ""            # blank -> customer
    policy: str = ""
    claim: str = ""
    insurer: str = ""
    loss_type: str = ""
    loss_date: str = ""
    point_of_impact: str = ""
    days_to_repair: str = ""


@dataclass
class Vehicle:
    year: str = ""
    make: str = ""
    model: str = ""
    details: str = ""          # trim / body / engine text after the model
    vin: str = ""
    license: str = ""
    state: str = ""
    interior_color: str = ""
    exterior_color: str = ""
    production_date: str = ""
    mileage_in: str = ""
    mileage_out: str = ""
    condition: str = ""
    vehicle_out: str = ""
    job_no: str = ""

    def description(self) -> str:
        return " ".join(p.strip() for p in (self.year, self.make, self.model, self.details) if p.strip())


@dataclass
class Line:
    """One row of the line-item table. kind = 'section' (bold heading) or 'item'."""
    kind: str = "item"
    sym: str = ""
    oper: str = "Repl"
    description: str = ""
    part_no: str = ""
    qty: str = ""
    price: str = ""            # unit price; extended = qty * price
    part_type: str = ""
    labor: str = ""            # hours, or text such as "Incl."
    labor_cat: str = ""        # "", M, F, S, E, D, G
    paint: str = ""            # refinish hours, or text
    changed: bool = False      # underline price/hours (how CCC marks supplement changes)


@dataclass
class Supplier:
    line: str = ""
    name: str = ""
    street: str = ""
    city: str = ""
    phone: str = ""
    part_no: str = ""
    description: str = ""
    quote: str = ""
    expires: str = ""
    price: str = ""


@dataclass
class Rates:
    body: float = 63.0
    paint: float = 63.0
    mechanical: float = 130.0
    frame: float = 105.0
    structural: float = 63.0
    electrical: float = 130.0
    diagnostic: float = 130.0
    glass: float = 63.0
    paint_supplies: float = 48.0
    tax_rate: float = 6.5
    tax_labor: bool = True     # tax the whole subtotal (as on the shop's estimates) vs parts + supplies only

    def for_cat(self, cat: str) -> float:
        return {"": self.body, "M": self.mechanical, "F": self.frame, "S": self.structural,
                "E": self.electrical, "D": self.diagnostic, "G": self.glass}[cat]


@dataclass
class Output:
    show_prices: bool = True
    include_disclosures: bool = True
    save_tex: bool = False
    open_after: bool = True


@dataclass
class Job:
    doc: Doc = field(default_factory=Doc)
    customer: Customer = field(default_factory=Customer)
    vehicle: Vehicle = field(default_factory=Vehicle)
    options: str = ""
    lines: list[Line] = field(default_factory=list)
    rates: Rates = field(default_factory=Rates)
    suppliers: list[Supplier] = field(default_factory=list)
    output: Output = field(default_factory=Output)

    # ------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        def build(dc, data):
            names = {f.name for f in fields(dc)}
            return dc(**{k: v for k, v in (data or {}).items() if k in names})
        return cls(
            doc=build(Doc, d.get("doc")), customer=build(Customer, d.get("customer")),
            vehicle=build(Vehicle, d.get("vehicle")), options=d.get("options", ""),
            lines=[build(Line, x) for x in d.get("lines", [])],
            rates=build(Rates, d.get("rates")),
            suppliers=[build(Supplier, x) for x in d.get("suppliers", [])],
            output=build(Output, d.get("output")),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Job":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # ------------------------------------------------------------ derived
    def shop(self) -> dict:
        # Always Rescue Automotive — the sister shop uses its own tools. Older job files
        # that named another shop still print with the Rescue header.
        return SHOPS[DEFAULT_SHOP]

    def printed(self) -> str:
        if self.doc.printed.strip():
            return self.doc.printed.strip()
        n = datetime.now()
        return f"{n.month}/{n.day}/{n.year} {n.strftime('%I:%M:%S %p').lstrip('0')}"

    def numbered(self) -> list[tuple[int, Line]]:
        """Line numbers are assigned in order; section headings take a number too (as CCC does)."""
        return [(i + 1, ln) for i, ln in enumerate(self.lines)]

    def totals(self) -> "Totals":
        return compute_totals(self)


# ---------------------------------------------------------------- math
def num(s) -> float | None:
    """Parse '1,234.50', '$ 12', '-0.3'; return None for blank or text like 'Incl.'."""
    if s is None:
        return None
    t = str(s).replace("$", "").replace(",", "").strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def money(v: float) -> str:
    return f"{v:,.2f}"


def hrs(v: float) -> str:
    return f"{v:.1f}"


def r2(v: float) -> float:
    return float(f"{v + (1e-9 if v >= 0 else -1e-9):.2f}")


def extended(ln: Line) -> float | None:
    p = num(ln.price)
    if p is None:
        return None
    q = num(ln.qty)
    return r2(p * (q if q is not None else 1))


@dataclass
class Totals:
    parts: float
    labor_hours: dict          # cat -> hours (only non-zero)
    labor_total_hours: float
    paint_hours: float
    rows: list                 # [(category, basis, rate, cost)]
    subtotal: float
    taxable: float
    tax: float
    grand: float


def compute_totals(job: Job) -> Totals:
    parts = 0.0
    cat_hours: dict[str, float] = {}
    paint = 0.0
    for ln in job.lines:
        if ln.kind != "item":
            continue
        e = extended(ln)
        if e is not None:
            parts += e
        h = num(ln.labor)
        if h is not None:
            cat = ln.labor_cat if ln.labor_cat in LABOR_CATS else ""
            cat_hours[cat] = cat_hours.get(cat, 0.0) + h
        p = num(ln.paint)
        if p is not None:
            paint += p
    parts = r2(parts)
    cat_hours = {k: round(v, 1) for k, v in cat_hours.items()}
    paint = round(paint, 1)
    R = job.rates
    rows = [("Parts", "", "", parts)]
    order = ["", "", "M", "F", "S", "E", "D", "G"]  # body, (paint inserted after body), ...
    labor_cost = 0.0
    # Body labor first, then Paint labor, then the rest — same order as the shop's estimates
    if cat_hours.get("", 0):
        c = r2(cat_hours[""] * R.body); labor_cost += c
        rows.append(("Body Labor", f"{hrs(cat_hours[''])} hrs", f"$ {R.body:,.2f} /hr", c))
    if paint:
        c = r2(paint * R.paint); labor_cost += c
        rows.append(("Paint Labor", f"{hrs(paint)} hrs", f"$ {R.paint:,.2f} /hr", c))
    for cat in order[2:]:
        h = cat_hours.get(cat, 0)
        if h:
            rate = R.for_cat(cat)
            c = r2(h * rate); labor_cost += c
            rows.append((LABOR_CATS[cat], f"{hrs(h)} hrs", f"$ {rate:,.2f} /hr", c))
    supplies = 0.0
    if paint:
        supplies = r2(paint * R.paint_supplies)
        rows.append(("Paint Supplies", f"{hrs(paint)} hrs", f"$ {R.paint_supplies:,.2f} /hr", supplies))
    subtotal = r2(parts + labor_cost + supplies)
    taxable = subtotal if R.tax_labor else r2(parts + supplies)
    tax = r2(taxable * R.tax_rate / 100.0)
    return Totals(
        parts=parts, labor_hours={k: v for k, v in cat_hours.items() if v},
        labor_total_hours=round(sum(cat_hours.values()), 1), paint_hours=paint,
        rows=rows, subtotal=subtotal, taxable=taxable, tax=tax, grand=r2(subtotal + tax),
    )


# ---------------------------------------------------------------- sample (the 2018 Sentra estimate)
def sample_job() -> Job:
    L = Line
    return Job(
        doc=Doc(title="Preliminary Estimate", workfile_id="00000000", ro_number="100001",
                written_by="Estimator", printed="11/4/2026 4:26:21 PM"),
        customer=Customer(customer="SAMPLE, CUSTOMER", claim="SAMPLE-CLAIM-0001",
                          insurer="SAMPLE INSURANCE COMPANY", days_to_repair="0"),
        vehicle=Vehicle(year="2018", make="NISS", model="Sentra",
                        details="SV w/Continuously Variable Transmission 4D SED 4-1.8L Gasoline Sequential MPI",
                        vin="SAMPLEVIN00000001"),
        options="\n".join([
            "TRANSMISSION", "Automatic Transmission", "POWER", "Power Steering", "Power Brakes",
            "Power Windows", "Power Locks", "Power Mirrors", "DECOR", "Dual Mirrors", "Tinted Glass",
            "Console/Storage", "Overhead Console", "CONVENIENCE", "Air Conditioning", "Intermittent Wipers",
            "Tilt Wheel", "Cruise Control", "Rear Defogger", "Keyless Entry", "Alarm", "Message Center",
            "Steering Wheel Touch Controls", "Telescopic Wheel", "Climate Control", "Backup Camera",
            "RADIO", "AM Radio", "FM Radio", "Stereo", "Search/Seek", "CD Player",
            "Auxiliary Audio Connection", "Satellite Radio", "SAFETY", "Drivers Side Air Bag",
            "Passenger Air Bag", "Anti-Lock Brakes (4)", "Front Side Impact Air Bags",
            "Head/Curtain Air Bags", "Hands Free Device", "SEATS", "Cloth Seats", "Bucket Seats",
            "WHEELS", "Aluminum/Alloy Wheels", "PAINT", "Clear Coat Paint", "OTHER", "Traction Control",
            "Stability Control"]),
        lines=[
            L("section", description="RADIATOR SUPPORT"),
            L(sym="*", oper="Repl", description="Upper tie bar", part_no="F25113SHMA", qty="1", price="287.60",
              part_type="s", labor="1.5", paint="0.8"),
            L("section", description="COOLING"),
            L(sym="**", oper="Repl", description="A/M Radiator all", part_no="214103SH0A", qty="1", price="140.00",
              part_type="m", labor="1.6", labor_cat="M"),
            L(sym="**", oper="Repl", description="A/M Fan assy", part_no="214819AP0A", qty="1", price="125.00",
              part_type="m", labor="Incl."),
            L("section", description="AIR CONDITIONER & HEATER"),
            L(sym="**", oper="Repl", description="A/M Condenser assy 1.8 liter", part_no="921003SH0C", qty="1",
              price="111.65", part_type="m", labor="0.6"),
            L(oper="", description="AC Service evacuate & recharge", part_type="m", labor="1.4", labor_cat="M"),
            L(oper="", description="AC Service refrigerant recovery", part_type="m", labor="0.4", labor_cat="M"),
            L(oper="", description="Deduct for Overlap", labor="-0.3", labor_cat="M"),
            L(sym="#", oper="Rpr", description="Setup & measure", labor="1.5", labor_cat="F"),
            L(sym="#", oper="Rpr", description="Rough pull", labor="1.5", labor_cat="F"),
            L("section", description="ELECTRICAL"),
            L(oper="Repl", description="Low note horn", part_no="256204AF0A", qty="1", price="124.05", labor="0.2"),
        ],
        suppliers=[
            Supplier("4", "Performance Radiator", "470 27th St", "Orlando FL 32806", "(407) 245-8787",
                     "#2332", "A/M Radiator all", "SAMPLE-Q-1001", "11/11/26", "140.00"),
            Supplier("5", "Performance Radiator", "470 27th St", "Orlando FL 32806", "(407) 245-8787",
                     "#622960", "A/M Fan assy", "SAMPLE-Q-1002", "11/11/26", "125.00"),
            Supplier("7", "KSI Collision Parts", "3863 W D Judge Dr, Suite 110", "Orlando FL 32808",
                     "(800) 574-7278", "#NI3030173", "A/M Condenser assy 1.8 liter", "SAMPLE-Q-1003",
                     "11/05/26", "111.65"),
        ],
    )
