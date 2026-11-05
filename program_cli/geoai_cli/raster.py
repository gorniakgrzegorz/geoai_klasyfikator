# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Wczytywanie i zapisywanie rastrów bez QGIS-a.

Program z wiersza poleceń ma działać na zwykłym Pythonie, dlatego
korzysta z biblioteki ``rasterio`` (instaluje się jednym poleceniem
pip i nosi własnego GDAL-a w środku). Jeśli ktoś uruchamia program
w środowisku QGIS-a, gdzie jest ``osgeo``, też zadziała — rasterio
jest wtedy tylko cienką nakładką na to samo.
"""
from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

# Jeden piksel siatki roboczej kosztuje ok. 100 bajtów we wszystkich
# pośrednich tablicach razem, więc 15 Mpx to już ok. 1,5 GB.
MAKS_PIKSELI = 15_000_000
ROZSZERZENIA = (".tif", ".tiff", ".img", ".jp2", ".png", ".vrt")


@dataclass
class Siatka:
    """Zdjęcie wczytane na jedną siatkę roboczą, z georeferencją."""

    tablica: np.ndarray          # (wiersze, kolumny, 3), wartości 0-1
    transformacja: object        # rasterio Affine
    crs: object                  # układ współrzędnych
    maska: np.ndarray            # True tam, gdzie są dane
    piksel: float                # bok piksela w jednostkach mapy
    sciezka: str = ""

    @property
    def ksztalt(self):
        return self.tablica.shape[:2]

    @property
    def powierzchnia_m2(self) -> float:
        return float(np.count_nonzero(self.maska)) * self.piksel ** 2

    def piksel_na_mape(self, wiersze, kolumny):
        x, y = rasterio.transform.xy(self.transformacja, wiersze, kolumny)
        return np.asarray(x), np.asarray(y)

    def mapa_na_piksel(self, x, y):
        wiersz, kolumna = rasterio.transform.rowcol(self.transformacja, x, y)
        return int(wiersz), int(kolumna)


def zdjecia_w_folderze(folder: str, rekurencyjnie: bool = False) -> list:
    """Lista plików rastrowych w folderze, posortowana po nazwie."""
    znalezione = []
    if rekurencyjnie:
        for katalog, _, pliki in os.walk(folder):
            for nazwa in pliki:
                if nazwa.lower().endswith(ROZSZERZENIA):
                    znalezione.append(os.path.join(katalog, nazwa))
    else:
        for nazwa in os.listdir(folder):
            pelna = os.path.join(folder, nazwa)
            if os.path.isfile(pelna) and nazwa.lower().endswith(ROZSZERZENIA):
                znalezione.append(pelna)
    return sorted(znalezione)


def rozmiar_piksela(sciezka: str) -> float:
    with rasterio.open(sciezka) as plik:
        return float(abs(plik.transform.a))


def wczytaj_rgb(sciezka: str, docelowy_piksel: float = 0.0) -> Siatka:
    """Wczytuje trzy pierwsze kanały na siatkę roboczą, w skali 0-1."""
    with rasterio.open(sciezka) as plik:
        if plik.count < 3:
            raise ValueError(
                "Potrzebne jest zdjęcie trójkanałowe (RGB), a plik "
                "{0} ma kanałów: {1}.".format(os.path.basename(sciezka),
                                              plik.count))

        wlasny = float(abs(plik.transform.a))
        skala = 1.0 if docelowy_piksel <= 0 else wlasny / docelowy_piksel
        if skala > 1.0:
            # nie rozdmuchujemy obrazu ponad jego własną rozdzielczość
            skala = 1.0
        szerokosc = max(1, int(round(plik.width * skala)))
        wysokosc = max(1, int(round(plik.height * skala)))

        if szerokosc * wysokosc > MAKS_PIKSELI:
            sugestia = wlasny * np.sqrt(
                plik.width * plik.height / MAKS_PIKSELI)
            raise MemoryError(
                "Siatka robocza {0} na {1} pikseli nie zmieści się "
                "w pamięci. Podaj grubszą rozdzielczość, np. "
                "--rozdzielczosc {2:.3f}.".format(szerokosc, wysokosc,
                                                  sugestia))

        dane = plik.read(
            indexes=[1, 2, 3],
            out_shape=(3, wysokosc, szerokosc),
            resampling=(Resampling.average if skala < 1.0
                        else Resampling.nearest)).astype(np.float32)
        tablica = np.transpose(dane, (1, 2, 0))

        maksimum = {"uint8": 255.0, "uint16": 65535.0,
                    "int16": 32767.0}.get(str(plik.dtypes[0]))
        if maksimum is None:
            skonczone = tablica[np.isfinite(tablica)]
            maksimum = float(skonczone.max()) if skonczone.size else 1.0
            maksimum = maksimum if maksimum > 1.5 else 1.0
        tablica = np.clip(tablica / maksimum, 0.0, 1.0)

        maska = np.ones((wysokosc, szerokosc), dtype=bool)
        # nie każdy plik ma czytelną maskę; gdy jej nie ma, zostaje
        # wartość nodata i test czarnych rogów poniżej
        with contextlib.suppress(Exception):
            odczyt = plik.read_masks(
                1, out_shape=(wysokosc, szerokosc),
                resampling=Resampling.nearest)
            if odczyt is not None:
                maska &= odczyt > 0
        if plik.nodata is not None:
            maska &= ~np.all(
                np.isclose(tablica * maksimum, plik.nodata), axis=2)
        # obrócone ortomozaiki zostawiają czarne rogi
        maska &= ~np.all(tablica <= 0.0, axis=2)

        transformacja = plik.transform * plik.transform.scale(
            plik.width / szerokosc, plik.height / wysokosc)
        return Siatka(tablica, transformacja, plik.crs, maska,
                      float(abs(transformacja.a)), sciezka)


def wczytaj_nmpt(sciezka: str, siatka: Siatka,
                 ostrzezenia=None) -> np.ndarray:
    """Dopasowuje model wysokości do siatki zdjęcia, po współrzędnych."""
    if ostrzezenia is None:
        ostrzezenia = []
    BRAK = -3.0e38
    wysokosc, szerokosc = siatka.ksztalt
    wynik = np.full((wysokosc, szerokosc), BRAK, dtype=np.float64)

    with rasterio.open(sciezka) as plik:
        reproject(
            source=rasterio.band(plik, 1),
            destination=wynik,
            src_transform=plik.transform,
            src_crs=plik.crs,
            src_nodata=plik.nodata,
            dst_transform=siatka.transformacja,
            dst_crs=siatka.crs,
            dst_nodata=BRAK,
            resampling=Resampling.bilinear)

    brakuje = (~np.isfinite(wynik)) | (wynik <= BRAK / 2.0) \
        | (np.abs(wynik) > 1.0e6)
    if brakuje.all():
        raise ValueError(
            "Model wysokości nie pokrywa się ze zdjęciem. Sprawdź, czy "
            "oba pliki obejmują ten sam teren i mają ten sam układ "
            "współrzędnych.")
    if brakuje.any():
        udzial = float(brakuje.mean())
        wynik[brakuje] = np.median(wynik[~brakuje])
        if udzial > 0.02:
            ostrzezenia.append(
                "model wysokości nie pokrywa {0:.0f} procent zdjęcia; "
                "te miejsca wypełniono medianą".format(udzial * 100))
    return wynik


def zapisz_klasyfikacje(sciezka: str, mapa: np.ndarray, siatka: Siatka,
                        nazwy_klas, kolory) -> str:
    """Zapisuje mapę jako GeoTIFF z paletą i plikiem stylu .qml."""
    wysokosc, szerokosc = mapa.shape
    paleta = {0: (0, 0, 0, 0)}
    for numer, kolor in enumerate(kolory, start=1):
        paleta[numer] = tuple(kolor) + (255,)

    with rasterio.open(
            sciezka, "w", driver="GTiff", width=szerokosc, height=wysokosc,
            count=1, dtype="uint8", crs=siatka.crs,
            transform=siatka.transformacja, nodata=0,
            compress="lzw", tiled=True) as plik:
        plik.write(np.clip(mapa, 0, 255).astype(np.uint8), 1)
        plik.write_colormap(1, paleta)

    _zapisz_qml(os.path.splitext(sciezka)[0] + ".qml", nazwy_klas, kolory)
    return sciezka


def _zapisz_qml(sciezka: str, nazwy_klas, kolory):
    """Styl QGIS, żeby mapa otworzyła się od razu w kolorach."""
    def bezpieczne(tekst):
        return (str(tekst).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    wpisy = "\n".join(
        '        <paletteEntry value="{0}" alpha="255" label="{1}" '
        'color="#{2:02x}{3:02x}{4:02x}"/>'.format(
            numer, bezpieczne(nazwa), kolor[0], kolor[1], kolor[2])
        for numer, (nazwa, kolor)
        in enumerate(zip(nazwy_klas, kolory), start=1))

    tresc = (
        "<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>\n"
        '<qgis version="3.22" styleCategories="AllStyleCategories">\n'
        "  <pipe>\n"
        '    <rasterrenderer type="paletted" band="1" opacity="1" '
        'alphaBand="-1">\n'
        "      <colorPalette>\n" + wpisy + "\n"
        "      </colorPalette>\n"
        "    </rasterrenderer>\n"
        "  </pipe>\n"
        "  <blendMode>0</blendMode>\n"
        "</qgis>\n")
    with open(sciezka, "w", encoding="utf-8") as plik:
        plik.write(tresc)
