# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Generuje angielską wersję wtyczki (GeoAI_Classification) z polskiej
(geoai_klasyfikator). Kod jest jeden; różnią się tylko napisy widoczne
dla użytkownika, metadane i README.

    python narzedzia/wersja_angielska.py wypisz    # napisy bez tłumaczenia
    python narzedzia/wersja_angielska.py zbuduj    # tworzy GeoAI_Classification/
    python narzedzia/wersja_angielska.py sprawdz   # czy wersja angielska jest aktualna

Tłumaczenia są w narzedzia/tlumaczenia_en.json: klucz to dokładny tekst
literału w kodzie (razem z cudzysłowami), wartość to tekst, który go
zastąpi. Wartość równa kluczowi oznacza „bez zmian” (identyfikatory,
nazwy pól, nazwy plików).
"""
import ast
import json
import pathlib
import re
import shutil
import sys
import tempfile

KORZEN = pathlib.Path(__file__).resolve().parent.parent
ZRODLO = KORZEN / "geoai_klasyfikator"
CEL = KORZEN / "GeoAI_Classification"
SZABLON = KORZEN / "narzedzia" / "wersja_angielska"     # metadata, README
TLUMACZENIA = KORZEN / "narzedzia" / "tlumaczenia_en.json"
POLSKIE = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
POMIJANE = {"metadata.txt", "README.md"}


def literaly(zrodlo: str):
    """Zewnętrzne literały napisów (bez docstringów) z pozycjami w tekście."""
    drzewo = ast.parse(zrodlo)
    docstringi = set()
    for wezel in ast.walk(drzewo):
        if isinstance(wezel, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if wezel.body and isinstance(wezel.body[0], ast.Expr) and \
                    isinstance(wezel.body[0].value, ast.Constant) and \
                    isinstance(wezel.body[0].value.value, str):
                docstringi.add(id(wezel.body[0].value))
    wewnetrzne = set()
    for wezel in ast.walk(drzewo):
        if isinstance(wezel, ast.JoinedStr):
            for dziecko in ast.walk(wezel):
                if dziecko is not wezel:
                    wewnetrzne.add(id(dziecko))
    linie = zrodlo.splitlines(keepends=True)
    poczatki = [0]
    for linia in linie:
        poczatki.append(poczatki[-1] + len(linia))
    wynik = []
    for wezel in ast.walk(drzewo):
        if id(wezel) in docstringi or id(wezel) in wewnetrzne:
            continue
        if isinstance(wezel, ast.JoinedStr) or (
                isinstance(wezel, ast.Constant) and isinstance(wezel.value, str)):
            a = poczatki[wezel.lineno - 1] + len(
                linie[wezel.lineno - 1].encode("utf-8")[:wezel.col_offset].decode("utf-8"))
            b = poczatki[wezel.end_lineno - 1] + len(
                linie[wezel.end_lineno - 1].encode("utf-8")[:wezel.end_col_offset].decode("utf-8"))
            wynik.append((a, b, zrodlo[a:b]))
    return sorted(wynik)


def do_tlumaczenia(tekst: str) -> bool:
    return bool(POLSKIE.search(tekst))


def wczytaj():
    if TLUMACZENIA.exists():
        return json.loads(TLUMACZENIA.read_text(encoding="utf-8"))
    return {}


def przetlumacz(plik: pathlib.Path, slownik: dict, braki: list) -> str:
    zrodlo = plik.read_text(encoding="utf-8")
    wynik = zrodlo
    for a, b, tekst in reversed(literaly(zrodlo)):
        if tekst in slownik:
            wynik = wynik[:a] + slownik[tekst] + wynik[b:]
        elif do_tlumaczenia(tekst):
            braki.append((plik.relative_to(KORZEN), tekst))
    return wynik


def zbuduj(cel: pathlib.Path) -> list:
    slownik = wczytaj()
    braki = []
    if cel.exists():
        shutil.rmtree(cel)
    for plik in sorted(ZRODLO.rglob("*")):
        if "__pycache__" in plik.parts or plik.suffix == ".pyc":
            continue
        docelowy = cel / plik.relative_to(ZRODLO)
        if plik.is_dir():
            continue
        docelowy.parent.mkdir(parents=True, exist_ok=True)
        if plik.name in POMIJANE and plik.parent == ZRODLO:
            continue
        if plik.suffix == ".py":
            tekst = przetlumacz(plik, slownik, braki)
            ast.parse(tekst)                     # tłumaczenie nie może zepsuć składni
            docelowy.write_text(tekst, encoding="utf-8", newline="\n")
        else:
            shutil.copy2(plik, docelowy)
    for plik in SZABLON.iterdir():
        shutil.copy2(plik, cel / plik.name)
    return braki


def porownaj(a: pathlib.Path, b: pathlib.Path) -> list:
    rozne = []
    pliki_a = {p.relative_to(a) for p in a.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    pliki_b = {p.relative_to(b) for p in b.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    for p in sorted(pliki_a ^ pliki_b):
        rozne.append(str(p))
    for p in sorted(pliki_a & pliki_b):
        # na Windowsie git może zamienić końce linii na CRLF; to nie różnica
        if (a / p).read_bytes().replace(b"\r\n", b"\n") != \
                (b / p).read_bytes().replace(b"\r\n", b"\n"):
            rozne.append(str(p))
    return rozne


def main():
    polecenie = sys.argv[1] if len(sys.argv) > 1 else "sprawdz"
    if polecenie == "wypisz":
        slownik = wczytaj()
        nowe = {}
        for plik in sorted(ZRODLO.rglob("*.py")):
            for _, _, tekst in literaly(plik.read_text(encoding="utf-8")):
                if do_tlumaczenia(tekst) and tekst not in slownik:
                    nowe[tekst] = ""
        print(json.dumps(nowe, ensure_ascii=False, indent=1))
        print("bez tłumaczenia:", len(nowe), file=sys.stderr)
    elif polecenie == "zbuduj":
        braki = zbuduj(CEL)
        for plik, tekst in braki:
            print("BRAK TŁUMACZENIA", plik, tekst[:80])
        sys.exit(1 if braki else 0)
    elif polecenie == "sprawdz":
        with tempfile.TemporaryDirectory() as tmp:
            braki = zbuduj(pathlib.Path(tmp) / "GeoAI_Classification")
            rozne = porownaj(pathlib.Path(tmp) / "GeoAI_Classification", CEL)
        for plik, tekst in braki:
            print("BRAK TŁUMACZENIA", plik, tekst[:80])
        for p in rozne:
            print("NIEAKTUALNE", p)
        if braki or rozne:
            print("Uruchom: python narzedzia/wersja_angielska.py zbuduj")
            sys.exit(1)
        print("Wersja angielska jest aktualna.")
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
