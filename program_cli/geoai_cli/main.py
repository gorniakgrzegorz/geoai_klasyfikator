# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
GeoAI Klasyfikator — wiersz poleceń.

Dwa polecenia wystarczą do wszystkiego:

    ucz          nauczenie modelu na jednym zdjęciu z przykładami
    klasyfikuj   zastosowanie modelu do wszystkich zdjęć w folderze

Pomocniczo:

    info         co siedzi w pliku modelu
    sprawdz      czy wszystkie biblioteki są na miejscu
    szablon      pusty plik przykładów do wypełnienia w QGIS

© Grzegorz Górniak <gorniakgrzegorz@gmail.com>
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

import numpy as np

OPIS = """GeoAI Klasyfikator — obiektowa klasyfikacja pokrycia terenu
ze zdjęć z drona i zdjęć lotniczych, z wiersza poleceń.

Typowa kolejność pracy:

  1. Przygotuj w QGIS plik z przykładami: poligony z kolumną "klasa".
  2. Naucz model na jednym, reprezentatywnym zdjęciu:
       geoai ucz --zdjecie proba.tif --probki przyklady.gpkg \\
                 --model moj_model.geoai
  3. Puść model na cały folder:
       geoai klasyfikuj --folder ./naloty --model moj_model.geoai \\
                        --wyjscie ./mapy
"""

PRZYKLADY = """
Przykłady:

  geoai sprawdz
      sprawdza, czy wszystkie biblioteki są zainstalowane

  geoai szablon --zdjecie proba.tif --plik przyklady.gpkg
      tworzy pusty plik przykładów w układzie zdjęcia

  geoai ucz --zdjecie proba.tif --probki przyklady.gpkg \\
            --nmpt proba_nmpt.tif --rozdzielczosc 0.05 \\
            --wielkosc-obiektu 10 --model model.geoai
      uczy model; --nmpt jest opcjonalne, ale bardzo pomaga

  geoai klasyfikuj --folder ./naloty --model model.geoai \\
                   --wyjscie ./mapy --nmpt-folder ./nmpt --mmu 10
      klasyfikuje wszystkie zdjęcia z folderu, zapisuje mapy i raport

  geoai info --model model.geoai
      pokazuje, na czym i jak model był uczony
"""


# ── drobne pomocniki wypisywania ─────────────────────────────────────

class Dziennik:
    """Wypisywanie z poziomami szczegółowości."""

    def __init__(self, cicho=False, gadatliwie=False):
        self.cicho = cicho
        self.gadatliwie = gadatliwie

    def __call__(self, tekst=""):
        if not self.cicho:
            print(tekst, flush=True)

    def szczegol(self, tekst):
        if self.gadatliwie and not self.cicho:
            print(tekst, flush=True)

    def blad(self, tekst):
        print("BŁĄD: " + tekst, file=sys.stderr, flush=True)

    def naglowek(self, tekst):
        if self.cicho:
            return
        print()
        print(tekst)
        print("=" * len(tekst), flush=True)


def _czas(sekundy: float) -> str:
    if sekundy < 60:
        return "{0:.0f} s".format(sekundy)
    minuty, reszta = divmod(int(sekundy), 60)
    return "{0} min {1} s".format(minuty, reszta)


# ── polecenie: sprawdz ───────────────────────────────────────────────

