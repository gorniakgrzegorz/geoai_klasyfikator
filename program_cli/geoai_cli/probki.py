# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Wczytywanie przykładów uczących z pliku wektorowego.

W wersji okienkowej przykłady wskazuje się klikając po mapie. Tutaj
podaje się je raz, w pliku: poligony albo punkty z kolumną, w której
wpisana jest nazwa klasy. Taki plik łatwo przygotować w QGIS-ie
(Warstwa → Utwórz warstwę → Nowa warstwa GeoPackage) i równie łatwo
przekazać komuś innemu razem z projektem.
"""
from __future__ import annotations

import os
from collections import Counter

import fiona
import numpy as np
from fiona.transform import transform_geom
from rasterio.features import rasterize

ROZSZERZENIA = (".gpkg", ".shp", ".geojson", ".json", ".gml", ".kml",
                ".sqlite")


def wczytaj_klasy(sciezka: str, pole: str) -> list:
    """Nazwy klas występujące w pliku, w kolejności pierwszego wystąpienia."""
    nazwy = []
    with fiona.open(sciezka) as warstwa:
        _sprawdz_pole(warstwa, pole, sciezka)
        for obiekt in warstwa:
            wartosc = obiekt["properties"].get(pole)
            if wartosc is None or str(wartosc).strip() == "":
                continue
            nazwa = str(wartosc).strip()
            if nazwa not in nazwy:
                nazwy.append(nazwa)
    if not nazwy:
        raise ValueError(
            "W pliku {0} kolumna „{1}” jest wszędzie pusta — nie ma "
            "z czego się uczyć.".format(os.path.basename(sciezka), pole))
    return nazwy


def _sprawdz_pole(warstwa, pole, sciezka):
    dostepne = list(warstwa.schema["properties"].keys())
    if pole not in dostepne:
        raise ValueError(
            "Plik {0} nie ma kolumny „{1}”. Kolumny, które w nim są: "
            "{2}. Podaj właściwą przez --pole.".format(
                os.path.basename(sciezka), pole, ", ".join(dostepne)))


def wypal_na_siatke(sciezka: str, pole: str, numery_klas: dict,
                    siatka) -> np.ndarray:
    """Rysuje przykłady na siatce zdjęcia jako numery klas.

    Zwraca tablicę tej samej wielkości co zdjęcie: 0 tam, gdzie nie ma
    przykładu, a numer klasy tam, gdzie jest. Punkty rysujemy z opcją
    „wszystkie dotknięte piksele”, żeby pojedynczy punkt nie przepadł
    przy zgrubnej siatce roboczej.
    """
    wysokosc, szerokosc = siatka.ksztalt
    ksztalty = []

    with fiona.open(sciezka) as warstwa:
        _sprawdz_pole(warstwa, pole, sciezka)
        crs_zrodla = warstwa.crs
        crs_celu = siatka.crs.to_dict() if hasattr(siatka.crs, "to_dict") \
            else siatka.crs
        trzeba_przeliczyc = bool(crs_zrodla) and bool(crs_celu) \
            and dict(crs_zrodla) != dict(crs_celu)

        for obiekt in warstwa:
            wartosc = obiekt["properties"].get(pole)
            if wartosc is None:
                continue
            nazwa = str(wartosc).strip()
            numer = numery_klas.get(nazwa)
            if not numer:
                continue
            geometria = obiekt["geometry"]
            if geometria is None:
                continue
            if trzeba_przeliczyc:
                geometria = transform_geom(crs_zrodla, crs_celu, geometria)
            ksztalty.append((geometria, numer))

    if not ksztalty:
        raise ValueError(
            "Żaden przykład z pliku {0} nie pasuje do listy klas."
            .format(os.path.basename(sciezka)))

    return rasterize(
        ksztalty, out_shape=(wysokosc, szerokosc),
        transform=siatka.transformacja, fill=0, all_touched=True,
        dtype=np.int32)


def przypisz_obiektom(wypalone: np.ndarray, etykiety: np.ndarray,
                      identyfikatory: np.ndarray,
                      minimalne_pokrycie: float = 0.5) -> dict:
    """Łączy przykłady z obiektami: który obiekt należy do której klasy.

    Obiekt dostaje klasę, jeśli przykłady pokrywają dość dużą jego
    część i nie są ze sobą sprzeczne. Obiekt, na którym spotykają się
    dwie klasy, zostaje pominięty — leży na granicy i nauczyłby
    klasyfikator nieprawdy.
    """
    wynik, sporne = {}, 0
    maska = wypalone > 0
    if not maska.any():
        return wynik

    etykiety_pod = etykiety[maska]
    klasy_pod = wypalone[maska]
    porzadek = np.argsort(etykiety_pod, kind="stable")
    etykiety_pod = etykiety_pod[porzadek]
    klasy_pod = klasy_pod[porzadek]

    granice = np.flatnonzero(np.diff(etykiety_pod)) + 1
    poczatki = np.concatenate([[0], granice])
    konce = np.concatenate([granice, [len(etykiety_pod)]])
    wielkosci = np.bincount(etykiety.ravel())

    for poczatek, koniec in zip(poczatki, konce):
        obiekt = int(etykiety_pod[poczatek])
        if obiekt <= 0:
            continue
        liczby = Counter(klasy_pod[poczatek:koniec].tolist())
        (numer, ile), = liczby.most_common(1)
        if len(liczby) > 1 and ile < 0.8 * (koniec - poczatek):
            sporne += 1
            continue
        wielkosc = int(wielkosci[obiekt]) if obiekt < len(wielkosci) else 0
        if wielkosc and ile < minimalne_pokrycie * wielkosc:
            continue
        wynik[obiekt] = int(numer)

    wynik["__sporne__"] = sporne
    return wynik


def zapisz_przyklady_wzorcowe(sciezka: str, nazwy_klas, crs) -> str:
    """Tworzy pusty plik przykładów, gotowy do wypełnienia w QGIS-ie."""
    schemat = {"geometry": "Polygon",
               "properties": {"klasa": "str:64", "uwagi": "str:200"}}
    with fiona.open(sciezka, "w", driver="GPKG", schema=schemat,
                    crs=crs, layer="przyklady"):
        pass
    return sciezka
