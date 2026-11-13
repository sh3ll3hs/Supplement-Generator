# PyInstaller build recipe — run:  python -m PyInstaller --noconfirm SupplementMaker.spec
# Windows -> dist/Supplement Maker.exe (single file)
# macOS   -> dist/Supplement Maker.app
import sys

APP = "Supplement Maker"
datas = [
    ("supplement_maker/fonts", "supplement_maker/fonts"),
    ("supplement_maker/template.tex", "supplement_maker"),
]
a = Analysis(
    ["app.py"],
    datas=datas,
    hiddenimports=["reportlab.graphics.barcode.common", "reportlab.graphics.barcode.code128"],
    excludes=["numpy", "matplotlib", "PyQt5", "PySide6", "pymupdf", "fitz"],
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP, console=False,
              argv_emulation=False, icon="assets/icon.icns")
    coll = COLLECT(exe, a.binaries, a.datas, name=APP)
    app = BUNDLE(coll, name=f"{APP}.app", icon="assets/icon.icns",
                 bundle_identifier="com.rescueautomotive.supplementmaker",
                 info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "1.0.0"})
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name=APP, console=False, upx=False,
              icon="assets/icon.ico")
