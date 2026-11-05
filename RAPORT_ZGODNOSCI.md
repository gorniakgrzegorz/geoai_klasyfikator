# Raport zgodności: wtyczka QGIS a program w Pythonie

Sprawdzenie, czy program wiersza poleceń liczy to samo, co wtyczka QGIS.
Data: 5 listopada 2026. Wersja 1.0.0.

## Co sprawdzano i jak

Wtyczka QGIS i program wiersza poleceń importują **te same pliki**
z katalogu `geoai_klasyfikator/core`. Sam fakt wspólnego kodu nie
wystarcza jednak za dowód: obie wersje mogłyby wywoływać te funkcje
w innej kolejności albo z innymi parametrami. Dlatego sprawdzenie było
dwustopniowe.

**Scena testowa.** Ortomozaika 400 na 400 pikseli o rozmiarze piksela
0,10 m (0,16 ha), 8-bitowa, w układzie EPSG:2180, z czterema
rozróżnialnymi klasami: dach (jasny, gładki, 6 m wysokości), droga
(szara, płaska), trawa (tło) i cztery korony drzew (ciemna zieleń,
9 m wysokości). Do tego model pokrycia terenu z tego samego układu
i 10 poligonów uczących z kolumną `klasa`.

**Krok 1.** Przebieg programu wiersza poleceń w całości: `geoai ucz`,
a następnie `geoai klasyfikuj` na folderze.

**Krok 2.** Odtworzenie kolejności wywołań panelu wtyczki na module
`core`, krok po kroku, tak jak robi to metoda `_classify_all` panelu:
wczytanie obrazu, `slic_segments`, `compute_features`,
`classifier.train`, `classifier.predict`, przepisanie etykiet na
piksele, wyzerowanie maski. Porównanie wynikowej tablicy z mapą
zapisaną przez program.

## Wyniki

| Sprawdzenie | Wynik |
|---|---|
| Mapa z 24 cechami (ze NMPT): piksele różniące się | **0 ze 160 000** |
| Mapa z 19 cechami (bez NMPT): piksele różniące się | **0 ze 160 000** |
| Usuwanie drobnych płatów (sito, próg 50 px) | **wynik identyczny** |
| Powtarzalność: dwa niezależne przebiegi programu | **mapy identyczne co do bajtu** |
| Liczba obiektów, liczba cech, liczba obiektów uczących | 434 obiekty, 24 cechy, 83 obiekty uczące, zgodnie w obu torach |

Reguły przeliczania jasności na zakres 0 do 1 porównano przez
odczytanie kodu obu modułów wejścia: `core/qgis_io.py` (wtyczka, przez
GDAL) i `program_cli/geoai_cli/raster.py` (program, przez rasterio)
stosują tę samą tabelę: 255 dla danych 8-bitowych, 65 535 dla
16-bitowych bez znaku, 32 767 dla 16-bitowych ze znakiem, a dla
pozostałych typów skalowanie przez wartość największą. Porównania
wykonawczego tych dwóch modułów nie przeprowadzono, ponieważ
w środowisku testowym nie były dostępne wiązania Pythona do GDAL-a;
wspólny jest natomiast cały dalszy tor obliczeń, od podziału na
obiekty po klasyfikację.

## Przy okazji sprawdzono

| Polecenie | Zachowanie |
|---|---|
| `geoai sprawdz` | wykrywa wszystkie sześć bibliotek i nazywa wybrane silniki |
| `geoai szablon` | tworzy pusty plik przykładów w układzie zdjęcia, z kolumną `klasa` |
| `geoai info` | wypisuje klasy modelu i pełną listę 24 nazw cech |
| `geoai ucz --separowalnosc` | liczy rozróżnialność wszystkich par klas i oznacza pary słabe |
| zdjęcie jednokanałowe | odrzucone komunikatem: „Potrzebne jest zdjęcie trójkanałowe (RGB), a plik ma kanałów: 1” |

Czas przebiegu na scenie testowej: nauka 3 sekundy, klasyfikacja
1 sekunda.

## Wniosek

Dla takich samych danych wejściowych i takich samych ustawień program
wiersza poleceń zwraca **tę samą mapę co wtyczka**, bez różnicy na
żadnym pikselu, zarówno w wariancie z modelem wysokości, jak i bez
niego. Wyniki są powtarzalne między przebiegami.

Zastrzeżenie: sprawdzenie wykonano na jednej scenie syntetycznej,
o znanej budowie, przy jednym zestawie ustawień. Nie zastępuje to
testów na danych rzeczywistych, które pozostają do wykonania.
