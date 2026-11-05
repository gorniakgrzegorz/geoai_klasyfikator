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
        "classifier": ("las losowy ze scikit-learn (wzorcowy)"
                       if HAS_SKLEARN
                       else "las losowy wbudowany we wtyczkę"),
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


INSTALL_HINT = (
    "Wtyczka działa od razu, bez niczego więcej. Jeśli jednak "
    "doinstalujesz dwie biblioteki, podział na obiekty i nauka pójdą "
    "<b>wyraźnie szybciej</b> na dużych zdjęciach, a wyniki będą "
    "identyczne z implementacją wzorcową.\n\n"
    "Jak to zrobić: w menu Start, w katalogu QGIS, otwórz "
    "<b>OSGeo4W Shell</b> i wpisz jedno polecenie:\n\n"
    "&nbsp;&nbsp;&nbsp;&nbsp;<code>python -m pip install scikit-image "
    "scikit-learn</code>\n\n"
    "Potem uruchom QGIS ponownie. Jeśli polecenie nie przejdzie, "
    "uruchom OSGeo4W Shell jako administrator."
)
