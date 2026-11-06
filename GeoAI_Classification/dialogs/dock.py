# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
PANEL WTYCZKI "GeoAI Klasyfikator" — cztery kroki, jeden pod drugim.

    1  Zdjęcie i obiekty   wczytanie, podział na obiekty, pomiary
    2  Klasy i przykłady   wskazywanie przykładów klikaniem po mapie
    3  Nauka i klasyfikacja  Random Forest, poprawki, zapis mapy
    4  Ocena dokładności   losowanie punktów, opis na ślepo, raport

© Grzegorz Górniak
"""
from __future__ import annotations

import os
from contextlib import suppress

import numpy as np
from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsCoordinateTransform,
    QgsFillSymbol,
    QgsMapLayerProxyModel,
    QgsMarkerSymbol,
    QgsProject,
    QgsRendererCategory,
    QgsVectorLayer,
)
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import accuracy as ACC
from ..core import classifier as CLF
from ..core import features as FEAT
from ..core import qgis_io as IO
from ..core import refine as REF
from ..core.compat import make_field
from ..core.deps import INSTALL_HINT, engine_report, missing_packages
from ..core.slic import DEFAULT_COMPACTNESS, DEFAULT_SIGMA, slic_segments
from .maptools import PointLabelTool, SegmentLabelTool

BRAND = "#00bde7"
BRAND_DARK = "#009ec2"

STYLE = """
QDockWidget { background: #ffffff; }
QLabel { color: #1a1a1a; }
QLabel#title { font-size: 14px; font-weight: bold; color: #ffffff; }
QLabel#subtitle { font-size: 11px; color: #eafaff; }
QWidget#header { background: __BRAND__; border-radius: 4px; }
QLabel#hint { color: #607d8b; font-size: 11px; }
QLabel#engine { color: #37474f; font-size: 11px; }
QLabel#signature { color: #000000; font-size: 10px; padding: 2px 3px 0 0; }
QGroupBox {
    border: 1px solid #d7e3e8; border-radius: 4px;
    margin-top: 9px; padding-top: 8px;
    font-weight: bold; color: #37474f;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QPushButton {
    background: #eceff1; border: 1px solid #cfd8dc;
    border-radius: 3px; padding: 3px 8px; color: #263238;
}
QPushButton:hover { background: #dfe6e9; }
QPushButton:disabled { color: #b0bec5; }
QPushButton#action {
    background: __BRAND__; color: #ffffff; border: none;
    border-radius: 4px; padding: 7px; font-weight: bold;
}
QPushButton#action:hover { background: __DARK__; }
QPushButton#action:disabled { background: #b0bec5; color: #eceff1; }
QPushButton#guide { background: #ffffff; color: __DARK__;
                    border: none; font-weight: bold; }
QProgressBar {
    border: 1px solid #cfd8dc; border-radius: 3px;
    text-align: center; height: 16px; background: #f5f7f8;
}
QProgressBar::chunk { background: __BRAND__; border-radius: 2px; }
QListWidget, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    border: 1px solid #cfd8dc; border-radius: 3px;
    background: #ffffff; color: #1a1a1a;
}
""".replace("__BRAND__", BRAND).replace("__DARK__", BRAND_DARK)

KOLORY = [
    "#8c6d4f", "#7bbf4a", "#2f8f3e", "#c9d84a", "#2f7fd1",
    "#1f6b2f", "#9e9e9e", "#d1495b", "#6d4c41", "#e0a030",
    "#00897b", "#5e35b1",
]

# podpowiedzi kolorów po nazwie klasy, jak w typowych opracowaniach
PODPOWIEDZI_KOLOROW = {
    # nazwy angielskie najpierw: "lake" zawiera polskie "lak"
    "forest": "#1f6b2f", "tree": "#1f6b2f", "wood": "#2f8f3e",
    "grass": "#7bbf4a", "lawn": "#7bbf4a", "meadow": "#c9d84a",
    "crop": "#e0c060", "field": "#e0c060", "arable": "#e0c060",
    "water": "#2f7fd1", "river": "#2f7fd1", "lake": "#2f7fd1",
    "pond": "#2f7fd1",
    "built": "#d1495b", "building": "#d1495b", "roof": "#d1495b",
    "road": "#9e9e9e", "asphalt": "#707070", "paved": "#808080",
    "soil": "#8c6d4f", "bare": "#8c6d4f", "sand": "#d8c9a0",
    "las": "#1f6b2f", "drzew": "#1f6b2f", "zadrzew": "#2f8f3e",
    "traw": "#7bbf4a", "łąk": "#c9d84a", "lak": "#c9d84a",
    "roln": "#e0c060", "upraw": "#e0c060", "pole": "#e0c060",
    "wod": "#2f7fd1", "rzek": "#2f7fd1", "staw": "#2f7fd1",
    "zabudow": "#d1495b", "budyn": "#d1495b", "dach": "#d1495b",
    "drog": "#9e9e9e", "asfalt": "#707070", "parking": "#808080",
    "gleb": "#8c6d4f", "grunt": "#8c6d4f", "piach": "#d8c9a0",
    "ciep": "#e0a030",
}


def _liczba(wartosc, miejsca=2):
    """Liczba z przecinkiem dziesiętnym, jak się pisze po polsku."""
    return ("{0:." + str(miejsca) + "f}").format(wartosc).replace(".", ".")


def _odmiana(liczba, jeden, kilka, wiele):
    """Polska odmiana po liczebniku: 1 obiekt, 3 obiekty, 7 obiektów."""
    liczba = int(liczba)
    if liczba == 1:
        return jeden
    reszta_10, reszta_100 = liczba % 10, liczba % 100
    if 2 <= reszta_10 <= 4 and not 12 <= reszta_100 <= 14:
        return kilka
    return wiele


def _procent(udzial, miejsca=1):
    """Udział 0-1 zapisany jako polski procent."""
    return _liczba(udzial * 100.0, miejsca) + "%"


def _orzeczenie(liczba, forma_mnoga, forma_dopelniaczowa):
    """Czasownik zgodny z liczebnikiem: 3 obiekty DOSTAŁY, 7 DOSTAŁO."""
    liczba = int(liczba)
    reszta_10, reszta_100 = liczba % 10, liczba % 100
    if liczba != 1 and 2 <= reszta_10 <= 4 and not 12 <= reszta_100 <= 14:
        return forma_mnoga
    return forma_dopelniaczowa


class PanelKlasyfikatora(QDockWidget):
    """Wszystko, co wtyczka potrafi, w jednym panelu."""

    def __init__(self, iface, plugin_dir, parent=None):
        super().__init__("GeoAI Classification", parent)
        self.iface = iface
        self.plugin_dir = plugin_dir

        self.grid = None
        self.labels = None
        self.feature_ids = None
        self.feature_matrix = None
        self.feature_names = []
        self.segments_layer = None
        self.classes = []
        self.training = {}
        self.model = None
        self.classified = None
        self.points_layer = None
        self.point_strata = None
        self.stratum_pixels = None
        self.active_tool = None
        self._busy = False
        self._switching_tool = False

        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea
                             | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._refresh_class_list()
        self._update_buttons()

    # ── budowa okna ──────────────────────────────────────────────────

    def _build_ui(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        layout.addWidget(self._header())
        layout.addWidget(self._step_image())
        layout.addWidget(self._step_classes())
        layout.addWidget(self._step_classify())
        layout.addWidget(self._step_accuracy())

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(92)
        self.log.setPlaceholderText(
            "Here you can see what the plugin is doing.")
        layout.addWidget(self.log)

        signature = QLabel(
            '<a href="mailto:gorniakgrzegorz@gmail.com" '
            'style="color:#000000; text-decoration:none;">'
            '&#169; Grzegorz G&#243;rniak</a>')
        signature.setObjectName("signature")
        signature.setOpenExternalLinks(True)
        signature.setCursor(Qt.CursorShape.PointingHandCursor)
        signature.setToolTip("Have a question or an idea? Write to me.")
        layout.addWidget(signature, 0, Qt.AlignmentFlag.AlignRight)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(inner)
        self.setWidget(scroll)

    def _header(self):
        header = QWidget()
        header.setObjectName("header")
        row = QHBoxLayout(header)
        row.setContentsMargins(9, 6, 9, 6)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("GeoAI Classification")
        title.setObjectName("title")
        subtitle = QLabel("Land cover from UAV and aerial imagery")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        titles.addWidget(title)
        titles.addWidget(subtitle)

        guide = QPushButton("Guide")
        guide.setObjectName("guide")
        guide.clicked.connect(self._show_guide)
        row.addLayout(titles, 1)
        row.addWidget(guide, 0, Qt.AlignmentFlag.AlignTop)
        return header

    def _step_image(self):
        box = QGroupBox("Step 1 · Image and segmentation")
        form = QFormLayout(box)
        form.setContentsMargins(8, 12, 8, 8)
        form.setSpacing(4)

        intro = QLabel(
            "The plugin does not classify single pixels but whole "
            "parts of the image: pieces of a field, a roof or a tree "
            "crown. First they have to be cut out.")
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        form.addRow(intro)

        self.cmb_image = QgsMapLayerComboBox()
        self.cmb_image.setFilters(QgsMapLayerProxyModel.Filter.RasterLayer)
        self.cmb_image.layerChanged.connect(self._on_image_changed)
        form.addRow("Image (RGB):", self.cmb_image)

        self.cmb_dsm = QgsMapLayerComboBox()
        self.cmb_dsm.setFilters(QgsMapLayerProxyModel.Filter.RasterLayer)
        self.cmb_dsm.setAllowEmptyLayer(True)
        self.cmb_dsm.setCurrentIndex(0)
        self.cmb_dsm.setToolTip(
            "A digital surface model (DSM) from the same flight. Not "
            "required, but very helpful: with it the plugin can tell a "
            "roof from asphalt and a tree from a lawn.")
        form.addRow("Elevation model (optional):", self.cmb_dsm)

        self.spin_resolution = QDoubleSpinBox()
        self.spin_resolution.setDecimals(3)
        self.spin_resolution.setRange(0.0, 100.0)
        self.spin_resolution.setSingleStep(0.01)
        self.spin_resolution.setSpecialValueText("as in file")
        self.spin_resolution.setToolTip(
            "The resolution used for the computations (in map units, "
            "usually metres). For drone images usually 0.05 m. Leave "
            "\"as in file\" if you are not sure.")
        form.addRow("Working resolution:", self.spin_resolution)

        self.spin_object_size = QDoubleSpinBox()
        self.spin_object_size.setRange(0.5, 10000.0)
        self.spin_object_size.setValue(10.0)
        self.spin_object_size.setDecimals(1)
        self.spin_object_size.setToolTip(
            "How large one object should be on the ground. Rule: an "
            "object must be smaller than the narrowest thing you want "
            "to show on the map. For fields and roofs 5-20 m², for "
            "single trees 2-5 m².")
        self.spin_object_size.valueChanged.connect(self._sync_segments)
        form.addRow("Object size (m²):", self.spin_object_size)

        self.spin_segments = QSpinBox()
        self.spin_segments.setRange(100, 2000000)
        self.spin_segments.setValue(10000)
        self.spin_segments.setGroupSeparatorShown(True)
        self.spin_segments.setToolTip(
            "The same thing expressed as a number of objects. Change "
            "one and the other is recalculated.")
        self.spin_segments.valueChanged.connect(self._on_segments_edited)
        form.addRow("or number of objects:", self.spin_segments)

        self.chk_advanced = QCheckBox("Show advanced settings")
        self.chk_advanced.toggled.connect(self._toggle_advanced)
        form.addRow(self.chk_advanced)

        self.spin_compactness = QDoubleSpinBox()
        self.spin_compactness.setRange(0.01, 1.0)
        self.spin_compactness.setSingleStep(0.01)
        self.spin_compactness.setDecimals(2)
        self.spin_compactness.setValue(DEFAULT_COMPACTNESS)
        self.spin_compactness.setToolTip(
            "Low value: objects closely follow colour boundaries. High "
            "value: they come out regular, almost square. Leave 0.15.")
        self.lbl_compactness = QLabel("Object compactness:")
        form.addRow(self.lbl_compactness, self.spin_compactness)

        self.spin_sigma = QDoubleSpinBox()
        self.spin_sigma.setRange(0.0, 10.0)
        self.spin_sigma.setSingleStep(0.5)
        self.spin_sigma.setValue(DEFAULT_SIGMA)
        self.spin_sigma.setToolTip(
            "A slight blur before segmentation, so that noise and fine "
            "texture do not create artificial objects. Leave 2.5.")
        self.lbl_sigma = QLabel("Smoothing:")
        form.addRow(self.lbl_sigma, self.spin_sigma)

        self.chk_extent = QCheckBox("Process only what is visible on screen")
        self.chk_extent.setToolTip(
            "A quick trial on part of the image. Useful on a slower "
            "computer and when you are choosing the object size.")
        form.addRow(self.chk_extent)

        self.lbl_engine = QLabel("")
        self.lbl_engine.setObjectName("engine")
        self.lbl_engine.setWordWrap(True)
        form.addRow(self.lbl_engine)
        self._describe_engines()

        self.btn_segment = QPushButton("SEGMENT AND MEASURE")
        self.btn_segment.setObjectName("action")
        self.btn_segment.clicked.connect(self.run_segmentation)
        form.addRow(self.btn_segment)

        self._toggle_advanced(False)
        return box

    def _toggle_advanced(self, shown):
        for widget in (self.lbl_compactness, self.spin_compactness,
                       self.lbl_sigma, self.spin_sigma):
            widget.setVisible(bool(shown))

    def _step_classes(self):
        box = QGroupBox("Step 2 · Classes and examples")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)

        intro = QLabel(
            "List the classes you want to distinguish (e.g. buildings, "
            "road, grass, forest, water, bare soil), then show the "
            "plugin a few examples of each.")
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list_classes = QListWidget()
        self.list_classes.setMaximumHeight(130)
        self.list_classes.setToolTip(
            "Click a class to make it active. Double-click changes its "
            "colour.")
        self.list_classes.itemDoubleClicked.connect(self._edit_class)
        layout.addWidget(self.list_classes)

        row = QHBoxLayout()
        row.setSpacing(4)
        for text, slot in (("Add class", self._add_class),
                           ("Remove class", self._remove_class),
                           ("Clear examples", self._clear_class_samples)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            row.addWidget(button)
        layout.addLayout(row)

        self.btn_collect = QPushButton("PICK EXAMPLES ON THE MAP")
        self.btn_collect.setObjectName("action")
        self.btn_collect.setCheckable(True)
        self.btn_collect.toggled.connect(self._toggle_collect)
        layout.addWidget(self.btn_collect)

        hint = QLabel(
            "Choose a class, then click the objects on the map that "
            "belong to it. Clicking again removes the object from the "
            "class. Hold <b>Ctrl</b> to paint by dragging the "
            "mouse.<br><br>Two tips make the biggest difference: "
            "spread the examples over the whole image, not in one "
            "corner, and show <i>every variant</i> of a class, both "
            "lush grass and dry grass. Pick only what you recognise "
            "without hesitation.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return box

    def _step_classify(self):
        box = QGroupBox("Step 3 · Training and map")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)

        intro = QLabel(
            "Now the plugin learns from your examples and assigns a "
            "class to every object in the image.")
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.btn_separability = QPushButton("Can the classes be told apart?")
        self.btn_separability.setToolTip(
            "Checks, before you start, whether your classes differ "
            "enough to be separated at all, and which features "
            "separate them.")
        self.btn_separability.clicked.connect(self.check_separability)
        self.btn_train = QPushButton("Train")
        self.btn_train.setToolTip(
            "Trains Random Forest on the examples you picked. It takes "
            "seconds, so you can repeat it as often as needed.")
        self.btn_train.clicked.connect(self.train_model)
        row.addWidget(self.btn_separability, 1)
        row.addWidget(self.btn_train)
        layout.addLayout(row)

        self.btn_classify = QPushButton("MAKE MAP")
        self.btn_classify.setObjectName("action")
        self.btn_classify.clicked.connect(self.classify_all)
        layout.addWidget(self.btn_classify)

        loop = QLabel(
            "After the first map, look over all of it and write down "
            "the <i>kinds</i> of errors (\"dry grass taken for soil\"). "
            "Add a few examples of each kind in different places and "
            "click Train and Make map again. The first two or three "
            "rounds improve the most.")
        loop.setObjectName("hint")
        loop.setWordWrap(True)
        layout.addWidget(loop)

        refine_box = QGroupBox("Recovering narrow strips (optional)")
        refine_form = QFormLayout(refine_box)
        refine_form.setContentsMargins(6, 10, 6, 6)
        refine_form.setSpacing(3)

        self.chk_refine = QCheckBox("Enable greenness refinement")
        self.chk_refine.setToolTip(
            "Objects still decide what kind of land it is, but for two "
            "selected classes each pixel is decided by its greenness. "
            "This recovers a strip of grass narrower than an object, "
            "such as a balk between plots or grass along a ditch.")
        refine_form.addRow(self.chk_refine)

        self.cmb_green = QComboBox()
        self.cmb_other = QComboBox()
        refine_form.addRow("Green class:", self.cmb_green)
        refine_form.addRow("Other class:", self.cmb_other)

        cutoff_row = QHBoxLayout()
        self.spin_cutoff = QDoubleSpinBox()
        self.spin_cutoff.setRange(-2.0, 2.0)
        self.spin_cutoff.setDecimals(4)
        self.spin_cutoff.setSingleStep(0.01)
        btn_cutoff = QPushButton("Compute from examples")
        btn_cutoff.clicked.connect(self._cutoff_from_samples)
        cutoff_row.addWidget(self.spin_cutoff, 1)
        cutoff_row.addWidget(btn_cutoff)
        refine_form.addRow("Greenness threshold:", cutoff_row)

        self.spin_window = QSpinBox()
        self.spin_window.setRange(1, 15)
        self.spin_window.setValue(REF.DEFAULT_WINDOW)
        self.spin_window.setSingleStep(2)
        self.spin_window.setToolTip(
            "Greenness is averaged over a small square so that single "
            "pixels do not flicker. A smaller window follows thin "
            "strips more closely but can be noisy.")
        refine_form.addRow("Averaging window (pixels):", self.spin_window)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Keep green objects whole",
                                "Each pixel separately, both ways"])
        self.cmb_mode.setToolTip(
            "The first option does not punch bare patches into grass "
            "and is safer. The second gives sharper edges.")
        refine_form.addRow("Mode:", self.cmb_mode)
        layout.addWidget(refine_box)

        mmu_row = QHBoxLayout()
        mmu_row.addWidget(QLabel("Minimum patch:"))
        self.spin_mmu = QSpinBox()
        self.spin_mmu.setRange(0, 200000)
        self.spin_mmu.setSuffix(" px")
        self.spin_mmu.setToolTip(
            "Patches of one class smaller than this are absorbed by "
            "their surroundings, so the map is no longer sprinkled "
            "with single specks (\"salt and pepper\"). Set it for how "
            "the map will be used, not to raise the accuracy score. "
            "Zero means no cleaning.")
        self.lbl_mmu = QLabel("")
        self.lbl_mmu.setObjectName("hint")
        self.spin_mmu.valueChanged.connect(self._update_mmu_label)
        mmu_row.addWidget(self.spin_mmu)
        mmu_row.addWidget(self.lbl_mmu, 1)
        layout.addLayout(mmu_row)

        self.btn_export = QPushButton("Save map to GeoTIFF")
        self.btn_export.clicked.connect(self.export_map)
        layout.addWidget(self.btn_export)
        return box

    def _step_accuracy(self):
        box = QGroupBox("Step 4 · How good is this map")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)

        intro = QLabel(
            "A map is worth as much as you know about its errors. The "
            "plugin draws check points, you label them by looking at "
            "the image alone, and at the end you get figures you can "
            "cite in a report.")
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setSpacing(4)

        self.cmb_design = QComboBox()
        self.cmb_design.addItems(["Stratified by map class (recommended)",
                                  "Simple random"])
        self.cmb_design.setToolTip(
            "Stratified sampling gives every class, even the smallest, "
            "enough points to say something about it. Simple random "
            "sampling spreads points evenly, and rare classes get too "
            "few.")
        form.addRow("Sampling design:", self.cmb_design)

        self.spin_min_class = QSpinBox()
        self.spin_min_class.setRange(1, 1000)
        self.spin_min_class.setValue(50)
        self.spin_min_class.setToolTip(
            "With fewer than 30 points per class, the results for that "
            "class will be very uncertain.")
        form.addRow("Minimum points per class:", self.spin_min_class)

        self.spin_points = QSpinBox()
        self.spin_points.setRange(1, 20000)
        self.spin_points.setValue(200)
        form.addRow("Total points:", self.spin_points)
        layout.addLayout(form)

        self.btn_points = QPushButton("Draw check points")
        self.btn_points.clicked.connect(self.generate_points)
        layout.addWidget(self.btn_points)

        self.btn_label_points = QPushButton("LABEL POINTS ON THE MAP")
        self.btn_label_points.setObjectName("action")
        self.btn_label_points.setCheckable(True)
        self.btn_label_points.toggled.connect(self._toggle_point_tool)
        layout.addWidget(self.btn_label_points)

        hint = QLabel(
            "Turn off the classification map layer and label the "
            "points by looking at the image alone; otherwise the "
            "plugin's answer will influence your judgement. Choose a "
            "class and click a point; the right mouse button clears "
            "the label. If you really cannot tell what is at a "
            "location, delete that point in the attribute table rather "
            "than guess.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.btn_assess = QPushButton("COMPUTE ACCURACY")
        self.btn_assess.setObjectName("action")
        self.btn_assess.clicked.connect(self.run_assessment)
        layout.addWidget(self.btn_assess)
        return box

    # ── drobiazgi ────────────────────────────────────────────────────

    def _describe_engines(self):
        report = engine_report()
        missing = missing_packages()
        if report["exact"]:
            text = ("Engines: {0}; {1}. Results match the reference "
                    "implementation.").format(report["segmentation"],
                                        report["classifier"])
        else:
            text = ("Engines built into the plugin. It works with nothing else "
                    "installed; if you install {0}, it will be faster and "
                    "closer to the reference implementation. Instructions are "
                    "in the Guide."
                    ).format(" and ".join(missing))
        self.lbl_engine.setText(text)

    def _zajety(self, czynnosc="Another computation is running"):
        """True, gdy coś już się liczy — chroni przed drugim przebiegiem.

        Paski postępu wołają processEvents(), więc użytkownik może w
        trakcie kliknąć przycisk jeszcze raz. Bez tej blokady drugi
        przebieg podmieniłby dane w środku pierwszego.
        """
        if self._busy:
            QMessageBox.information(
                self, "Just a moment",
                "{0}. Wait until the progress bar reaches the end."
                .format(czynnosc))
            return True
        return False

    def _akcje(self):
        return (self.btn_segment, self.btn_train, self.btn_classify,
                self.btn_separability, self.btn_export, self.btn_points,
                self.btn_assess)

    def _zablokuj_akcje(self, zablokowane):
        self._busy = bool(zablokowane)
        for przycisk in self._akcje():
            przycisk.setEnabled(not zablokowane)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor) \
            if zablokowane else QApplication.restoreOverrideCursor()
        QApplication.processEvents()

    def say(self, message):
        self.log.append(message)
        QApplication.processEvents()

    def step(self, percent, message):
        self.progress.setVisible(True)
        self.progress.setValue(int(percent))
        self.progress.setFormat(message)
        QApplication.processEvents()

    def to_grid_crs(self, point):
        """Przenosi punkt z kanwy do układu zdjęcia."""
        if self.grid is None:
            return None
        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        grid_crs = self.grid.crs()
        if not grid_crs.isValid() or canvas_crs == grid_crs:
            return point
        transform = QgsCoordinateTransform(canvas_crs, grid_crs,
                                           QgsProject.instance())
        with suppress(Exception):
            return transform.transform(point)
        return point

    def _area_of_scene(self):
        if self.grid is None:
            return 0.0
        pixels = int(np.count_nonzero(self.grid.mask))
        return pixels * (self.grid.pixel_size ** 2)

    def _sync_segments(self, value):
        self._ostatnio_liczba = False
        area = self._area_of_scene()
        if area <= 0 or value <= 0:
            return
        count = max(100, int(round(area / value)))
        self.spin_segments.blockSignals(True)
        self.spin_segments.setValue(min(count, self.spin_segments.maximum()))
        self.spin_segments.blockSignals(False)

    def _on_segments_edited(self, value):
        """Użytkownik podał liczbę obiektów — to ona rozstrzyga."""
        self._ostatnio_liczba = True
        self._sync_object_size(value)

    def _sync_object_size(self, value):
        area = self._area_of_scene()
        if area <= 0 or value <= 0:
            return
        self.spin_object_size.blockSignals(True)
        self.spin_object_size.setValue(max(0.5, area / value))
        self.spin_object_size.blockSignals(False)

    def _update_mmu_label(self, value):
        if self.grid is None:
            self.lbl_mmu.setText("")
            return
        area = REF.pixels_to_area(value, self.grid.pixel_size)
        self.lbl_mmu.setText(
            "that is {0} m²".format(_liczba(area, 1)))

    def _on_image_changed(self, layer):
        """Nowe zdjęcie oznacza nową sesję — stary stan przestaje pasować."""
        if self.labels is not None:
            self.say("The image has changed: the previous segmentation, "
                     "examples and map no longer fit and have been cleared.")
        self._wyczysc_sesje()
        if layer is None:
            self._update_buttons()
            return
        with suppress(Exception):
            size = IO.native_pixel_size(IO._layer_path(layer))
            self.spin_resolution.setMinimum(0.0)
            self.spin_resolution.setToolTip(
                "This file has {0} m per pixel. The working resolution "
                "cannot be finer than that; a smaller number only "
                "upsamples the image."
                .format(_liczba(size, 4)))
            self._native_pixel = float(size)
        self._update_buttons()

    def _wyczysc_sesje(self):
        """Zeruje wszystko, co było związane z poprzednim zdjęciem."""
        self._zdejmij_narzedzie()
        for warstwa in (self.segments_layer, self.points_layer):
            if warstwa is not None:
                with suppress(Exception):
                    QgsProject.instance().removeMapLayer(warstwa.id())
        self.grid = None
        self.labels = None
        self.feature_ids = None
        self.feature_matrix = None
        self.feature_names = []
        self.segments_layer = None
        self.points_layer = None
        self.point_strata = None
        self.stratum_pixels = None
        self.training = {}
        self.model = None
        self.classified = None
        self._refresh_class_list()

    def _zdejmij_narzedzie(self):
        """Zdejmuje narzędzie z kanwy, nie wywołując zwrotnych sygnałów."""
        narzedzie, self.active_tool = self.active_tool, None
        if narzedzie is None:
            return
        self._switching_tool = True
        try:
            with suppress(Exception):
                self.iface.mapCanvas().unsetMapTool(narzedzie)
        finally:
            self._switching_tool = False
        for przycisk in (self.btn_collect, self.btn_label_points):
            przycisk.blockSignals(True)
            przycisk.setChecked(False)
            przycisk.blockSignals(False)
        self.btn_collect.setText("PICK EXAMPLES ON THE MAP")
        self.btn_label_points.setText("LABEL POINTS ON THE MAP")

    def _suggest_colour(self, name):
        """Dobiera kolor do nazwy klasy, jak w typowych opracowaniach."""
        lowered = name.lower()
        for fragment, colour in PODPOWIEDZI_KOLOROW.items():
            if fragment in lowered:
                return QColor(colour)
        return QColor(KOLORY[len(self.classes) % len(KOLORY)])

    # ── krok 1: podział na obiekty ───────────────────────────────────

    def run_segmentation(self):
        layer = self.cmb_image.currentLayer()
        if layer is None:
            QMessageBox.warning(
                self, "No image",
                "Choose the image to work on. If it is not in the list, "
                "load it into the QGIS project first.")
            return

        extent = None
        if self.chk_extent.isChecked():
            extent = self._zasieg_kanwy_w_ukladzie_zdjecia(layer)
            if extent is None:
                return

        if self._zajety("Segmentation in progress"):
            return

        self.log.clear()
        self._zablokuj_akcje(True)
        try:
            self.step(5, "Loading image...")
            zadana = self.spin_resolution.value()
            wlasna = getattr(self, "_native_pixel", 0.0)
            if zadana > 0 and wlasna > 0 and zadana < wlasna * 0.999:
                odpowiedz = QMessageBox.question(
                    self, "Resolution finer than the file",
                    "You asked for {0} m per pixel, but the image has {1} m. "
                    "The image will only be upsampled: processing will take "
                    "many times longer and no detail will be gained.\n\nUse the "
                    "file resolution ({1} m)?"
                    .format(_liczba(zadana, 4), _liczba(wlasna, 4)))
                if odpowiedz == QMessageBox.StandardButton.Yes:
                    zadana = 0.0
                    self.spin_resolution.setValue(0.0)
            self.grid = IO.read_rgb(layer, zadana, extent)
            height, width = self.grid.shape
            self.say("Working grid: {0} by {1} pixels, {2:.4f} map units each. "
                     "Area: {3:.2f} ha."
                     .format(width, height, self.grid.pixel_size,
                             self._area_of_scene() / 10000.0))

            dsm = None
            dsm_layer = self.cmb_dsm.currentLayer()
            if dsm_layer is not None:
                self.step(15, "Loading elevation model...")
                ostrzezenia_dsm = []
                dsm = IO.read_dsm_like(dsm_layer, self.grid,
                                       ostrzezenia_dsm)
                for uwaga in ostrzezenia_dsm:
                    self.say("Note: " + uwaga)
                self.say("Elevation model aligned to the same grid.")
                szerokosc_m = min(self.grid.shape) * self.grid.pixel_size
                if szerokosc_m < 80.0:
                    self.say("Note: the extent is only {0} m across, so the ground is "
                             "estimated with a window narrower than the recommended 40 "
                             "m. Wide roofs and dense stands of trees may get a height "
                             "above ground close to zero; process the whole image if "
                             "the height needs to be reliable.".format(_liczba(szerokosc_m, 0)))

            # to, co użytkownik ustawił jako ostatnie, jest wiążące
            if not getattr(self, "_ostatnio_liczba", False):
                self._sync_segments(self.spin_object_size.value())
            requested = self.spin_segments.value()
            self.step(25, "Segmenting the image...")
            self.labels = slic_segments(
                self.grid.array, requested,
                self.spin_compactness.value(), self.spin_sigma.value(),
                mask=self.grid.mask)
            realised = int(self.labels.max())
            rozmiary = np.bincount(self.labels.ravel())[1:]
            rozmiary = rozmiary[rozmiary > 0] * (self.grid.pixel_size ** 2)
            mediana = float(np.median(rozmiary)) if rozmiary.size else 0.0
            najwiekszy = float(rozmiary.max()) if rozmiary.size else 0.0
            zamowiona = self.spin_object_size.value()
            self.say("Created {0} objects ({1} requested). Median area: {2} m², "
                     "largest {3} m²."
                     .format(realised, requested, _liczba(mediana),
                             _liczba(najwiekszy)))
            if zamowiona > 0 and mediana > zamowiona * 1.3:
                self.say("Objects came out larger than requested ({0} m²). If they "
                         "merge two kinds of land, reduce \"Object size\" or raise "
                         "\"Object compactness\" in the advanced settings.".format(_liczba(zamowiona, 1)))

            def progress(message, fraction):
                self.step(35 + fraction * 40, message)

            self.feature_ids, self.feature_matrix, self.feature_names = \
                FEAT.compute_features(self.grid.array, self.labels,
                                      self.grid.pixel_size, dsm=dsm,
                                      progress=progress)
            self.say("Measured {0} features per object{1}."
                     .format(len(self.feature_names),
                             "" if dsm is not None
                             else " (without elevation model)"))

            self.step(80, "Building the object layer...")
            self._build_segments_layer()

            # nowy podział unieważnia wszystko, co było z nim związane
            self.training = {}
            self.model = None
            self.classified = None
            self.stratum_pixels = None
            self.point_strata = None
            if self.points_layer is not None:
                with suppress(Exception):
                    QgsProject.instance().removeMapLayer(
                        self.points_layer.id())
                self.points_layer = None
                self.say("The previous check points were removed because they "
                         "referred to the old segmentation.")
            self.step(100, "Objects ready.")
            self.progress.setVisible(False)
            self._update_mmu_label(self.spin_mmu.value())
            self._update_buttons()

            self.say("Now go to step 2: add classes and pick a few examples of "
                     "each.")
            self.iface.messageBar().pushMessage(
                "GeoAI Classification",
                "Done: {0} objects. Add classes and pick examples."
                .format(realised), Qgis.MessageLevel.Success, 6)

        except MemoryError as error:
            self.progress.setVisible(False)
            QMessageBox.warning(
                self, "Too large for the computer's memory",
                "{0}\n\nWhat you can do:\n  • set a coarser working "
                "resolution (e.g. 0.10 instead of 0.05),\n  • tick \"Process "
                "only what is visible on screen\",\n  • close other programs.".format(error))
        except Exception as error:
            self.progress.setVisible(False)
            self.say("Stopped: {0}".format(error))
            QMessageBox.critical(
                self, "Could not segment the image",
                "{0}\n\nIf you do not know what to do about it, write to "
                "gorniakgrzegorz@gmail.com and include the text of this "
                "message.".format(error))
        finally:
            self._zablokuj_akcje(False)

    def _zasieg_kanwy_w_ukladzie_zdjecia(self, layer):
        """Prostokąt widoczny na ekranie, przeliczony do układu zdjęcia.

        Kanwa bywa w innym układzie niż raster (typowo: projekt w
        EPSG:3857 od mapy podkładowej, ortomozaika w PL-1992). Bez
        przeliczenia wycinek wypadłby w zupełnie innym miejscu.
        """
        prostokat = self.iface.mapCanvas().extent()
        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        raster_crs = layer.crs()
        if raster_crs.isValid() and canvas_crs.isValid() \
                and canvas_crs != raster_crs:
            try:
                przelicz = QgsCoordinateTransform(canvas_crs, raster_crs,
                                                  QgsProject.instance())
                prostokat = przelicz.transformBoundingBox(prostokat)
            except Exception as blad:
                QMessageBox.warning(
                    self, "Cannot transform the view",
                    "The map view uses a different coordinate reference system "
                    "than the image, and the transformation "
                    "failed:\n{0}\n\nUntick \"Process only what is visible on "
                    "screen\" or set the project CRS to that of the image."
                    .format(blad))
                return None
        if prostokat.isEmpty():
            QMessageBox.warning(
                self, "Empty view",
                "The visible part of the map does not overlap the image. "
                "Zoom to the image or untick \"Process only what is visible "
                "on screen\".")
            return None
        return (prostokat.xMinimum(), prostokat.yMinimum(),
                prostokat.xMaximum(), prostokat.yMaximum())

    def _ostrzez_o_widocznej_mapie(self):
        """Pilnuje, by ocena nie była robiona z podglądem klasyfikacji."""
        widoczne = []
        drzewo = QgsProject.instance().layerTreeRoot()
        for warstwa in (self.segments_layer,):
            if warstwa is None:
                continue
            wezel = drzewo.findLayer(warstwa.id())
            if wezel is not None and wezel.isVisible():
                widoczne.append(warstwa.name())
        if not widoczne:
            return
        QMessageBox.information(
            self, "Turn off the classification preview first",
            "The layer \"{0}\" with the finished map is visible in the "
            "Layers panel.\n\nLabel the points by looking at the image "
            "alone. If you can see the plugin's answer, the assessment "
            "will be inflated and cannot be honestly "
            "published.\n\nUntick this layer in the Layers panel and "
            "come back here."
            .format(", ".join(widoczne)))

    def _build_segments_layer(self):
        """Jedna warstwa poligonowa z obiektami, ich pomiarami i dwiema
        kolumnami klas — cała sesja widoczna w tabeli atrybutów."""
        if self.segments_layer is not None:
            with suppress(Exception):
                QgsProject.instance().removeMapLayer(self.segments_layer.id())

        layer = IO.polygonize_segments(self.labels, self.grid,
                                       "GeoAI objects")
        provider = layer.dataProvider()
        provider.addAttributes(
            [make_field("train_class", "string", 64),
             make_field("map_class", "string", 64)]
            + [make_field(name, "double") for name in self.feature_names])
        layer.updateFields()

        lookup = {int(identifier): row for row, identifier
                  in enumerate(self.feature_ids)}
        positions = {name: index for index, name
                     in enumerate(self.feature_names)}
        indices = {name: layer.fields().indexOf(name)
                   for name in self.feature_names}

        changes = {}
        for feature in layer.getFeatures():
            row = lookup.get(int(feature["segment_id"]))
            if row is None:
                continue
            values = {}
            for name, index in indices.items():
                if index >= 0:
                    values[index] = float(
                        self.feature_matrix[row, positions[name]])
            changes[feature.id()] = values
        if changes:
            provider.changeAttributeValues(changes)

        QgsProject.instance().addMapLayer(layer)
        self.segments_layer = layer
        self._style_by_field("train_class")

    def _style_by_field(self, field):
        """Koloruje warstwę obiektów wg przykładów albo wg gotowej mapy."""
        if self.segments_layer is None:
            return
        categories = []
        for entry in self.classes:
            symbol = QgsFillSymbol.createSimple({
                "color": entry["colour"].name(),
                "outline_color": "#00000000",
                "outline_width": "0",
            })
            symbol.setOpacity(0.7)
            categories.append(QgsRendererCategory(
                entry["name"], symbol, entry["name"]))
        empty = QgsFillSymbol.createSimple({
            "color": "#00000000", "outline_color": "#00000000"})
        categories.append(QgsRendererCategory(
            None, empty, "no class"))

        with suppress(Exception):
            self.segments_layer.setRenderer(
                QgsCategorizedSymbolRenderer(field, categories))
            self.segments_layer.triggerRepaint()

    # ── krok 2: klasy i przykłady ────────────────────────────────────

    def _add_class(self):
        name, accepted = QInputDialog.getText(
            self, "New class",
            "Land cover class name\n(e.g. buildings, road, grass, "
            "forest, water, bare soil):")
        if not accepted or not name.strip():
            return
        name = name.strip()
        if any(entry["name"] == name for entry in self.classes):
            QMessageBox.information(self, "Class already exists",
                                    "A class with this name already exists.")
            return
        self.classes.append({"name": name,
                             "colour": self._suggest_colour(name),
                             "value": len(self.classes) + 1})
        self._refresh_class_list()
        self.list_classes.setCurrentRow(len(self.classes) - 1)
        self._style_by_field("map_class" if self.classified is not None
                             else "train_class")

    def _remove_class(self):
        row = self.list_classes.currentRow()
        if row < 0:
            return
        name = self.classes[row]["name"]
        answer = QMessageBox.question(
            self, "Remove class?",
            "Remove class \"{0}\" together with its examples?".format(name))
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.training = {key: value for key, value in self.training.items()
                         if value != name}
        del self.classes[row]
        for index, entry in enumerate(self.classes):
            entry["value"] = index + 1

        # numery klas się przesunęły, więc gotowa mapa i wylosowane
        # punkty odnosiłyby się do cudzych nazw — unieważniamy je
        if self.classified is not None or self.points_layer is not None:
            self._uniewaznij_mape(
                "Removing the class shifted the numbers of the remaining "
                "classes, so the map and the check points no longer fit. "
                "Train and make the map again.")
        self.model = None
        self._refresh_class_list()
        self._write_training_to_layer()
        self._update_buttons()

    def _uniewaznij_mape(self, powod):
        """Kasuje mapę i punkty, gdy przestały odpowiadać stanowi klas."""
        self.classified = None
        self.stratum_pixels = None
        self.point_strata = None
        if self.points_layer is not None:
            with suppress(Exception):
                QgsProject.instance().removeMapLayer(self.points_layer.id())
            self.points_layer = None
        self.say(powod)
        self._update_buttons()

    def _edit_class(self, item):
        row = self.list_classes.row(item)
        if row < 0:
            return
        entry = self.classes[row]
        colour = QColorDialog.getColor(
            entry["colour"], self, "Class colour " + entry["name"])
        if colour.isValid():
            entry["colour"] = colour
            self._refresh_class_list()
            self._style_by_field("map_class" if self.classified is not None
                                 else "train_class")

    def _clear_class_samples(self):
        row = self.list_classes.currentRow()
        if row < 0:
            return
        name = self.classes[row]["name"]
        self.training = {key: value for key, value in self.training.items()
                         if value != name}
        self._refresh_class_list()
        self._write_training_to_layer()
        self.say("Examples of class \"{0}\" cleared.".format(name))

    def _refresh_class_list(self):
        current = self.list_classes.currentRow()
        self.list_classes.clear()
        counts = {}
        for name in self.training.values():
            counts[name] = counts.get(name, 0) + 1

        for entry in self.classes:
            count = counts.get(entry["name"], 0)
            word = _odmiana(count, "example", "examples", "examples")
            item = QListWidgetItem("{0}   ({1} {2})".format(
                entry["name"], count, word))
            item.setForeground(entry["colour"])
            self.list_classes.addItem(item)

        if 0 <= current < self.list_classes.count():
            self.list_classes.setCurrentRow(current)
        elif self.list_classes.count():
            self.list_classes.setCurrentRow(0)

        names = [entry["name"] for entry in self.classes]
        for combo in (self.cmb_green, self.cmb_other):
            previous = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            if previous in names:
                combo.setCurrentIndex(names.index(previous))
            combo.blockSignals(False)
        self._update_buttons()

    def active_class(self):
        row = self.list_classes.currentRow()
        return self.classes[row]["name"] if 0 <= row < len(self.classes) \
            else None

    def _toggle_collect(self, checked):
        if self._switching_tool:
            return
        if not checked:
            self._zdejmij_narzedzie()
            return
        if self.labels is None:
            self._odznacz(self.btn_collect)
            QMessageBox.information(
                self, "Nothing to pick",
                "First segment the image into objects (step 1).")
            return
        if self.active_class() is None:
            self._odznacz(self.btn_collect)
            QMessageBox.information(
                self, "No class",
                "First add a class and select it in the list (the \"Add "
                "class\" button in step 2).")
            return

        self._zdejmij_narzedzie()
        self._switching_tool = True
        try:
            self.btn_collect.blockSignals(True)
            self.btn_collect.setChecked(True)
            self.btn_collect.blockSignals(False)
            self.active_tool = SegmentLabelTool(self.iface.mapCanvas(),
                                                self)
            self.iface.mapCanvas().setMapTool(self.active_tool)
        finally:
            self._switching_tool = False
        self.btn_collect.setText("PICKING: click to stop")
        self._style_by_field("train_class")

    def _odznacz(self, przycisk):
        """Odznacza przycisk, nie wywołując jego sygnału toggled."""
        przycisk.blockSignals(True)
        przycisk.setChecked(False)
        przycisk.blockSignals(False)

    # ── sygnały z narzędzia na mapie ─────────────────────────────────

    def on_segment_clicked(self, segment_id):
        name = self.active_class()
        if name is None:
            return
        if self.training.get(segment_id) == name:
            self.training.pop(segment_id, None)
        else:
            self.training[segment_id] = name
        self._refresh_class_list()
        self._write_training_to_layer([segment_id])

    def on_segment_painted(self, segment_id):
        name = self.active_class()
        if name is None:
            return
        self.training[segment_id] = name
        self._write_training_to_layer([segment_id])

    def on_painting_finished(self):
        self._refresh_class_list()

    def on_segment_right_clicked(self, segment_id):
        if self.feature_matrix is None:
            return
        found = np.flatnonzero(self.feature_ids == segment_id)
        if not len(found):
            return
        similar = self._similar_segments(int(found[0]))
        self.say("Objects most similar to this one: {0}."
                 .format(", ".join(str(value) for value in similar[:8])))

    def on_tool_deactivated(self):
        """Kanwa zabrała nam narzędzie (np. użytkownik wybrał inne)."""
        if self._switching_tool:
            return
        self.active_tool = None
        for przycisk, napis in ((self.btn_collect,
                                 "PICK EXAMPLES ON THE MAP"),
                                (self.btn_label_points,
                                 "LABEL POINTS ON THE MAP")):
            self._odznacz(przycisk)
            przycisk.setText(napis)

    def _similar_segments(self, row, limit=20):
        values = self.feature_matrix
        spread = np.std(values, axis=0)
        spread[spread == 0] = 1.0
        scaled = values / spread
        distance = np.linalg.norm(scaled - scaled[row], axis=1)
        return self.feature_ids[np.argsort(distance)[1:limit + 1]]

    def _write_training_to_layer(self, only=None):
        if self.segments_layer is None:
            return
        index = self.segments_layer.fields().indexOf("train_class")
        if index < 0:
            return
        wanted = set(only) if only is not None else None
        changes = {}
        for feature in self.segments_layer.getFeatures():
            segment = int(feature["segment_id"])
            if wanted is not None and segment not in wanted:
                continue
            changes[feature.id()] = {index: self.training.get(segment)}
        if changes:
            self.segments_layer.dataProvider().changeAttributeValues(changes)
            self.segments_layer.triggerRepaint()

    # ── krok 3: nauka, mapa, zapis ───────────────────────────────────

    def _training_arrays(self):
        if not self.training:
            raise ValueError(
                "You have not picked any examples yet. Go back to step 2 "
                "and click a few objects on the map.")
        lookup = {int(identifier): row for row, identifier
                  in enumerate(self.feature_ids)}
        rows, labels = [], []
        for segment, name in self.training.items():
            row = lookup.get(int(segment))
            if row is not None:
                rows.append(row)
                labels.append(name)
        if len(set(labels)) < 2:
            raise ValueError(
                "Training needs examples of at least two classes; "
                "otherwise there is nothing to tell apart.")
        return self.feature_matrix[rows], np.array(labels)

    def check_separability(self):
        try:
            features, labels = self._training_arrays()
        except ValueError as error:
            QMessageBox.information(self, "Not enough examples", str(error))
            return

        self.step(30, "Checking whether the classes can be told apart...")
        report = CLF.separability_report(features, labels,
                                         self.feature_names)
        self.progress.setVisible(False)
        self._show_separability(report)

    def _show_separability(self, report):
        lines = [
            "<h3>Can these classes be told apart?</h3>",
            "<p>For each pair of classes we compute how much ",
            "your examples differ. The scale runs from 0 to 2: <b>0</b> means both ",
            "classes look identical and there is nothing to separate, ",
            "<b>2</b> means they are completely different.</p>",
            "<p>Above 1.9 is good, 1.7 to 1.9 fair, below ",
            "1.7 poor: such a pair will be confused, and you need to either ",
            "add examples or merge the two classes into one.</p>",
            "<table cellpadding='4' border='1' ",
            "style='border-collapse:collapse'>",
            "<tr><th>Class pair</th><th>Score</th><th>Rating</th>",
            "<th>What separates them most</th></tr>"]
        oceny = {"good": "good", "fair": "fair", "poor": "poor"}
        for pair in report["pairs"]:
            leading = ", ".join(self._feature_label(name)
                                for name, _ in pair["leading"][:3])
            lines.append(
                "<tr><td>{0} vs {1}</td><td "
                "align='right'>{2:.2f}</td><td>{3}</td><td>{4}</td></tr>".format(
                    pair["a"], pair["b"], pair["jm"],
                    oceny.get(pair["verdict"], pair["verdict"]), leading))
        lines.append("</table>")

        sizes = ", ".join("{0}: {1}".format(name, count)
                          for name, count in report["sample_sizes"].items())
        lines.append(
            "<p style='color:#607d8b'>Number of features: {0}. "
            "Examples per class: {1}. It is good to have at least as "
            "many examples as features.</p>".format(report["n_features"], sizes))

        self._show_html("Class separability", "".join(lines), 640, 500)

    @staticmethod
    def _feature_label(name):
        """Nazwa cechy po ludzku, do pokazania użytkownikowi."""
        opisy = {
            "r_mean": "red", "g_mean": "green", "b_mean": "blue",
            "r_std": "red variability", "g_std": "green variability",
            "b_std": "blue variability",
            "brightness_mean": "brightness",
            "exg_mean": "greenness (ExG)", "vari_mean": "VARI index",
            "ngrdi_mean": "NGRDI index",
            "contrast": "texture contrast",
            "homogeneity": "texture homogeneity",
            "energy": "texture regularity",
            "entropy": "texture disorder",
            "area": "area", "perimeter": "perimeter",
            "circularity": "circularity", "convexity": "convexity",
            "brightness_rel_neighbors": "brightness relative to neighbours",
            "dsm_mean": "height", "dsm_std": "height variability",
            "slope_mean": "slope",
            "dsm_rel_neighbors": "height relative to neighbours",
            "hag_mean": "height above ground",
        }
        return opisy.get(name, name)

    def train_model(self):
        try:
            features, labels = self._training_arrays()
        except ValueError as error:
            QMessageBox.information(self, "Not enough examples", str(error))
            return
        self.step(40, "Training Random Forest...")
        try:
            self.model = CLF.train(features, labels)
        except Exception as error:
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Training failed",
                                 str(error))
            return
        self.progress.setVisible(False)
        self.say("Trained on {0} objects in {1} classes, {2} features."
                 .format(len(labels), len(set(labels.tolist())),
                         features.shape[1]))
        duza, mala, stosunek = CLF.niezrownowazenie(labels)
        if stosunek >= 5.0 and duza and mala:
            self.say("Class \"{0}\" has {1} times more examples than \"{2}\". "
                     "Random Forest does not balance this; add examples to the "
                     "rarer class, otherwise it will keep losing the votes.".format(
                         duza, _liczba(stosunek, 0), mala))
        importance = CLF.feature_importance(self.model, self.feature_names)
        if importance:
            top = ", ".join("{0} ({1})".format(
                self._feature_label(name), _procent(value, 0))
                for name, value in importance[:4])
            self.say("The most important were: {0}.".format(top))
        else:
            self.say("Only the scikit-learn engine shows which features "
                     "mattered; installation instructions are in the Guide.")
        self.say("Now click \"MAKE MAP\".")
        self._update_buttons()

    def classify_all(self):
        if self._zajety("Map in progress"):
            return
        if self.model is None:
            QMessageBox.information(
                self, "Train first",
                "Before making a map, click \"Train\".")
            return
        if self.grid is None or self.labels is None:
            QMessageBox.information(
                self, "No segmentation",
                "Go back to step 1 and segment the image into objects.")
            return
        self._zablokuj_akcje(True)
        try:
            self._classify_all()
        except Exception as error:
            self.progress.setVisible(False)
            self.say("Stopped: {0}".format(error))
            QMessageBox.critical(
                self, "Could not make the map",
                "{0}\n\nTry training the classifier again (step 3).".format(error))
        finally:
            self._zablokuj_akcje(False)

    def _classify_all(self):
        self.step(50, "Assigning a class to each object...")
        predicted, confidence = CLF.predict(self.model, self.feature_matrix)

        values = {entry["name"]: entry["value"] for entry in self.classes}
        mapping = np.zeros(int(self.feature_ids.max()) + 1, dtype=np.int32)
        for identifier, name in zip(self.feature_ids, predicted):
            mapping[int(identifier)] = values.get(str(name), 0)
        self.classified = mapping[self.labels]
        self.classified[~self.grid.mask] = 0

        self.step(70, "Applying refinements...")
        self._apply_refinements()

        self.step(85, "Colouring the object layer...")
        self._write_map_to_layer(predicted)
        self._style_by_field("map_class")

        self.step(100, "Map ready.")
        self.progress.setVisible(False)

        total = float(np.count_nonzero(self.classified > 0))
        shares = []
        for entry in self.classes:
            count = float(np.count_nonzero(self.classified == entry["value"]))
            if count and total:
                area = count * (self.grid.pixel_size ** 2) / 10000.0
                shares.append("{0} {1:.1f}% ({2:.2f} ha)".format(
                    entry["name"], 100.0 * count / total, area))
        self.say("Map: " + ", ".join(shares))

        uncertain = int(np.count_nonzero(confidence < 0.5))
        if uncertain:
            self.say("{0} {1} got less than half of the votes; this is where "
                     "the plugin is least certain and where your examples will "
                     "help most.".format(
                         uncertain,
                         _odmiana(uncertain, "object", "objects",
                                  "objects")))
        self.say("Review the map and improve it in steps 2 and 3, then "
                 "check it in step 4.")
        self._update_buttons()

    def _apply_refinements(self):
        if self.chk_refine.isChecked() and len(self.classes) >= 2:
            green = self.cmb_green.currentText()
            other = self.cmb_other.currentText()
            values = {entry["name"]: entry["value"] for entry in self.classes}
            if green in values and other in values and green != other:
                mode = (REF.MODE_WHOLE if self.cmb_mode.currentIndex() == 0
                        else REF.MODE_PIXEL)
                self.classified, to_green, to_other = REF.refine_by_greenness(
                    self.classified, self.grid.array, self.labels,
                    values[green], values[other], self.spin_cutoff.value(),
                    self.spin_window.value(), mode)
                self.say("Greenness refinement: {0} pixels moved to class {1}, {2} "
                         "to {3}."
                         .format(to_green, green, to_other, other))

        if self.spin_mmu.value() > 0:
            before = self.classified.copy()
            self.classified = REF.sieve(self.classified,
                                        self.spin_mmu.value())
            moved = int(np.count_nonzero(before != self.classified))
            self.say("Cleaning small patches: {0} pixels moved to neighbouring "
                     "classes.".format(moved))

    def _write_map_to_layer(self, predicted):
        if self.segments_layer is None:
            return
        index = self.segments_layer.fields().indexOf("map_class")
        if index < 0:
            return
        by_segment = {int(identifier): str(name) for identifier, name
                      in zip(self.feature_ids, predicted)}
        changes = {}
        for feature in self.segments_layer.getFeatures():
            changes[feature.id()] = {
                index: by_segment.get(int(feature["segment_id"]))}
        if changes:
            self.segments_layer.dataProvider().changeAttributeValues(changes)
            self.segments_layer.triggerRepaint()

    def _cutoff_from_samples(self):
        if not self.training or self.grid is None:
            QMessageBox.information(
                self, "No examples",
                "First pick examples of both classes on the map.")
            return
        green = self.cmb_green.currentText()
        other = self.cmb_other.currentText()
        if green == other:
            QMessageBox.information(self, "Same class",
                                    "Choose two different classes.")
            return

        greenness = REF.excess_green(self.grid.array)
        green_values, other_values = [], []
        for segment, name in self.training.items():
            pixels = greenness[self.labels == segment]
            if name == green:
                green_values.append(pixels)
            elif name == other:
                other_values.append(pixels)
        if not green_values or not other_values:
            QMessageBox.information(
                self, "Not enough examples",
                "To compute the threshold I need examples of both selected "
                "classes.")
            return

        cutoff = REF.cutoff_from_samples(np.concatenate(green_values),
                                         np.concatenate(other_values))
        self.spin_cutoff.setValue(cutoff)
        self.say("Greenness threshold computed from examples: {0:.4f}."
                 .format(cutoff))

    def export_map(self):
        if self.classified is None or self.grid is None:
            QMessageBox.information(self, "No map yet",
                                    "First click \"MAKE MAP\".")
            return
        base = os.path.splitext(os.path.basename(
            self.grid.source_path or "map"))[0]
        suggestion = os.path.join(
            os.path.dirname(self.grid.source_path or ""),
            base + "_classification.tif")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save classification map", suggestion,
            "GeoTIFF (*.tif)")
        if not path:
            return
        if not path.lower().endswith((".tif", ".tiff")):
            path += ".tif"

        names = [entry["name"] for entry in self.classes]
        colours = [entry["colour"] for entry in self.classes]
        try:
            IO.write_classified_tif(path, self.classified, self.grid,
                                    names, colours)
        except Exception as error:
            QMessageBox.critical(
                self, "Saving failed",
                "{0}\n\nCheck that the file is not open in another program "
                "and that you have write permission in this folder."
                .format(error))
            return
        self.say("Map saved: {0}. A .qml style file sits next to it, so it "
                 "opens in colour for anyone else too."
                 .format(path))
        layer = IO.load_as_layer(path, base + "_classification")
        if layer is not None:
            QgsProject.instance().addMapLayer(layer)

    # ── krok 4: ocena dokładności ────────────────────────────────────

    def generate_points(self):
        if self._zajety("Point sampling in progress"):
            return
        if self.classified is None or self.grid is None:
            QMessageBox.information(
                self, "No map yet",
                "First make the map: points are drawn within its classes "
                "so that each class gets enough of them.")
            return

        training_mask = np.zeros(self.labels.shape, dtype=bool)
        if self.training:
            wanted = np.array(sorted(self.training.keys()), dtype=np.int64)
            training_mask = np.isin(self.labels, wanted)

        values = [entry["value"] for entry in self.classes]
        stratified = self.cmb_design.currentIndex() == 0

        self._zablokuj_akcje(True)
        try:
            self.step(30, "Drawing check points...")
            points, strata = self._losuj(stratified, values, training_mask)
        except Exception as error:
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Could not draw points",
                                 str(error))
            return
        finally:
            self._zablokuj_akcje(False)

        self.progress.setVisible(False)
        if len(points) == 0:
            QMessageBox.information(
                self, "No points",
                "No pixel is left to draw from. This happens when all "
                "objects have already been used as training examples.")
            return
        self._po_losowaniu(points, strata, stratified, training_mask)

    def _losuj(self, stratified, values, training_mask):
        if stratified:
            points, strata = ACC.stratified_points(
                self.classified, values, self.spin_min_class.value(),
                self.spin_points.value(), seed=42, exclude=training_mask)
        else:
            points = ACC.simple_random_points(
                self.grid.mask & (self.classified > 0),
                self.spin_points.value(), seed=42, exclude=training_mask)
            strata = (self.classified[points[:, 0], points[:, 1]]
                      if len(points) else np.empty(0, dtype=np.int64))
        return points, strata

    def _po_losowaniu(self, points, strata, stratified, training_mask):
        self.point_strata = strata
        # wagi powierzchniowe zapamiętujemy W CHWILI LOSOWANIA: warstwy
        # mają zostać przy próbie, nawet gdy mapa się potem zmieni
        self.stratum_pixels = {
            entry["value"]: float(np.count_nonzero(
                (self.classified == entry["value"]) & ~training_mask))
            for entry in self.classes}
        self._build_points_layer(points, strata)
        self.say("Drew {0} check {1}, design: {2}. Objects used for "
                 "training were skipped.".format(
                     len(points),
                     _odmiana(len(points), "point", "points", "points"),
                     "stratified" if stratified else "simple random"))
        self.say("Now turn off the map layer and label the points by "
                 "looking at the image alone.")
        self._update_buttons()

    def _build_points_layer(self, points, strata):
        from qgis.core import QgsFeature, QgsGeometry, QgsPointXY

        if self.points_layer is not None:
            with suppress(Exception):
                QgsProject.instance().removeMapLayer(self.points_layer.id())

        authid = self.grid.crs().authid() if self.grid.crs().isValid() else ""
        uri = "Point?crs={0}".format(authid) if authid else "Point"
        layer = QgsVectorLayer(uri, "GeoAI check points", "memory")
        provider = layer.dataProvider()
        provider.addAttributes([
            make_field("numer", "int"),
            make_field("ref_class", "string", 64),
            make_field("map_class", "string", 64),
            make_field("stratum", "string", 64),
        ])
        layer.updateFields()

        names = {entry["value"]: entry["name"] for entry in self.classes}
        x_values, y_values = self.grid.pixel_to_map(points[:, 0],
                                                    points[:, 1])
        features = []
        for index in range(len(points)):
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromPointXY(
                QgsPointXY(float(x_values[index]), float(y_values[index]))))
            mapped = int(self.classified[points[index, 0],
                                         points[index, 1]])
            feature.setAttributes([
                index + 1, None, names.get(mapped, ""),
                names.get(int(strata[index]), "")])
            features.append(feature)
        provider.addFeatures(features)
        layer.updateExtents()

        self._style_points(layer)
        QgsProject.instance().addMapLayer(layer)
        self.points_layer = layer

    def _style_points(self, layer):
        categories = []
        for entry in self.classes:
            symbol = QgsMarkerSymbol.createSimple({
                "name": "circle", "color": entry["colour"].name(),
                "outline_color": "#ffffff", "outline_width": "0.4",
                "size": "2.6"})
            categories.append(QgsRendererCategory(
                entry["name"], symbol, entry["name"]))
        unlabelled = QgsMarkerSymbol.createSimple({
            "name": "circle", "color": "#00000000",
            "outline_color": "#ffffff", "outline_width": "0.6",
            "size": "2.6"})
        categories.append(QgsRendererCategory(
            None, unlabelled, "not yet labelled"))
        with suppress(Exception):
            layer.setRenderer(QgsCategorizedSymbolRenderer(
                "ref_class", categories))

    def _toggle_point_tool(self, checked):
        if self._switching_tool:
            return
        if not checked:
            self._zdejmij_narzedzie()
            return
        if self.points_layer is None:
            self._odznacz(self.btn_label_points)
            QMessageBox.information(self, "No points",
                                    "First draw check points.")
            return
        if self.active_class() is None:
            self._odznacz(self.btn_label_points)
            QMessageBox.information(
                self, "No class",
                "Select in the list the class you want to assign to points.")
            return

        self._zdejmij_narzedzie()
        self._switching_tool = True
        try:
            self.btn_label_points.blockSignals(True)
            self.btn_label_points.setChecked(True)
            self.btn_label_points.blockSignals(False)
            self.active_tool = PointLabelTool(self.iface.mapCanvas(), self)
            self.iface.mapCanvas().setMapTool(self.active_tool)
        finally:
            self._switching_tool = False
        self.btn_label_points.setText("LABELLING: click to stop")
        self._ostrzez_o_widocznej_mapie()

    def on_point_labelled(self, feature_id):
        name = self.active_class()
        if name is None or self.points_layer is None:
            return
        self._set_point_class(feature_id, name)

    def on_point_cleared(self, feature_id):
        self._set_point_class(feature_id, None)

    def _set_point_class(self, feature_id, value):
        index = self.points_layer.fields().indexOf("ref_class")
        if index < 0:
            return
        self.points_layer.dataProvider().changeAttributeValues(
            {feature_id: {index: value}})
        self.points_layer.triggerRepaint()
        labelled = sum(1 for feature in self.points_layer.getFeatures()
                       if feature["ref_class"])
        total = self.points_layer.featureCount()
        self.step(100 * labelled / max(total, 1),
                  "{0} of {1} points labelled".format(labelled, total))

    def run_assessment(self):
        if self._zajety("Accuracy computation in progress"):
            return
        if self.points_layer is None or self.classified is None \
                or self.grid is None:
            QMessageBox.information(
                self, "Nothing to assess",
                "First make the map and draw check points.")
            return

        names = {entry["value"]: entry["name"] for entry in self.classes}
        values = [entry["value"] for entry in self.classes]
        by_name = {entry["name"]: entry["value"] for entry in self.classes}

        map_classes, reference_classes, strata = [], [], []
        unlabelled = 0
        for feature in self.points_layer.getFeatures():
            reference = feature["ref_class"]
            if not reference or reference not in by_name:
                unlabelled += 1
                continue
            geometry = feature.geometry().asPoint()
            row, col = self.grid.map_to_pixel(geometry.x(), geometry.y())
            height, width = self.classified.shape
            if not (0 <= row < height and 0 <= col < width):
                continue
            mapped = int(self.classified[row, col])
            if mapped <= 0:
                continue
            map_classes.append(mapped)
            reference_classes.append(by_name[reference])
            strata.append(by_name.get(feature["stratum"], mapped))

        if len(map_classes) < 2:
            QMessageBox.information(
                self, "Too few labelled points",
                "Label the check points before computing accuracy. Turn on "
                "\"LABEL POINTS ON THE MAP\", choose a class and click the "
                "points.")
            return
        if unlabelled:
            self.say("{0} {1} without a label were skipped.".format(
                unlabelled,
                _odmiana(unlabelled, "point", "points", "points")))

        stratified = self.cmb_design.currentIndex() == 0
        stratum_pixels = None
        if stratified:
            if not self.stratum_pixels:
                QMessageBox.information(
                    self, "No area weights",
                    "Draw the check points again: area weights are stored at "
                    "the moment of sampling.")
                return
            # wagi z chwili losowania, nie z bieżącej mapy: warstwy
            # muszą zostać przy próbie (Stehman 2014)
            stratum_pixels = [self.stratum_pixels.get(value, 0.0)
                              for value in values]
            map_classes = strata
            puste = [names[value] for value, piksele
                     in zip(values, stratum_pixels) if piksele <= 0]
            if puste:
                self.say("Classes with no area at the time of sampling: {0}."
                         .format(", ".join(puste)))

        report = ACC.assess(
            map_classes, reference_classes, values, names,
            stratum_pixels=stratum_pixels,
            pixel_area=self.grid.pixel_size ** 2,
            design=(ACC.DESIGN_STRATIFIED if stratified
                    else ACC.DESIGN_SIMPLE))
        self.progress.setVisible(False)
        report["classes_without_points"] = [
            names[value] for value, liczba
            in zip(values, report["matrix"].sum(axis=1)) if liczba == 0]
        self._show_assessment(report)

    def _show_assessment(self, report):
        names = report["class_names"]
        matrix = report["matrix"]
        counts = report["counts"]
        weighted = report.get("weighted")

        lines = [
            "<h3>Map accuracy assessment</h3>",
            "<p>Rows show what the map says, columns show what ",
            "is visible in the image. The highlighted diagonal holds the ",
            "agreements.</p>",
            "<table cellpadding='4' border='1' ",
            "style='border-collapse:collapse'>",
            "<tr><th>map \\ image</th>"]
        lines.extend("<th>{0}</th>".format(name) for name in names)
        lines.append("<th>total</th><th>user's<br>accuracy</th></tr>")

        for index, name in enumerate(names):
            lines.append("<tr><th>{0}</th>".format(name))
            for column in range(len(names)):
                cell = int(matrix[index, column])
                style = (" style='background:#e8f8fc;font-weight:bold'"
                         if index == column else "")
                lines.append("<td align='right'{0}>{1}</td>".format(
                    style, cell))
            users = (weighted["users"][index] if weighted is not None
                     else counts["users"][index])
            lines.append("<td align='right'>{0}</td>".format(
                int(matrix[index].sum())))
            lines.append("<td align='right'>{0}</td></tr>".format(
                "n/a" if not np.isfinite(users) else _procent(users, 0)))

        lines.append("<tr><th>total</th>")
        for column in range(len(names)):
            lines.append("<td align='right'>{0}</td>".format(
                int(matrix[:, column].sum())))
        lines.append("<td align='right'>{0}</td><td></td></tr>".format(
            int(matrix.sum())))

        producers = (weighted["producers"] if weighted is not None
                     else counts["producers"])
        lines.append("<tr><th>producer's accuracy</th>")
        for value in producers:
            lines.append("<td align='right'>{0}</td>".format(
                "n/a" if not np.isfinite(value) else _procent(value, 0)))
        lines.append("<td></td><td></td></tr></table>")

        lines.append(
            "<p style='color:#607d8b'><b>User's accuracy</b>: when the "
            "map says \"grass\", how often it really is grass. "
            "<b>Producer's accuracy</b>: how much of the real grass "
            "the map found.</p>")

        bez_punktow = report.get("classes_without_points") or []
        if bez_punktow and weighted is not None:
            udzial = float(np.sum(weighted["proportions"]))
            lines.append(
                "<p style='background:#fff3cd;padding:8px;border:1px solid "
                "#e0a030'><b>Note:</b> classes <b>{0}</b> have no labelled "
                "point at all, so they dropped out of the estimate. Area "
                "shares add up to {1} instead of 100%, and overall "
                "accuracy is underestimated. Label points of these classes "
                "or remove them from the list before you cite these "
                "figures.</p>".format(", ".join(bez_punktow),
                                     _procent(udzial)))

        if weighted is not None:
            lines.append(
                "<p><b>Overall accuracy: {0:.0f}%, plus or minus {1:.0f} "
                "percentage points</b> (area-weighted); counting the "
                "points alone would give {2:.0f}%. The difference arises "
                "because sampling gives each class a similar number of "
                "points, while the weighted figure counts each class by "
                "the area it covers.</p>"
                .format(weighted["overall"] * 100,
                        weighted["overall_ci"] * 100,
                        counts["overall"] * 100))
            lines.append(
                "<h4>Class areas</h4><table cellpadding='4' border='1' "
                "style='border-collapse:collapse'><tr><th>Class</th><th>Mapped "
                "(ha)</th><th>Estimated (ha)</th><th>Uncertainty "
                "(ha)</th></tr>")
            for index, name in enumerate(names):
                lines.append(
                    "<tr><td>{0}</td><td align='right'>{1:.3f}</td>"
                    "<td align='right'>{2:.3f}</td>"
                    "<td align='right'>± {3:.3f}</td></tr>".format(
                        name, weighted["mapped_area"][index] / 10000.0,
                        weighted["estimated_area"][index] / 10000.0,
                        weighted["estimated_area_ci"][index] / 10000.0))
            lines.append("</table>")
            lines.append(
                "<p style='color:#607d8b'>If you report areas in hectares, "
                "cite the <b>estimated</b> area with its uncertainty, not "
                "the mapped one: the estimate corrects the map for the "
                "errors found by the sample (Olofsson et al., 2014).</p>")
        else:
            lines.append(
                "<p><b>Overall accuracy: {0:.0f}%</b> from {1} points.</p>".format(counts["overall"] * 100,
                                      counts["n"]))

        lines.append(
            "<p style='color:#607d8b'>Points labelled from the air are "
            "high-quality reference data, but they are not the same as "
            "field measurements. The kappa coefficient is deliberately "
            "not computed: current recommendations advise against "
            "it.</p>")

        self._show_html("Accuracy assessment", "".join(lines), 700, 560,
                        save=report)

    def _show_html(self, title, html, width, height, save=None):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(width, height)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser(dialog)
        browser.setOpenExternalLinks(True)
        browser.setHtml(html)
        if save is not None:
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save
                | QDialogButtonBox.StandardButton.Close)
            buttons.accepted.connect(lambda: self._save_report(save))
        else:
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(browser, 1)
        layout.addWidget(buttons)
        dialog.exec()

    def _save_report(self, report):
        import csv
        path, _ = QFileDialog.getSaveFileName(
            self, "Save accuracy report", "accuracy_report.csv",
            "CSV file (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle, delimiter=";")
            for row in ACC.report_rows(report):
                writer.writerow(row)
            weighted = report.get("weighted")
            if weighted is not None:
                writer.writerow([])
                writer.writerow(["overall accuracy, area-weighted",
                                 round(float(weighted["overall"]), 4),
                                 "95% interval",
                                 round(float(weighted["overall_ci"]), 4)])
                writer.writerow(["class", "mapped area (ha)",
                                 "estimated area (ha)",
                                 "uncertainty (ha)"])
                for index, name in enumerate(report["class_names"]):
                    writer.writerow([
                        name,
                        round(float(weighted["mapped_area"][index]) / 1e4, 4),
                        round(float(weighted["estimated_area"][index])
                              / 1e4, 4),
                        round(float(weighted["estimated_area_ci"][index])
                              / 1e4, 4)])
        self.say("Report saved: {0}.".format(path))

    # ── reszta ───────────────────────────────────────────────────────

    def _update_buttons(self):
        has_objects = self.labels is not None
        has_samples = bool(self.training)
        self.btn_collect.setEnabled(has_objects and bool(self.classes))
        self.btn_separability.setEnabled(has_samples)
        self.btn_train.setEnabled(has_samples)
        self.btn_classify.setEnabled(self.model is not None)
        self.btn_export.setEnabled(self.classified is not None)
        self.btn_points.setEnabled(self.classified is not None)
        self.btn_label_points.setEnabled(self.points_layer is not None)
        self.btn_assess.setEnabled(self.points_layer is not None)

    def _show_guide(self):
        self._show_html("GeoAI Classification: guide",
                        GUIDE_HTML.replace("__INSTALL__",
                                           INSTALL_HINT.replace("\n", "<br>")),
                        660, 600)

    def closeEvent(self, event):
        if self.active_tool is not None:
            with suppress(Exception):
                self.iface.mapCanvas().unsetMapTool(self.active_tool)
        super().closeEvent(event)


GUIDE_HTML = """
<h2>How it works</h2>
<p>The plugin makes a land cover map from a drone image or an aerial
photo. It does not look at single pixels. First it cuts the image into
<b>objects</b> (pieces of a field, a roof, a tree crown), and then it
learns from you what is what.</p>
<p>Why objects and not pixels? A single pixel tells you only its colour.
An object also has texture, shape, height and surroundings, and the map
does not come out littered with single specks.</p>

<h3>What you need</h3>
<ul>
  <li><b>An RGB image</b>: a drone orthomosaic, an aerial photo or a
  satellite scene. Three bands are enough: red, green and blue.</li>
  <li><b>An elevation model (DSM)</b>: optional, but very helpful.
  Without it the plugin measures 19 features, with it 24, including
  height above ground. That is what tells a roof from asphalt and a tree
  from a lawn.</li>
</ul>
<p>Ordinary drone cameras do not record near infrared, so there is no
NDVI here. It is replaced by visible-band indices (ExG greenness, VARI,
NGRDI), texture, shape and height.</p>

<h3>Step 1: segmentation</h3>
<p>The most important field is <b>Object size</b>. There is one rule:
an object must be smaller than the narrowest thing you want to show on
the map. For fields and roofs 5-20 m&sup2; works well; for single trees
2-5 m&sup2;.</p>
<p>After segmentation, look at the result on the map and check two
things: that no object lies on two different kinds of land at once
(that is a problem, so make the objects smaller), and that a uniform
meadow has not broken into hundreds of specks (that is only an
inconvenience).</p>
<p>On a large image, first tick "Process only what is visible on
screen" and choose the object size on a small part.</p>

<h3>Step 2: classes and examples</h3>
<p>Add the classes you want to distinguish, then click the objects on
the map that belong to them. Three things decide the result:</p>
<ul>
  <li><b>Spread examples over the whole image.</b> Light and shadow
  change from place to place.</li>
  <li><b>Show every variant of a class.</b> "Bare soil" is freshly
  ploughed land, a trodden path and a dry embankment.</li>
  <li><b>Pick only what you recognise without hesitation.</b> One wrong
  example teaches the plugin a wrong rule. Leave out objects that lie on
  the border of two classes.</li>
</ul>
<p>10-20 examples per class are enough to start. You will add more
anyway.</p>

<h3>Step 3: training and map</h3>
<p>Before you start, click <b>"Can the classes be told apart?"</b>.
If a pair scores poorly, there is no point in more work: either add
examples or merge those classes.</p>
<p><b>Correcting the map is not a failure, it is the method.</b> The
first map is never good. Look over all of it, write down the kinds of
errors, add a few examples of each kind in different places and repeat.
Two or three rounds bring the most.</p>
<p><b>Greenness refinement</b> helps when you map fields: a strip of
grass between plots is often narrower than an object and gets lost.
This option hands the decision to single pixels, but only for the two
selected classes. Note: recovered strips come out slightly wider than
in reality, so be careful when reporting their area.</p>

<h3>Step 4: how good is this map</h3>
<p>Here the plugin does something QGIS lacks: it computes accuracy the
way reviewers and good practice require.</p>
<ol>
  <li>It draws check points, never on objects used for training.</li>
  <li>You label each point by looking at <i>the image alone</i>.
  <b>Turn off the classification map layer</b> before you start;
  otherwise the plugin's answer influences your judgement and the result
  is inflated.</li>
  <li>You get the error matrix, user's and producer's accuracy for each
  class, and overall accuracy.</li>
</ol>
<p>With stratified sampling, small classes get proportionally many
points, so the share of points is not the share of area. That is why
the plugin also reports <b>area-weighted</b> figures and estimated class
areas with confidence intervals. Cite those in a publication.</p>

<h3>What stays in the project</h3>
<ul>
  <li><b>GeoAI objects</b>: a polygon layer; its attribute table holds
  all measured features of each object, the column
  <code>train_class</code> (your examples) and <code>map_class</code>
  (the result).</li>
  <li><b>GeoAI check points</b>: points with the label from the image,
  the class from the map and the sampling stratum.</li>
  <li>A saved <b>GeoTIFF</b> with a .qml style file next to it.</li>
</ul>

<h3>Faster and more accurate</h3>
<p>__INSTALL__</p>

<h3>Where the method comes from</h3>
<p>SLIC segmentation (Achanta et al., 2012), GLCM texture (Haralick
et al., 1973), ExG greenness (Woebbecke et al., 1995), Random Forest
(Breiman, 2001; Belgiu and Drăguţ, 2016), class separability with the
Jeffries-Matusita distance, and accuracy assessment following Congalton
and Green, Olofsson et al. (2014) and Stehman (2014).</p>

"""
