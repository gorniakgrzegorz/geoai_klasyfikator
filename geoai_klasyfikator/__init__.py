# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""GeoAI Klasyfikator — moduł startowy wtyczki QGIS."""


def classFactory(iface):        # noqa: N802 (name required by QGIS)
    from .main_plugin import GeoaiKlasyfikator
    return GeoaiKlasyfikator(iface)
