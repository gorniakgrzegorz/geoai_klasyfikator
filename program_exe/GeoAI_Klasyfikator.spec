# -*- mode: python ; coding: utf-8 -*-
# Przepis dla PyInstallera: jak złożyć program w jeden katalog z .exe.
#
# Uruchamia się to poleceniem:
#     pyinstaller GeoAI_Klasyfikator.spec --noconfirm
# albo po prostu dwuklikiem w zbuduj.bat.

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

TU = os.path.abspath(os.getcwd())
KORZEN = os.path.dirname(TU)          # katalog repozytorium

# rasterio i fiona noszą własne dane GDAL-a i PROJ-a; bez nich .exe
# nie otworzy żadnego GeoTIFF-a ani GeoPackage'a
dane = []
for pakiet in ("rasterio", "fiona", "pyproj", "certifi"):
    try:
        dane += collect_data_files(pakiet)
    except Exception:
        pass

# moduły wczytywane dynamicznie, których PyInstaller sam nie znajdzie
ukryte = ["rasterio.sample", "rasterio.vrt", "rasterio._features",
          "rasterio.control", "rasterio.crs", "rasterio.rpc",
          "fiona._shim", "fiona.schema", "fiona.crs"]
for pakiet in ("rasterio", "fiona", "sklearn", "skimage", "scipy"):
    try:
        ukryte += collect_submodules(pakiet)
    except Exception:
        pass

analiza = Analysis(
    ["okno.py"],
    pathex=[TU, KORZEN, os.path.join(KORZEN, "program_cli")],
    binaries=[],
    datas=dane + [
        (os.path.join(KORZEN, "geoai_klasyfikator", "core"),
         "geoai_klasyfikator/core"),
        (os.path.join(KORZEN, "geoai_klasyfikator", "__init__.py"),
         "geoai_klasyfikator"),
        (os.path.join(KORZEN, "program_cli", "geoai_cli"), "geoai_cli"),
        (os.path.join(KORZEN, "geoai_klasyfikator", "icon.png"), "."),
        (os.path.join(KORZEN, "LICENSE"), "."),
    ],
    hiddenimports=ukryte,
    hookspath=[],
    runtime_hooks=[],
    # to, czego na pewno nie potrzebujemy, a waży swoje
    excludes=["matplotlib", "PyQt5", "PyQt6", "PySide2", "PySide6",
              "IPython", "jupyter", "notebook", "pytest", "torch",
              "tensorflow", "pandas.tests"],
    noarchive=False,
)

archiwum = PYZ(analiza.pure)

program = EXE(
    archiwum,
    analiza.scripts,
    [],
    exclude_binaries=True,
    name="GeoAI Klasyfikator",
    debug=False,
    strip=False,
    upx=False,
    console=False,                 # okno bez czarnej konsoli w tle
    icon=os.path.join(TU, "ikona.ico") if os.path.isfile(
        os.path.join(TU, "ikona.ico")) else None,
    # nazwa produktu i wersja wpisane w plik .exe; Windows pokazuje je
    # we właściwościach pliku, a podpisywanie kodu przez SignPath.io
    # wymaga, żeby te pola były ustawione i niezmienne
    version=os.path.join(TU, "wersja.txt") if os.path.isfile(
        os.path.join(TU, "wersja.txt")) else None,
)

calosc = COLLECT(
    program,
    analiza.binaries,
    analiza.datas,
    strip=False,
    upx=False,
    name="GeoAI Klasyfikator",
)
