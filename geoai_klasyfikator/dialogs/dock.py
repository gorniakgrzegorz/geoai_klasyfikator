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
from ..core.compat import liczba, lokalizacja_liczb, make_field
from ..core.deps import (HAS_SKIMAGE, INSTALL_HINT, engine_report,
                         missing_packages)
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


# Bez scikit-image wbudowany SLIC jest praktyczny do ok. pół miliona
# pikseli (tak też podaje strona programu); powyżej pytamy przed startem.
PROG_BEZ_SKIMAGE = 500_000


def _liczba(wartosc, miejsca=2):
    """Liczba z przecinkiem dziesiętnym, jak się pisze po polsku."""
    return liczba(wartosc, miejsca)


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
    return _liczba(udzial * 100.0, miejsca) + " proc."


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
        super().__init__("GeoAI Klasyfikator", parent)
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
        # pola liczbowe przyjmują i pokazują przecinek dziesiętny
        for pole in self.findChildren(QDoubleSpinBox) + self.findChildren(QSpinBox):
            pole.setLocale(lokalizacja_liczb())
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


        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(92)
        self.log.setPlaceholderText(
            "Tu na bieżąco widać, co wtyczka robi.")
        layout.addWidget(self.log)

        signature = QLabel(
            '<a href="mailto:gorniakgrzegorz@gmail.com" '
            'style="color:#000000; text-decoration:none;">'
            '&#169; Grzegorz G&#243;rniak</a>')
        signature.setObjectName("signature")
        signature.setOpenExternalLinks(True)
        signature.setCursor(Qt.CursorShape.PointingHandCursor)
        signature.setToolTip("Masz pytanie albo pomysł? Napisz do mnie.")
        layout.addWidget(signature, 0, Qt.AlignmentFlag.AlignRight)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(inner)
        # pasek postępu poza przewijanym obszarem: widać go zawsze,
        # niezależnie od tego, który krok jest akurat na ekranie
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        calosc = QWidget()
        uklad = QVBoxLayout(calosc)
        uklad.setContentsMargins(0, 0, 0, 4)
        uklad.setSpacing(4)
        uklad.addWidget(scroll, 1)
        uklad.addWidget(self.progress)
        self.setWidget(calosc)

    def _header(self):
        header = QWidget()
        header.setObjectName("header")
        row = QHBoxLayout(header)
        row.setContentsMargins(9, 6, 9, 6)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("GeoAI Klasyfikator")
        title.setObjectName("title")
        subtitle = QLabel("Pokrycie terenu ze zdjęć z drona "
                          "i zdjęć lotniczych")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        titles.addWidget(title)
        titles.addWidget(subtitle)

        guide = QPushButton("Instrukcja")
        guide.setObjectName("guide")
        guide.clicked.connect(self._show_guide)
        row.addLayout(titles, 1)
        row.addWidget(guide, 0, Qt.AlignmentFlag.AlignTop)
        return header

    def _step_image(self):
        box = QGroupBox("Krok 1 · Zdjęcie i podział na obiekty")
        form = QFormLayout(box)
        form.setContentsMargins(8, 12, 8, 8)
        form.setSpacing(4)

        intro = QLabel(
            "Wtyczka nie klasyfikuje pojedynczych pikseli, tylko całe "
            "fragmenty zdjęcia — kawałki pola, dachu czy korony drzewa. "
            "Najpierw trzeba je wyciąć.")
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        form.addRow(intro)

        self.cmb_image = QgsMapLayerComboBox()
        self.cmb_image.setFilters(QgsMapLayerProxyModel.Filter.RasterLayer)
        self.cmb_image.layerChanged.connect(self._on_image_changed)
        form.addRow("Zdjęcie (RGB):", self.cmb_image)

        self.cmb_dsm = QgsMapLayerComboBox()
        self.cmb_dsm.setFilters(QgsMapLayerProxyModel.Filter.RasterLayer)
        self.cmb_dsm.setAllowEmptyLayer(True)
        self.cmb_dsm.setCurrentIndex(0)
        self.cmb_dsm.setToolTip(
            "Model pokrycia terenu (NMPT) z tego samego nalotu. "
            "Nie jest konieczny, ale bardzo pomaga: dzięki niemu "
            "wtyczka odróżni dach od asfaltu, a drzewo od trawnika.")
        form.addRow("Model wysokości (opcjonalnie):", self.cmb_dsm)

        self.spin_resolution = QDoubleSpinBox()
        self.spin_resolution.setDecimals(3)
        self.spin_resolution.setRange(0.0, 100.0)
        self.spin_resolution.setSingleStep(0.01)
        self.spin_resolution.setSpecialValueText("jak w pliku")
        self.spin_resolution.setToolTip(
            "W jakiej rozdzielczości liczymy (w jednostkach mapy, "
            "zwykle w metrach). Dla zdjęć z drona zwykle 0,05 m. "
            "Zostaw „jak w pliku”, jeśli nie wiesz.")
        form.addRow("Rozdzielczość robocza (m):", self.spin_resolution)

        self.spin_object_size = QDoubleSpinBox()
        self.spin_object_size.setRange(0.5, 10000.0)
        self.spin_object_size.setValue(10.0)
        self.spin_object_size.setDecimals(1)
        self.spin_object_size.setToolTip(
            "Jak duży ma być jeden obiekt w terenie. Zasada: obiekt "
            "musi być mniejszy niż najwęższa rzecz, którą chcesz "
            "pokazać na mapie. Dla pól i dachów 5-20 m², dla "
            "pojedynczych drzew 2-5 m².")
        self.spin_object_size.valueChanged.connect(self._sync_segments)
        form.addRow("Wielkość obiektu (m²):", self.spin_object_size)

        self.spin_segments = QSpinBox()
        self.spin_segments.setRange(100, 2000000)
        self.spin_segments.setValue(10000)
        self.spin_segments.setGroupSeparatorShown(True)
        self.spin_segments.setToolTip(
            "To samo, tylko wyrażone liczbą obiektów. Zmieniasz jedno, "
            "drugie przelicza się samo.")
        self.spin_segments.valueChanged.connect(self._on_segments_edited)
        form.addRow("albo liczba obiektów:", self.spin_segments)

        self.chk_advanced = QCheckBox("Pokaż ustawienia zaawansowane")
        self.chk_advanced.toggled.connect(self._toggle_advanced)
        form.addRow(self.chk_advanced)

        self.spin_compactness = QDoubleSpinBox()
        self.spin_compactness.setRange(0.01, 1.0)
        self.spin_compactness.setSingleStep(0.01)
        self.spin_compactness.setDecimals(2)
        self.spin_compactness.setValue(DEFAULT_COMPACTNESS)
        self.spin_compactness.setToolTip(
            "Niska wartość — obiekty wiernie trzymają się granic "
            "kolorów. Wysoka — wychodzą regularne, prawie kwadratowe. "
            "Zostaw 0,15.")
        self.lbl_compactness = QLabel("Zwartość obiektów:")
        form.addRow(self.lbl_compactness, self.spin_compactness)

        self.spin_sigma = QDoubleSpinBox()
        self.spin_sigma.setRange(0.0, 10.0)
        self.spin_sigma.setSingleStep(0.5)
        self.spin_sigma.setValue(DEFAULT_SIGMA)
        self.spin_sigma.setToolTip(
            "Lekkie rozmycie przed podziałem, żeby szum i drobna "
            "faktura nie tworzyły sztucznych obiektów. Zostaw 2,5.")
        self.lbl_sigma = QLabel("Wygładzenie:")
        form.addRow(self.lbl_sigma, self.spin_sigma)

        self.chk_extent = QCheckBox("Policz tylko to, co widać na ekranie")
        self.chk_extent.setToolTip(
            "Szybka próba na fragmencie zdjęcia. Przydaje się na "
            "słabszym komputerze i wtedy, gdy dobierasz wielkość "
            "obiektu.")
        form.addRow(self.chk_extent)

        self.lbl_engine = QLabel("")
        self.lbl_engine.setObjectName("engine")
        self.lbl_engine.setWordWrap(True)
        form.addRow(self.lbl_engine)
        self._describe_engines()

        self.btn_segment = QPushButton("PODZIEL NA OBIEKTY I ZMIERZ")
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
        box = QGroupBox("Krok 2 · Klasy i przykłady")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)

        intro = QLabel(
            "Wypisz klasy, które chcesz rozróżniać (np. zabudowa, "
            "droga, trawa, las, woda, grunt odkryty), a potem pokaż "
            "wtyczce po kilka przykładów każdej z nich.")
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list_classes = QListWidget()
        self.list_classes.setMaximumHeight(130)
        self.list_classes.setToolTip(
            "Kliknij klasę, żeby stała się aktywna. Dwuklik zmienia "
            "jej kolor.")
        self.list_classes.itemDoubleClicked.connect(self._edit_class)
        layout.addWidget(self.list_classes)

        row = QHBoxLayout()
        row.setSpacing(4)
        for text, slot in (("Dodaj klasę", self._add_class),
                           ("Usuń klasę", self._remove_class),
                           ("Wyczyść przykłady", self._clear_class_samples)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            row.addWidget(button)
        layout.addLayout(row)

        self.btn_collect = QPushButton("WSKAZUJ PRZYKŁADY NA MAPIE")
        self.btn_collect.setObjectName("action")
        self.btn_collect.setCheckable(True)
        self.btn_collect.toggled.connect(self._toggle_collect)
        layout.addWidget(self.btn_collect)

        hint = QLabel(
            "Wybierz klasę, a potem klikaj na mapie obiekty, które do "
            "niej należą. Kliknięcie drugi raz usuwa obiekt z klasy. "
            "Z wciśniętym <b>Ctrl</b> możesz malować, przeciągając "
            "myszą.<br><br>Dwie rady, które robią największą różnicę: "
            "rozrzucaj przykłady po całym zdjęciu, a nie w jednym "
            "rogu, i pokaż <i>każdą odmianę</i> klasy — i bujną trawę, "
            "i tę przyschniętą. Wskazuj tylko to, co rozpoznajesz bez wahania.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return box

    def _step_classify(self):
        box = QGroupBox("Krok 3 · Nauka i mapa")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)

        intro = QLabel(
            "Teraz wtyczka uczy się z Twoich przykładów i nadaje klasę "
            "każdemu obiektowi na zdjęciu.")
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.btn_separability = QPushButton("Czy klasy da się rozróżnić?")
        self.btn_separability.setToolTip(
            "Sprawdza, zanim zaczniesz, czy Twoje klasy w ogóle różnią "
            "się na tyle, by je rozdzielić — i które cechy je dzielą.")
        self.btn_separability.clicked.connect(self.check_separability)
        self.btn_train = QPushButton("Naucz")
        self.btn_train.setToolTip(
            "Uczy Random Forest na wskazanych przykładach. Trwa sekundy, "
            "możesz powtarzać do skutku.")
        self.btn_train.clicked.connect(self.train_model)
        row.addWidget(self.btn_separability, 1)
        row.addWidget(self.btn_train)
        layout.addLayout(row)

        self.btn_classify = QPushButton("ZRÓB MAPĘ")
        self.btn_classify.setObjectName("action")
        self.btn_classify.clicked.connect(self.classify_all)
        layout.addWidget(self.btn_classify)

        loop = QLabel(
            "Po pierwszej mapie przejrzyj ją całą i wypisz sobie "
            "<i>rodzaje</i> pomyłek („sucha trawa brana za grunt”). "
            "Dodaj po kilka przykładów każdego rodzaju w różnych "
            "miejscach i kliknij Naucz oraz Zrób mapę jeszcze raz. "
            "Pierwsze dwie, trzy rundy poprawiają najwięcej.")
        loop.setObjectName("hint")
        loop.setWordWrap(True)
        layout.addWidget(loop)

        refine_box = QGroupBox("Dociąganie wąskich pasów (opcjonalnie)")
        refine_form = QFormLayout(refine_box)
        refine_form.setContentsMargins(6, 10, 6, 6)
        refine_form.setSpacing(3)

        self.chk_refine = QCheckBox("Włącz dociąganie po zieloności")
        self.chk_refine.setToolTip(
            "Obiekty nadal decydują, co to za teren, ale dla dwóch "
            "wybranych klas o każdym pikselu rozstrzyga jego zieloność. "
            "Dzięki temu odzyskasz pas trawy węższy niż obiekt — "
            "miedzę między zagonami albo trawę przy rowie.")
        refine_form.addRow(self.chk_refine)

        self.cmb_green = QComboBox()
        self.cmb_other = QComboBox()
        refine_form.addRow("Klasa zielona:", self.cmb_green)
        refine_form.addRow("Klasa druga:", self.cmb_other)

        cutoff_row = QHBoxLayout()
        self.spin_cutoff = QDoubleSpinBox()
        self.spin_cutoff.setRange(-2.0, 2.0)
        self.spin_cutoff.setDecimals(4)
        self.spin_cutoff.setSingleStep(0.01)
        btn_cutoff = QPushButton("Wylicz z przykładów")
        btn_cutoff.clicked.connect(self._cutoff_from_samples)
        cutoff_row.addWidget(self.spin_cutoff, 1)
        cutoff_row.addWidget(btn_cutoff)
        refine_form.addRow("Próg zieloności:", cutoff_row)

        self.spin_window = QSpinBox()
        self.spin_window.setRange(1, 15)
        self.spin_window.setValue(REF.DEFAULT_WINDOW)
        self.spin_window.setSingleStep(2)
        self.spin_window.setToolTip(
            "Zieloność uśredniamy w małym kwadracie, żeby pojedyncze "
            "piksele nie migotały. Mniejsze okno wierniej trzyma się "
            "cienkich pasów, ale bywa niespokojne.")
        refine_form.addRow("Okno uśredniania (piksele):", self.spin_window)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Zachowaj zielone obiekty w całości",
                                "Każdy piksel osobno, w obie strony"])
        self.cmb_mode.setToolTip(
            "Pierwszy sposób nie dziurawi trawy łysinami i jest "
            "bezpieczniejszy. Drugi daje ostrzejsze krawędzie.")
        refine_form.addRow("Sposób:", self.cmb_mode)
        layout.addWidget(refine_box)

        mmu_row = QHBoxLayout()
        mmu_row.addWidget(QLabel("Najmniejszy płat:"))
        self.spin_mmu = QSpinBox()
        self.spin_mmu.setRange(0, 200000)
        self.spin_mmu.setSuffix(" px")
        self.spin_mmu.setToolTip(
            "Płaty jednej klasy mniejsze niż to zostaną wchłonięte "
            "przez otoczenie — mapa przestaje być usiana "
            "pojedynczymi drobinami („sól z pieprzem”). Ustaw to "
            "pod zastosowanie mapy, a nie po to, żeby podbić wynik "
            "dokładności. Zero oznacza brak czyszczenia.")
        self.lbl_mmu = QLabel("")
        self.lbl_mmu.setObjectName("hint")
        self.spin_mmu.valueChanged.connect(self._update_mmu_label)
        mmu_row.addWidget(self.spin_mmu)
        mmu_row.addWidget(self.lbl_mmu, 1)
        layout.addLayout(mmu_row)

        self.btn_export = QPushButton("Zapisz mapę do pliku GeoTIFF")
        self.btn_export.clicked.connect(self.export_map)
        layout.addWidget(self.btn_export)
        return box

    def _step_accuracy(self):
        box = QGroupBox("Krok 4 · Ile ta mapa jest warta")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)

        intro = QLabel(
            "Mapa jest tyle warta, ile wiesz o jej błędach. Wtyczka "
            "losuje punkty kontrolne, Ty opisujesz je patrząc na samo "
            "zdjęcie, a na końcu dostajesz liczby, które można "
            "zacytować w opracowaniu.")
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setSpacing(4)

        self.cmb_design = QComboBox()
        self.cmb_design.addItems(["Warstwowy, wg klas mapy (zalecany)",
                                  "Prosty losowy"])
        self.cmb_design.setToolTip(
            "Warstwowy daje każdej klasie, nawet najmniejszej, dość "
            "punktów, żeby dało się o niej cokolwiek powiedzieć. "
            "Prosty losowy rozsypuje punkty równomiernie i rzadkie "
            "klasy dostają ich za mało.")
        form.addRow("Sposób losowania:", self.cmb_design)

        self.spin_min_class = QSpinBox()
        self.spin_min_class.setRange(1, 1000)
        self.spin_min_class.setValue(50)
        self.spin_min_class.setToolTip(
            "Poniżej 30 punktów na klasę wyniki dla niej będą bardzo "
            "niepewne.")
        form.addRow("Minimum punktów na klasę:", self.spin_min_class)

        self.spin_points = QSpinBox()
        self.spin_points.setRange(1, 20000)
        self.spin_points.setValue(200)
        form.addRow("Łącznie punktów:", self.spin_points)
        layout.addLayout(form)

        self.btn_points = QPushButton("Wylosuj punkty kontrolne")
        self.btn_points.clicked.connect(self.generate_points)
        layout.addWidget(self.btn_points)

        self.btn_label_points = QPushButton("OPISUJ PUNKTY NA MAPIE")
        self.btn_label_points.setObjectName("action")
        self.btn_label_points.setCheckable(True)
        self.btn_label_points.toggled.connect(self._toggle_point_tool)
        layout.addWidget(self.btn_label_points)

        hint = QLabel(
            "Wyłącz warstwę z mapą klasyfikacji i opisuj punkty "
            "patrząc na samo zdjęcie — inaczej podpowiedź wtyczki "
            "wpłynie na Twoją ocenę. Wybierz klasę i kliknij punkt; "
            "prawy przycisk czyści opis. Jeśli naprawdę nie wiesz, co "
            "jest w danym miejscu, lepiej ten punkt skasować w tabeli "
            "atrybutów niż zgadywać.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.btn_assess = QPushButton("POLICZ DOKŁADNOŚĆ")
        self.btn_assess.setObjectName("action")
        self.btn_assess.clicked.connect(self.run_assessment)
        layout.addWidget(self.btn_assess)
        return box

    # ── drobiazgi ────────────────────────────────────────────────────

    def _describe_engines(self):
        report = engine_report()
        missing = missing_packages()
        if report["exact"]:
            text = ("Silniki: {0}; {1}. Wyniki zgodne z implementacją "
                    "wzorcową.").format(report["segmentation"],
                                        report["classifier"])
        else:
            text = ("Silniki wbudowane we wtyczkę. Działa bez niczego "
                    "więcej; jeśli doinstalujesz {0}, będzie szybciej "
                    "i dokładniej — przepis jest w Instrukcji."
                    ).format(" oraz ".join(missing))
        self.lbl_engine.setText(text)

    def _zajety(self, czynnosc="Trwa inne obliczenie"):
        """True, gdy coś już się liczy — chroni przed drugim przebiegiem.

        Paski postępu wołają processEvents(), więc użytkownik może w
        trakcie kliknąć przycisk jeszcze raz. Bez tej blokady drugi
        przebieg podmieniłby dane w środku pierwszego.
        """
        if self._busy:
            QMessageBox.information(
                self, "Chwileczkę",
                "{0}. Poczekaj, aż pasek postępu dojdzie do końca."
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
            "to jest {0} m²".format(_liczba(area, 1)))

    def _on_image_changed(self, layer):
        """Nowe zdjęcie oznacza nową sesję — stary stan przestaje pasować."""
        if self.labels is not None:
            self.say("Zmieniono zdjęcie — poprzedni podział, przykłady "
                     "i mapa przestały pasować i zostały wyczyszczone.")
        self._wyczysc_sesje()
        if layer is None:
            self._update_buttons()
            return
        with suppress(Exception):
            size = IO.native_pixel_size(IO._layer_path(layer))
            self.spin_resolution.setMinimum(0.0)
            self.spin_resolution.setToolTip(
                "Ten plik ma {0} m na piksel. Rozdzielczość robocza nie "
                "może być od niej drobniejsza — wpisanie mniejszej "
                "liczby tylko rozdmucha obraz."
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
        self.btn_collect.setText("WSKAZUJ PRZYKŁADY NA MAPIE")
        self.btn_label_points.setText("OPISUJ PUNKTY NA MAPIE")

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
                self, "Brak zdjęcia",
                "Wskaż zdjęcie, na którym mamy pracować. Jeśli nie ma "
                "go na liście, wczytaj je najpierw do projektu QGIS.")
            return

        extent = None
        if self.chk_extent.isChecked():
            extent = self._zasieg_kanwy_w_ukladzie_zdjecia(layer)
            if extent is None:
                return

        if self._zajety("Trwa podział na obiekty"):
            return

        self.log.clear()
        self._zablokuj_akcje(True)
        try:
            self.step(5, "Wczytuję zdjęcie...")
            zadana = self.spin_resolution.value()
            wlasna = getattr(self, "_native_pixel", 0.0)
            if zadana > 0 and wlasna > 0 and zadana < wlasna * 0.999:
                odpowiedz = QMessageBox.question(
                    self, "Rozdzielczość drobniejsza niż plik",
                    "Prosisz o {0} m na piksel, a zdjęcie ma {1} m. "
                    "Zdjęcie zostanie tylko rozdmuchane — liczenie "
                    "potrwa wielokrotnie dłużej, a szczegółów nie "
                    "przybędzie.\n\nUżyć rozdzielczości pliku ({1} m)?"
                    .format(_liczba(zadana, 4), _liczba(wlasna, 4)))
                if odpowiedz == QMessageBox.StandardButton.Yes:
                    zadana = 0.0
                    self.spin_resolution.setValue(0.0)
            siatka = IO.read_rgb(layer, zadana, extent)
            height, width = siatka.shape
            if not HAS_SKIMAGE and height * width > PROG_BEZ_SKIMAGE:
                obecna = siatka.pixel_size
                proponowana = obecna * np.sqrt(
                    height * width / PROG_BEZ_SKIMAGE)
                proponowana = np.ceil(proponowana * 100) / 100
                odpowiedz = QMessageBox.question(
                    self, "To może potrwać bardzo długo",
                    "Siatka robocza ma {0} mln pikseli, a biblioteka "
                    "scikit-image nie jest zainstalowana. Wbudowany "
                    "podział na obiekty radzi sobie sprawnie do około "
                    "pół miliona pikseli; przy większej siatce liczy "
                    "bardzo długo. Postęp widać na pasku na dole panelu, "
                    "a QGIS może w tym czasie reagować z opóźnieniem."
                    "\n\nSzybciej: ustaw rozdzielczość roboczą "
                    "co najmniej {1} m albo zainstaluj scikit-image "
                    "(przepis jest w Instrukcji).\n\nLiczyć mimo to?"
                    .format(_liczba(height * width / 1e6, 1),
                            _liczba(proponowana, 2)))
                if odpowiedz != QMessageBox.StandardButton.Yes:
                    self.progress.setVisible(False)
                    self.say("Przerwane przed podziałem: siatka za duża "
                             "dla wbudowanego podziału.")
                    return
            self.grid = siatka
            self.say("Siatka robocza: {0} na {1} pikseli, rozdzielczość "
                     "{2} m. Powierzchnia: {3} ha."
                     .format(width, height, _liczba(self.grid.pixel_size, 4),
                             _liczba(self._area_of_scene() / 10000.0, 2)))

            dsm = None
            dsm_layer = self.cmb_dsm.currentLayer()
            if dsm_layer is not None:
                self.step(15, "Wczytuję model wysokości...")
                ostrzezenia_dsm = []
                dsm = IO.read_dsm_like(dsm_layer, self.grid,
                                       ostrzezenia_dsm)
                for uwaga in ostrzezenia_dsm:
                    self.say("Uwaga: " + uwaga)
                self.say("Model wysokości dopasowany do tej samej siatki.")
                szerokosc_m = min(self.grid.shape) * self.grid.pixel_size
                if szerokosc_m < 80.0:
                    self.say("Uwaga: wycinek ma tylko {0} m w poprzek, "
                             "więc grunt szacujemy oknem węższym niż "
                             "zalecane 40 m. Szerokie dachy i zwarte "
                             "drzewostany mogą wyjść z wysokością nad "
                             "gruntem bliską zera — policz całe "
                             "zdjęcie, jeśli wysokość ma być "
                             "wiarygodna.".format(_liczba(szerokosc_m, 0)))

            # to, co użytkownik ustawił jako ostatnie, jest wiążące
            if not getattr(self, "_ostatnio_liczba", False):
                self._sync_segments(self.spin_object_size.value())
            requested = self.spin_segments.value()
            self.step(25, "Dzielę zdjęcie na obiekty...")

            def postep_podzialu(ulamek):
                self.step(25 + 10 * ulamek,
                          "Dzielę zdjęcie na obiekty: {0}".format(
                              _procent(ulamek, 0)))

            self.labels = slic_segments(
                self.grid.array, requested,
                self.spin_compactness.value(), self.spin_sigma.value(),
                mask=self.grid.mask, progress=postep_podzialu)
            realised = int(self.labels.max())
            rozmiary = np.bincount(self.labels.ravel())[1:]
            rozmiary = rozmiary[rozmiary > 0] * (self.grid.pixel_size ** 2)
            mediana = float(np.median(rozmiary)) if rozmiary.size else 0.0
            najwiekszy = float(rozmiary.max()) if rozmiary.size else 0.0
            zamowiona = self.spin_object_size.value()
            self.say("Powstało {0} obiektów (zamawiano {1}). Mediana "
                     "powierzchni: {2} m\u00b2, największy {3} m\u00b2."
                     .format(realised, requested, _liczba(mediana),
                             _liczba(najwiekszy)))
            if zamowiona > 0 and mediana > zamowiona * 1.3:
                self.say("Obiekty wyszły większe, niż zamawiałeś ({0} "
                         "m\u00b2). Jeśli zlewają dwa rodzaje terenu, "
                         "zmniejsz „Wielkość obiektu” albo podnieś "
                         "„Zwartość obiektów” w ustawieniach "
                         "zaawansowanych.".format(_liczba(zamowiona, 1)))

            def progress(message, fraction):
                self.step(35 + fraction * 40, message)

            self.feature_ids, self.feature_matrix, self.feature_names = \
                FEAT.compute_features(self.grid.array, self.labels,
                                      self.grid.pixel_size, dsm=dsm,
                                      progress=progress)
            self.say("Zmierzono {0} cech każdego obiektu{1}."
                     .format(len(self.feature_names),
                             "" if dsm is not None
                             else " (bez modelu wysokości)"))

            self.step(80, "Buduję warstwę obiektów...")
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
                self.say("Poprzednie punkty kontrolne usunięto — "
                         "odnosiły się do starego podziału.")
            self.step(100, "Obiekty gotowe.")
            self.progress.setVisible(False)
            self._update_mmu_label(self.spin_mmu.value())
            self._update_buttons()

            self.say("Teraz przejdź do kroku 2: dodaj klasy i wskaż "
                     "po kilka przykładów każdej.")
            self.iface.messageBar().pushMessage(
                "GeoAI Klasyfikator",
                "Gotowe: {0} obiektów. Dodaj klasy i wskaż przykłady."
                .format(realised), Qgis.MessageLevel.Success, 6)

        except MemoryError as error:
            self.progress.setVisible(False)
            QMessageBox.warning(
                self, "Za duże jak na pamięć komputera",
                "{0}\n\nCo możesz zrobić:\n"
                "  • wpisz w polu „Rozdzielczość robocza (m)” co "
                "najmniej tę wartość,\n"
                "  • zaznacz „Policz tylko to, co widać na "
                "ekranie”,\n"
                "  • podziel zdjęcie na kafle (np. narzędziem GDAL "
                "Retile) i licz je po kolei.".format(error))
        except Exception as error:
            self.progress.setVisible(False)
            self.say("Przerwane: {0}".format(error))
            QMessageBox.critical(
                self, "Nie udało się podzielić zdjęcia",
                "{0}\n\nJeśli nie wiesz, co z tym zrobić, napisz na "
                "gorniakgrzegorz@gmail.com i dołącz treść tego "
                "komunikatu.".format(error))
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
                    self, "Nie da się przeliczyć widoku",
                    "Widok mapy jest w innym układzie współrzędnych niż "
                    "zdjęcie, a przeliczenie się nie powiodło:\n{0}\n\n"
                    "Odznacz „Policz tylko to, co widać na ekranie” albo "
                    "ustaw układ projektu taki sam jak zdjęcia."
                    .format(blad))
                return None
        if prostokat.isEmpty():
            QMessageBox.warning(
                self, "Pusty widok",
                "Widoczny fragment mapy nie pokrywa się ze zdjęciem. "
                "Przybliż się do zdjęcia albo odznacz „Policz tylko to, "
                "co widać na ekranie”.")
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
            self, "Wyłącz najpierw podgląd klasyfikacji",
            "W panelu warstw widoczna jest warstwa „{0}” z gotową mapą.\n\n"
            "Opisuj punkty patrząc na samo zdjęcie — jeśli będziesz "
            "widział odpowiedź wtyczki, ocena wyjdzie zawyżona i nie "
            "da się jej uczciwie opublikować.\n\n"
            "Odznacz tę warstwę w panelu warstw i wróć tutaj."
            .format(", ".join(widoczne)))

    def _build_segments_layer(self):
        """Jedna warstwa poligonowa z obiektami, ich pomiarami i dwiema
        kolumnami klas — cała sesja widoczna w tabeli atrybutów."""
        if self.segments_layer is not None:
            with suppress(Exception):
                QgsProject.instance().removeMapLayer(self.segments_layer.id())

        layer = IO.polygonize_segments(self.labels, self.grid,
                                       "GeoAI obiekty")
        provider = layer.dataProvider()
        provider.addAttributes(
            [make_field("klasa_uczaca", "string", 64),
             make_field("klasa_mapy", "string", 64)]
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
        self._style_by_field("klasa_uczaca")

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
            None, empty, "bez klasy"))

        with suppress(Exception):
            self.segments_layer.setRenderer(
                QgsCategorizedSymbolRenderer(field, categories))
            self.segments_layer.triggerRepaint()

    # ── krok 2: klasy i przykłady ────────────────────────────────────

    def _add_class(self):
        name, accepted = QInputDialog.getText(
            self, "Nowa klasa",
            "Nazwa klasy pokrycia terenu\n"
            "(np. zabudowa, droga, trawa, las, woda, grunt odkryty):")
        if not accepted or not name.strip():
            return
        name = name.strip()
        if any(entry["name"] == name for entry in self.classes):
            QMessageBox.information(self, "Taka klasa już jest",
                                    "Klasa o tej nazwie już istnieje.")
            return
        self.classes.append({"name": name,
                             "colour": self._suggest_colour(name),
                             "value": len(self.classes) + 1})
        self._refresh_class_list()
        self.list_classes.setCurrentRow(len(self.classes) - 1)
        self._style_by_field("klasa_mapy" if self.classified is not None
                             else "klasa_uczaca")

    def _remove_class(self):
        row = self.list_classes.currentRow()
        if row < 0:
            return
        name = self.classes[row]["name"]
        answer = QMessageBox.question(
            self, "Usunąć klasę?",
            "Usunąć klasę „{0}” razem z jej przykładami?".format(name))
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
                "Usunięcie klasy przesunęło numery pozostałych klas, "
                "więc mapa i punkty kontrolne przestały pasować. "
                "Naucz i zrób mapę jeszcze raz.")
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
            entry["colour"], self, "Kolor klasy " + entry["name"])
        if colour.isValid():
            entry["colour"] = colour
            self._refresh_class_list()
            self._style_by_field("klasa_mapy" if self.classified is not None
                                 else "klasa_uczaca")

    def _clear_class_samples(self):
        row = self.list_classes.currentRow()
        if row < 0:
            return
        name = self.classes[row]["name"]
        self.training = {key: value for key, value in self.training.items()
                         if value != name}
        self._refresh_class_list()
        self._write_training_to_layer()
        self.say("Przykłady klasy „{0}” wyczyszczone.".format(name))

    def _refresh_class_list(self):
        current = self.list_classes.currentRow()
        self.list_classes.clear()
        counts = {}
        for name in self.training.values():
            counts[name] = counts.get(name, 0) + 1

        for entry in self.classes:
            count = counts.get(entry["name"], 0)
            word = _odmiana(count, "przykład", "przykłady", "przykładów")
            item = QListWidgetItem("{0}   — {1} {2}".format(
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
                self, "Nie ma czego wskazywać",
                "Najpierw podziel zdjęcie na obiekty — to krok 1.")
            return
        if self.active_class() is None:
            self._odznacz(self.btn_collect)
            QMessageBox.information(
                self, "Brak klasy",
                "Najpierw dodaj klasę i zaznacz ją na liście "
                "(przycisk „Dodaj klasę” w kroku 2).")
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
        self.btn_collect.setText("WSKAZUJESZ — kliknij, by zakończyć")
        self._style_by_field("klasa_uczaca")

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
        self.say("Obiekty najbardziej podobne do tego: {0}."
                 .format(", ".join(str(value) for value in similar[:8])))

    def on_tool_deactivated(self):
        """Kanwa zabrała nam narzędzie (np. użytkownik wybrał inne)."""
        if self._switching_tool:
            return
        self.active_tool = None
        for przycisk, napis in ((self.btn_collect,
                                 "WSKAZUJ PRZYKŁADY NA MAPIE"),
                                (self.btn_label_points,
                                 "OPISUJ PUNKTY NA MAPIE")):
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
        index = self.segments_layer.fields().indexOf("klasa_uczaca")
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
                "Nie wskazałeś jeszcze żadnych przykładów. Wróć do "
                "kroku 2 i kliknij na mapie kilka obiektów.")
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
                "Do nauki potrzebne są przykłady co najmniej dwóch "
                "klas — inaczej nie ma czego od czego odróżniać.")
        return self.feature_matrix[rows], np.array(labels)

    def check_separability(self):
        try:
            features, labels = self._training_arrays()
        except ValueError as error:
            QMessageBox.information(self, "Za mało przykładów", str(error))
            return

        self.step(30, "Sprawdzam, czy klasy da się rozróżnić...")
        report = CLF.separability_report(features, labels,
                                         self.feature_names)
        self.progress.setVisible(False)
        self._show_separability(report)

    def _show_separability(self, report):
        lines = [
            "<h3>Czy te klasy da się rozróżnić?</h3>",
            "<p>Dla każdej pary klas liczymy, jak bardzo różnią się ",
            "Twoje przykłady. Skala od 0 do 2: <b>0</b> znaczy, że obie ",
            "klasy wyglądają identycznie i nie ma czego rozdzielać, ",
            "<b>2</b> — że są zupełnie inne.</p>",
            "<p>Powyżej 1,9 jest dobrze, 1,7 do 1,9 znośnie, poniżej ",
            "1,7 słabo: taka para będzie się myliła i albo trzeba ",
            "dodać przykładów, albo połączyć te klasy w jedną.</p>",
            "<table cellpadding='4' border='1' ",
            "style='border-collapse:collapse'>",
            "<tr><th>Para klas</th><th>Wynik</th><th>Ocena</th>",
            "<th>Co je najbardziej dzieli</th></tr>"]
        oceny = {"good": "dobrze", "fair": "znośnie", "poor": "słabo"}
        for pair in report["pairs"]:
            leading = ", ".join(self._feature_label(name)
                                for name, _ in pair["leading"][:3])
            lines.append(
                "<tr><td>{0} — {1}</td><td align='right'>{2}</td>"
                "<td>{3}</td><td>{4}</td></tr>".format(
                    pair["a"], pair["b"], _liczba(pair["jm"], 2),
                    oceny.get(pair["verdict"], pair["verdict"]), leading))
        lines.append("</table>")

        sizes = ", ".join("{0}: {1}".format(name, count)
                          for name, count in report["sample_sizes"].items())
        lines.append(
            "<p style='color:#607d8b'>Liczba cech: {0}. Przykładów na "
            "klasę — {1}. Dobrze jest mieć ich co najmniej tyle, "
            "ile cech.</p>".format(report["n_features"], sizes))

        self._show_html("Rozróżnialność klas", "".join(lines), 640, 500)

    @staticmethod
    def _feature_label(name):
        """Nazwa cechy po ludzku, do pokazania użytkownikowi."""
        opisy = {
            "r_mean": "czerwień", "g_mean": "zieleń", "b_mean": "niebieski",
            "r_std": "zmienność czerwieni", "g_std": "zmienność zieleni",
            "b_std": "zmienność niebieskiego",
            "brightness_mean": "jasność",
            "exg_mean": "zieloność (ExG)", "vari_mean": "wskaźnik VARI",
            "ngrdi_mean": "wskaźnik NGRDI",
            "contrast": "kontrast faktury",
            "homogeneity": "jednolitość faktury",
            "energy": "powtarzalność faktury",
            "entropy": "nieuporządkowanie faktury",
            "area": "powierzchnia", "perimeter": "obwód",
            "circularity": "okrągłość", "convexity": "wypukłość",
            "brightness_rel_neighbors": "jasność na tle sąsiadów",
            "dsm_mean": "wysokość", "dsm_std": "zmienność wysokości",
            "slope_mean": "nachylenie",
            "dsm_rel_neighbors": "wysokość na tle sąsiadów",
            "hag_mean": "wysokość nad gruntem",
        }
        return opisy.get(name, name)

    def train_model(self):
        try:
            features, labels = self._training_arrays()
        except ValueError as error:
            QMessageBox.information(self, "Za mało przykładów", str(error))
            return
        self.step(40, "Uczę Random Forest...")
        try:
            self.model = CLF.train(features, labels)
        except Exception as error:
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Nauka się nie powiodła",
                                 str(error))
            return
        self.progress.setVisible(False)
        self.say("Nauczone na {0} obiektach w {1} klasach, {2} cech."
                 .format(len(labels), len(set(labels.tolist())),
                         features.shape[1]))
        duza, mala, stosunek = CLF.niezrownowazenie(labels)
        if stosunek >= 5.0 and duza and mala:
            self.say("Klasa „{0}” ma {1} razy więcej przykładów niż "
                     "„{2}”. Random Forest tego nie wyrównuje — dołóż "
                     "przykładów rzadszej klasie, inaczej będzie "
                     "przegrywać głosowania.".format(
                         duza, _liczba(stosunek, 0), mala))
        importance = CLF.feature_importance(self.model, self.feature_names)
        if importance:
            top = ", ".join("{0} ({1})".format(
                self._feature_label(name), _procent(value, 0))
                for name, value in importance[:4])
            self.say("Najważniejsze okazały się: {0}.".format(top))
        else:
            self.say("Które cechy zaważyły, pokazuje tylko silnik "
                     "scikit-learn — przepis na jego instalację "
                     "jest w Instrukcji.")
        self.say("Teraz kliknij „ZRÓB MAPĘ”.")
        self._update_buttons()

    def classify_all(self):
        if self._zajety("Trwa robienie mapy"):
            return
        if self.model is None:
            QMessageBox.information(
                self, "Najpierw nauka",
                "Zanim zrobimy mapę, kliknij „Naucz”.")
            return
        if self.grid is None or self.labels is None:
            QMessageBox.information(
                self, "Brak podziału na obiekty",
                "Wróć do kroku 1 i podziel zdjęcie na obiekty.")
            return
        self._zablokuj_akcje(True)
        try:
            self._classify_all()
        except Exception as error:
            self.progress.setVisible(False)
            self.say("Przerwane: {0}".format(error))
            QMessageBox.critical(
                self, "Nie udało się zrobić mapy",
                "{0}\n\nSpróbuj nauczyć klasyfikator jeszcze raz "
                "(krok 3).".format(error))
        finally:
            self._zablokuj_akcje(False)

    def _classify_all(self):
        self.step(50, "Nadaję klasę każdemu obiektowi...")
        predicted, confidence = CLF.predict(self.model, self.feature_matrix)

        values = {entry["name"]: entry["value"] for entry in self.classes}
        mapping = np.zeros(int(self.feature_ids.max()) + 1, dtype=np.int32)
        for identifier, name in zip(self.feature_ids, predicted):
            mapping[int(identifier)] = values.get(str(name), 0)
        self.classified = mapping[self.labels]
        self.classified[~self.grid.mask] = 0

        self.step(70, "Nanoszę poprawki...")
        self._apply_refinements()

        self.step(85, "Koloruję warstwę obiektów...")
        self._write_map_to_layer(predicted)
        self._style_by_field("klasa_mapy")

        self.step(100, "Mapa gotowa.")
        self.progress.setVisible(False)

        total = float(np.count_nonzero(self.classified > 0))
        shares = []
        for entry in self.classes:
            count = float(np.count_nonzero(self.classified == entry["value"]))
            if count and total:
                area = count * (self.grid.pixel_size ** 2) / 10000.0
                shares.append("{0} {1} ({2} ha)".format(
                    entry["name"], _procent(count / total, 1),
                    _liczba(area, 2)))
        self.say("Mapa: " + ", ".join(shares))

        uncertain = int(np.count_nonzero(confidence < 0.5))
        if uncertain:
            self.say("{0} {1} dostało mniej niż połowę głosów — to "
                     "tam wtyczka najbardziej się waha i tam najbardziej "
                     "przydadzą się Twoje przykłady.".format(
                         uncertain,
                         _odmiana(uncertain, "obiekt", "obiekty",
                                  "obiektów")))
        self.say("Przejrzyj mapę i popraw ją w kroku 2 i 3, a potem "
                 "sprawdź ją w kroku 4.")
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
                self.say("Dociąganie po zieloności: {0} pikseli przeszło "
                         "do klasy {1}, {2} do {3}."
                         .format(to_green, green, to_other, other))

        if self.spin_mmu.value() > 0:
            before = self.classified.copy()
            self.classified = REF.sieve(self.classified,
                                        self.spin_mmu.value())
            moved = int(np.count_nonzero(before != self.classified))
            self.say("Czyszczenie drobnych płatów: {0} pikseli przeszło "
                     "do sąsiednich klas.".format(moved))

    def _write_map_to_layer(self, predicted):
        if self.segments_layer is None:
            return
        index = self.segments_layer.fields().indexOf("klasa_mapy")
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
                self, "Brak przykładów",
                "Najpierw wskaż na mapie przykłady obu klas.")
            return
        green = self.cmb_green.currentText()
        other = self.cmb_other.currentText()
        if green == other:
            QMessageBox.information(self, "Ta sama klasa",
                                    "Wybierz dwie różne klasy.")
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
                self, "Za mało przykładów",
                "Żeby wyliczyć próg, potrzebuję przykładów obu "
                "wybranych klas.")
            return

        cutoff = REF.cutoff_from_samples(np.concatenate(green_values),
                                         np.concatenate(other_values))
        self.spin_cutoff.setValue(cutoff)
        self.say("Próg zieloności wyliczony z przykładów: {0}."
                 .format(_liczba(cutoff, 4)))

    def export_map(self):
        if self.classified is None or self.grid is None:
            QMessageBox.information(self, "Nie ma jeszcze mapy",
                                    "Najpierw kliknij „ZRÓB MAPĘ”.")
            return
        base = os.path.splitext(os.path.basename(
            self.grid.source_path or "mapa"))[0]
        suggestion = os.path.join(
            os.path.dirname(self.grid.source_path or ""),
            base + "_klasyfikacja.tif")
        path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz mapę klasyfikacji", suggestion,
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
                self, "Zapis się nie powiódł",
                "{0}\n\nSprawdź, czy plik nie jest otwarty w innym "
                "programie i czy masz prawo zapisu w tym folderze."
                .format(error))
            return
        self.say("Mapa zapisana: {0}. Obok leży plik stylu .qml, więc "
                 "u kogoś innego otworzy się od razu w kolorach."
                 .format(path))
        layer = IO.load_as_layer(path, base + "_klasyfikacja")
        if layer is not None:
            QgsProject.instance().addMapLayer(layer)

    # ── krok 4: ocena dokładności ────────────────────────────────────

    def generate_points(self):
        if self._zajety("Trwa losowanie punktów"):
            return
        if self.classified is None or self.grid is None:
            QMessageBox.information(
                self, "Nie ma jeszcze mapy",
                "Najpierw zrób mapę — punkty losujemy w obrębie jej "
                "klas, żeby każda dostała ich dość.")
            return

        training_mask = np.zeros(self.labels.shape, dtype=bool)
        if self.training:
            wanted = np.array(sorted(self.training.keys()), dtype=np.int64)
            training_mask = np.isin(self.labels, wanted)

        values = [entry["value"] for entry in self.classes]
        stratified = self.cmb_design.currentIndex() == 0

        self._zablokuj_akcje(True)
        try:
            self.step(30, "Losuję punkty kontrolne...")
            points, strata = self._losuj(stratified, values, training_mask)
        except Exception as error:
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Nie udało się wylosować punktów",
                                 str(error))
            return
        finally:
            self._zablokuj_akcje(False)

        self.progress.setVisible(False)
        if len(points) == 0:
            QMessageBox.information(
                self, "Brak punktów",
                "Nie został żaden piksel, z którego dałoby się losować. "
                "Zdarza się to, gdy wszystkie obiekty posłużyły już "
                "jako przykłady uczące.")
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
        self.say("Wylosowano {0} {1} kontrolnych, sposób: {2}. Obiekty "
                 "użyte do nauki zostały pominięte.".format(
                     len(points),
                     _odmiana(len(points), "punkt", "punkty", "punktów"),
                     "warstwowy" if stratified else "prosty losowy"))
        self.say("Teraz wyłącz warstwę z mapą i opisz punkty patrząc "
                 "na samo zdjęcie.")
        self._update_buttons()

    def _build_points_layer(self, points, strata):
        from qgis.core import QgsFeature, QgsGeometry, QgsPointXY

        if self.points_layer is not None:
            with suppress(Exception):
                QgsProject.instance().removeMapLayer(self.points_layer.id())

        authid = self.grid.crs().authid() if self.grid.crs().isValid() else ""
        uri = "Point?crs={0}".format(authid) if authid else "Point"
        layer = QgsVectorLayer(uri, "GeoAI punkty kontrolne", "memory")
        provider = layer.dataProvider()
        provider.addAttributes([
            make_field("numer", "int"),
            make_field("klasa_ze_zdjecia", "string", 64),
            make_field("klasa_mapy", "string", 64),
            make_field("warstwa_losowania", "string", 64),
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
            None, unlabelled, "jeszcze nieopisany"))
        with suppress(Exception):
            layer.setRenderer(QgsCategorizedSymbolRenderer(
                "klasa_ze_zdjecia", categories))

    def _toggle_point_tool(self, checked):
        if self._switching_tool:
            return
        if not checked:
            self._zdejmij_narzedzie()
            return
        if self.points_layer is None:
            self._odznacz(self.btn_label_points)
            QMessageBox.information(self, "Brak punktów",
                                    "Najpierw wylosuj punkty kontrolne.")
            return
        if self.active_class() is None:
            self._odznacz(self.btn_label_points)
            QMessageBox.information(
                self, "Brak klasy",
                "Zaznacz na liście klasę, którą chcesz przypisywać "
                "punktom.")
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
        self.btn_label_points.setText("OPISUJESZ — kliknij, by zakończyć")
        self._ostrzez_o_widocznej_mapie()

    def on_point_labelled(self, feature_id):
        name = self.active_class()
        if name is None or self.points_layer is None:
            return
        self._set_point_class(feature_id, name)

    def on_point_cleared(self, feature_id):
        self._set_point_class(feature_id, None)

    def _set_point_class(self, feature_id, value):
        index = self.points_layer.fields().indexOf("klasa_ze_zdjecia")
        if index < 0:
            return
        self.points_layer.dataProvider().changeAttributeValues(
            {feature_id: {index: value}})
        self.points_layer.triggerRepaint()
        labelled = sum(1 for feature in self.points_layer.getFeatures()
                       if feature["klasa_ze_zdjecia"])
        total = self.points_layer.featureCount()
        self.step(100 * labelled / max(total, 1),
                  "opisano {0} z {1} punktów".format(labelled, total))

    def run_assessment(self):
        if self._zajety("Trwa liczenie dokładności"):
            return
        if self.points_layer is None or self.classified is None \
                or self.grid is None:
            QMessageBox.information(
                self, "Nie ma czego oceniać",
                "Najpierw zrób mapę i wylosuj punkty kontrolne.")
            return

        names = {entry["value"]: entry["name"] for entry in self.classes}
        values = [entry["value"] for entry in self.classes]
        by_name = {entry["name"]: entry["value"] for entry in self.classes}

        map_classes, reference_classes, strata = [], [], []
        unlabelled = 0
        for feature in self.points_layer.getFeatures():
            reference = feature["klasa_ze_zdjecia"]
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
            strata.append(by_name.get(feature["warstwa_losowania"], mapped))

        if len(map_classes) < 2:
            QMessageBox.information(
                self, "Za mało opisanych punktów",
                "Opisz punkty kontrolne, zanim policzymy dokładność. "
                "Włącz „OPISUJ PUNKTY NA MAPIE”, wybierz klasę i "
                "klikaj punkty.")
            return
        if unlabelled:
            self.say("{0} {1} bez opisu zostało pominiętych.".format(
                unlabelled,
                _odmiana(unlabelled, "punkt", "punkty", "punktów")))

        stratified = self.cmb_design.currentIndex() == 0
        stratum_pixels = None
        if stratified:
            if not self.stratum_pixels:
                QMessageBox.information(
                    self, "Brak wag powierzchniowych",
                    "Wylosuj punkty kontrolne jeszcze raz — wagi "
                    "powierzchni zapamiętujemy w chwili losowania.")
                return
            # wagi z chwili losowania, nie z bieżącej mapy: warstwy
            # muszą zostać przy próbie (Stehman 2014)
            stratum_pixels = [self.stratum_pixels.get(value, 0.0)
                              for value in values]
            map_classes = strata
            puste = [names[value] for value, piksele
                     in zip(values, stratum_pixels) if piksele <= 0]
            if puste:
                self.say("Klasy bez powierzchni w chwili losowania: {0}."
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
            "<h3>Ocena dokładności mapy</h3>",
            "<p>W wierszach to, co mówi mapa, w kolumnach to, co ",
            "widać na zdjęciu. Na przekątnej (podświetlonej) leżą ",
            "zgodności.</p>",
            "<table cellpadding='4' border='1' ",
            "style='border-collapse:collapse'>",
            "<tr><th>mapa \\ zdjęcie</th>"]
        lines.extend("<th>{0}</th>".format(name) for name in names)
        lines.append("<th>razem</th><th>trafność<br>mapy</th></tr>")

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
                "—" if not np.isfinite(users) else _procent(users, 0)))

        lines.append("<tr><th>razem</th>")
        for column in range(len(names)):
            lines.append("<td align='right'>{0}</td>".format(
                int(matrix[:, column].sum())))
        lines.append("<td align='right'>{0}</td><td></td></tr>".format(
            int(matrix.sum())))

        producers = (weighted["producers"] if weighted is not None
                     else counts["producers"])
        lines.append("<tr><th>kompletność</th>")
        for value in producers:
            lines.append("<td align='right'>{0}</td>".format(
                "—" if not np.isfinite(value) else _procent(value, 0)))
        lines.append("<td></td><td></td></tr></table>")

        lines.append(
            "<p style='color:#607d8b'><b>Trafność mapy</b>: gdy mapa "
            "mówi „trawa”, jak często to naprawdę trawa. "
            "<b>Kompletność</b>: ile z rzeczywistej trawy mapa "
            "znalazła.</p>")

        bez_punktow = report.get("classes_without_points") or []
        if bez_punktow and weighted is not None:
            udzial = float(np.sum(weighted["proportions"]))
            lines.append(
                "<p style='background:#fff3cd;padding:8px;border:1px "
                "solid #e0a030'><b>Uwaga:</b> klasy <b>{0}</b> nie mają "
                "ani jednego opisanego punktu, więc wypadły z bilansu. "
                "Udziały powierzchni sumują się do {1} zamiast do 100 "
                "proc., a dokładność ogólna jest zaniżona. Opisz punkty "
                "tych klas albo usuń je z listy, zanim zacytujesz te "
                "liczby.</p>".format(", ".join(bez_punktow),
                                     _procent(udzial)))

        if weighted is not None:
            lines.append(
                "<p><b>Dokładność ogólna: {0:.0f} proc., plus minus "
                "{1:.0f} punktu procentowego</b> (ważona powierzchnią); "
                "licząc po samych punktach wyszłoby {2:.0f} proc. "
                "Różnica bierze się stąd, że losowanie daje każdej "
                "klasie podobnie dużo punktów, a liczba ważona liczy "
                "każdą klasę wedle powierzchni, jaką zajmuje.</p>"
                .format(weighted["overall"] * 100,
                        weighted["overall_ci"] * 100,
                        counts["overall"] * 100))
            lines.append(
                "<h4>Powierzchnie klas</h4>"
                "<table cellpadding='4' border='1' "
                "style='border-collapse:collapse'>"
                "<tr><th>Klasa</th><th>Z mapy (ha)</th>"
                "<th>Szacowana (ha)</th><th>Niepewność (ha)</th></tr>")
            for index, name in enumerate(names):
                lines.append(
                    "<tr><td>{0}</td><td align='right'>{1}</td>"
                    "<td align='right'>{2}</td>"
                    "<td align='right'>± {3}</td></tr>".format(
                        name,
                        _liczba(weighted["mapped_area"][index] / 10000.0, 3),
                        _liczba(weighted["estimated_area"][index] / 10000.0, 3),
                        _liczba(weighted["estimated_area_ci"][index] / 10000.0, 3)))
            lines.append("</table>")
            lines.append(
                "<p style='color:#607d8b'>Jeśli podajesz powierzchnie "
                "w hektarach, cytuj <b>szacowaną</b> wraz z "
                "niepewnością, a nie tę z mapy: szacunek poprawia mapę "
                "o błędy, które wykryła próba (Olofsson i in., 2014).</p>")
        else:
            lines.append(
                "<p><b>Dokładność ogólna: {0:.0f} proc.</b> z {1} "
                "punktów.</p>".format(counts["overall"] * 100,
                                      counts["n"]))

        lines.append(
            "<p style='color:#607d8b'>Punkty opisane z lotu ptaka to "
            "dane referencyjne wysokiej jakości, ale nie są tym samym, "
            "co pomiar w terenie. Współczynnika kappa świadomie nie "
            "liczymy — obecne zalecenia go odradzają.</p>")

        self._show_html("Ocena dokładności", "".join(lines), 700, 560,
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
            self, "Zapisz raport dokładności", "raport_dokladnosci.csv",
            "Plik CSV (*.csv)")
        if not path:
            return
        przecinek = lokalizacja_liczb().decimalPoint()

        class _Pisarz:
            """Ułamki z przecinkiem, żeby Excel czytał je jako liczby."""
            def __init__(self, baza):
                self.baza = baza

            def writerow(self, wiersz):
                self.baza.writerow([
                    str(w).replace(".", przecinek) if isinstance(w, float)
                    else w for w in wiersz])

        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = _Pisarz(csv.writer(handle, delimiter=";"))
            for row in ACC.report_rows(report):
                writer.writerow(row)
            weighted = report.get("weighted")
            if weighted is not None:
                writer.writerow([])
                writer.writerow(["dokladnosc ogolna wazona powierzchnia",
                                 round(float(weighted["overall"]), 4),
                                 "przedzial 95 proc.",
                                 round(float(weighted["overall_ci"]), 4)])
                writer.writerow(["klasa", "powierzchnia z mapy (ha)",
                                 "powierzchnia szacowana (ha)",
                                 "niepewnosc (ha)"])
                for index, name in enumerate(report["class_names"]):
                    writer.writerow([
                        name,
                        round(float(weighted["mapped_area"][index]) / 1e4, 4),
                        round(float(weighted["estimated_area"][index])
                              / 1e4, 4),
                        round(float(weighted["estimated_area_ci"][index])
                              / 1e4, 4)])
        self.say("Raport zapisany: {0}.".format(path))

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
        self._show_html("GeoAI Klasyfikator — instrukcja",
                        GUIDE_HTML.replace("__INSTALL__",
                                           INSTALL_HINT.replace("\n", "<br>")),
                        660, 600)

    def closeEvent(self, event):
        if self.active_tool is not None:
            with suppress(Exception):
                self.iface.mapCanvas().unsetMapTool(self.active_tool)
        super().closeEvent(event)


