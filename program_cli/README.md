# GeoAI Klasyfikator — wersja dla wiersza poleceń

Ta sama klasyfikacja co we wtyczce QGIS, tylko **bez klikania**:
uczysz model raz, a potem puszczasz go na cały folder nalotów.

Oba programy liczą dokładnie to samo — ten sam podział na obiekty, te
same 19 albo 24 cechy, ten sam Random Forest. Dzielą katalog `core`.

---

## Instalacja — krok po kroku

### 1. Zainstaluj Pythona

Potrzebny jest **Python 3.9 lub nowszy**. Jeśli nie masz:
pobierz z [python.org](https://www.python.org/downloads/) i przy
instalacji **zaznacz „Add Python to PATH"**.

Sprawdzenie, czy jest:

```
python --version
```

### 2. Pobierz program

Ściągnij repozytorium (zielony przycisk *Code* → *Download ZIP*) i
rozpakuj. Potrzebne są dwa katalogi, obok siebie:

```
geoai_klasyfikator/      <- moduły obliczeniowe (ten sam co wtyczka)
program_cli/             <- ten program
```

### 3. Zainstaluj biblioteki

W katalogu `program_cli`:

```
python -m pip install -r requirements.txt
```

Jeśli pojawi się błąd o braku uprawnień, dodaj `--user`:

```
python -m pip install --user -r requirements.txt
```

### 4. Sprawdź, czy wszystko gra

```
python geoai.py sprawdz
```

Powinno wypisać listę bibliotek z dopiskiem `[jest]` i na końcu
„Wszystko na miejscu".

---

## Jak się tego używa

### Krok 1 — przygotuj przykłady

Program musi się od czegoś nauczyć. Przykłady podajesz w pliku
wektorowym: poligony (albo punkty) z kolumną, w której wpisana jest
nazwa klasy.

Pusty plik do wypełnienia zrobisz poleceniem:

```
python geoai.py szablon --zdjecie naloty/nalot_01.tif --plik przyklady.gpkg
```

Potem w QGIS: otwórz `przyklady.gpkg` i zdjęcie, włącz edycję i rysuj
poligony na terenach, które znasz, wpisując w kolumnie `klasa` nazwę:
`trawa`, `droga`, `zabudowa`, `las`, `grunt odkryty`...

**Trzy rady, które decydują o wyniku:**

1. Rozrzuć przykłady po **całym** zdjęciu, nie w jednym rogu.
2. Pokaż **każdą odmianę** klasy — i bujną trawę, i tę przyschniętą.
3. Rysuj tylko tam, gdzie jesteś pewien. Poligon na granicy dwóch
   klas zostanie zresztą pominięty (program o tym powie).

Na początek wystarczy po kilkanaście poligonów na klasę.

### Krok 2 — naucz model

```
python geoai.py ucz ^
    --zdjecie naloty/nalot_01.tif ^
    --probki przyklady.gpkg ^
    --nmpt nmpt/nalot_01_nmpt.tif ^
    --rozdzielczosc 0.05 ^
    --wielkosc-obiektu 10 ^
    --separowalnosc ^
    --model moj_model.geoai
```

(W Linuksie i na macOS zamiast `^` użyj `\` na końcu linii.)

Co znaczą te opcje:

| Opcja | Co robi |
|---|---|
| `--zdjecie` | jedno, reprezentatywne zdjęcie do nauki |
| `--probki` | plik z przykładami |
| `--pole` | kolumna z nazwą klasy (domyślnie `klasa`) |
| `--nmpt` | model wysokości pokrycia terenu; nieobowiązkowy, ale bardzo pomaga — bez niego 19 cech, z nim 24 |
| `--rozdzielczosc` | w jednostkach mapy, zwykle metrach; `0` = rozdzielczość pliku |
| `--wielkosc-obiektu` | ile metrów kwadratowych ma mieć jeden obiekt |
| `--separowalnosc` | sprawdza przy okazji, czy klasy w ogóle da się rozróżnić |

**Najważniejsza jest `--wielkosc-obiektu`.** Obiekt musi być mniejszy
niż najwęższa rzecz, którą chcesz pokazać na mapie. Dla pól i dachów
zwykle 5–20 m², dla pojedynczych drzew 2–5 m².

Powstaje plik `moj_model.geoai` — jedno archiwum z nauczonym modelem Random Forest,
listą klas, kolorami i wszystkimi ustawieniami. Możesz go przekazać
komuś innemu albo dołączyć do artykułu.

### Krok 3 — puść na cały folder

```
python geoai.py klasyfikuj ^
    --folder naloty ^
    --model moj_model.geoai ^
    --wyjscie mapy ^
    --nmpt-folder nmpt ^
    --mmu 10
```

Program przeleci po kolei każde zdjęcie, zapisze mapę jako GeoTIFF
z plikiem stylu `.qml` obok, a na końcu zbiorczy `raport.csv`
z powierzchnią każdej klasy na każdym zdjęciu.

Przydatne opcje:

| Opcja | Co robi |
|---|---|
| `--rekurencyjnie` | szuka zdjęć także w podfolderach |
| `--nadpisuj` | liczy ponownie też te, dla których wynik już jest |
| `--nmpt-folder` | folder z modelami wysokości (dopasowuje po nazwie) |
| `--mmu 10` | usuwa płaty mniejsze niż 10 m² |
| `--klasa-zielona trawa --klasa-druga "grunt odkryty"` | dociąganie po zieloności: odzyskuje pasy trawy węższe niż obiekt |
| `--przerwij-na-bledzie` | zatrzymaj się przy pierwszym problemie |
| `--gadatliwie` | pokaż też kroki pośrednie |

Przerwany przebieg można wznowić — bez `--nadpisuj` program pomija
zdjęcia, które już mają wynik.

---

## Wszystkie polecenia

```
python geoai.py sprawdz                 sprawdza biblioteki i silniki
python geoai.py szablon --zdjecie ...   tworzy pusty plik przykładów
python geoai.py ucz --zdjecie ...       uczy model
python geoai.py klasyfikuj --folder ... klasyfikuje cały folder
python geoai.py info --model ...        pokazuje, jak model był uczony
```

Każde przyjmuje `--help`:

```
python geoai.py ucz --help
```

---

## Jak dopasowywane są modele wysokości

Przy `--nmpt-folder` program szuka pliku o nazwie zdjęcia
z przyrostkiem (domyślnie `_nmpt`):

```
naloty/nalot_01.tif   ->   nmpt/nalot_01_nmpt.tif
```

Jeśli Twoje pliki nazywają się inaczej, zmień przyrostek:
`--nmpt-przyrostek _dsm`.

Gdy model uczył się z wysokością, a dla któregoś zdjęcia jej zabraknie,
program **nie policzy tego zdjęcia po cichu z gorszym zestawem cech** —
zgłosi błąd i poleci dalej, a brakujące wypisze w raporcie.

---

## Najczęstsze kłopoty

| Komunikat | Co zrobić |
|---|---|
| `ModuleNotFoundError: No module named 'rasterio'` | nie zainstalowano bibliotek: `python -m pip install -r requirements.txt` |
| `Nie znalazłem modułów obliczeniowych wtyczki` | katalog `geoai_klasyfikator` musi leżeć obok; albo ustaw zmienną `GEOAI_KLASYFIKATOR` na jego ścieżkę |
| `Siatka robocza ... nie zmieści się w pamięci` | podaj grubszą `--rozdzielczosc` (np. 0.10 zamiast 0.05) |
| `Potrzebne jest zdjęcie trójkanałowe (RGB)` | podajesz NMPT albo maskę zamiast zdjęcia |
| `Plik ... nie ma kolumny „klasa"` | podaj właściwą przez `--pole` (program wypisze, jakie są) |
| `Klasy bez ani jednego obiektu uczącego` | poligony są za małe wobec wielkości obiektu — narysuj większe albo zmniejsz `--wielkosc-obiektu` |
| `Ten model uczył się z modelem wysokości` | dodaj `--nmpt-folder` albo naucz model bez `--nmpt` |

---

## Co dalej

Ocena dokładności (losowanie punktów, macierz błędów, powierzchnie
z przedziałami ufności) jest we **wtyczce QGIS** — tam można opisywać
punkty klikając po mapie, czego w wierszu poleceń zrobić się nie da.
Wczytaj gotową mapę do QGIS i przejdź do kroku 4 wtyczki.

---

© Grzegorz Górniak · GPL-3.0-or-later · gorniakgrzegorz@gmail.com
