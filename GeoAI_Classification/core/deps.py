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
        "segmentation": ("SLIC from scikit-image (reference)" if HAS_SKIMAGE
                         else "built-in SLIC"),
        "classifier": ("Random Forest from scikit-learn (reference)"
                       if HAS_SKLEARN
                       else "built-in Random Forest"),
        "filters": ("SciPy" if HAS_SCIPY else "built-in"),
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
    "The plugin works out of the box. If you install two libraries, "
    "segmentation and training will run <b>much faster</b> on large images, "
    "and the results will match the reference implementation.\n\n"
    "The easiest way: in step 1 click <b>Install acceleration libraries</b> "
    "and restart QGIS when it finishes.\n\n"
    "If that fails, do it by hand: in the Start menu, in the QGIS folder, open "
    "<b>OSGeo4W Shell</b> and type one command:\n\n"
    "&nbsp;&nbsp;&nbsp;&nbsp;<code>python -m pip install scikit-image "
    "scikit-learn</code>\n\n"
    "Then restart QGIS. If the command fails, run OSGeo4W Shell as "
    "administrator."
)
