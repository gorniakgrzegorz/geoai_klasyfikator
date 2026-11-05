# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Zapisywanie i wczytywanie nauczonego modelu.

Model to jeden plik .geoai: zwykłe archiwum ZIP z nauczonym lasem
losowym, listą klas wraz z kolorami, listą cech i wszystkimi
ustawieniami, przy których powstał. Dzięki temu klasyfikacja setki
zdjęć przebiega dokładnie tak samo jak nauka, a plik można przekazać
komuś innemu albo dołączyć do artykułu.
"""
from __future__ import annotations

import json
import os
import pickle      # nosec B403 - patrz uwaga o zaufaniu poniżej
import zipfile
from datetime import datetime

WERSJA_FORMATU = 1
ROZSZERZENIE = ".geoai"


class BladModelu(Exception):
    """Model jest nieczytelny albo nie pasuje do zdjęcia."""


# UWAGA O ZAUFANIU
# Nauczony las losowy zapisujemy modułem pickle, bo tak robi to cały
# ekosystem scikit-learn (również joblib pod spodem). Wczytanie pliku
# pickle potrafi wykonać dowolny kod, więc obowiązuje jedna zasada:
#
#     otwieraj tylko te pliki .geoai, które sam stworzyłeś albo
#     dostałeś od kogoś, komu ufasz
#
# Zanim cokolwiek odpakujemy, sprawdzamy, czy plik jest archiwum ZIP
# i czy ma opis o właściwej wersji formatu - to odsiewa pomyłki,
# choć nie zastąpi ostrożności.


def zapisz(sciezka: str, model, nazwy_cech, klasy, ustawienia) -> str:
    """Zapisuje wszystko, co potrzebne do powtórzenia klasyfikacji.

    ``klasy`` to lista słowników ``{"nazwa", "numer", "kolor"}``,
    ``ustawienia`` to parametry podziału na obiekty i pomiarów.
    """
    if not sciezka.lower().endswith(ROZSZERZENIE):
        sciezka += ROZSZERZENIE

    opis = {
        "format": WERSJA_FORMATU,
        "utworzono": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "program": "GeoAI Klasyfikator",
        "cechy": list(nazwy_cech),
        "klasy": klasy,
        "ustawienia": ustawienia,
    }
    with zipfile.ZipFile(sciezka, "w", zipfile.ZIP_DEFLATED) as paczka:
        paczka.writestr("opis.json",
                        json.dumps(opis, ensure_ascii=False, indent=2))
        paczka.writestr("las.pickle", pickle.dumps(model, protocol=4))
    return sciezka


def wczytaj(sciezka: str):
    """Odtwarza model z pliku. Zwraca ``(model, opis)``."""
    if not os.path.isfile(sciezka):
        raise BladModelu(
            "Nie znalazłem pliku modelu: {0}".format(sciezka))
    try:
        with zipfile.ZipFile(sciezka) as paczka:
            opis = json.loads(paczka.read("opis.json").decode("utf-8"))
            model = pickle.loads(                       # nosec B301
                paczka.read("las.pickle"))
    except Exception as blad:
        raise BladModelu(
            "Plik {0} nie wygląda na model GeoAI ({1}). Czy na pewno "
            "podajesz plik utworzony poleceniem „ucz”?"
            .format(os.path.basename(sciezka), blad))

    if opis.get("format") != WERSJA_FORMATU:
        raise BladModelu(
            "Model zapisano w innej wersji formatu ({0}). Naucz go "
            "jeszcze raz tą wersją programu."
            .format(opis.get("format")))
    return model, opis


def sprawdz_zgodnosc(opis: dict, ma_nmpt: bool):
    """Pilnuje, by zdjęcie dało się opisać tak samo jak przy nauce."""
    cechy = opis.get("cechy", [])
    wymaga_nmpt = any(nazwa.startswith(("dsm_", "slope_", "hag_"))
                      for nazwa in cechy)
    if wymaga_nmpt and not ma_nmpt:
        raise BladModelu(
            "Ten model uczył się z modelem wysokości (24 cechy), więc "
            "do klasyfikacji też go potrzebuje. Wskaż folder z plikami "
            "NMPT przez --nmpt albo naucz model bez wysokości.")
    if not wymaga_nmpt and ma_nmpt:
        return ("Model uczył się bez modelu wysokości, więc podany NMPT "
                "zostanie pominięty.")
    return None


def opis_tekstowy(opis: dict) -> str:
    """Czytelne podsumowanie modelu, do polecenia „info”."""
    ustawienia = opis.get("ustawienia", {})
    klasy = opis.get("klasy", [])
    linie = [
        "Model GeoAI Klasyfikator",
        "  utworzono:        {0}".format(opis.get("utworzono", "?")),
        "  klas:             {0} ({1})".format(
            len(klasy), ", ".join(k["nazwa"] for k in klasy)),
        "  cech:             {0}".format(len(opis.get("cechy", []))),
        "  z modelem wysokości: {0}".format(
            "tak" if any(n.startswith(("dsm_", "slope_", "hag_"))
                         for n in opis.get("cechy", [])) else "nie"),
        "",
        "Ustawienia, przy których powstał:",
    ]
    etykiety = {
        "rozdzielczosc": "rozdzielczość robocza",
        "wielkosc_obiektu": "wielkość obiektu (m2)",
        "zwartosc": "zwartość obiektów",
        "wygladzenie": "wygładzenie",
        "przykladow": "przykładów uczących",
    }
    for klucz, wartosc in ustawienia.items():
        linie.append("  {0:22s} {1}".format(
            etykiety.get(klucz, klucz) + ":", wartosc))
    return "\n".join(linie)
