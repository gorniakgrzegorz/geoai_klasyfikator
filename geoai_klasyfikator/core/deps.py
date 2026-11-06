# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Which optional scientific libraries are available, and what that means
for the results.

The reference implementation this plugin reproduces uses scikit-image
for SLIC and scikit-learn for the Random Forest. When those libraries
are present the plugin calls them with the same settings, so the output
matches. When they are missing it falls back to the implementations in
this package, which follow the same published algorithms but will not
be identical down to the last segment.
"""
from __future__ import annotations

HAS_SKIMAGE = False
HAS_SKLEARN = False
HAS_SCIPY = False

try:
    import skimage  # noqa: F401
    from skimage.segmentation import slic as _slic  # noqa: F401
    HAS_SKIMAGE = True
except Exception:
    HAS_SKIMAGE = False

try:
    from sklearn.ensemble import RandomForestClassifier  # noqa: F401
    HAS_SKLEARN = True
except Exception:
    HAS_SKLEARN = False

try:
    import scipy.ndimage  # noqa: F401
    HAS_SCIPY = True
except Exception:
    HAS_SCIPY = False


def engine_report() -> dict:
    """A short description of the engines in use, shown in the panel."""
    return {
        "segmentation": ("SLIC ze scikit-image (wzorcowy)" if HAS_SKIMAGE
                         else "SLIC wbudowany we wtyczkę"),
        "classifier": ("Random Forest ze scikit-learn (wzorcowy)"
                       if HAS_SKLEARN
                       else "Random Forest wbudowany we wtyczkę"),
        "filters": ("SciPy" if HAS_SCIPY else "wbudowane"),
        "exact": HAS_SKIMAGE and HAS_SKLEARN,
    }


def missing_packages() -> list:
    """Packages that would make the run bit-for-bit comparable."""
    missing = []
    if not HAS_SKIMAGE:
        missing.append("scikit-image")
    if not HAS_SKLEARN:
        missing.append("scikit-learn")
    return missing


def python_qgis() -> str | None:
    """Plik wykonywalny Pythona, w którym działa QGIS.

    W QGIS ``sys.executable`` wskazuje zwykle sam program QGIS, a nie
    Pythona, więc szukamy interpretera obok bibliotek standardowych.
    """
    import os
    import sys
    kandydaci = []
    exe = sys.executable or ""
    if os.path.basename(exe).lower().startswith("python"):
        kandydaci.append(exe)
    if os.name == "nt":
        kandydaci += [os.path.join(sys.exec_prefix, "python.exe"),
                      os.path.join(sys.exec_prefix, "python3.exe")]
    else:
        wersja = "python{0}.{1}".format(*sys.version_info[:2])
        for katalog in (os.path.join(sys.exec_prefix, "bin"),
                        os.path.join(os.path.dirname(exe), "bin")):
            kandydaci += [os.path.join(katalog, nazwa)
                          for nazwa in (wersja, "python3", "python")]
    for sciezka in kandydaci:
        if sciezka and os.path.isfile(sciezka):
            return sciezka
    return None


def polecenie_instalacji(pakiety, plik_ograniczen) -> list:
    """Argumenty pip: instalacja dla bieżącego użytkownika, bez praw
    administratora. Plik ograniczeń przypina wersję numpy z QGIS, żeby
    pip jej nie podmienił (od numpy zależy GDAL wbudowany w QGIS)."""
    return ["-m", "pip", "install", "--user",
            "--disable-pip-version-check", "--no-warn-script-location",
            "-c", plik_ograniczen] + list(pakiety)


def ograniczenia() -> str:
    """Treść pliku ograniczeń dla pip."""
    import numpy
    return "numpy=={0}\n".format(numpy.__version__)


INSTALL_HINT = (
    "Wtyczka działa od razu, bez niczego więcej. Jeśli jednak "
    "doinstalujesz dwie biblioteki, podział na obiekty i nauka pójdą "
    "<b>wyraźnie szybciej</b> na dużych zdjęciach, a wyniki będą "
    "identyczne z implementacją wzorcową.\n\n"
    "Najprościej: w kroku 1 kliknij <b>Zainstaluj biblioteki "
    "przyspieszające</b> i po zakończeniu uruchom QGIS ponownie.\n\n"
    "Gdyby się nie udało, zrób to ręcznie: w menu Start, w katalogu QGIS, otwórz "
    "<b>OSGeo4W Shell</b> i wpisz jedno polecenie:\n\n"
    "&nbsp;&nbsp;&nbsp;&nbsp;<code>python -m pip install scikit-image "
    "scikit-learn</code>\n\n"
    "Potem uruchom QGIS ponownie. Jeśli polecenie nie przejdzie, "
    "uruchom OSGeo4W Shell jako administrator."
)
