# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
NARZĘDZIA NA MAPIE: klikanie obiektów, żeby przypisać im klasę, oraz
klikanie punktów kontrolnych, żeby je opisać.

Kliknięcie obiektu dodaje go do aktywnej klasy, kliknięcie drugi raz
usuwa. Z wciśniętym Ctrl można malować: każdy obiekt, przez który
przejedzie kursor, trafia do aktywnej klasy.
"""
from __future__ import annotations

from qgis.core import QgsPointXY
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt


class SegmentLabelTool(QgsMapTool):
    """Znajduje obiekt pod kursorem i przekazuje go do panelu."""

    def __init__(self, canvas, panel):
        super().__init__(canvas)
        self.canvas = canvas
        self.panel = panel
        self.painting = False
        self.visited = set()
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ── events ───────────────────────────────────────────────────────

    def canvasPressEvent(self, event):
        segment = self._segment_at(event)
        if segment is None:
            return
        modifiers = event.modifiers()
        if event.button() == Qt.MouseButton.RightButton:
            self.panel.on_segment_right_clicked(segment)
            return

        self.visited = {segment}
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self.painting = True
            self.panel.on_segment_painted(segment)
        else:
            self.panel.on_segment_clicked(segment)

    def canvasMoveEvent(self, event):
        if not self.painting:
            return
        segment = self._segment_at(event)
        if segment is None or segment in self.visited:
            return
        self.visited.add(segment)
        self.panel.on_segment_painted(segment)

    def canvasReleaseEvent(self, event):
        if self.painting:
            self.painting = False
            self.visited = set()
            self.panel.on_painting_finished()

    def deactivate(self):
        self.painting = False
        super().deactivate()
        self.panel.on_tool_deactivated()

    # ── helpers ──────────────────────────────────────────────────────

    def _segment_at(self, event):
        grid = getattr(self.panel, "grid", None)
        labels = getattr(self.panel, "labels", None)
        if grid is None or labels is None:
            return None

        point = self.toMapCoordinates(event.pos())
        point = self.panel.to_grid_crs(QgsPointXY(point))
        if point is None:
            return None

        row, col = grid.map_to_pixel(point.x(), point.y())
        height, width = labels.shape
        if not (0 <= row < height and 0 <= col < width):
            return None
        value = int(labels[row, col])
        return value if value > 0 else None


class PointLabelTool(QgsMapTool):
    """Nadaje punktowi pod kursorem aktywną klasę."""

    SEARCH_PIXELS = 12

    def __init__(self, canvas, panel):
        super().__init__(canvas)
        self.canvas = canvas
        self.panel = panel
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def canvasPressEvent(self, event):
        layer = getattr(self.panel, "points_layer", None)
        if layer is None:
            return
        point = self.toMapCoordinates(event.pos())
        tolerance = (self.canvas.mapUnitsPerPixel() * self.SEARCH_PIXELS)

        nearest_id = None
        nearest_distance = None
        for feature in layer.getFeatures():
            geometry = feature.geometry()
            if geometry.isEmpty():
                continue
            distance = geometry.asPoint().distance(point)
            if distance <= tolerance and (nearest_distance is None
                                          or distance < nearest_distance):
                nearest_distance = distance
                nearest_id = feature.id()

        if nearest_id is None:
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.panel.on_point_cleared(nearest_id)
        else:
            self.panel.on_point_labelled(nearest_id)

    def deactivate(self):
        super().deactivate()
        self.panel.on_tool_deactivated()
