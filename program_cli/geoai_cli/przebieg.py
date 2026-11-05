# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Wspólny przebieg obliczeń: od zdjęcia do mapy.

Tu mieszka to, co robią oba polecenia — „ucz” i „klasyfikuj”. Dzięki
temu jedno i drugie dzieli zdjęcie na obiekty i mierzy je dokładnie
tak samo.
"""
from __future__ import annotations

import numpy as np

from . import raster
from .rdzen import classifier, features, refine, slic

KOLORY_DOMYSLNE = [
    (140, 109, 79), (123, 191, 74), (47, 143, 62), (201, 216, 74),
    (47, 127, 209), (31, 107, 47), (158, 158, 158), (209, 73, 91),
    (109, 76, 65), (224, 160, 48), (0, 137, 123), (94, 53, 177),
]

PODPOWIEDZI_KOLOROW = {
    "las": (31, 107, 47), "drzew": (31, 107, 47),
    "traw": (123, 191, 74), "łąk": (201, 216, 74), "lak": (201, 216, 74),
    "roln": (224, 192, 96), "upraw": (224, 192, 96), "pole": (224, 192, 96),
    "wod": (47, 127, 209), "rzek": (47, 127, 209), "staw": (47, 127, 209),
    "zabudow": (209, 73, 91), "budyn": (209, 73, 91), "dach": (209, 73, 91),
    "drog": (158, 158, 158), "asfalt": (112, 112, 112),
    "gleb": (140, 109, 79), "grunt": (140, 109, 79),
}


def kolor_dla_klasy(nazwa: str, numer: int):
    """Dobiera kolor po nazwie klasy, a gdy nie rozpozna — z listy."""
    male = nazwa.lower()
    for fragment, kolor in PODPOWIEDZI_KOLOROW.items():
        if fragment in male:
            return kolor
    return KOLORY_DOMYSLNE[(numer - 1) % len(KOLORY_DOMYSLNE)]


def podziel_i_zmierz(siatka, sciezka_nmpt=None, rozdzielczosc=0.0,
                     wielkosc_obiektu=10.0, liczba_obiektow=0,
                     zwartosc=0.15, wygladzenie=2.5, mowi=print):
    """Dzieli zdjęcie na obiekty i mierzy każdy z nich.

    Zwraca ``(etykiety, identyfikatory, macierz_cech, nazwy_cech,
    ostrzezenia)``.
    """
    ostrzezenia = []
    nmpt = None
    if sciezka_nmpt:
        nmpt = raster.wczytaj_nmpt(sciezka_nmpt, siatka, ostrzezenia)
        for uwaga in ostrzezenia:
            mowi("    uwaga: {0}".format(uwaga))
        szerokosc_m = min(siatka.ksztalt) * siatka.piksel
        if szerokosc_m < 80.0:
            mowi("    uwaga: zdjęcie ma tylko {0:.0f} m w poprzek, więc "
                 "grunt szacujemy oknem węższym niż zalecane 40 m; "
                 "szerokie dachy mogą wyjść z zerową wysokością nad "
                 "gruntem".format(szerokosc_m))

    if liczba_obiektow > 0:
        zadane = int(liczba_obiektow)
    else:
        zadane = max(100, int(round(siatka.powierzchnia_m2
                                    / max(wielkosc_obiektu, 0.01))))

    mowi("    dzielę na obiekty (zamawiam {0})...".format(zadane))
    etykiety = slic.slic_segments(siatka.tablica, zadane, zwartosc,
                                  wygladzenie, mask=siatka.maska)
    powstalo = int(etykiety.max())

    rozmiary = np.bincount(etykiety.ravel())[1:]
    rozmiary = rozmiary[rozmiary > 0] * (siatka.piksel ** 2)
    mediana = float(np.median(rozmiary)) if rozmiary.size else 0.0
    mowi("    powstało {0} obiektów, mediana powierzchni {1:.2f} m2"
         .format(powstalo, mediana))

    mowi("    mierzę cechy obiektów...")
    identyfikatory, macierz, nazwy = features.compute_features(
        siatka.tablica, etykiety, siatka.piksel, dsm=nmpt)
    return etykiety, identyfikatory, macierz, nazwy, ostrzezenia


def zrob_mape(model, etykiety, identyfikatory, macierz, siatka,
              klasy, mmu_pikseli=0, zielona=None, druga=None,
              prog_zielonosci=0.0, okno=3, mowi=print):
    """Nadaje klasę każdemu obiektowi i składa z tego mapę."""
    przewidziane, pewnosc = classifier.predict(model, macierz)

    numery = {wpis["nazwa"]: wpis["numer"] for wpis in klasy}
    przelicznik = np.zeros(int(identyfikatory.max()) + 1, dtype=np.int32)
    for identyfikator, nazwa in zip(identyfikatory, przewidziane):
        przelicznik[int(identyfikator)] = numery.get(str(nazwa), 0)
    mapa = przelicznik[etykiety]
    mapa[~siatka.maska] = 0

    if zielona and druga and zielona != druga:
        mapa, do_zieleni, do_drugiej = refine.refine_by_greenness(
            mapa, siatka.tablica, etykiety, numery[zielona], numery[druga],
            prog_zielonosci, okno, refine.MODE_WHOLE)
        mowi("    dociąganie po zieloności: {0} pikseli do klasy {1}, "
             "{2} do {3}".format(do_zieleni, zielona, do_drugiej, druga))

    if mmu_pikseli > 0:
        przed = mapa.copy()
        mapa = refine.sieve(mapa, int(mmu_pikseli))
        mowi("    czyszczenie drobnych płatów: {0} pikseli przepisanych"
             .format(int(np.count_nonzero(przed != mapa))))

    return mapa, przewidziane, pewnosc


def udzialy_klas(mapa, siatka, klasy):
    """Udział i powierzchnia każdej klasy na gotowej mapie."""
    razem = float(np.count_nonzero(mapa > 0))
    wynik = []
    for wpis in klasy:
        ile = float(np.count_nonzero(mapa == wpis["numer"]))
        if razem <= 0:
            continue
        wynik.append({
            "nazwa": wpis["nazwa"],
            "udzial": ile / razem,
            "hektary": ile * (siatka.piksel ** 2) / 10000.0,
        })
    return wynik