def polecenie_sprawdz(args, mowi):
    mowi.naglowek("Sprawdzanie środowiska")
    braki = []

    for nazwa, opis in (("numpy", "obliczenia"),
                        ("rasterio", "odczyt i zapis zdjęć"),
                        ("fiona", "odczyt plików z przykładami")):
        try:
            modul = __import__(nazwa)
            wersja = getattr(modul, "__version__", "?")
            mowi("  [jest]  {0:12s} {1:10s} {2}".format(nazwa, wersja, opis))
        except ImportError:
            braki.append(nazwa)
            mowi("  [BRAK]  {0:12s} {1:10s} {2}".format(nazwa, "", opis))

    for nazwa, opis in (("scikit-image", "szybszy podział na obiekty"),
                        ("scikit-learn", "szybszy Random Forest"),
                        ("scipy", "szybsze filtry")):
        modul = {"scikit-image": "skimage",
                 "scikit-learn": "sklearn"}.get(nazwa, nazwa)
        try:
            __import__(modul)
            mowi("  [jest]  {0:12s} {1:10s} {2}".format(nazwa, "", opis))
        except ImportError:
            mowi("  [opcj.] {0:12s} {1:10s} {2}".format(nazwa, "", opis))

    if braki:
        mowi()
        mowi("Brakuje bibliotek koniecznych do pracy. Zainstaluj je "
             "poleceniem:")
        mowi("    python -m pip install " + " ".join(braki))
        return 1

    try:
        from .rdzen import deps
        raport = deps.engine_report()
        mowi()
        mowi("Silniki obliczeniowe:")
        mowi("  podział na obiekty: {0}".format(raport["segmentation"]))
        mowi("  Random Forest:         {0}".format(raport["classifier"]))
        if not raport["exact"]:
            mowi()
            mowi("Działa, ale na dużych zdjęciach będzie wolno. Dla "
                 "pełnej szybkości:")
            mowi("    python -m pip install scikit-image scikit-learn")
    except ImportError as blad:
        mowi.blad(str(blad))
        return 1

    mowi()
    mowi("Wszystko na miejscu.")
    return 0


# ── polecenie: szablon ───────────────────────────────────────────────

def polecenie_szablon(args, mowi):
    from . import probki, raster

    mowi.naglowek("Tworzenie pustego pliku przykładów")
    siatka = raster.wczytaj_rgb(args.zdjecie, 0.0)
    sciezka = probki.zapisz_przyklady_wzorcowe(
        args.plik, [], siatka.crs.to_wkt() if siatka.crs else None)
    mowi("  Utworzono: {0}".format(sciezka))
    mowi()
    mowi("Co dalej:")
    mowi("  1. Otwórz ten plik i zdjęcie w QGIS.")
    mowi("  2. Włącz edycję warstwy „przyklady”.")
    mowi("  3. Rysuj poligony na terenach, które znasz, i w kolumnie")
    mowi("     „klasa” wpisuj nazwę: trawa, droga, zabudowa, las...")
    mowi("  4. Na każdą klasę daj kilkanaście poligonów, rozrzuconych")
    mowi("     po całym zdjęciu i pokazujących każdą jej odmianę.")
    mowi("  5. Zapisz i naucz model poleceniem „geoai ucz”.")
    return 0


# ── polecenie: ucz ───────────────────────────────────────────────────

