# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Główna klasa wtyczki "GeoAI Klasyfikator".

Stawia na pasku narzędzi jeden przycisk (ikona i napis), który
otwiera albo zamyka panel po prawej stronie okna QGIS.

© Grzegorz Górniak <gorniakgrzegorz@gmail.com>
"""
from __future__ import annotations

import contextlib
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QToolBar, QToolButton

MENU = "&GeoAI Klasyfikator"


class GeoaiKlasyfikator:
    """Podpina wtyczkę do interfejsu QGIS."""

    TOOLBAR_NAME = "GeoAI Klasyfikator"

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.toolbar: QToolBar | None = None
        self.panel = None

    def initGui(self) -> None:
        """QGIS woła to przy starcie — dodajemy przycisk i menu."""
        icon = QIcon(os.path.join(self.plugin_dir, "icon.svg"))
        if icon.isNull():
            icon = QIcon(os.path.join(self.plugin_dir, "icon.png"))

        self.action = QAction(icon, "GeoAI Klasyfikator",
                              self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setToolTip(
            "Mapa pokrycia terenu ze zdjęć z drona i zdjęć "
            "lotniczych, metodą obiektową")
        self.action.triggered.connect(self.toggle_panel)

        self.toolbar = self.iface.addToolBar(self.TOOLBAR_NAME)
        self.toolbar.setObjectName("GeoAIKlasyfikatorToolbar")
        button = QToolButton()
        button.setDefaultAction(self.action)
        button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toolbar.addWidget(button)

        self.iface.addPluginToRasterMenu(MENU, self.action)

    def unload(self) -> None:
        """Sprzątanie przy wyłączaniu wtyczki.

        Najważniejsze jest zdjęcie narzędzia z kanwy: gdyby zostało,
        pierwsze kliknięcie po mapie trafiłoby w usunięty już panel
        i wywróciłoby QGIS.
        """
        if self.panel is not None:
            narzedzie = getattr(self.panel, "active_tool", None)
            if narzedzie is not None:
                with contextlib.suppress(Exception):
                    self.iface.mapCanvas().unsetMapTool(narzedzie)
                self.panel.active_tool = None
            self.iface.removeDockWidget(self.panel)
            self.panel.deleteLater()
            self.panel = None

        if self.action is not None:
            self.iface.removePluginRasterMenu(MENU, self.action)
            self.action.deleteLater()
            self.action = None

        if self.toolbar is not None:
            with contextlib.suppress(Exception):
                self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
            self.toolbar = None

    def toggle_panel(self) -> None:
        """Klik w przycisk: pokaż panel albo go schowaj."""
        created = False
        if self.panel is None:
            try:
                from .dialogs.dock import PanelKlasyfikatora
                self.panel = PanelKlasyfikatora(
                    self.iface, self.plugin_dir, self.iface.mainWindow())
                self.panel.setObjectName("GeoaiKlasyfikatorPanel")
                self.panel.visibilityChanged.connect(self.action.setChecked)
                self.iface.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, self.panel)
                created = True
            except Exception as error:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Nie udało się uruchomić wtyczki",
                    "Panel się nie otworzył:\n{0}".format(error))
                self.action.setChecked(False)
                return

        if created or not self.panel.isVisible():
            self.panel.setVisible(True)
            self.action.setChecked(True)
            self.panel.raise_()
        else:
            with contextlib.suppress(Exception):
                self.panel._zdejmij_narzedzie()
            self.panel.setVisible(False)
            self.action.setChecked(False)