GUIDE_HTML = """
<h2>Jak to działa</h2>
<p>Wtyczka robi mapę pokrycia terenu ze zdjęcia z drona albo zdjęcia
lotniczego. Nie patrzy na pojedyncze piksele, tylko najpierw tnie
zdjęcie na <b>obiekty</b> — kawałki pola, dachu, korony drzewa — a
potem uczy się od Ciebie, co jest czym.</p>
<p>Dlaczego obiekty, a nie piksele? Pojedynczy piksel mówi tylko
o kolorze. Obiekt ma jeszcze fakturę, kształt, wysokość i otoczenie,
a mapa nie wychodzi „zaśmiecona” pojedynczymi kropkami.</p>

<h3>Czego potrzebujesz</h3>
<ul>
  <li><b>Zdjęcie RGB</b> — ortomozaika z drona, zdjęcie lotnicze albo
  scena satelitarna. Wystarczą trzy kanały: czerwony, zielony,
  niebieski.</li>
  <li><b>Model wysokości (NMPT)</b> — nieobowiązkowy, ale bardzo
  pomaga. Bez niego wtyczka mierzy 19 cech, z nim 24, w tym wysokość
  nad gruntem. To ona odróżnia dach od asfaltu i drzewo od trawnika.</li>
</ul>
<p>Zwykłe kamery dronowe nie rejestrują podczerwieni, więc NDVI tu nie
ma. Zastępują go wskaźniki z zakresu widzialnego (zieloność ExG, VARI,
NGRDI), faktura, kształt i wysokość.</p>

<h3>Krok 1 — podział na obiekty</h3>
<p>Najważniejsze jest pole <b>Wielkość obiektu</b>. Zasada jest jedna:
obiekt musi być mniejszy niż najwęższa rzecz, którą chcesz pokazać na
mapie. Jeśli kartujesz pola i dachy, dobrze działa 5-20 m&sup2;; jeśli
pojedyncze drzewa — 2-5 m&sup2;.</p>
<p>Po podziale obejrzyj wynik na mapie i sprawdź dwie rzeczy: czy
żaden obiekt nie leży jednocześnie na dwóch różnych rodzajach terenu
(to jest problem, zmniejsz obiekty) i czy jednolita łąka nie rozsypała
się na setki drobin (to już tylko niewygoda).</p>
<p>Pracując na dużym zdjęciu, najpierw zaznacz „Policz tylko to, co
widać na ekranie” i dobierz wielkość obiektu na fragmencie.</p>

<h3>Krok 2 — klasy i przykłady</h3>
<p>Dodaj klasy, które chcesz rozróżniać, a potem klikaj na mapie
obiekty, które do nich należą. Trzy rzeczy decydują o wyniku:</p>
<ul>
  <li><b>Rozrzuć przykłady po całym zdjęciu.</b> Światło i cień
  zmieniają się z miejsca na miejsce.</li>
  <li><b>Pokaż każdą odmianę klasy.</b> „Grunt odkryty” to i świeżo
  zaorana ziemia, i udeptana ścieżka, i sucha skarpa.</li>
  <li><b>Wskazuj tylko to, co rozpoznajesz bez wahania.</b> Jeden błędny
  przykład uczy wtyczkę błędnej reguły. Obiekt leżący na granicy
  dwóch klas lepiej pominąć.</li>
</ul>
<p>Na początek wystarczy 10-20 przykładów na klasę. Potem i tak
będziesz dokładać.</p>

<h3>Krok 3 — nauka i mapa</h3>
<p>Zanim zaczniesz, kliknij <b>„Czy klasy da się rozróżnić?”</b>.
Jeśli któraś para wypada słabo, nie ma sensu dokładać pracy — albo
dodaj przykładów, albo połącz te klasy.</p>
<p><b>Poprawianie mapy to nie porażka, to metoda.</b> Pierwsza mapa
nigdy nie jest dobra. Przejrzyj ją całą, wypisz sobie rodzaje pomyłek,
dodaj po kilka przykładów każdego rodzaju w różnych miejscach i
powtórz. Dwie, trzy rundy dają najwięcej.</p>
<p><b>Dociąganie po zieloności</b> przydaje się, gdy mapujesz pola:
pas trawy między zagonami bywa węższy niż obiekt i ginie. Ta opcja
oddaje decyzję pojedynczym pikselom, ale tylko dla dwóch wskazanych
klas. Uwaga: odzyskane pasy wychodzą nieco szersze niż w naturze, więc
ostrożnie z podawaniem ich powierzchni.</p>

<h3>Krok 4 — ile ta mapa jest warta</h3>
<p>Tu wtyczka robi rzecz, której w QGIS-ie brakuje: liczy dokładność
tak, jak wymagają tego recenzenci i dobre praktyki.</p>
<ol>
  <li>Losuje punkty kontrolne — nigdy na obiektach użytych do nauki.</li>
  <li>Ty opisujesz każdy punkt patrząc na <i>samo zdjęcie</i>.
  <b>Wyłącz warstwę z mapą klasyfikacji</b>, zanim zaczniesz — inaczej
  podpowiedź wtyczki wpłynie na Twoją ocenę i wynik będzie zawyżony.</li>
  <li>Dostajesz macierz błędów, trafność i kompletność każdej klasy
  oraz dokładność ogólną.</li>
</ol>
<p>Przy losowaniu warstwowym małe klasy dostają proporcjonalnie dużo
punktów, więc udział punktów nie jest udziałem powierzchni. Dlatego
wtyczka podaje też liczby <b>ważone powierzchnią</b> i szacowane
powierzchnie klas z przedziałami ufności. W publikacji cytuj właśnie
te.</p>

<h3>Co zostaje w projekcie</h3>
<ul>
  <li><b>GeoAI obiekty</b> — warstwa poligonowa; w tabeli atrybutów
  masz wszystkie zmierzone cechy każdego obiektu, kolumnę
  <code>klasa_uczaca</code> (Twoje przykłady) i <code>klasa_mapy</code>
  (wynik).</li>
  <li><b>GeoAI punkty kontrolne</b> — punkty z opisem ze zdjęcia,
  klasą z mapy i warstwą losowania.</li>
  <li>Zapisany <b>GeoTIFF</b> z plikiem stylu .qml obok.</li>
</ul>

<h3>Szybciej i dokładniej</h3>
<p>__INSTALL__</p>

<h3>Skąd ta metoda</h3>
<p>Segmentacja SLIC (Achanta i in., 2012), faktura GLCM (Haralick
i in., 1973), zieloność ExG (Woebbecke i in., 1995), Random Forest
(Breiman, 2001; Belgiu i Drăguţ, 2016), rozróżnialność klas miarą
Jeffriesa-Matusity oraz ocena dokładności wg Congaltona i Greena,
Olofssona i in. (2014) i Stehmana (2014).</p>

"""