def polecenie_ucz(args, mowi):
    from . import model as mod
    from . import probki, przebieg, raster
    from .rdzen import classifier

    poczatek = time.time()
    mowi.naglowek("Nauka modelu")

    if not os.path.isfile(args.zdjecie):
        mowi.blad("Nie ma takiego zdjęcia: {0}".format(args.zdjecie))
        return 2
    if not os.path.isfile(args.probki):
        mowi.blad("Nie ma takiego pliku z przykładami: {0}"
                  .format(args.probki))
        return 2

    mowi("  zdjęcie:   {0}".format(os.path.basename(args.zdjecie)))
    mowi("  przykłady: {0} (kolumna „{1}”)"
         .format(os.path.basename(args.probki), args.pole))
    if args.nmpt:
        mowi("  wysokość:  {0}".format(os.path.basename(args.nmpt)))

    nazwy_klas = probki.wczytaj_klasy(args.probki, args.pole)
    mowi("  klas:      {0} ({1})".format(len(nazwy_klas),
                                         ", ".join(nazwy_klas)))

    klasy = [{"nazwa": nazwa, "numer": numer,
              "kolor": list(przebieg.kolor_dla_klasy(nazwa, numer))}
             for numer, nazwa in enumerate(nazwy_klas, start=1)]
    numery = {wpis["nazwa"]: wpis["numer"] for wpis in klasy}

    mowi()
    mowi("  wczytuję zdjęcie...")
    siatka = raster.wczytaj_rgb(args.zdjecie, args.rozdzielczosc)
    mowi("    siatka {0} na {1} pikseli, po {2:.4f} na piksel, {3:.2f} ha"
         .format(siatka.ksztalt[1], siatka.ksztalt[0], siatka.piksel,
                 siatka.powierzchnia_m2 / 10000.0))

    etykiety, identyfikatory, macierz, nazwy_cech, _ = \
        przebieg.podziel_i_zmierz(
            siatka, args.nmpt, args.rozdzielczosc, args.wielkosc_obiektu,
            args.liczba_obiektow, args.zwartosc, args.wygladzenie, mowi)
    mowi("    cech na obiekt: {0}".format(len(nazwy_cech)))

    mowi()
    mowi("  łączę przykłady z obiektami...")
    wypalone = probki.wypal_na_siatke(args.probki, args.pole, numery, siatka)
    przypisane = probki.przypisz_obiektom(wypalone, etykiety,
                                          identyfikatory, args.pokrycie)
    sporne = przypisane.pop("__sporne__", 0)
    if sporne:
        mowi("    pominięto {0} obiektów leżących na granicy dwóch klas"
             .format(sporne))
    if len(przypisane) < 2:
        mowi.blad(
            "Z przykładów wyszło tylko {0} obiektów uczących. Narysuj "
            "większe poligony albo zmniejsz wielkość obiektu."
            .format(len(przypisane)))
        return 1

    pozycje = {int(ident): wiersz for wiersz, ident
               in enumerate(identyfikatory)}
    wiersze, etykietki = [], []
    nazwy_po_numerze = {wpis["numer"]: wpis["nazwa"] for wpis in klasy}
    for obiekt, numer in przypisane.items():
        wiersz = pozycje.get(int(obiekt))
        if wiersz is not None:
            wiersze.append(wiersz)
            etykietki.append(nazwy_po_numerze[numer])

    etykietki = np.array(etykietki)
    liczby = {nazwa: int(np.count_nonzero(etykietki == nazwa))
              for nazwa in nazwy_klas}
    mowi("    obiektów uczących: {0}".format(len(wiersze)))
    for nazwa in nazwy_klas:
        mowi("      {0:24s} {1}".format(nazwa, liczby[nazwa]))

    puste = [nazwa for nazwa, ile in liczby.items() if ile == 0]
    if puste:
        mowi.blad(
            "Klasy bez ani jednego obiektu uczącego: {0}. Narysuj dla "
            "nich przykłady albo usuń je z pliku."
            .format(", ".join(puste)))
        return 1
    if len(set(etykietki.tolist())) < 2:
        mowi.blad("Do nauki potrzebne są przykłady co najmniej dwóch klas.")
        return 1

    duza, mala, stosunek = classifier.niezrownowazenie(etykietki)
    if stosunek >= 5.0:
        mowi("    uwaga: klasa „{0}” ma {1:.0f} razy więcej przykładów "
             "niż „{2}”; Random Forest tego nie wyrównuje"
             .format(duza, stosunek, mala))

    if args.separowalnosc:
        mowi()
        mowi("  sprawdzam, czy klasy da się rozróżnić...")
        raport = classifier.separability_report(
            macierz[wiersze], etykietki, nazwy_cech)
        oceny = {"good": "dobrze", "fair": "znośnie", "poor": "SŁABO"}
        for para in raport["pairs"]:
            mowi("    {0:>16s} - {1:16s} {2:.2f}  {3}".format(
                para["a"][:16], para["b"][:16], para["jm"],
                oceny.get(para["verdict"], "")))

    mowi()
    mowi("  uczę Random Forest...")
    las = classifier.train(macierz[wiersze], etykietki)

    waznosc = classifier.feature_importance(las, nazwy_cech)
    if waznosc:
        mowi("    najważniejsze cechy: " + ", ".join(
            "{0} ({1:.0f} proc.)".format(nazwa, wartosc * 100)
            for nazwa, wartosc in waznosc[:5]))

    ustawienia = {
        "rozdzielczosc": args.rozdzielczosc,
        "wielkosc_obiektu": args.wielkosc_obiektu,
        "liczba_obiektow": args.liczba_obiektow,
        "zwartosc": args.zwartosc,
        "wygladzenie": args.wygladzenie,
        "przykladow": len(wiersze),
    }
    sciezka = mod.zapisz(args.model, las, nazwy_cech, klasy, ustawienia)
    mowi()
    mowi("  Model zapisany: {0}".format(sciezka))
    mowi("  Czas: {0}".format(_czas(time.time() - poczatek)))
    mowi()
    mowi("Teraz możesz puścić go na cały folder:")
    mowi("    geoai klasyfikuj --folder ./zdjecia --model {0} "
         "--wyjscie ./mapy".format(os.path.basename(sciezka)))
    return 0


