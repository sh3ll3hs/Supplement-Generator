# Supplement Maker

A desktop app for **Rescue Automotive**, 10531 E Colonial Dr, Orlando, FL 32817. Every PDF it makes carries the Rescue Automotive header. Fill in a form with the vehicle, customer and insurance details and the lines being requested, including hours and prices, and it produces the supplement PDF in the same layout as the shop's estimates. Nobody has to open or edit LaTeX.

## Using the app

1. **Vehicle & Customer**: pick the title (*Supplement of Record 1*, *2*, … or *Preliminary Estimate*), then fill in the customer, insurance company, claim number and vehicle (year, make, model, trim, VIN…). The vehicle options box is optional. Put one option per line; lines typed in ALL CAPS print as bold headings.
2. **Supplement Lines**: click **+ Add line** for each item being requested. Set the operation (Repl, Rpr, R&I…), part number, quantity, unit price, labor hours and labor type, and paint hours. Use **+ Add section heading** to group lines (FRONT BUMPER, COOLING…). Line numbers are assigned automatically, and the totals update as you type. Tick *Changed on this supplement* to underline a line's price and hours, which is how CCC marks supplement changes.
3. **Rates & Output**: set the labor rates, paint supplies rate and sales tax. Click **Save these rates as my defaults** so new jobs start with them. Untick **Show prices** to send a list of what's needed with hours only, no dollar amounts and no totals block.
4. **Parts Suppliers** (optional): add supplier quotes to get the Parts Supplier List page.

Click **Generate Supplement PDF…** to create the PDF. **Save job** writes a `.json` file you can reopen later to make Supplement 2 from Supplement 1.

How totals are calculated (the same math as the shop's CCC estimates):
- Parts = qty × unit price, summed
- Each labor type's hours × its rate. Lines with no labor type count as Body labor.
- Paint hours × paint rate, plus paint hours × paint supplies rate
- Sales tax is applied to the whole subtotal. Untick *Tax labor too* to tax parts and paint supplies only.

The PDF uses Tahoma when it's installed (it ships with Windows and macOS), which matches CCC's printouts. If Tahoma is missing it falls back to the bundled DejaVu Sans.

## Getting the Windows and Mac apps

### Easiest: let GitHub build them (free)

1. Create a **private** repository on GitHub and upload this whole folder, including the hidden `.github` folder.
2. Open the repo's **Actions** tab. The *Build Windows and Mac apps* workflow runs on every push to `main`, and you can also start it with **Run workflow**.
3. When it finishes (about 5 minutes), download the artifacts from the run page:
   - `Supplement-Maker-Windows` contains a zip with `Supplement Maker.exe`
   - `Supplement-Maker-Mac-AppleSilicon` is for M1/M2/M3/M4 Macs
   - `Supplement-Maker-Mac-Intel` is for older Intel Macs

   Each build is checked automatically: the packaged app renders a sample PDF (`selftest.pdf`, included in the artifact) before the zip is uploaded.
4. To publish a download page, go to **Releases → Draft a new release**, type a new tag such as `v1.0.0`, and click **Publish release**. The workflow builds all three apps and attaches the zips to that release within a few minutes.

### Or build on the computer itself

You need Python 3.10 or newer from python.org.
- **Windows:** double-click `build_windows.bat`. The result is `dist\Supplement Maker.exe`.
- **Mac:** double-click `build_mac.command`, or run `bash build_mac.command`. The result is `dist/Supplement Maker.app`.

Windows apps can't be built on a Mac and Mac apps can't be built on Windows. Each one has to be built on its own system, which is why the GitHub route is the easy way to get both.

### First launch: security prompts

The apps aren't code-signed, so both systems warn the first time:
- **Windows SmartScreen** ("Windows protected your PC"): click **More info**, then **Run anyway**.
- **macOS** ("can't be opened because Apple cannot check it"): right-click the app, choose **Open**, then **Open** again. On recent macOS versions, use **System Settings → Privacy & Security → Open Anyway** instead.

You only have to do this once per computer.

## Running from source (for development)

```
python -m pip install -r requirements.txt
python app.py
```

## Files

| Path | What it is |
|---|---|
| `app.py` | Entry point. `--selftest out.pdf` renders the example job without the window |
| `supplement_maker/model.py` | Job data, shop profiles, totals math, the example job |
| `supplement_maker/pdf_render.py` | Draws the PDF using positions measured from the shop's estimate |
| `supplement_maker/latex_export.py` | Fills `template.tex` (the LaTeX template) when *Also save the LaTeX source* is ticked |
| `supplement_maker/gui.py` | The window and forms |
| `SupplementMaker.spec` | PyInstaller build recipe |
| `.github/workflows/build.yml` | GitHub build for Windows and both Mac types |

To change the shop's address or phone, edit `SHOPS` at the top of `supplement_maker/model.py` and rebuild.
