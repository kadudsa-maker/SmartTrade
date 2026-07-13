# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import importlib.util

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_dir = Path(SPECPATH)

datas = []
datas += collect_data_files("customtkinter")
datas += collect_data_files("certifi")

default_watchlist = project_dir / "data" / "watchlist.json"
if default_watchlist.exists():
    datas.append((str(default_watchlist), "data"))

ca_bundle = project_dir / "data" / "windows_ca_bundle.pem"
if ca_bundle.exists():
    datas.append((str(ca_bundle), "data"))

app_icon = project_dir / "SmartTrade.ico"
if app_icon.exists():
    datas.append((str(app_icon), "."))

hiddenimports = []
hiddenimports += collect_submodules("pybit")

optional_hiddenimports = [
    "plyer",
    "plyer.platforms.win.notification",
    "truststore",
    "win10toast",
]

for module_name in optional_hiddenimports:
    try:
        module_exists = importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        module_exists = False

    if module_exists:
        hiddenimports.append(module_name)


a = Analysis(
    ["main.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "_pytest",
        "iniconfig",
        "pluggy",
        "pygments",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SmartTrade",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_dir / "SmartTrade.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SmartTrade",
)