# ── polecenie: klasyfikuj ────────────────────────────────────────────

def _znajdz_nmpt(sciezka_zdjecia, folder_nmpt, przyrostek):
    """Dopasowuje plik wysokości do zdjęcia po nazwie."""
    if not folder_nmpt:
        return None
    trzon = os.path.splitext(os.path.basename(sciezka_zdjecia))[0]
    kandydaci = [trzon + przyrostek + ".tif",
                 trzon + przyrostek + ".tiff",
                 trzon + ".tif", trzon + ".tiff"]
    for nazwa in kandydaci:
        pelna = os.path.join(folder_nmpt, nazwa)
        if os.path.isfile(pelna):
            return pelna
    return None


def polecenie_klasyfikuj(args, mowi):
    from . import model as mod
    from . import przebieg, raster

    poczatek = time.time()
    mowi.naglowek("Klasyfikacja wsadowa")

    if not os.path.isdir(args.folder):
        mowi.blad("Nie ma takiego folderu: {0}".format(args.folder))
        return 2

    try:
        las, opis = mod.wczytaj(args.model)
    except mod.BladModelu as blad:
        mowi.blad(str(blad))
        return 2

    klasy = opis["klasy"]
    nazwy_klas = [wpis["nazwa"] for wpis in klasy]
    kolory = [tuple(wpis["kolor"]) for wpis in klasy]
    ustawienia = opis.get("ustawienia", {})

    zdjecia = raster.zdjecia_w_folderze(args.folder, args.rekurencyjnie)
    if not zdjecia:
        mowi.blad(
            "W folderze {0} nie ma żadnego pliku rastrowego ({1})."
            .format(args.folder, ", ".join(raster.ROZSZERZENIA)))
        return 1

    os.makedirs(args.wyjscie, exist_ok=True)
    mowi("  model:    {0} ({1} klas: {2})".format(
        os.path.basename(args.model), len(klasy), ", ".join(nazwy_klas)))
    mowi("  folder:   {0}".format(args.folder))
    mowi("  wyjście:  {0}".format(args.wyjscie))
    mowi("  zdjęć do przerobienia: {0}".format(len(zdjecia)))

    # ustawienia podziału bierzemy z modelu, żeby każde zdjęcie było
    # opisane tak samo jak to, na którym model się uczył
    rozdzielczosc = (args.rozdzielczosc if args.rozdzielczosc > 0
                     else float(ustawienia.get("rozdzielczosc", 0.0)))
    wielkosc = float(ustawienia.get("wielkosc_obiektu", 10.0))
    zwartosc = float(ustawienia.get("zwartosc", 0.15))
    wygladzenie = float(ustawienia.get("wygladzenie", 2.5))

    mmu_pikseli = 0
    if args.mmu > 0:
        mmu_pikseli = -1       # przeliczymy przy pierwszym zdjęciu

    wiersze_raportu = []
    udane, nieudane, pominiete = 0, 0, 0

    for numer, sciezka in enumerate(zdjecia, start=1):
        nazwa = os.path.basename(sciezka)
        wyjscie = os.path.join(
            args.wyjscie,
            os.path.splitext(nazwa)[0] + args.przyrostek + ".tif")

        mowi()
        mowi("[{0}/{1}] {2}".format(numer, len(zdjecia), nazwa))

        if os.path.exists(wyjscie) and not args.nadpisuj:
            mowi("    pomijam — wynik już istnieje "
                 "(użyj --nadpisuj, żeby policzyć ponownie)")
            pominiete += 1
            continue

        czas_zdjecia = time.time()
        try:
            nmpt = _znajdz_nmpt(sciezka, args.nmpt_folder,
                                args.nmpt_przyrostek)
            uwaga = mod.sprawdz_zgodnosc(opis, nmpt is not None)
            if uwaga:
                mowi("    uwaga: {0}".format(uwaga))
                nmpt = None
            if args.nmpt_folder and nmpt is None:
                raise ValueError(
                    "nie znalazłem pliku wysokości dla tego zdjęcia "
                    "w folderze {0}".format(args.nmpt_folder))

            siatka = raster.wczytaj_rgb(sciezka, rozdzielczosc)
            mowi("    siatka {0} na {1} pikseli, {2:.2f} ha".format(
                siatka.ksztalt[1], siatka.ksztalt[0],
                siatka.powierzchnia_m2 / 10000.0))

            etykiety, identyfikatory, macierz, nazwy_cech, _ = \
                przebieg.podziel_i_zmierz(
                    siatka, nmpt, rozdzielczosc, wielkosc, 0,
                    zwartosc, wygladzenie, mowi.szczegol)

            if list(nazwy_cech) != list(opis["cechy"]):
                raise ValueError(
                    "zdjęcie opisano {0} cechami, a model uczył się na "
                    "{1} — sprawdź, czy wszystkie zdjęcia mają model "
                    "wysokości".format(len(nazwy_cech),
                                       len(opis["cechy"])))

            if mmu_pikseli == -1:
                mmu_pikseli = int(round(args.mmu / (siatka.piksel ** 2)))
                mowi("    najmniejszy płat: {0} m² = {1} pikseli"
                     .format(args.mmu, mmu_pikseli))

            mapa, _, pewnosc = przebieg.zrob_mape(
                las, etykiety, identyfikatory, macierz, siatka, klasy,
                max(mmu_pikseli, 0), args.klasa_zielona, args.klasa_druga,
                args.prog_zielonosci, args.okno, mowi.szczegol)

            raster.zapisz_klasyfikacje(wyjscie, mapa, siatka,
                                       nazwy_klas, kolory)

            udzialy = przebieg.udzialy_klas(mapa, siatka, klasy)
            niepewne = int(np.count_nonzero(pewnosc < 0.5))
            mowi("    zapisano: {0}".format(os.path.basename(wyjscie)))
            mowi("    " + ", ".join(
                "{0} {1:.1f} proc.".format(wpis["nazwa"],
                                           wpis["udzial"] * 100)
                for wpis in udzialy))
            if niepewne:
                mowi("    obiektów niepewnych (poniżej połowy głosów): "
                     "{0}".format(niepewne))

            wiersz = {"plik": nazwa, "wynik": os.path.basename(wyjscie),
                      "status": "ok",
                      "hektary": round(siatka.powierzchnia_m2 / 10000.0, 4),
                      "obiektow": int(etykiety.max()),
                      "niepewnych": niepewne,
                      "sekundy": round(time.time() - czas_zdjecia, 1)}
            for wpis in udzialy:
                wiersz["udzial_" + wpis["nazwa"]] = round(wpis["udzial"], 4)
                wiersz["ha_" + wpis["nazwa"]] = round(wpis["hektary"], 4)
            wiersze_raportu.append(wiersz)
            udane += 1

        except Exception as blad:
            mowi("    NIE UDAŁO SIĘ: {0}".format(blad))
            wiersze_raportu.append({"plik": nazwa, "wynik": "",
                                    "status": "blad: {0}".format(blad),
                                    "sekundy": round(
                                        time.time() - czas_zdjecia, 1)})
            nieudane += 1
            if args.przerwij_na_bledzie:
                mowi.blad("Przerywam na żądanie (--przerwij-na-bledzie).")
                break

    raport = os.path.join(args.wyjscie, "raport.csv")
    _zapisz_raport(raport, wiersze_raportu)

    mowi()
    mowi("=" * 54)
    mowi("Gotowe w {0}.".format(_czas(time.time() - poczatek)))
    mowi("  zrobione:  {0}".format(udane))
    if pominiete:
        mowi("  pominięte: {0} (wynik już istniał)".format(pominiete))
    if nieudane:
        mowi("  błędy:     {0}".format(nieudane))
    mowi("  raport:    {0}".format(raport))
    return 0 if nieudane == 0 else 1


