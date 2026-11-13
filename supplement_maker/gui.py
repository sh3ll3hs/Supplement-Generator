"""Tkinter desktop form: fill in the job, list the supplement lines, generate the PDF."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import asdict, fields
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .model import (DEFAULT_SHOP, LABOR_CAT_NAMES, OPERATIONS, PART_TYPES, SHOPS, SYMBOLS, TITLES,
                    Job, Line, Rates, Supplier, extended, hrs, money, num, sample_job)
from .pdf_render import render_pdf

APP_NAME = "Supplement Maker"
IS_MAC = sys.platform == "darwin"
MOD = "Command" if IS_MAC else "Control"
MOD_LABEL = "Cmd" if IS_MAC else "Ctrl"

CAT_LABELS = {k: (f"{v} ({k})" if k else v) for k, v in LABOR_CAT_NAMES.items()}
CAT_FROM_LABEL = {v: k for k, v in CAT_LABELS.items()}
PTYPE_LABELS = {"": "(none)", "m": "m - mechanical", "s": "s - structural", "T": "T - misc. taxed",
                "X": "X - misc. non-taxed"}
PTYPE_FROM_LABEL = {v: k for k, v in PTYPE_LABELS.items()}
SYM_LABELS = {"": "(none)", "#": "# - manual entry", "*": "* - modified data", "**": "** - alternate source"}
SYM_FROM_LABEL = {v: k for k, v in SYM_LABELS.items()}


# ---------------------------------------------------------------- settings
def settings_path() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "SupplementMaker" / "settings.json"


def load_settings() -> dict:
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(d: dict) -> None:
    try:
        p = settings_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except Exception:
        pass


def open_file(path: str) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif IS_MAC:
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def documents_dir() -> str:
    d = Path.home() / "Documents"
    return str(d if d.exists() else Path.home())


# ---------------------------------------------------------------- small widgets
class Form:
    """Grid helper: label + entry/combobox pairs bound to StringVars."""

    def __init__(self, parent, vars_: dict, on_change):
        self.parent, self.vars, self.on_change = parent, vars_, on_change

    def var(self, key):
        if key not in self.vars:
            v = tk.StringVar()
            v.trace_add("write", lambda *_: self.on_change())
            self.vars[key] = v
        return self.vars[key]

    def add(self, row, col, label, key, width=24, values=None, readonly=False, hint=None):
        ttk.Label(self.parent, text=label).grid(row=row, column=col, sticky="w", padx=(8, 4), pady=3)
        if values is not None:
            w = ttk.Combobox(self.parent, textvariable=self.var(key), values=values, width=width - 2,
                             state="readonly" if readonly else "normal")
        else:
            w = ttk.Entry(self.parent, textvariable=self.var(key), width=width)
        w.grid(row=row, column=col + 1, sticky="we", padx=(0, 8), pady=3)
        if hint:
            ttk.Label(self.parent, text=hint, style="Hint.TLabel").grid(
                row=row, column=col + 2, sticky="w", padx=(0, 8))
        return w


class Dialog(tk.Toplevel):
    """Modal dialog base with OK / Cancel (and optional 'Save & add another')."""

    def __init__(self, master, title, another=False):
        super().__init__(master)
        self.withdraw()
        self.title(title)
        self.transient(master)
        self.resizable(False, False)
        self.result = None
        self.again = False
        self.body = ttk.Frame(self, padding=12)
        self.body.pack(fill="both", expand=True)
        btns = ttk.Frame(self, padding=(12, 0, 12, 12))
        btns.pack(fill="x")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="OK", command=self._ok, style="Accent.TButton").pack(side="right", padx=6)
        if another:
            ttk.Button(btns, text="OK + add another", command=lambda: self._ok(again=True)).pack(side="right")
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

    def show(self):
        self.update_idletasks()
        m = self.master
        x = m.winfo_rootx() + (m.winfo_width() - self.winfo_reqwidth()) // 2
        y = m.winfo_rooty() + (m.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.grab_set()
        self.focus_first()
        self.wait_window()
        return self.result

    def focus_first(self):
        pass

    def _ok(self, again=False):
        r = self.validate()
        if r is None:
            return
        self.result, self.again = r, again
        self.destroy()

    def validate(self):
        return True


class LineDialog(Dialog):
    def __init__(self, master, line: Line | None = None, title="Supplement line"):
        super().__init__(master, title, another=line is None)
        ln = line or Line()
        f = self.body
        self.v = {k: tk.StringVar(value=getattr(ln, k)) for k in
                  ("oper", "description", "part_no", "qty", "price", "labor", "paint")}
        self.sym = tk.StringVar(value=SYM_LABELS.get(ln.sym, ln.sym))
        self.ptype = tk.StringVar(value=PTYPE_LABELS.get(ln.part_type, ln.part_type))
        self.cat = tk.StringVar(value=CAT_LABELS.get(ln.labor_cat, "Body"))
        self.changed = tk.BooleanVar(value=ln.changed)

        def row(r, label, widget, hint=None):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=4, padx=(0, 8))
            widget.grid(row=r, column=1, sticky="we" if widget is getattr(self, "desc", None) else "w", pady=4)
            if hint:
                ttk.Label(f, text=hint, style="Hint.TLabel").grid(row=r, column=2, sticky="w", padx=8)

        self.desc = ttk.Entry(f, textvariable=self.v["description"], width=44)
        row(0, "Description *", self.desc, "e.g. Upper tie bar, AC Service evacuate & recharge")
        row(1, "Operation", ttk.Combobox(f, textvariable=self.v["oper"], values=OPERATIONS, width=14),
            "Repl = replace, Rpr = repair, R&I = remove & install, Refn = refinish")
        row(2, "Part number", ttk.Entry(f, textvariable=self.v["part_no"], width=22))
        row(3, "Quantity", ttk.Entry(f, textvariable=self.v["qty"], width=8), "blank = 1 when a price is entered")
        row(4, "Unit price $", ttk.Entry(f, textvariable=self.v["price"], width=12), "extended price = qty × unit price")
        self.ext = ttk.Label(f, text="", style="Hint.TLabel")
        self.ext.grid(row=5, column=1, sticky="w")
        row(6, "Part type", ttk.Combobox(f, textvariable=self.ptype, values=list(PTYPE_LABELS.values()),
                                         state="readonly", width=20))
        row(7, "Labor hours", ttk.Entry(f, textvariable=self.v["labor"], width=8), "number, or text like Incl.")
        row(8, "Labor type", ttk.Combobox(f, textvariable=self.cat, values=list(CAT_LABELS.values()),
                                          state="readonly", width=20), "sets which labor rate is used")
        row(9, "Paint (refinish) hours", ttk.Entry(f, textvariable=self.v["paint"], width=8),
            "also bills paint supplies")
        row(10, "Symbol", ttk.Combobox(f, textvariable=self.sym, values=list(SYM_LABELS.values()),
                                       state="readonly", width=20))
        ttk.Checkbutton(f, text="Changed on this supplement (underline its price and hours)",
                        variable=self.changed).grid(row=11, column=1, columnspan=2, sticky="w", pady=(6, 0))
        for k in ("qty", "price"):
            self.v[k].trace_add("write", lambda *_: self._ext())
        self._ext()

    def focus_first(self):
        self.desc.focus_set()

    def _ext(self):
        tmp = Line(qty=self.v["qty"].get(), price=self.v["price"].get())
        e = extended(tmp)
        self.ext.config(text=f"Extended: $ {money(e)}" if e is not None else "")

    def validate(self):
        g = {k: v.get().strip() for k, v in self.v.items()}
        if not g["description"]:
            messagebox.showwarning(APP_NAME, "Enter a description for this line.", parent=self)
            return None
        for k, label in (("qty", "Quantity"), ("price", "Unit price")):
            if g[k] and num(g[k]) is None:
                messagebox.showwarning(APP_NAME, f"{label} must be a number.", parent=self)
                return None
        return Line(kind="item", sym=SYM_FROM_LABEL.get(self.sym.get(), ""), oper=g["oper"],
                    description=g["description"], part_no=g["part_no"], qty=g["qty"], price=g["price"],
                    part_type=PTYPE_FROM_LABEL.get(self.ptype.get(), ""), labor=g["labor"],
                    labor_cat=CAT_FROM_LABEL.get(self.cat.get(), ""), paint=g["paint"],
                    changed=self.changed.get())


class SectionDialog(Dialog):
    def __init__(self, master, line: Line | None = None):
        super().__init__(master, "Section heading")
        self.v = tk.StringVar(value=(line.description if line else ""))
        ttk.Label(self.body, text="Section name (e.g. FRONT BUMPER, COOLING, ELECTRICAL)").pack(anchor="w")
        self.e = ttk.Entry(self.body, textvariable=self.v, width=40)
        self.e.pack(fill="x", pady=6)

    def focus_first(self):
        self.e.focus_set()

    def validate(self):
        s = self.v.get().strip()
        if not s:
            messagebox.showwarning(APP_NAME, "Enter a section name.", parent=self)
            return None
        return Line(kind="section", description=s.upper(), oper="")


class SupplierDialog(Dialog):
    LABELS = [("line", "Line # on estimate"), ("name", "Supplier name"), ("street", "Street"),
              ("city", "City, state ZIP"), ("phone", "Phone"), ("part_no", "Part # (e.g. #2332)"),
              ("description", "Part description"), ("quote", "Quote #"), ("expires", "Quote expires"),
              ("price", "Price $")]

    def __init__(self, master, sup: Supplier | None = None):
        super().__init__(master, "Parts supplier", another=sup is None)
        s = sup or Supplier()
        self.v = {k: tk.StringVar(value=getattr(s, k)) for k, _ in self.LABELS}
        for r, (k, label) in enumerate(self.LABELS):
            ttk.Label(self.body, text=label).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 8))
            e = ttk.Entry(self.body, textvariable=self.v[k], width=36)
            e.grid(row=r, column=1, sticky="we", pady=3)
            if r == 0:
                self.first = e

    def focus_first(self):
        self.first.focus_set()

    def validate(self):
        g = {k: v.get().strip() for k, v in self.v.items()}
        if not g["name"]:
            messagebox.showwarning(APP_NAME, "Enter the supplier name.", parent=self)
            return None
        if g["price"] and num(g["price"]) is None:
            messagebox.showwarning(APP_NAME, "Price must be a number.", parent=self)
            return None
        return Supplier(**g)


# ---------------------------------------------------------------- main window
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1180x780")
        self.minsize(1000, 640)
        self.settings = load_settings()
        self.vars: dict[str, tk.StringVar] = {}
        self.path: str | None = None
        self.dirty = False
        self._loading = False
        self._style()
        self._menu()
        self._build()
        self.load_job(self.new_job_from_settings(), None)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- look
    def _style(self):
        st = ttk.Style(self)
        if not IS_MAC and not sys.platform.startswith("win"):
            st.theme_use("clam")
        base = tkfont.nametofont("TkDefaultFont")
        self.f_base = base
        self.f_bold = base.copy()
        self.f_bold.configure(weight="bold")
        self.f_total = base.copy()
        self.f_total.configure(weight="bold", size=abs(int(base.cget("size"))) + 2)
        st.configure("Hint.TLabel", foreground="#6b6b6b")
        st.configure("Total.TLabel", font=self.f_total)
        st.configure("Accent.TButton", font=self.f_bold)
        st.configure("Treeview", rowheight=24)

    def _menu(self):
        m = tk.Menu(self)
        fm = tk.Menu(m, tearoff=False)
        fm.add_command(label="New job", accelerator=f"{MOD_LABEL}+N", command=self.cmd_new)
        fm.add_command(label="Open job…", accelerator=f"{MOD_LABEL}+O", command=self.cmd_open)
        fm.add_command(label="Save job", accelerator=f"{MOD_LABEL}+S", command=self.cmd_save)
        fm.add_command(label="Save job as…", command=self.cmd_save_as)
        fm.add_separator()
        fm.add_command(label="Generate supplement PDF…", accelerator=f"{MOD_LABEL}+G", command=self.cmd_generate)
        if not IS_MAC:
            fm.add_separator()
            fm.add_command(label="Exit", command=self.on_close)
        m.add_cascade(label="File", menu=fm)
        hm = tk.Menu(m, tearoff=False)
        hm.add_command(label="Load example job (2018 Nissan Sentra)", command=self.cmd_example)
        hm.add_command(label="How it works", command=self.cmd_help)
        m.add_cascade(label="Help", menu=hm)
        self.config(menu=m)
        for key, fn in (("n", self.cmd_new), ("o", self.cmd_open), ("s", self.cmd_save), ("g", self.cmd_generate)):
            self.bind_all(f"<{MOD}-{key}>", lambda e, f=fn: f())

    def _build(self):
        outer = ttk.Frame(self, padding=(10, 8, 10, 0))
        outer.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(outer)
        self.nb.pack(fill="both", expand=True)
        self._tab_vehicle()
        self._tab_lines()
        self._tab_rates()
        self._tab_suppliers()

        bar = ttk.Frame(self, padding=10)
        bar.pack(fill="x")
        self.status = ttk.Label(bar, text="", style="Hint.TLabel")
        self.status.pack(side="left")
        ttk.Button(bar, text="Generate Supplement PDF…", style="Accent.TButton",
                   command=self.cmd_generate).pack(side="right")
        ttk.Button(bar, text="Save job", command=self.cmd_save).pack(side="right", padx=6)
        ttk.Button(bar, text="Open job…", command=self.cmd_open).pack(side="right")
        ttk.Button(bar, text="New", command=self.cmd_new).pack(side="right", padx=6)

    # ---------- tab 1: vehicle & customer
    def _tab_vehicle(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="  1. Vehicle & Customer  ")
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)

        doc = ttk.LabelFrame(tab, text="Shop & document", padding=6)
        doc.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        F = Form(doc, self.vars, self.mark_dirty)
        shop = SHOPS[DEFAULT_SHOP]
        ttk.Label(doc, text="Shop").grid(row=0, column=0, sticky="w", padx=(8, 4), pady=3)
        ttk.Label(doc, text=f"Rescue Automotive — {shop['street']}, {shop['city']}  {shop['phone']}").grid(
            row=0, column=1, columnspan=2, sticky="w", pady=3)
        F.add(1, 0, "Title", "doc.title", 30, values=TITLES)
        F.add(2, 0, "Workfile ID", "doc.workfile_id", 30)
        F.add(3, 0, "RO number", "doc.ro_number", 30, hint="printed in the footer")
        F.add(4, 0, "Written by", "doc.written_by", 30)
        F.add(5, 0, "Job number", "doc.job_number", 30)
        F.add(6, 0, "Date printed", "doc.printed", 30, hint="blank = now")
        doc.columnconfigure(1, weight=1)

        cust = ttk.LabelFrame(tab, text="Customer & insurance", padding=6)
        cust.grid(row=0, column=1, sticky="nsew", pady=(0, 6))
        F = Form(cust, self.vars, self.mark_dirty)
        F.add(0, 0, "Customer name *", "customer.customer", 30, hint="LAST, FIRST")
        F.add(1, 0, "Insured", "customer.insured", 30, hint="blank = customer")
        F.add(2, 0, "Owner", "customer.owner", 30, hint="blank = customer")
        F.add(3, 0, "Insurance company", "customer.insurer", 30)
        F.add(4, 0, "Claim #", "customer.claim", 30)
        F.add(5, 0, "Policy #", "customer.policy", 30)
        F.add(6, 0, "Type of loss", "customer.loss_type", 14)
        F.add(7, 0, "Date of loss", "customer.loss_date", 14)
        F.add(8, 0, "Point of impact", "customer.point_of_impact", 30)
        F.add(9, 0, "Days to repair", "customer.days_to_repair", 8)
        cust.columnconfigure(1, weight=1)

        veh = ttk.LabelFrame(tab, text="Vehicle", padding=6)
        veh.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        F = Form(veh, self.vars, self.mark_dirty)
        F.add(0, 0, "Year *", "vehicle.year", 8)
        F.add(0, 2, "Make *", "vehicle.make", 14)
        F.add(1, 0, "Model *", "vehicle.model", 14)
        F.add(1, 2, "VIN", "vehicle.vin", 20)
        ttk.Label(veh, text="Trim / details").grid(row=2, column=0, sticky="w", padx=(8, 4), pady=3)
        ttk.Entry(veh, textvariable=F.var("vehicle.details")).grid(row=2, column=1, columnspan=3, sticky="we",
                                                                    padx=(0, 8), pady=3)
        self.veh_preview = ttk.Label(veh, text="", style="Hint.TLabel", wraplength=480)
        self.veh_preview.grid(row=3, column=0, columnspan=4, sticky="w", padx=8, pady=(0, 6))
        F.add(4, 0, "License", "vehicle.license", 12)
        F.add(4, 2, "State", "vehicle.state", 6)
        F.add(5, 0, "Exterior color", "vehicle.exterior_color", 12)
        F.add(5, 2, "Interior color", "vehicle.interior_color", 12)
        F.add(6, 0, "Mileage in", "vehicle.mileage_in", 12)
        F.add(6, 2, "Mileage out", "vehicle.mileage_out", 12)
        F.add(7, 0, "Production date", "vehicle.production_date", 12)
        F.add(7, 2, "Condition", "vehicle.condition", 12)
        F.add(8, 0, "Vehicle out", "vehicle.vehicle_out", 12)
        F.add(8, 2, "Job #", "vehicle.job_no", 12)
        veh.columnconfigure(1, weight=1)
        veh.columnconfigure(3, weight=1)

        opt = ttk.LabelFrame(tab, text="Vehicle options (one per line — ALL CAPS lines print as bold headings)",
                             padding=6)
        opt.grid(row=1, column=1, sticky="nsew")
        opt.rowconfigure(0, weight=1)
        opt.columnconfigure(0, weight=1)
        self.options = tk.Text(opt, width=40, height=12, wrap="none", undo=True, font=self.f_base)
        sb = ttk.Scrollbar(opt, orient="vertical", command=self.options.yview)
        self.options.configure(yscrollcommand=sb.set)
        self.options.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.options.bind("<<Modified>>", self._options_modified)
        ttk.Label(opt, text="Optional — leave empty to skip the options grid.", style="Hint.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 0))

    def _options_modified(self, _e=None):
        if self.options.edit_modified():
            self.mark_dirty()
            self.options.edit_modified(False)

    # ---------- tab 2: lines
    COLS = [("n", "Line", 44, "center"), ("sym", "Sym", 40, "center"), ("oper", "Oper", 56, "center"),
            ("description", "Description", 280, "w"), ("part_no", "Part number", 110, "w"),
            ("qty", "Qty", 44, "e"), ("price", "Unit $", 80, "e"), ("ext", "Extended $", 90, "e"),
            ("part_type", "Type", 44, "center"), ("labor", "Labor hrs", 72, "e"),
            ("labor_cat", "Labor type", 92, "w"), ("paint", "Paint hrs", 70, "e"), ("changed", "Chg", 40, "center")]

    def _tab_lines(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="  2. Supplement Lines  ")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        tools = ttk.Frame(tab)
        tools.grid(row=0, column=0, sticky="we", pady=(0, 6))
        ttk.Button(tools, text="+ Add line", style="Accent.TButton", command=self.line_add).pack(side="left")
        ttk.Button(tools, text="+ Add section heading", command=self.section_add).pack(side="left", padx=6)
        ttk.Separator(tools, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(tools, text="Edit", command=self.line_edit).pack(side="left")
        ttk.Button(tools, text="Duplicate", command=self.line_dup).pack(side="left", padx=6)
        ttk.Button(tools, text="Delete", command=self.line_delete).pack(side="left")
        ttk.Separator(tools, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(tools, text="▲ Move up", command=lambda: self.line_move(-1)).pack(side="left")
        ttk.Button(tools, text="▼ Move down", command=lambda: self.line_move(1)).pack(side="left", padx=6)
        ttk.Label(tools, text="Double-click a row to edit it.", style="Hint.TLabel").pack(side="right")

        wrap = ttk.Frame(tab)
        wrap.grid(row=1, column=0, sticky="nsew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in self.COLS], show="headings", selectmode="browse")
        for key, head, w, anchor in self.COLS:
            self.tree.heading(key, text=head)
            self.tree.column(key, width=w, anchor=anchor, stretch=(key == "description"))
        self.tree.tag_configure("section", font=self.f_bold, background="#eef1f5")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda e: self.line_edit())
        self.tree.bind("<Delete>", lambda e: self.line_delete())
        self.tree.bind("<BackSpace>", lambda e: self.line_delete())

        tot = ttk.LabelFrame(tab, text="Totals (updates as you go)", padding=8)
        tot.grid(row=2, column=0, sticky="we", pady=(8, 0))
        self.tot_detail = ttk.Label(tot, text="", justify="left")
        self.tot_detail.pack(side="left")
        self.tot_grand = ttk.Label(tot, text="", style="Total.TLabel")
        self.tot_grand.pack(side="right")

    # ---------- tab 3: rates
    RATE_FIELDS = [("body", "Body labor $/hr"), ("paint", "Paint labor $/hr"), ("mechanical", "Mechanical $/hr"),
                   ("frame", "Frame $/hr"), ("structural", "Structural $/hr"), ("electrical", "Electrical $/hr"),
                   ("diagnostic", "Diagnostic $/hr"), ("glass", "Glass $/hr"),
                   ("paint_supplies", "Paint supplies $/paint hr"), ("tax_rate", "Sales tax %")]

    def _tab_rates(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="  3. Rates & Output  ")
        rates = ttk.LabelFrame(tab, text="Labor rates & tax", padding=8)
        rates.grid(row=0, column=0, sticky="nw", padx=(0, 12))
        F = Form(rates, self.vars, self.mark_dirty)
        for r, (k, label) in enumerate(self.RATE_FIELDS):
            F.add(r, 0, label, f"rates.{k}", 10)
        self.tax_labor = tk.BooleanVar(value=True)
        ttk.Checkbutton(rates, text="Tax labor too (tax the whole subtotal)", variable=self.tax_labor,
                        command=self.mark_dirty).grid(row=len(self.RATE_FIELDS), column=0, columnspan=3,
                                                      sticky="w", padx=8, pady=(8, 0))
        ttk.Button(rates, text="Save these rates as my defaults", command=self.save_rate_defaults).grid(
            row=len(self.RATE_FIELDS) + 1, column=0, columnspan=3, sticky="w", padx=8, pady=(12, 0))

        out = ttk.LabelFrame(tab, text="What goes on the PDF", padding=8)
        out.grid(row=0, column=1, sticky="nw")
        self.out = {k: tk.BooleanVar() for k in ("show_prices", "include_disclosures", "save_tex", "open_after")}
        labels = {
            "show_prices": "Show prices and the Estimate Totals block\n(uncheck for a list of what's needed — hours only)",
            "include_disclosures": "Include the Florida notice and abbreviation pages",
            "save_tex": "Also save the LaTeX source (.tex) next to the PDF",
            "open_after": "Open the PDF after it's created",
        }
        for r, (k, lab) in enumerate(labels.items()):
            ttk.Checkbutton(out, text=lab, variable=self.out[k], command=self._out_changed).grid(
                row=r, column=0, sticky="w", pady=4)

    def _out_changed(self):
        self.mark_dirty()

    # ---------- tab 4: suppliers
    def _tab_suppliers(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="  4. Parts Suppliers  ")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        tools = ttk.Frame(tab)
        tools.grid(row=0, column=0, sticky="we", pady=(0, 6))
        ttk.Button(tools, text="+ Add supplier", style="Accent.TButton", command=self.sup_add).pack(side="left")
        ttk.Button(tools, text="Edit", command=self.sup_edit).pack(side="left", padx=6)
        ttk.Button(tools, text="Delete", command=self.sup_delete).pack(side="left")
        ttk.Label(tools, text="Optional — prints a Parts Supplier List page when filled in.",
                  style="Hint.TLabel").pack(side="right")
        cols = [("line", "Line", 50), ("name", "Supplier", 200), ("phone", "Phone", 110),
                ("part_no", "Part #", 110), ("description", "Description", 240), ("quote", "Quote #", 140),
                ("expires", "Expires", 80), ("price", "Price $", 80)]
        self.stree = ttk.Treeview(tab, columns=[c[0] for c in cols], show="headings", selectmode="browse")
        for k, h, w in cols:
            self.stree.heading(k, text=h)
            self.stree.column(k, width=w, anchor="e" if k == "price" else "w")
        self.stree.grid(row=1, column=0, sticky="nsew")
        self.stree.bind("<Double-1>", lambda e: self.sup_edit())
        self.stree.bind("<Delete>", lambda e: self.sup_delete())

    # ---------- job <-> form
    def new_job_from_settings(self) -> Job:
        j = Job()
        s = self.settings
        if "rates" in s:
            j.rates = Job.from_dict({"rates": s["rates"]}).rates
        if "output" in s:
            j.output = Job.from_dict({"output": s["output"]}).output
        j.doc.shop = DEFAULT_SHOP
        j.doc.written_by = s.get("written_by", "")
        return j

    def load_job(self, job: Job, path: str | None):
        self._loading = True
        try:
            self.job = job
            self.path = path
            for section in ("doc", "customer", "vehicle"):
                obj = getattr(job, section)
                for f in fields(obj):
                    key = f"{section}.{f.name}"
                    if key in self.vars:
                        self.vars[key].set(getattr(obj, f.name))
            for k, _ in self.RATE_FIELDS:
                v = getattr(job.rates, k)
                self.vars[f"rates.{k}"].set(f"{v:g}" if k == "tax_rate" else f"{v:.2f}")
            self.tax_labor.set(job.rates.tax_labor)
            for k, var in self.out.items():
                var.set(getattr(job.output, k))
            self.options.delete("1.0", "end")
            self.options.insert("1.0", job.options)
            self.options.edit_modified(False)
            self.refresh_lines()
            self.refresh_suppliers()
        finally:
            self._loading = False
        self.dirty = False
        self.update_title()
        self.refresh_preview()

    def collect(self, strict=True) -> Job | None:
        """Copy the form into self.job. Returns None (after a message) when a rate is invalid."""
        j = self.job
        for key, var in self.vars.items():
            section, attr = key.split(".", 1)
            if section in ("doc", "customer", "vehicle"):
                setattr(getattr(j, section), attr, var.get().strip())
        for k, label in self.RATE_FIELDS:
            v = num(self.vars[f"rates.{k}"].get())
            if v is None:
                if strict:
                    self.nb.select(2)
                    messagebox.showwarning(APP_NAME, f"'{label}' must be a number.")
                    return None
                v = getattr(Rates(), k)
            setattr(j.rates, k, v)
        j.rates.tax_labor = self.tax_labor.get()
        for k, var in self.out.items():
            setattr(j.output, k, var.get())
        j.options = self.options.get("1.0", "end").strip()
        j.doc.shop = DEFAULT_SHOP
        return j

    # ---------- refreshers
    def mark_dirty(self):
        if self._loading:
            return
        self.dirty = True
        self.update_title()
        self.refresh_preview()

    def update_title(self):
        name = Path(self.path).name if self.path else "Untitled job"
        self.title(f"{'• ' if self.dirty else ''}{name} — {APP_NAME}")

    def refresh_preview(self):
        if not hasattr(self, "veh_preview"):
            return
        g = lambda k: self.vars.get(k, tk.StringVar()).get().strip()
        desc = " ".join(p for p in (g("vehicle.year"), g("vehicle.make"), g("vehicle.model"), g("vehicle.details")) if p)
        self.veh_preview.config(text=f"Prints as: {desc}" if desc else "")
        self.refresh_totals()

    def refresh_totals(self):
        if not hasattr(self, "tot_detail") or self._loading:
            return
        j = self.collect(strict=False)
        t = j.totals()
        parts = [f"Parts $ {money(t.parts)}"]
        for cat, basis, rate, cost in t.rows[1:]:
            parts.append(f"{cat} {basis} = $ {money(cost)}")
        lines = ["    ".join(parts[i:i + 3]) for i in range(0, len(parts), 3)]
        lines.append(f"Subtotal $ {money(t.subtotal)}    Tax $ {money(t.tax)}    "
                     f"Labor {hrs(t.labor_total_hours)} hrs    Paint {hrs(t.paint_hours)} hrs")
        self.tot_detail.config(text="\n".join(lines))
        self.tot_grand.config(text=f"Grand Total  $ {money(t.grand)}")

    def refresh_lines(self, select: int | None = None):
        self.tree.delete(*self.tree.get_children())
        for i, (n, ln) in enumerate(self.job.numbered()):
            if ln.kind == "section":
                vals = [n, "", "", ln.description] + [""] * 9
                self.tree.insert("", "end", iid=str(i), values=vals, tags=("section",))
            else:
                e = extended(ln)
                vals = [n, ln.sym, ln.oper, ln.description, ln.part_no, ln.qty,
                        money(num(ln.price)) if num(ln.price) is not None else ln.price,
                        money(e) if e is not None else "", ln.part_type, ln.labor,
                        LABOR_CAT_NAMES.get(ln.labor_cat, ln.labor_cat) if num(ln.labor) is not None else "",
                        ln.paint, "✓" if ln.changed else ""]
                self.tree.insert("", "end", iid=str(i), values=vals)
        if select is not None and 0 <= select < len(self.job.lines):
            self.tree.selection_set(str(select))
            self.tree.see(str(select))
        self.refresh_totals()

    def refresh_suppliers(self, select: int | None = None):
        self.stree.delete(*self.stree.get_children())
        for i, s in enumerate(self.job.suppliers):
            self.stree.insert("", "end", iid=str(i), values=[s.line, s.name, s.phone, s.part_no, s.description,
                                                             s.quote, s.expires, s.price])
        if select is not None and 0 <= select < len(self.job.suppliers):
            self.stree.selection_set(str(select))

    # ---------- line actions
    def _sel(self, tree) -> int | None:
        s = tree.selection()
        return int(s[0]) if s else None

    def _insert_at(self) -> int:
        i = self._sel(self.tree)
        return len(self.job.lines) if i is None else i + 1

    def line_add(self):
        at = self._insert_at()
        while True:
            d = LineDialog(self)
            r = d.show()
            if not r:
                break
            self.job.lines.insert(at, r)
            self.refresh_lines(select=at)
            self.mark_dirty()
            at += 1
            if not d.again:
                break

    def section_add(self):
        r = SectionDialog(self).show()
        if r:
            at = self._insert_at()
            self.job.lines.insert(at, r)
            self.refresh_lines(select=at)
            self.mark_dirty()

    def line_edit(self):
        i = self._sel(self.tree)
        if i is None:
            return
        ln = self.job.lines[i]
        r = SectionDialog(self, ln).show() if ln.kind == "section" else LineDialog(self, ln, "Edit line").show()
        if r:
            self.job.lines[i] = r
            self.refresh_lines(select=i)
            self.mark_dirty()

    def line_dup(self):
        i = self._sel(self.tree)
        if i is None:
            return
        self.job.lines.insert(i + 1, Line(**asdict(self.job.lines[i])))
        self.refresh_lines(select=i + 1)
        self.mark_dirty()

    def line_delete(self):
        i = self._sel(self.tree)
        if i is None:
            return
        ln = self.job.lines[i]
        if not messagebox.askyesno(APP_NAME, f"Delete line {i + 1}: {ln.description}?"):
            return
        del self.job.lines[i]
        self.refresh_lines(select=min(i, len(self.job.lines) - 1))
        self.mark_dirty()

    def line_move(self, step):
        i = self._sel(self.tree)
        if i is None:
            return
        k = i + step
        if 0 <= k < len(self.job.lines):
            L = self.job.lines
            L[i], L[k] = L[k], L[i]
            self.refresh_lines(select=k)
            self.mark_dirty()

    # ---------- supplier actions
    def sup_add(self):
        while True:
            d = SupplierDialog(self)
            r = d.show()
            if not r:
                break
            self.job.suppliers.append(r)
            self.refresh_suppliers(select=len(self.job.suppliers) - 1)
            self.mark_dirty()
            if not d.again:
                break

    def sup_edit(self):
        i = self._sel(self.stree)
        if i is None:
            return
        r = SupplierDialog(self, self.job.suppliers[i]).show()
        if r:
            self.job.suppliers[i] = r
            self.refresh_suppliers(select=i)
            self.mark_dirty()

    def sup_delete(self):
        i = self._sel(self.stree)
        if i is None:
            return
        if messagebox.askyesno(APP_NAME, f"Delete supplier {self.job.suppliers[i].name}?"):
            del self.job.suppliers[i]
            self.refresh_suppliers()
            self.mark_dirty()

    # ---------- commands
    def confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        r = messagebox.askyesnocancel(APP_NAME, "Save changes to the current job first?")
        if r is None:
            return False
        if r:
            return self.cmd_save()
        return True

    def cmd_new(self):
        if self.confirm_discard():
            self.load_job(self.new_job_from_settings(), None)
            self.nb.select(0)

    def cmd_example(self):
        if self.confirm_discard():
            j = sample_job()
            j.output = self.new_job_from_settings().output
            self.load_job(j, None)
            self.dirty = True
            self.update_title()

    def cmd_open(self):
        if not self.confirm_discard():
            return
        p = filedialog.askopenfilename(title="Open job", initialdir=self.settings.get("job_dir", documents_dir()),
                                       filetypes=[("Supplement job", "*.json"), ("All files", "*.*")])
        if not p:
            return
        try:
            self.load_job(Job.load(p), p)
            self.settings["job_dir"] = str(Path(p).parent)
            save_settings(self.settings)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Couldn't open that file:\n{e}")

    def cmd_save(self) -> bool:
        if not self.path:
            return self.cmd_save_as()
        return self._write_job(self.path)

    def cmd_save_as(self) -> bool:
        p = filedialog.asksaveasfilename(title="Save job", defaultextension=".json",
                                         initialdir=self.settings.get("job_dir", documents_dir()),
                                         initialfile=self.default_name() + ".json",
                                         filetypes=[("Supplement job", "*.json")])
        if not p:
            return False
        return self._write_job(p)

    def _write_job(self, p) -> bool:
        j = self.collect()
        if j is None:
            return False
        try:
            j.save(p)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Couldn't save the job:\n{e}")
            return False
        self.path = p
        self.dirty = False
        self.settings["job_dir"] = str(Path(p).parent)
        save_settings(self.settings)
        self.update_title()
        self.status.config(text=f"Saved {Path(p).name}")
        return True

    def default_name(self) -> str:
        j = self.collect(strict=False)
        kind = "SUPPLEMENT" if j.doc.title.lower().startswith("supplement") else "ESTIMATE"
        last = j.customer.customer.split(",")[0].strip()
        parts = [kind, j.vehicle.year, j.vehicle.make, j.vehicle.model, last]
        name = "_".join(p for p in parts if p)
        return re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_").upper() or "SUPPLEMENT"

    def save_rate_defaults(self):
        j = self.collect()
        if j is None:
            return
        self.settings["rates"] = asdict(j.rates)
        self.settings["output"] = asdict(j.output)
        if j.doc.written_by:
            self.settings["written_by"] = j.doc.written_by
        save_settings(self.settings)
        self.status.config(text="Rates and output choices saved as defaults for new jobs.")

    def cmd_generate(self):
        j = self.collect()
        if j is None:
            return
        missing = []
        if not j.customer.customer:
            missing.append("customer name")
        if not (j.vehicle.year and j.vehicle.make and j.vehicle.model):
            missing.append("vehicle year / make / model")
        if not any(ln.kind == "item" for ln in j.lines):
            missing.append("at least one supplement line")
        if missing and not messagebox.askyesno(
                APP_NAME, "Still missing: " + ", ".join(missing) + ".\n\nGenerate the PDF anyway?"):
            return
        p = filedialog.asksaveasfilename(title="Save supplement PDF", defaultextension=".pdf",
                                         initialdir=self.settings.get("pdf_dir", documents_dir()),
                                         initialfile=self.default_name() + ".pdf",
                                         filetypes=[("PDF", "*.pdf")])
        if not p:
            return
        try:
            self.config(cursor="watch")
            self.update_idletasks()
            warnings = render_pdf(j, p)
            if j.output.save_tex:
                from .latex_export import write_tex
                write_tex(j, str(Path(p).with_suffix(".tex")))
        except PermissionError:
            messagebox.showerror(APP_NAME, "Couldn't write the PDF — is it open in another program? "
                                           "Close it and try again.")
            return
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Something went wrong creating the PDF:\n{e}")
            return
        finally:
            self.config(cursor="")
        self.settings["pdf_dir"] = str(Path(p).parent)
        save_settings(self.settings)
        self.status.config(text=f"Created {Path(p).name}")
        if warnings:
            messagebox.showinfo(APP_NAME, "PDF created, with notes:\n\n" + "\n".join(warnings))
        if j.output.open_after:
            open_file(p)

    def cmd_help(self):
        messagebox.showinfo(APP_NAME, (
            "1. Vehicle & Customer — fill in the shop, title (e.g. Supplement of Record 1), "
            "customer, insurance and vehicle.\n\n"
            "2. Supplement Lines — add each item being requested. Use section headings "
            "(FRONT BUMPER, COOLING…) to group them. Enter labor hours and pick the labor type; "
            "paint hours also bill paint supplies.\n\n"
            "3. Rates & Output — check the labor rates and tax. Uncheck 'Show prices' to send "
            "a list of what's needed without dollar amounts.\n\n"
            "4. Parts Suppliers — optional quotes page.\n\n"
            "Save the job to come back to it later; Generate creates the PDF."))

    def on_close(self):
        if self.confirm_discard():
            self.destroy()


def main():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = App()
    app.mainloop()
