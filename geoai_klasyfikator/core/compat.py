# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Field creation that works across QGIS 3.22 to 4.x."""
from __future__ import annotations

from qgis.core import QgsField
from qgis.PyQt.QtCore import QLocale

_MODERN = None
_LEGACY = None

try:
    from qgis.PyQt.QtCore import QMetaType
    _MODERN = {"string": QMetaType.Type.QString,
               "int": QMetaType.Type.Int,
               "double": QMetaType.Type.Double}
except Exception:
    _MODERN = None

try:
    from qgis.PyQt.QtCore import QVariant
    _LEGACY = {"string": QVariant.String,
               "int": QVariant.Int,
               "double": QVariant.Double}
except Exception:
    _LEGACY = None


def make_field(name: str, kind: str = "string", length: int = 0,
               precision: int = 0) -> QgsField:
    """Create a QgsField whichever Qt generation QGIS was built against."""
    problems = []
    for table in (_MODERN, _LEGACY):
        if table is None:
            continue
        try:
            if length or precision:
                return QgsField(name, table[kind], len=length,
                                prec=precision)
            return QgsField(name, table[kind])
        except Exception as error:
            problems.append(str(error))
    raise RuntimeError(
        f"Nie udało się utworzyć kolumny '{name}': "
        + "; ".join(problems))


# Zapis liczb w polach i komunikatach. Wersja polska zawsze używa
# przecinka dziesiętnego, niezależnie od ustawień systemu; angielska
# (pusty napis) idzie za ustawieniami regionalnymi QGIS.
LOKALE_LICZB = "pl_PL"


def lokalizacja_liczb() -> QLocale:
    """Lokalizacja dla pól liczbowych i liczb w komunikatach."""
    return QLocale(LOKALE_LICZB) if LOKALE_LICZB else QLocale()


def liczba(wartosc, miejsca=2) -> str:
    """Liczba z separatorem dziesiętnym zgodnym z polami wtyczki."""
    tekst = ("{0:." + str(miejsca) + "f}").format(wartosc)
    return tekst.replace(".", lokalizacja_liczb().decimalPoint())
