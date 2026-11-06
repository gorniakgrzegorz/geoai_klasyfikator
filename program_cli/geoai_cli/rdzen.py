# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Most do modułów obliczeniowych wtyczki.

Wtyczka QGIS i program wiersza poleceń liczą dokładnie to samo — ten
sam podział na obiekty, te same 19 albo 24 cechy, ten sam Random Forest.
Różni je tylko to, skąd biorą dane i gdzie odkładają wynik. Dlatego
pliki z katalogu ``core`` są wspólne i leżą obok, w katalogu
``geoai_klasyfikator``.
"""
from __future__ import annotations

import os
import sys

# katalog, w którym leży ten plik
_TU = os.path.dirname(os.path.abspath(__file__))

# Szukamy pakietu wtyczki w kilku typowych miejscach: obok programu,
# piętro wyżej, albo w katalogu wskazanym zmienną GEOAI_KLASYFIKATOR.
_KANDYDACI = [
    os.environ.get("GEOAI_KLASYFIKATOR", ""),
    os.path.join(_TU, "..", "geoai_klasyfikator"),
    os.path.join(_TU, "..", "..", "geoai_klasyfikator"),
    os.path.join(_TU, "geoai_klasyfikator"),
]


def _znajdz_pakiet():
    for sciezka in _KANDYDACI:
        if not sciezka:
            continue
        pelna = os.path.normpath(os.path.abspath(sciezka))
        if os.path.isfile(os.path.join(pelna, "core", "features.py")):
            return pelna
    return None


_PAKIET = _znajdz_pakiet()
if _PAKIET is None:
    raise ImportError(
        "Nie znalazłem modułów obliczeniowych wtyczki.\n"
        "Katalog 'geoai_klasyfikator' powinien leżeć obok katalogu "
        "'geoai_cli'. Możesz też wskazać go zmienną środowiskową "
        "GEOAI_KLASYFIKATOR.")

_RODZIC = os.path.dirname(_PAKIET)
if _RODZIC not in sys.path:
    sys.path.insert(0, _RODZIC)

_NAZWA = os.path.basename(_PAKIET)
_core = __import__(_NAZWA + ".core", fromlist=["core"])

# moduły obliczeniowe, już gotowe do użycia
accuracy = __import__(_NAZWA + ".core.accuracy", fromlist=["accuracy"])
classifier = __import__(_NAZWA + ".core.classifier", fromlist=["classifier"])
features = __import__(_NAZWA + ".core.features", fromlist=["features"])
refine = __import__(_NAZWA + ".core.refine", fromlist=["refine"])
slic = __import__(_NAZWA + ".core.slic", fromlist=["slic"])
deps = __import__(_NAZWA + ".core.deps", fromlist=["deps"])

SCIEZKA_PAKIETU = _PAKIET