def _zapisz_raport(sciezka, wiersze):
    """Zestawienie wszystkich przerobionych zdjęć, do Excela."""
    if not wiersze:
        return
    kolumny = []
    for wiersz in wiersze:
        for klucz in wiersz:
            if klucz not in kolumny:
                kolumny.append(klucz)
    with open(sciezka, "w", newline="", encoding="utf-8-sig") as plik:
        pisarz = csv.DictWriter(plik, fieldnames=kolumny, delimiter=";")
        pisarz.writeheader()
        for wiersz in wiersze:
            pisarz.writerow(wiersz)


# ── polecenie: info ──────────────────────────────────────────────────

def polecenie_info(args, mowi):
    from . import model as mod
    try:
        _, opis = mod.wczytaj(args.model)
    except mod.BladModelu as blad:
        mowi.blad(str(blad))
        return 2
    mowi()
    mowi(mod.opis_tekstowy(opis))
    mowi()
    mowi("Cechy, których używa:")
    for nazwa in opis.get("cechy", []):
        mowi("  " + nazwa)
    return 0


# ── budowa wiersza poleceń ───────────────────────────────────────────

def zbuduj_parser():
    # te dwie opcje mają działać i przed nazwą polecenia, i po niej
    wspolne = argparse.ArgumentParser(add_help=False)
    # SUPPRESS sprawia, że opcja trafia do wyniku tylko wtedy, gdy
    # ktoś ją naprawdę podał — inaczej podpolecenie nadpisywałoby
    # wartość ustawioną przed jego nazwą
    wspolne.add_argument("--cicho", action="store_true",
                         default=argparse.SUPPRESS,
                         help="nie wypisuj nic poza błędami")
    wspolne.add_argument("--gadatliwie", action="store_true",
                         default=argparse.SUPPRESS,
                         help="wypisuj także kroki pośrednie")

    parser = argparse.ArgumentParser(
        parents=[wspolne],
        prog="geoai",
        description=OPIS,
        epilog=PRZYKLADY,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wersja", action="store_true",
                        help="pokaż wersję i zakończ")

    podpolecenia = parser.add_subparsers(dest="polecenie",
                                         metavar="POLECENIE")

    # sprawdz
    podpolecenia.add_parser(
        "sprawdz", parents=[wspolne], help="sprawdź, czy wszystkie biblioteki są na miejscu",
        description="Sprawdza, czy środowisko Pythona ma wszystko, "
                    "czego program potrzebuje.")

    # szablon
    szablon = podpolecenia.add_parser(
        "szablon", parents=[wspolne], help="utwórz pusty plik przykładów do wypełnienia",
        description="Tworzy pusty plik GeoPackage w układzie zdjęcia, "
                    "gotowy do rysowania przykładów w QGIS.")
    szablon.add_argument("--zdjecie", required=True,
                         help="zdjęcie, w którego układzie ma powstać plik")
    szablon.add_argument("--plik", default="przyklady.gpkg",
                         help="nazwa tworzonego pliku "
                              "(domyślnie przyklady.gpkg)")

    # ucz
    ucz = podpolecenia.add_parser(
        "ucz", parents=[wspolne], help="naucz model na jednym zdjęciu z przykładami",
        description="Uczy model na jednym, reprezentatywnym zdjęciu. "
                    "Powstały plik .geoai stosujesz potem do całego "
                    "folderu poleceniem „klasyfikuj”.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ucz.add_argument("--zdjecie", required=True,
                     help="zdjęcie RGB, na którym się uczymy")
    ucz.add_argument("--probki", required=True,
                     help="plik wektorowy z przykładami (GPKG, SHP...)")
    ucz.add_argument("--pole", default="klasa",
                     help="kolumna z nazwą klasy")
    ucz.add_argument("--model", default="model.geoai",
                     help="gdzie zapisać nauczony model")
    ucz.add_argument("--nmpt", default=None,
                     help="model wysokości pokrycia terenu (opcjonalny, "
                          "ale bardzo pomaga)")
    ucz.add_argument("--rozdzielczosc", type=float, default=0.0,
                     help="rozdzielczość robocza w jednostkach mapy; "
                          "0 oznacza rozdzielczość pliku")
    ucz.add_argument("--wielkosc-obiektu", dest="wielkosc_obiektu",
                     type=float, default=10.0,
                     help="wielkość jednego obiektu w metrach kwadratowych")
    ucz.add_argument("--liczba-obiektow", dest="liczba_obiektow",
                     type=int, default=0,
                     help="zamiast wielkości: ile obiektów ma powstać")
    ucz.add_argument("--zwartosc", type=float, default=0.15,
                     help="zwartość obiektów przy podziale")
    ucz.add_argument("--wygladzenie", type=float, default=2.5,
                     help="rozmycie zdjęcia przed podziałem")
    ucz.add_argument("--pokrycie", type=float, default=0.5,
                     help="jaka część obiektu musi być przykryta "
                          "przykładem, żeby się liczył")
    ucz.add_argument("--separowalnosc", action="store_true",
                     help="sprawdź przy okazji, czy klasy da się "
                          "rozróżnić")

    # klasyfikuj
    klas = podpolecenia.add_parser(
        "klasyfikuj", parents=[wspolne], help="zastosuj model do wszystkich zdjęć w folderze",
        description="Przerabia po kolei każde zdjęcie we wskazanym "
                    "folderze i zapisuje mapy oraz zbiorczy raport CSV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    klas.add_argument("--folder", required=True,
                      help="folder ze zdjęciami do sklasyfikowania")
    klas.add_argument("--model", required=True,
                      help="plik modelu z polecenia „ucz”")
    klas.add_argument("--wyjscie", default="wyniki",
                      help="folder, w którym zapiszemy mapy")
    klas.add_argument("--rekurencyjnie", action="store_true",
                      help="szukaj zdjęć także w podfolderach")
    klas.add_argument("--nadpisuj", action="store_true",
                      help="policz ponownie także te zdjęcia, "
                           "dla których wynik już istnieje")
    klas.add_argument("--przyrostek", default="_klasyfikacja",
                      help="co dopisać do nazwy pliku wynikowego")
    klas.add_argument("--nmpt-folder", dest="nmpt_folder", default=None,
                      help="folder z modelami wysokości")
    klas.add_argument("--nmpt-przyrostek", dest="nmpt_przyrostek",
                      default="_nmpt",
                      help="jak odróżnić plik wysokości po nazwie")
    klas.add_argument("--rozdzielczosc", type=float, default=0.0,
                      help="nadpisz rozdzielczość zapisaną w modelu")
    klas.add_argument("--mmu", type=float, default=0.0,
                      help="najmniejszy zachowany płat w metrach "
                           "kwadratowych; 0 wyłącza czyszczenie")
    klas.add_argument("--klasa-zielona", dest="klasa_zielona", default=None,
                      help="dociąganie po zieloności: klasa roślinna")
    klas.add_argument("--klasa-druga", dest="klasa_druga", default=None,
                      help="dociąganie po zieloności: klasa, z której "
                           "odzyskujemy piksele")
    klas.add_argument("--prog-zielonosci", dest="prog_zielonosci",
                      type=float, default=0.05,
                      help="próg zieloności przy dociąganiu")
    klas.add_argument("--okno", type=int, default=3,
                      help="okno uśredniania zieloności w pikselach")
    klas.add_argument("--przerwij-na-bledzie",
                      dest="przerwij_na_bledzie", action="store_true",
                      help="zatrzymaj się przy pierwszym błędzie zamiast "
                           "lecieć dalej")

    # info
    info = podpolecenia.add_parser(
        "info", parents=[wspolne], help="pokaż, co siedzi w pliku modelu")
    info.add_argument("--model", required=True, help="plik modelu")

    return parser


def main(argv=None):
    parser = zbuduj_parser()
    args = parser.parse_args(argv)
    mowi = Dziennik(getattr(args, "cicho", False),
                    getattr(args, "gadatliwie", False))

    if getattr(args, "wersja", False):
        from . import __version__
        print("GeoAI Klasyfikator {0}".format(__version__))
        return 0

    if not args.polecenie:
        parser.print_help()
        return 0

    polecenia = {
        "sprawdz": polecenie_sprawdz,
        "szablon": polecenie_szablon,
        "ucz": polecenie_ucz,
        "klasyfikuj": polecenie_klasyfikuj,
        "info": polecenie_info,
    }
    try:
        return polecenia[args.polecenie](args, mowi)
    except KeyboardInterrupt:
        mowi()
        mowi.blad("Przerwane przez użytkownika.")
        return 130
    except MemoryError as blad:
        mowi.blad(str(blad))
        return 1
    except Exception as blad:
        mowi.blad(str(blad))
        if getattr(args, "gadatliwie", False):
            import traceback
            traceback.print_exc()
        else:
            mowi.blad("Uruchom z --gadatliwie, żeby zobaczyć szczegóły.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
