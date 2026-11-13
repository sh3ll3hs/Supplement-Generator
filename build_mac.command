#!/bin/bash
# Builds "dist/Supplement Maker.app". Needs Python 3.10+ from python.org.
# Double-click in Finder, or run:  bash build_mac.command
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm SupplementMaker.spec
echo
echo "Done: dist/Supplement Maker.app"
