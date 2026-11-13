"""Fill the shop's LaTeX template (template.tex) with a Job and write the .tex source."""
from __future__ import annotations

import math
import re
from pathlib import Path

from .model import Job, extended, money, hrs, num
from .pdf_render import fmt_hours, resource_dir

_ESC = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
        "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def esc(s) -> str:
    return "".join(_ESC.get(ch, ch) for ch in str(s or ""))


def _set(tex: str, name: str, value: str) -> str:
    pat = re.compile(r"(\\newcommand\{\\" + name + r"\}\{)(.*?)(\})(?=[^\n]*\n)")
    new, n = pat.subn(lambda m: m.group(1) + value + m.group(3), tex, count=1)
    if not n:
        raise ValueError(f"template has no \\{name}")
    return new


def _between(tex: str, start: str, end: str, body: str) -> str:
    i = tex.index(start) + len(start)
    j = tex.index(end, i)
    return tex[:i] + "\n" + body + "\n" + tex[j:]


def build_tex(job: Job) -> str:
    tex = (resource_dir() / "template.tex").read_text(encoding="utf-8")
    shop, c, v, d = job.shop(), job.customer, job.vehicle, job.doc
    show = job.output.show_prices
    values = {
        "ShopName": shop["name"], "ShopAddress": f"{shop['street']}, {shop['city']}",
        "ShopStreet": shop["street"], "ShopCity": shop["city"], "ShopPhone": shop["phone"],
        "ShopFax": shop.get("fax", ""), "EstimateTitle": d.title, "WorkfileID": d.workfile_id,
        "RONumber": d.ro_number, "PrintedDate": job.printed(), "CustomerName": c.customer,
        "JobNumber": d.job_number, "WrittenBy": d.written_by, "Insured": c.insured or c.customer,
        "PolicyNo": c.policy, "ClaimNo": c.claim, "TypeOfLoss": c.loss_type, "DateOfLoss": c.loss_date,
        "DaysToRepair": c.days_to_repair, "PointOfImpact": c.point_of_impact,
        "OwnerName": c.owner or c.customer, "InsuranceCompany": c.insurer,
        "VehicleDesc": v.description(), "VIN": v.vin, "License": v.license, "VehState": v.state,
        "InteriorColor": v.interior_color, "ExteriorColor": v.exterior_color,
        "ProductionDate": v.production_date, "MileageIn": v.mileage_in, "MileageOut": v.mileage_out,
        "Condition": v.condition, "VehicleOut": v.vehicle_out, "JobNo": v.job_no,
    }
    for k, val in values.items():
        tex = _set(tex, k, esc(val))

    # vehicle options grid (column-major, 4 columns, ALL CAPS lines are headings)
    opts = [o.strip() for o in job.options.splitlines() if o.strip()]
    rows = max(1, math.ceil(len(opts) / 4)) if opts else 0
    grid = [["" for _ in range(4)] for _ in range(rows)]
    for i, o in enumerate(opts):
        col, row = divmod(i, rows)
        heading = o.upper() == o and any(ch.isalpha() for ch in o)
        grid[row][col] = rf"\textbf{{{esc(o)}}}" if heading else esc(o)
    opt_body = "\n".join("  " + " & ".join(r) + r"\\" for r in grid) or r"  & & & \\"
    start = tex.index("% ---------- Vehicle options")
    tab_start = tex.index("\n", tex.index(r"\begin{tabular}", start)) + 1
    tab_end = tex.index(r"\end{tabular}", tab_start)
    tex = tex[:tab_start] + opt_body + "\n" + tex[tab_end:]

    # line items
    out, first = [], True
    for n, ln in job.numbered():
        if ln.kind == "section":
            if not first:
                out.append(r"  \groupsep")
            out.append(rf"  \Group{{{n}}}{{{esc(ln.description.upper())}}}")
        else:
            e = extended(ln)
            ext = money(e) if (show and e is not None) else ""
            lab, pnt = fmt_hours(ln.labor), fmt_hours(ln.paint)
            u = (lambda s: rf"\ul{{{esc(s)}}}" if (ln.changed and num(s) is not None) else esc(s))
            args = [str(n), ln.sym, ln.oper, ln.description, ln.part_no, ln.qty]
            out.append("  \\Item" + "".join("{%s}" % esc(a) for a in args)
                       + "{%s}{%s}{%s}{%s}{%s}" % (u(ext), esc(ln.part_type), u(lab), esc(ln.labor_cat) if num(ln.labor) is not None else "", u(pnt)))
        first = False
    t = job.totals()
    out.append(rf"  \Subtotals{{{money(t.parts) if show else ''}}}{{{hrs(t.labor_total_hours)}}}{{{hrs(t.paint_hours)}}}")
    tex = _between(tex, r"\begin{lineitems}", r"\end{lineitems}", "\n".join(out))

    # totals
    if show:
        tot = [rf"  \TotalRow{{{esc(cat)}}}{{{esc(b)}}}{{{esc(r)}}}{{{money(cost)}}}" for cat, b, r, cost in t.rows]
        tot += [rf"  \TotalLine{{Subtotal}}{{{money(t.subtotal)}}}",
                rf"  \TaxRow{{Sales Tax}}{{\$ {money(t.taxable)}}}{{{job.rates.tax_rate:.4f} \%}}{{{money(t.tax)}}}",
                rf"  \GrandTotal{{Grand Total}}{{{money(t.grand)}}}"]
        tex = _between(tex, r"\begin{totals}", r"\end{totals}", "\n".join(tot))
    else:
        i = tex.index(r"\begin{totals}")
        j = tex.index(r"\end{totals}") + len(r"\end{totals}")
        tex = tex[:i] + tex[j:]

    # suppliers
    sups = [s for s in job.suppliers if any(str(x).strip() for x in vars(s).values())]
    p5 = tex.index("%  PAGE 5")
    p5 = tex.rindex(r"\newpage", 0, p5)
    if sups:
        rows_ = []
        for s in sups:
            p = num(s.price)
            price = (rf"\$ {money(p)}" if p is not None else esc(s.price)) if show else ""
            fields_ = [s.line, s.name, s.street, s.city, s.phone, s.part_no, s.description,
                       f"Quote: {s.quote}" if s.quote.strip() else "",
                       f"Expires: {s.expires}" if s.expires.strip() else ""]
            rows_.append("  \\Supplier" + "".join("{%s}" % esc(f) for f in fields_) + "{%s}" % price)
        tex = _between(tex, r"\begin{suppliers}", r"\end{suppliers}", "\n".join(rows_))
    else:
        tex = tex[:p5] + tex[tex.index(r"\end{document}"):]

    # disclosure pages
    if not job.output.include_disclosures:
        p3 = tex.rindex(r"\newpage", 0, tex.index("%  PAGE 3"))
        p5 = tex.find("%  PAGE 5")
        end = tex.rindex(r"\newpage", 0, p5) if p5 != -1 else tex.index(r"\end{document}")
        tex = tex[:p3] + tex[end:]
    return tex


def write_tex(job: Job, path: str | Path) -> None:
    Path(path).write_text(build_tex(job), encoding="utf-8")
