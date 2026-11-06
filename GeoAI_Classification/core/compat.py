# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Field creation that works across QGIS 3.22 to 4.x."""
from __future__ import annotations

from qgis.core import QgsField

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
        f"Could not create the column '{name}': "
        + "; ".join(problems))
