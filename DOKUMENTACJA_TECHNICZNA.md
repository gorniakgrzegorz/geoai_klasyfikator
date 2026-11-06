# Dokumentacja techniczna

**GeoAI Klasyfikator, wersja 1.0.2.** Opis dla pracy naukowej: co
narzędzie robi, jakimi algorytmami, na jakich bibliotekach, z jakimi
ustawieniami i co z tego wynika dla odtwarzalności.

Dokument opisuje stan faktyczny kodu, nie zamierzenia. Wszystkie stałe
i wywołania podane niżej zostały odczytane z plików źródłowych.
Uzupełnia go [UWARUNKOWANIA_NAUKOWE.md](UWARUNKOWANIA_NAUKOWE.md),
gdzie są pełne wyprowadzenia wzorów.

---

## Spis treści

1. [Czym to narzędzie jest](#1-czym-to-narzędzie-jest)
2. [Czy to jest sztuczna inteligencja](#2-czy-to-jest-sztuczna-inteligencja)
3. [Architektura i mapa plików](#3-architektura-i-mapa-plików)
4. [Przepływ przetwarzania](#4-przepływ-przetwarzania)
5. [Algorytmy, jeden po drugim](#5-algorytmy-jeden-po-drugim)
6. [Biblioteki i ich źródła](#6-biblioteki-i-ich-źródła)
7. [Mechanizm zapasowy](#7-mechanizm-zapasowy)
8. [Pełny wykaz parametrów](#8-pełny-wykaz-parametrów)
9. [Skrypty i pliki konfiguracyjne](#9-skrypty-i-pliki-konfiguracyjne)
10. [Odtwarzalność](#10-odtwarzalność)
11. [Słownik pojęć technicznych](#11-słownik-pojęć-technicznych)
12. [Jak to cytować](#12-jak-to-cytować)
13. [Bibliografia](#13-bibliografia)

---

## 1. Czym to narzędzie jest

Narzędzie wykonuje **nadzorowaną klasyfikację obiektową pokrycia terenu**
(GEOBIA, *geographic object-based image analysis*) na obrazach o bardzo
wysokiej rozdzielczości przestrzennej, w trzech kanałach widzialnych,
opcjonalnie wsparte numerycznym modelem pokrycia terenu.

Łańcuch przetwarzania składa się z sześciu etapów:

1. **segmentacja** obrazu na obiekty algorytmem SLIC,
2. **ekstrakcja cech**: 19 wielkości z obrazu, 24 z modelem wysokości,
3. **zebranie próby uczącej** od operatora,
4. **ocena rozdzielności klas** przed uczeniem,
5. **klasyfikacja** klasyfikatorem Random Forest,
6. **ocena dokładności** z estymacją powierzchni i jej niepewności.

Etapy 4 i 6 odróżniają to narzędzie od typowych wtyczek klasyfikacyjnych:
pierwszy mówi, czy przyjęta legenda jest w ogóle wykonalna na tych
danych, drugi podaje liczby nadające się do publikacji.

### Czego narzędzie nie robi

- Nie korzysta z bliskiej podczerwieni, więc nie liczy NDVI.
- Nie zawiera modelu wytrenowanego na danych zewnętrznych. Każdy
  przebieg zaczyna od zera, od próby uczącej operatora.
- Nie wykrywa zmian w czasie, nie klasyfikuje szeregów czasowych.
- Nie zawiera sieci neuronowych w żadnej postaci.

---

## 2. Czy to jest sztuczna inteligencja

Pytanie zasadne i warte precyzyjnej odpowiedzi, bo nazwa narzędzia
zawiera skrót AI.

**Odpowiedź krótka: tak, w sensie uczenia maszynowego, ale nie
w sensie uczenia głębokiego.** Jedynym algorytmem uczącym się
z nadzorem jest Random Forest. Drugim algorytmem należącym do uczenia
maszynowego jest SLIC, który jest metodą nienadzorowaną. Wszystko
pozostałe to deterministyczne przetwarzanie obrazu i statystyka
matematyczna.

Poniższa tabela dzieli składniki według tego, czym naprawdę są.

| Składnik | Kategoria | Czy się uczy |
|---|---|---|
| SLIC | grupowanie nienadzorowane, wariant k-średnich z ograniczeniem przestrzennym | tak, ale bez etykiet: szuka struktury w danych |
| Random Forest | uczenie nadzorowane, metoda zespołowa (*ensemble*) | tak, z etykiet operatora |
| Konwersja sRGB do CIELAB | przekształcenie kolorymetryczne, wzór zamknięty | nie |
| Wskaźniki ExG, VARI, NGRDI | wzory arytmetyczne na kanałach | nie |
| Macierz współwystąpień GLCM | statystyka opisowa tekstury | nie |
| Estymator obwodu Croftona | geometria stochastyczna, wzór | nie |
| Otoczka wypukła | geometria obliczeniowa, algorytm Andrew | nie |
| Morfologia matematyczna (grunt z NMPT) | filtracja obrazu | nie |
| Odległość Jeffriesa i Matusity | statystyka: miara rozdzielności rozkładów | nie |
| Regularyzacja Ledoita i Wolfa | estymacja macierzy kowariancji | nie |
| Próg Youdena | optymalizacja jednoparametrowa | nie |
| Sito (*sieve*) | operacja na spójnych składowych | nie |
| Estymatory Olofssona | wnioskowanie statystyczne z próby warstwowej | nie |

Z trzynastu wymienionych składników **dwa** należą do uczenia
maszynowego. Jest to klasyfikator płytki, interpretowalny i tani
obliczeniowo, a nie model głęboki. Określenie *GeoAI* w nazwie odnosi
się do zastosowania uczenia maszynowego do danych przestrzennych, a nie
do sieci neuronowych.

### Dlaczego nie ma uczenia głębokiego

Zrezygnowano z tego z trzech powodów:

1. **Rozmiar.** Dołączenie biblioteki PyTorch i wag modelu podnosi
   wielkość wtyczki z kilkudziesięciu kilobajtów do kilkuset megabajtów.
2. **Sprzęt.** Bez akceleratora graficznego ekstrakcja cech
   z transformera na scenie o kilkunastu milionach pikseli trwa
   godzinami.
3. **Interpretowalność.** 24 nazwane wielkości fizyczne da się opisać
   w artykule i zweryfikować; wektor 384 liczb z sieci nie.

**Konsekwencja, którą trzeba wymienić w ograniczeniach pracy:** klasy
różniące się *wzorem przestrzennym*, a nie materiałem, pozostają
nierozdzielone. Dwie uprawy o tej samej barwie, fakturze i wysokości,
różniące się rozstawem rzędów, mają niemal identyczne wektory cech.

---

## 3. Architektura i mapa plików

Trzy programy, jeden rdzeń obliczeniowy. Rdzeń nie zależy od QGIS ani
od interfejsu, jest czystym kodem NumPy.

```
geoai_klasyfikator/            pakiet wtyczki QGIS
  core/                        RDZEŃ, wspólny dla wszystkich wersji
    slic.py                    CIELAB, rozmycie Gaussa, SLIC
    features.py                19 albo 24 cechy obiektów
    classifier.py              Random Forest, rozdzielność JM
    refine.py                  korekta zieloności, sito
    accuracy.py                losowanie punktów, macierz błędów, Olofsson
    qgis_io.py                 odczyt rastrów przez GDAL, zapis GeoTIFF i QML
    compat.py                  zgodność QGIS 3.22 do 4.x (Qt5 i Qt6)
    deps.py                    wykrywanie bibliotek opcjonalnych
  dialogs/
    dock.py                    panel wtyczki, cztery kroki
    maptools.py                narzędzia wskazywania na mapie
  main_plugin.py               rejestracja przycisku na pasku QGIS
  metadata.txt                 metadane wtyczki

program_cli/                   wersja dla wiersza poleceń
  geoai.py                     punkt wejścia
  geoai_cli/
    main.py                    polecenia: sprawdz, szablon, ucz, klasyfikuj, info
    raster.py                  odczyt rastrów przez rasterio
    probki.py                  odczyt poligonów przez Fiona, wypalanie na siatkę
    model.py                   zapis i odczyt modelu .geoai
    przebieg.py                złożenie etapów w jeden przebieg
    rdzen.py                   most do pakietu core

program_exe/                   program okienkowy dla Windows
  okno.py                      interfejs w tkinterze
  GeoAI_Klasyfikator.spec      przepis dla PyInstallera
  wersja.txt                   zasób wersji wpisywany w plik .exe
  instalator.iss               skrypt instalatora Inno Setup
  zbuduj.bat                   budowanie jednym kliknięciem
```

Istotna cecha architektury: **moduł `rdzen.py` odnajduje pakiet `core`
i importuje te same pliki**, których używa wtyczka. Nie ma dwóch
implementacji tego samego. Zgodność potwierdzono eksperymentalnie, zero
różnic na 160 000 pikseli; zobacz
[RAPORT_ZGODNOSCI.md](RAPORT_ZGODNOSCI.md).

Różnice między wersjami dotyczą wyłącznie wejścia i wyjścia:

| Warstwa | Wtyczka QGIS | Wiersz poleceń i program okienkowy |
|---|---|---|
| Odczyt rastra | `osgeo.gdal` przez `core/qgis_io.py` | `rasterio` przez `geoai_cli/raster.py` |
| Odczyt wektora | API QGIS | `fiona` |
| Interfejs | PyQt (Qt5 albo Qt6) | argparse, tkinter |

Reguła przeliczania jasności na zakres 0 do 1 jest w obu torach
identyczna: dzielenie przez 255 dla danych 8-bitowych, 65 535 dla
16-bitowych bez znaku, 32 767 dla 16-bitowych ze znakiem, a dla
pozostałych typów przez wartość największą.

---

## 4. Przepływ przetwarzania

Dla każdego etapu podano, co wchodzi, co wychodzi i która funkcja to
robi.

### Etap 1. Wczytanie obrazu

`qgis_io.read_rgb()` albo `raster.wczytaj_rgb()`

| | |
|---|---|
| Wejście | plik rastrowy, trzy pierwsze kanały |
| Wyjście | tablica `(wiersze, kolumny, 3)` typu float32 w zakresie 0 do 1, maska ważnych pikseli, rozmiar piksela, układ współrzędnych |

Obraz jest przeliczany na siatkę roboczą o rozdzielczości podanej przez
operatora; przy zgrubianiu wartości pikseli są uśredniane. Siatka
robocza większa niż `MAX_WORKING_PIXELS = 15 000 000` pikseli jest
odrzucana z komunikatem i trzeba wtedy podać grubszą rozdzielczość.
Wynik zapisywany jest na siatce roboczej.

### Etap 2. Segmentacja

`slic.slic_segments()`

| | |
|---|---|
| Wejście | tablica RGB, zamawiana liczba segmentów, zwartość, sigma, maska |
| Wyjście | tablica etykiet całkowitych o tym samym kształcie, numeracja od 1 |

Liczbę segmentów wylicza się z podanej przez operatora wielkości
obiektu: `liczba = powierzchnia_w_m² / wielkość_obiektu_w_m²`, nie
mniej niż 100.

### Etap 3. Ekstrakcja cech

`features.compute_features()`

| | |
|---|---|
| Wejście | RGB, etykiety segmentów, rozmiar piksela, opcjonalnie NMPT |
| Wyjście | wektor identyfikatorów, macierz `(liczba_obiektów, 19 albo 24)`, lista nazw cech |

### Etap 4. Próba ucząca

`probki.wypal_na_siatke()` i `probki.przypisz_obiektom()`, albo
klikanie na kanwie w `dialogs/maptools.py`

| | |
|---|---|
| Wejście | poligony z kolumną klasy albo kliknięcia operatora |
| Wyjście | odwzorowanie identyfikator obiektu na numer klasy |

Obiekt dostaje etykietę, gdy przykłady pokrywają dość dużą jego część
(domyślnie połowę) i nie są ze sobą sprzeczne. **Obiekt, na którym
spotykają się dwie klasy, zostaje pominięty**, bo leżałby na granicy
i nauczyłby klasyfikator nieprawdy.

### Etap 5. Ocena rozdzielności

`classifier.separability_report()`

| | |
|---|---|
| Wejście | macierz cech, etykiety obiektów uczących |
| Wyjście | dla każdej pary klas odległość JM w zakresie 0 do 2 i słowna ocena |

Wykonywana **przed** uczeniem. Para poniżej progu `JM_FAIR = 1.7` nie
rozdzieli się niezależnie od liczby przykładów.

### Etap 6. Uczenie

`classifier.train()`

| | |
|---|---|
| Wejście | podmacierz cech obiektów uczących, wektor etykiet |
| Wyjście | obiekt modelu |

### Etap 7. Klasyfikacja

`classifier.predict()`

| | |
|---|---|
| Wejście | model, pełna macierz cech |
| Wyjście | wektor etykiet dla wszystkich obiektów, wektor pewności |

Etykiety obiektów rozsmarowuje się z powrotem na piksele przez tablicę
przeliczeniową indeksowaną etykietą segmentu.

### Etap 8. Korekty (opcjonalne)

`refine.refine_by_greenness()`, `refine.sieve()`

Obie są operacjami **pikselowymi** wewnątrz toru obiektowego. Ich użycie
trzeba podać wprost w opisie metody, bo mapa przestaje być czysto
obiektowa.

### Etap 9. Ocena dokładności

`accuracy.stratified_points()`, `accuracy.error_matrix()`,
`accuracy.olofsson_estimates()`

| | |
|---|---|
| Wejście | mapa klas, opisy punktów kontrolnych, powierzchnie warstw |
| Wyjście | macierz błędów, dokładności, powierzchnie skorygowane z przedziałami ufności |

---

## 5. Algorytmy, jeden po drugim

### 5.1 Konwersja sRGB do CIELAB

Plik `core/slic.py`, funkcja `rgb_to_lab()`.

Dlaczego: odległość euklidesowa w przestrzeni RGB nie odpowiada
różnicy postrzeganej. CIELAB jest w przybliżeniu percepcyjnie
jednorodna, więc ta sama różnica liczbowa znaczy w niej mniej więcej
to samo w każdym miejscu przestrzeni barw.

Kroki: linearyzacja sRGB z progiem 0,04045, przejście do przestrzeni
XYZ, normalizacja punktem bieli D65 (0,950456; 1,0; 1,088754),
przekształcenie nieliniowe ze stałymi ε = 216/24389 i κ = 24389/27.
Implementacja zweryfikowana wobec wartości tablicowych CIE.

### 5.2 SLIC, segmentacja superpikselowa

Plik `core/slic.py`. Źródło metody: Achanta i in. (2012).

Algorytm jest wariantem **k-średnich z ograniczeniem przestrzennym**.
Zasiewa środki skupień w regularnej siatce o boku *S*, a następnie
iteracyjnie przypisuje piksele do najbliższego środka i przelicza
środki. Kluczowa różnica wobec zwykłych k-średnich: piksel może trafić
tylko do skupienia, którego środek leży w promieniu 2*S*, co daje
złożoność liniową zamiast kwadratowej.

Odległość łączy człon barwny i przestrzenny:

$$D = \sqrt{d_{\text{barwa}}^{2} + \left(\frac{d_{\text{odleg}}}{S}\right)^{2} m^{2}}$$

gdzie *m* jest zwartością. Wartości domyślne: *m* = 0,15, rozmycie
wstępne sigma = 2,5, liczba iteracji 10. Niska zwartość oznacza, że
o przebiegu granicy decyduje przede wszystkim barwa.

Po iteracjach wymuszana jest **spójność**: segmenty rozpadnięte na
kawałki są scalane albo przyłączane do sąsiada.

### 5.3 Cechy barwy, 7 wielkości

Plik `core/features.py`, funkcja `colour_features()`.

Średnie i odchylenia standardowe trzech kanałów oraz średnia jasność
liczona jako `0,299 R + 0,587 G + 0,114 B`, czyli wagi luminancji
z zalecenia ITU-R BT.601.

### 5.4 Wskaźniki roślinności, 3 wielkości

Liczone na **współrzędnych chromatycznych**, czyli udziałach kanałów
w ich sumie, a nie na surowych jasnościach. Dzięki temu ten sam
materiał w cieniu i w pełnym słońcu daje zbliżone wartości.

| Wskaźnik | Wzór | Źródło |
|---|---|---|
| ExG | 2g − r − b | Woebbecke i in. (1995) |
| VARI | (g − r) / (g + r − b) | Gitelson i in. (2002) |
| NGRDI | (g − r) / (g + r) | Hunt i in. (2005) |

### 5.5 Faktura GLCM, 4 wielkości

Plik `core/features.py`, funkcje `_glcm_for_patch()` i
`texture_features()`. Źródło: Haralick i in. (1973).

Macierz współwystąpień zlicza, jak często piksel o poziomie *i* sąsiaduje
z pikselem o poziomie *j*. Parametry: `GREY_LEVELS = 15` poziomów
szarości, odległość 1 piksel, cztery kierunki (0, 45, 90 i 135 stopni),
macierz symetryczna.

Dwa szczegóły implementacyjne mające znaczenie dla porównywalności:

1. **Kwantyzacja liczona jest z całego zdjęcia**, nie z pojedynczego
   obiektu. Inaczej wartości nie byłyby porównywalne między obiektami.
2. **Poziom 0 jest odrzucany i macierz renormalizowana**, żeby piksele
   spoza obiektu nie wchodziły do statystyki.

Obiekty mniejsze niż `MIN_TEXTURE_PIXELS = 16` otrzymują wartości
neutralne.

Liczone wielkości: kontrast, jednorodność, energia (drugi moment
kątowy) i entropia. Jednorodność zgodna z definicją `graycoprops`
w scikit-image, czyli z wagą `1 / (1 + (i − j)²)`.

### 5.6 Kształt, 4 wielkości

Powierzchnia, obwód, okrągłość i wypukłość.

**Obwód** szacowany jest estymatorem Croftona z geometrii
stochastycznej, a nie przez zliczanie krawędzi pikselowych:

$$P \approx \frac{\pi}{4}\left[\frac{P_0 + P_{90}}{2} + \frac{P_{45} + P_{135}}{2\sqrt{2}}\right]$$

Uzasadnienie: zliczanie krawędzi zamienia okrąg w schodki i zawyża jego
obwód o około 27 procent, przez co okrągłość koła nigdy nie osiągnęłaby
jedności. Estymator Croftona dla koła o promieniu 30 pikseli daje 190,2
przy wartości prawdziwej 188,5. Ceną jest niewielkie zaniżenie dla
prostokątów.

**Otoczka wypukła** liczona jest z narożników pikseli, nie z ich
środków. Liczenie ze środków zaniża pole otoczki i dawało wypukłość
równą jedności dla każdego obiektu.

### 5.7 Kontekst, 1 wielkość

Jasność obiektu odniesiona do średniej jasności jego sąsiadów. Pary
sąsiedztwa wyznacza `adjacency_pairs()` przez porównanie etykiet
w poziomie i w pionie.

Dlaczego to jest potrzebne: dach jest jasny *względem otoczenia*,
a nie w sensie bezwzględnym. Cecha bezwzględna tego nie uchwyci przy
zmiennym oświetleniu sceny.

### 5.8 Cechy wysokościowe, 5 wielkości

Dostępne tylko z numerycznym modelem pokrycia terenu.

Średnia i odchylenie wysokości, nachylenie w stopniach, wysokość
względem sąsiedztwa oraz **wysokość nad gruntem**, czyli cecha
o największej wartości rozdzielczej.

Grunt szacowany jest z samego NMPT w trzech krokach
(`features.ground_surface()`):

1. minimum w blokach około `GROUND_BLOCK_M = 1,0` m, co usuwa pojedyncze
   wysokie punkty,
2. otwarcie morfologiczne o oknie `GROUND_OPENING_M = 40,0` m, czyli
   minimum ruchome, po którym maksimum ruchome; usuwa wszystko węższe
   niż okno,
3. wygładzenie średnią ruchomą, likwidujące schodki po otwarciu.

Okno otwarcia jest ograniczane do połowy krótszego boku obrazu, bo przy
małej scenie szersze okno zawyżało grunt.

**Znane ograniczenie:** obiekty szersze niż 40 m, na przykład duże hale,
są częściowo traktowane jako grunt i ich wysokość jest zaniżana.
Zastosowanie osobnego numerycznego modelu terenu usuwa ten problem.

### 5.9 Random Forest

Plik `core/classifier.py`. Źródło metody: Breiman (2001). Przegląd
zastosowań w teledetekcji: Belgiu i Drăguţ (2016).

#### Jak działa, krok po kroku

Pojedyncze **drzewo decyzyjne** dzieli zbiór uczący serią pytań
o jedną cechę naraz, w postaci „czy cecha *k* jest mniejsza niż próg
*t*". Próg wybierany jest tak, by zminimalizować **nieczystość Giniego**
w powstałych gałęziach:

$$G = 1 - \sum_{c} p_c^{2}$$

gdzie *p_c* to udział klasy *c* w węźle. Wartość 0 oznacza węzeł czysty,
zawierający jedną klasę.

Pojedyncze drzewo łatwo przeucza: wystarczy jeden nietypowy przykład,
żeby cała gałąź poszła w złą stronę. **Random Forest** buduje ich sto
i wprowadza dwa niezależne źródła losowości:

1. **Bagging**: każde drzewo rośnie na losowej próbie ze zwracaniem
   z obiektów uczących, o tej samej liczebności co zbiór oryginalny.
   Przeciętnie około 37 procent obiektów nie trafia do danego drzewa.
2. **Losowy podzbiór cech**: przy każdym podziale rozpatrywany jest
   tylko pierwiastek z liczby cech, zaokrąglony w dół, czyli 4 cechy
   zarówno przy 19, jak i przy 24. Od wersji 1.0.1 tak samo liczy
   implementacja wbudowana; w wersji 1.0.0 zaokrąglała do najbliższej
   liczby całkowitej, czyli przy 24 cechach brała 5. To dekoreluje drzewa, bo nie wszystkie mogą oprzeć się na tej samej
   najsilniejszej cesze.

Klasyfikacja odbywa się przez **głosowanie miękkie**: każde drzewo
zwraca rozkład prawdopodobieństwa klas, rozkłady są uśredniane, wygrywa
klasa o największej średniej. Udział głosów klasy zwycięskiej zapisywany
jest jako **pewność przypisania**; obiekty poniżej 0,5 są raportowane
operatorowi jako miejsca, gdzie warto dołożyć przykłady.

#### Dokładne wywołanie w kodzie

```python
RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
```

Trzy rzeczy, które trzeba z tego wyczytać i napisać w artykule:

- Jawnie ustawione są **tylko** liczba drzew, ziarno generatora
  i zrównoleglenie. `n_jobs` nie wpływa na wynik, tylko na czas.
- Kryterium podziału, liczba cech przy podziale, głębokość drzewa
  i losowanie ze zwracaniem przyjmują **wartości domyślne biblioteki**.
  Dla scikit-learn w wersjach 1.x są to odpowiednio: Gini, pierwiastek
  z liczby cech, brak ograniczenia głębokości, bootstrap włączony.
- **To jest zależność od wersji.** Gdyby biblioteka zmieniła którąś
  z domyślnych wartości, wynik mógłby się zmienić przy niezmienionym
  kodzie. W opisie badania trzeba podać wersję scikit-learn.

Wagi klas **nie są stosowane**, więc klasa z garstką przykładów
przegrywa głosowania z klasą licznie naklikaną. Funkcja
`niezrownowazenie()` zwraca stosunek najliczniejszej do najrzadszej
klasy, żeby operator o tym wiedział.

#### Ważność cech

`feature_importance()` zwraca ważność opartą na spadku nieczystości
Giniego. Jest to miara użyteczna do orientacji, ale **nie jest miarą
przyczynową** i jest znana z faworyzowania cech o wielu możliwych
progach. W artykule należy ją podać z tym zastrzeżeniem.

### 5.10 Rozdzielność klas, odległość Jeffriesa i Matusity

Plik `core/classifier.py`, funkcja `pair_separability()`.

Miara mówi, na ile rozkłady cech dwóch klas da się od siebie odróżnić.
Przyjmuje wartości od 0 (rozkłady identyczne) do 2 (rozłączne).

Procedura dla każdej pary klas:

1. podział próby na 5 części (walidacja krzyżowa),
2. na części uczącej wyznaczenie **kierunku Fishera**, czyli jednego
   wymiaru najlepiej rozdzielającego klasy,
3. regularyzacja macierzy kowariancji estymatorem Ledoita i Wolfa
   (2004), niezbędna, bo przy kilkunastu obiektach i 24 cechach macierz
   jest osobliwa,
4. na części testowej rzut na ten kierunek i obliczenie odległości
   Bhattacharyi w jednym wymiarze,
5. przeliczenie: JM = 2(1 − e^−B),
6. uśrednienie po pięciu podziałach.

**Dlaczego z walidacją krzyżową.** Klasyczna JM liczona w pełnej
przestrzeni cech na tych samych próbkach osiąga wartość bliską 2,00 dla
niemal każdej pary, również dla pary powstałej ze sztucznego podziału
jednej klasy na pół. Jest to przeuczenie miary, nie rzeczywista
rozdzielność. Wariant z walidacją krzyżową dla takiej pary kontrolnej
zwraca 0,02 do 0,07, czyli poprawnie rozpoznaje, że klas nie ma czego
rozdzielać.

Progi interpretacyjne: `JM_GOOD = 1,9` i `JM_FAIR = 1,7`.

### 5.11 Korekta zieloności

Plik `core/refine.py`.

ExG wygładzony w oknie `DEFAULT_WINDOW = 3` na 3 piksele. Próg
dobierany jest jako wartość maksymalizująca **wskaźnik Youdena**
(1950), czyli sumę czułości i swoistości pomniejszoną o jeden, spośród
256 kandydatów rozłożonych w zakresie obserwowanych wartości.

Dwa tryby:

- `MODE_WHOLE`: segment zmienia klasę w całości, gdy udział pikseli
  zielonych przekracza `WHOLE_SEGMENT_SHARE = 0,25`. Bezpieczniejszy,
  nie dziurawi trawy łysinami.
- `MODE_PIXEL`: każdy piksel rozstrzyga o sobie, w obie strony. Daje
  ostrzejsze krawędzie.

### 5.12 Sito

`refine.sieve()`. Łaty mniejsze od progu są pochłaniane przez
otoczenie w sąsiedztwie czterospójnym, bez wygładzania granic. Gdy
dostępny jest GDAL, używana jest jego funkcja `SieveFilter`; w przeciwnym
razie wbudowana implementacja oparta na spójnych składowych
i głosowaniu większościowym sąsiadów.

Operacja zmienia powierzchnie klas, więc musi być wykonana **przed**
oceną dokładności, nie po niej.

### 5.13 Ocena dokładności i estymacja powierzchni

Plik `core/accuracy.py`. Źródła: Olofsson i in. (2014), Stehman (2014),
wcześniejsze ujęcie Olofsson i in. (2013).

Próba warstwowa, w której warstwami są klasy mapy. Warstwa zapisywana
jest razem z punktem, co jest warunkiem poprawności estymatorów przy
niezgodności warstw z klasami. Punkty kontrolne nie trafiają na obiekty
użyte jako przykłady uczące.

Udziały w macierzy błędów ważone są powierzchnią warstw:

$$p_{ij} = W_i \frac{n_{ij}}{n_i}$$

gdzie *W_i* to udział powierzchniowy warstwy *i*, *n_i* liczba punktów
w tej warstwie, *n_ij* liczba punktów z warstwy *i* o klasie
referencyjnej *j*. Z macierzy liczone są dokładność ogólna, dokładności
producenta i użytkownika oraz powierzchnie klas, a wariancje z równań
5 do 7 pracy źródłowej. Przedziały ufności przy `CONFIDENCE_Z = 1,96`,
czyli 95 procent.

**Dlaczego to jest potrzebne:** powierzchnia policzona przez zliczenie
pikseli klasy nie jest estymatorem powierzchni tej klasy, bo mapa
zawiera błędy, które się nie znoszą.

Implementację sprawdzono na przykładzie rachunkowym z tabeli 8 pracy
źródłowej: dokładność ogólna 0,9449 wobec 0,944 podanego przez autorów.

Współczynnik kappa **nie jest** raportowany jako miara główna, zgodnie
z argumentacją Pontiusa i Millonesa (2011).

---

## 6. Biblioteki i ich źródła

### 6.1 Wymagane

| Biblioteka | Wersja minimalna | Licencja | Rola w narzędziu | Cytowanie |
|---|---|---|---|---|
| **Python** | 3.9 | PSF License | język implementacji | van Rossum i Drake (2009) |
| **NumPy** | 1.21 | BSD-3-Clause | wszystkie obliczenia tablicowe | Harris i in. (2020) |
| **rasterio** | 1.3 | BSD-3-Clause | odczyt i zapis GeoTIFF poza QGIS; niesie własnego GDAL-a | Gillies i in. (2013-) |
| **Fiona** | 1.8 | BSD-3-Clause | odczyt warstw wektorowych z przykładami | Gillies i in. (2011-) |
| **GDAL/OGR** | zależnie od QGIS | MIT | odczyt rastrów we wtyczce, sito, polygonizacja | GDAL/OGR contributors (2026) |
| **PROJ** | zależnie od GDAL | MIT | przekształcenia układów współrzędnych | PROJ contributors (2026) |

### 6.2 Opcjonalne, ale zalecane

Bez nich narzędzie działa, lecz korzysta z implementacji wbudowanych,
wolniejszych i w jednym przypadku nie identycznych (rozdział 7).

| Biblioteka | Wersja minimalna | Licencja | Rola | Cytowanie |
|---|---|---|---|---|
| **scikit-image** | 0.19 | BSD-3-Clause | wzorcowa implementacja SLIC | van der Walt i in. (2014) |
| **scikit-learn** | 1.0 | BSD-3-Clause | wzorcowa implementacja klasyfikatora Random Forest | Pedregosa i in. (2011) |
| **SciPy** | 1.7 | BSD-3-Clause | filtry: minimum i maksimum ruchome, etykietowanie spójnych składowych | Virtanen i in. (2020) |

### 6.3 Środowisko wykonawcze

| Składnik | Licencja | Rola |
|---|---|---|
| **QGIS** 3.22 do 4.99 | GPL-2.0-or-later | środowisko wtyczki, kanwa mapy, warstwy |
| **PyQt** (Qt5 albo Qt6) | GPL-3.0 (powiązanie) | interfejs panelu wtyczki |
| **tkinter** | PSF License, część biblioteki standardowej | interfejs programu okienkowego |

Plik `core/compat.py` odpowiada za zgodność z obiema generacjami Qt:
tworzenie pól atrybutów różni się między `QVariant` (Qt5)
a `QMetaType.Type` (Qt6).

### 6.4 Narzędzia budowania, nie wchodzą w skład programu

| Narzędzie | Licencja | Rola |
|---|---|---|
| **PyInstaller** 6.x | GPL-2.0-or-later z wyjątkiem pozwalającym na dystrybucję programów zamkniętych | złożenie pliku .exe |
| **Inno Setup** 6 | licencja własna, zbliżona do BSD | instalator Windows |
| **GitHub Actions** | usługa | budowanie w chmurze |

### 6.5 Uwaga o licencjach

Narzędzie jest objęte GPL-3.0-or-later, co jest zgodne z licencjami
BSD i MIT wszystkich bibliotek wymienionych wyżej: te licencje są
permisywne i dają się włączyć do dzieła na GPL.

Pełne teksty licencji bibliotek składanych do pliku .exe trafiają do
katalogu instalacyjnego razem z programem. **Przed publikacją wydania
warto zweryfikować licencje dokładnie tych wersji**, które PyInstaller
faktycznie dołączył, bo lista zależności pośrednich bywa dłuższa niż
lista zależności bezpośrednich.

---

## 7. Mechanizm zapasowy

Jest to cecha architektury, którą trzeba opisać w artykule, bo wpływa
na odtwarzalność.

Plik `core/deps.py` wykrywa przy starcie, które biblioteki opcjonalne
są obecne, i ustawia trzy znaczniki: `HAS_SKIMAGE`, `HAS_SKLEARN`,
`HAS_SCIPY`. Rdzeń zawiera **własne implementacje** wszystkich trzech
funkcji, używane, gdy biblioteki brak.

| Funkcja | Z biblioteką | Bez biblioteki |
|---|---|---|
| Segmentacja SLIC | `skimage.segmentation.slic` | `_slic_builtin()` w `slic.py` |
| Random Forest | `sklearn.ensemble.RandomForestClassifier` | `BuiltinRandomForest` w `classifier.py` |
| Filtry morfologiczne | `scipy.ndimage` | `_sliding_extreme()`, `_box_mean()` |
| Sito | `gdal.SieveFilter` | `_sieve_builtin()` |

Funkcja `deps.engine_report()` zwraca pole `exact`, prawdziwe wyłącznie
wtedy, gdy obecne są **i** scikit-image, **i** scikit-learn. Polecenie
`geoai sprawdz` wypisuje to operatorowi wprost, a wtyczka pokazuje
w panelu.

**Zalecenie dla pracy naukowej:** przeprowadzać badanie wyłącznie
w konfiguracji pełnej, z obiema bibliotekami, i podać to w opisie
metody. Implementacje wbudowane służą temu, żeby narzędzie w ogóle
działało u osoby, która nie potrafi doinstalować bibliotek, a nie temu,
żeby produkować wyniki do publikacji.

---

## 8. Pełny wykaz parametrów

### 8.1 Dostępne w interfejsie

| Parametr | Domyślnie | Zakres | Gdzie ustawiany |
|---|---|---|---|
| Wielkość obiektu | 10 m² | 0,5 do 10 000 | panel krok 1, zakładka Nauka |
| Liczba obiektów | 10 000 | 100 do 2 000 000 | to samo, wyrażone inaczej |
| Rozdzielczość robocza | jak w pliku | 0 do 100 | panel krok 1 |
| Zwartość SLIC | 0,15 | 0,01 do 1,0 | panel krok 1, ustawienia zaawansowane |
| Wygładzanie sigma | 2,5 | 0 do 10 | to samo |
| Tylko widok ekranu | wyłączone | tak, nie | panel krok 1 |
| Próg zieloności | z przykładów | −2,0 do 2,0 | panel krok 3 |
| Okno uśredniania | 3 px | 1 do 15 | panel krok 3 |
| Tryb korekty | całosegmentowy | dwa tryby | panel krok 3 |
| Najmniejszy płat | 0 | 0 do 200 000 px | panel krok 3 (we wtyczce w pikselach, w programie w m²) |
| Sposób losowania | warstwowy | warstwowy, prosty | panel krok 4 |
| Minimum punktów na klasę | 50 | 1 do 1 000 | panel krok 4 |
| Łącznie punktów | 200 | 1 do 20 000 | panel krok 4 |
| Minimalne pokrycie obiektu | 0,5 | 0 do 1 | tylko wiersz poleceń, `--pokrycie` |

### 8.2 Stałe w kodzie, niedostępne z interfejsu

| Stała | Wartość | Plik | Znaczenie |
|---|---|---|---|
| `N_TREES` | 100 | classifier.py | liczba drzew w modelu Random Forest |
| `RANDOM_SEED` | 42 | classifier.py | ziarno wszystkich losowań |
| `JM_GOOD` | 1,9 | classifier.py | próg oceny „dobrze" |
| `JM_FAIR` | 1,7 | classifier.py | próg oceny „słabo" |
| `MAX_ITERATIONS` | 10 | slic.py | iteracje SLIC |
| `DEFAULT_COMPACTNESS` | 0,15 | slic.py | zwartość |
| `DEFAULT_SIGMA` | 2,5 | slic.py | rozmycie wstępne |
| `GREY_LEVELS` | 15 | features.py | poziomy szarości GLCM |
| `DIRECTIONS` | 4 kierunki | features.py | 0, 45, 90, 135 stopni |
| `MIN_TEXTURE_PIXELS` | 16 | features.py | próg liczenia faktury |
| `GROUND_BLOCK_M` | 1,0 m | features.py | blok minimum przy szacowaniu gruntu |
| `GROUND_OPENING_M` | 40,0 m | features.py | okno otwarcia morfologicznego |
| `WHOLE_SEGMENT_SHARE` | 0,25 | refine.py | próg przewrócenia segmentu |
| `DEFAULT_WINDOW` | 3 | refine.py | okno uśredniania ExG |
| `CONFIDENCE_Z` | 1,96 | accuracy.py | przedział ufności 95 procent |
| `MAX_WORKING_PIXELS` | 15 000 000 | qgis_io.py | największa dopuszczalna siatka robocza |
| `OSTRZEZENIE_PIKSELE` | 6 000 000 | qgis_io.py | próg ostrzeżenia o czasie |

Zmiana którejkolwiek z tych stałych wymaga edycji kodu i unieważnia
porównywalność z wynikami uzyskanymi na wersji 1.0.2.

---

## 9. Skrypty i pliki konfiguracyjne

### `metadata.txt`

Plik wymagany przez QGIS. Zawiera nazwę wtyczki, wersję, zakres
obsługiwanych wersji QGIS (`qgisMinimumVersion=3.22`,
`qgisMaximumVersion=4.99`), autora, opis, ikonę i adres repozytorium.
QGIS odczytuje go przy instalacji i wyświetla w menedżerze wtyczek.

**Pułapka:** plik jest w formacie INI czytanym przez `configparser`,
który traktuje znak procenta jako wprowadzenie podstawienia. Znak
procenta w opisie powoduje błąd instalacji, dlatego w opisie użyto
słowa „proc.".

### `requirements.txt` i `requirements-minimalne.txt`

Listy zależności dla wersji z wiersza poleceń, w formacie `pip`.
Pierwsza zawiera komplet, druga tylko trzy biblioteki konieczne.
Wersje podane są jako dolne ograniczenia (`>=`), co ułatwia instalację,
ale **nie zapewnia odtwarzalności**: do badania naukowego należy
zamrozić dokładne wersje poleceniem `pip freeze` i dołączyć wynik do
materiałów uzupełniających.

### `GeoAI_Klasyfikator.spec`

Przepis dla PyInstallera, plik w składni Pythona. Określa:

- punkt wejścia (`okno.py`) i ścieżki wyszukiwania modułów,
- **dane towarzyszące**: pliki GDAL-a i PROJ-a zbierane przez
  `collect_data_files`, bez których program nie otworzyłby żadnego
  GeoTIFF-a,
- **moduły ukryte**: wczytywane dynamicznie, których analizator
  statyczny sam nie znajdzie (`rasterio.sample`, `fiona.schema` i inne),
- **wykluczenia**: matplotlib, PyQt, PyTorch, TensorFlow i inne pakiety,
  które nie są używane, a ważą swoje,
- nazwę pliku wynikowego, ikonę i zasób wersji.

### `wersja.txt`

Zasób wersji wpisywany w plik .exe. Windows pokazuje go we
właściwościach pliku. Zawiera nazwę produktu, wersję, autora
i informację o licencji. Wymagany przez SignPath.io przy podpisywaniu
kodu, które wymusza niezmienność tych pól.

### `instalator.iss`

Skrypt Inno Setup. Buduje instalator bez wymogu uprawnień
administratora (`PrivilegesRequired=lowest`), instalujący do katalogu
użytkownika, z polskim interfejsem, skrótem w menu Start i wpisem
umożliwiającym odinstalowanie.

### `.github/workflows/zbuduj-exe.yml`

Definicja procesu budowania w chmurze GitHuba, w formacie YAML.
Dwanaście kroków na maszynie `windows-latest`: pobranie repozytorium,
instalacja Pythona 3.11, instalacja bibliotek, sprawdzenie składni,
budowanie pliku .exe, weryfikacja jego nazwy, rozmiaru, ikony i metadanych,
instalacja Inno Setup, zbudowanie instalatora, spakowanie wersji
przenośnej, policzenie sum SHA-256 i publikacja.

Znaczenie dla pracy naukowej: **każdy plik wykonywalny jest
odtwarzalnie zbudowany z oznaczonego stanu repozytorium**, na maszynie
bez dostępu do komputera autora, a jego suma kontrolna jest publikowana.

### `.gitattributes` i `.gitignore`

Pierwszy ustala końce wierszy (LF dla kodu, CRLF dla plików wsadowych
Windows, brak zmian dla plików binarnych). Drugi wyklucza z repozytorium
wyniki budowania i środowiska wirtualne.

### `zbuduj.bat`

Skrypt wsadowy dla Windows, budujący program lokalnie: tworzy
środowisko wirtualne, instaluje biblioteki, uruchamia PyInstallera
i Inno Setup.

---

## 10. Odtwarzalność

### Co zapewnia powtarzalność

Ziarno generatora liczb pseudolosowych jest ustalone na 42 we wszystkich
losowaniach: w klasyfikatorze Random Forest, w walidacji krzyżowej przy liczeniu
rozdzielności i w losowaniu punktów kontrolnych. Te same dane wejściowe
i te same ustawienia dają **tę samą mapę co do piksela**, co sprawdzono
dwoma niezależnymi przebiegami.

### Co może zmienić wynik mimo niezmienionego kodu

| Czynnik | Dlaczego |
|---|---|
| Wersja scikit-learn | domyślne wartości `RandomForestClassifier` nie są w kodzie ustawione jawnie |
| Wersja scikit-image | drobne zmiany w implementacji SLIC między wydaniami |
| Brak bibliotek opcjonalnych | uruchomienie implementacji zapasowych (rozdział 7) |
| Rozdzielczość robocza | inna siatka daje inne obiekty i inne wartości cech; siatka powyżej 15 mln pikseli jest odrzucana |
| Rozmiar sceny mniejszy niż 80 m | ogranicza okno otwarcia przy szacowaniu gruntu |

### Minimum, które trzeba podać w artykule

1. Wersja narzędzia (1.0.2) i identyfikator rewizji w repozytorium.
2. Wersje Pythona, NumPy, SciPy, scikit-learn, scikit-image, rasterio,
   Fiona i GDAL-a, najlepiej jako wynik `pip freeze`.
3. Wersja QGIS, jeśli badanie prowadzono wtyczką.
4. Wszystkie parametry z tabeli 8.1, nie tylko te zmienione.
5. Informacja, czy użyto korekty zieloności i sita, oraz z jakimi
   wartościami.
6. Potwierdzenie, że obie biblioteki opcjonalne były obecne.

---

## 11. Słownik pojęć technicznych

**Bagging** (*bootstrap aggregating*): budowanie wielu modeli na
losowych próbach ze zwracaniem i uśrednianie ich odpowiedzi.

**Bootstrap**: losowanie ze zwracaniem próby o liczebności równej
oryginalnej.

**Cecha** (*feature*): jedna liczba opisująca obiekt. Tutaj 19 albo 24.

**Entropia**: miara nieuporządkowania rozkładu. W GLCM wysoka entropia
oznacza fakturę chaotyczną.

**Głosowanie miękkie**: uśrednianie rozkładów prawdopodobieństwa
zwracanych przez składowe modele, w odróżnieniu od głosowania twardego,
które liczy same wskazania.

**Nieczystość Giniego**: miara wymieszania klas w węźle drzewa.

**Otwarcie morfologiczne**: erozja, po niej dylatacja. Usuwa obiekty
węższe od elementu strukturalnego.

**Próba warstwowa**: losowanie, w którym populacja dzielona jest na
warstwy, a próba losowana jest osobno w każdej z nich.

**Przeuczenie** (*overfitting*): dopasowanie modelu do szczegółów próby
uczącej kosztem zdolności uogólniania.

**Superpiksel**: zwarta grupa pikseli o podobnych właściwościach,
traktowana jako jednostka analizy.

**Walidacja krzyżowa**: podział próby na części, uczenie na jednych
i sprawdzanie na pozostałych, z rotacją.

**Wskaźnik Youdena**: czułość plus swoistość minus jeden; maksymalizuje
się go przy doborze progu.

**Współrzędne chromatyczne**: udziały kanałów w ich sumie, niewrażliwe
na jasność oświetlenia.

---

## 12. Jak to cytować

**Narzędzie:**

> Górniak, G. (2026). *GeoAI Klasyfikator* (wersja 1.0.2) [oprogramowanie
> komputerowe]. <https://github.com/gorniakgrzegorz/geoai_klasyfikator>

Metadane do cytowania są w pliku [CITATION.cff](CITATION.cff), a GitHub
pokazuje je pod przyciskiem *Cite this repository*. Każde wydanie jest
archiwizowane w Zenodo, które nadaje mu DOI; **[DO UZUPEŁNIENIA: DOI
po pierwszej archiwizacji]**.

**Metody**, które trzeba zacytować niezależnie od narzędzia, bo
narzędzie jest tylko ich implementacją: Achanta i in. (2012) przy
segmentacji, Haralick i in. (1973) przy fakturze, Breiman (2001) przy
klasyfikatorze Random Forest, Olofsson i in. (2014) oraz Stehman (2014) przy ocenie
dokładności, a przy wskaźnikach roślinności odpowiednio Woebbecke i in.
(1995), Gitelson i in. (2002) i Hunt i in. (2005).

---

## 13. Bibliografia

Pozycje sprawdzone w bazie Crossref (preprint scikit-learn w DataCite):
autorzy, rok, tytuł, czasopismo i DOI zgadzają się z rekordem i żadna
pozycja nie jest wycofana. Do pracy o SciPy (Virtanen i in., 2020)
wydawca dołączył sprostowanie (*correction*), które nie jest
wycofaniem.

### Metody

Achanta, R., Shaji, A., Smith, K., Lucchi, A., Fua, P., Süsstrunk, S.
(2012). SLIC superpixels compared to state-of-the-art superpixel
methods. *IEEE Transactions on Pattern Analysis and Machine
Intelligence*, 34(11), 2274–2282.
doi:[10.1109/TPAMI.2012.120](https://doi.org/10.1109/TPAMI.2012.120)

Belgiu, M., Drăguţ, L. (2016). Random forest in remote sensing:
A review of applications and future directions. *ISPRS Journal of
Photogrammetry and Remote Sensing*, 114, 24–31.
doi:[10.1016/j.isprsjprs.2016.01.011](https://doi.org/10.1016/j.isprsjprs.2016.01.011)

Blaschke, T. (2010). Object based image analysis for remote sensing.
*ISPRS Journal of Photogrammetry and Remote Sensing*, 65(1), 2–16.
doi:[10.1016/j.isprsjprs.2009.06.004](https://doi.org/10.1016/j.isprsjprs.2009.06.004)

Breiman, L. (2001). Random forests. *Machine Learning*, 45(1), 5–32.
doi:[10.1023/A:1010933404324](https://doi.org/10.1023/A:1010933404324)

Gitelson, A. A., Kaufman, Y. J., Stark, R., Rundquist, D. (2002).
Novel algorithms for remote estimation of vegetation fraction.
*Remote Sensing of Environment*, 80(1), 76–87.
doi:[10.1016/S0034-4257(01)00289-9](https://doi.org/10.1016/S0034-4257%2801%2900289-9)

Haralick, R. M., Shanmugam, K., Dinstein, I. (1973). Textural features
for image classification. *IEEE Transactions on Systems, Man, and
Cybernetics*, 3(6), 610–621.
doi:[10.1109/TSMC.1973.4309314](https://doi.org/10.1109/TSMC.1973.4309314)

Hunt, E. R., Cavigelli, M., Daughtry, C. S. T., McMurtrey, J. E.,
Walthall, C. L. (2005). Evaluation of digital photography from model
aircraft for remote sensing of crop biomass and nitrogen status.
*Precision Agriculture*, 6(4), 359–378.
doi:[10.1007/s11119-005-2324-5](https://doi.org/10.1007/s11119-005-2324-5)

Ledoit, O., Wolf, M. (2004). A well-conditioned estimator for
large-dimensional covariance matrices. *Journal of Multivariate
Analysis*, 88(2), 365–411.
doi:[10.1016/S0047-259X(03)00096-4](https://doi.org/10.1016/S0047-259X%2803%2900096-4)

Olofsson, P., Foody, G. M., Stehman, S. V., Woodcock, C. E. (2013).
Making better use of accuracy data in land change studies: Estimating
accuracy and area and quantifying uncertainty using stratified
estimation. *Remote Sensing of Environment*, 129, 122–131.
doi:[10.1016/j.rse.2012.10.031](https://doi.org/10.1016/j.rse.2012.10.031)

Olofsson, P., Foody, G. M., Herold, M., Stehman, S. V., Woodcock, C. E.,
Wulder, M. A. (2014). Good practices for estimating area and assessing
accuracy of land change. *Remote Sensing of Environment*, 148, 42–57.
doi:[10.1016/j.rse.2014.02.015](https://doi.org/10.1016/j.rse.2014.02.015)

Pontius, R. G. Jr., Millones, M. (2011). Death to Kappa: birth of
quantity disagreement and allocation disagreement for accuracy
assessment. *International Journal of Remote Sensing*, 32(15),
4407–4429.
doi:[10.1080/01431161.2011.552923](https://doi.org/10.1080/01431161.2011.552923)

Stehman, S. V. (2014). Estimating area and map accuracy for stratified
random sampling when the strata are different from the map classes.
*International Journal of Remote Sensing*, 35(13), 4923–4939.
doi:[10.1080/01431161.2014.930207](https://doi.org/10.1080/01431161.2014.930207)

Woebbecke, D. M., Meyer, G. E., Von Bargen, K., Mortensen, D. A.
(1995). Color indices for weed identification under various soil,
residue, and lighting conditions. *Transactions of the ASAE*, 38(1),
259–269.
doi:[10.13031/2013.27838](https://doi.org/10.13031/2013.27838)

Youden, W. J. (1950). Index for rating diagnostic tests. *Cancer*,
3(1), 32–35.
doi:[10.1002/1097-0142(1950)3:1<32::AID-CNCR2820030106>3.0.CO;2-3](https://doi.org/10.1002/1097-0142%281950%293:1%3C32::AID-CNCR2820030106%3E3.0.CO;2-3)

### Oprogramowanie

Harris, C. R., Millman, K. J., van der Walt, S. J. i in. (2020). Array
programming with NumPy. *Nature*, 585, 357–362.
doi:[10.1038/s41586-020-2649-2](https://doi.org/10.1038/s41586-020-2649-2)

Pedregosa, F., Varoquaux, G., Gramfort, A. i in. (2011). Scikit-learn:
Machine Learning in Python. *Journal of Machine Learning Research*, 12,
2825–2830. Wersja preprintu:
doi:[10.48550/arXiv.1201.0490](https://doi.org/10.48550/arXiv.1201.0490)

van der Walt, S., Schönberger, J. L., Nunez-Iglesias, J. i in. (2014).
scikit-image: image processing in Python. *PeerJ*, 2, e453.
doi:[10.7717/peerj.453](https://doi.org/10.7717/peerj.453)

Virtanen, P., Gommers, R., Oliphant, T. E. i in. (2020). SciPy 1.0:
fundamental algorithms for scientific computing in Python. *Nature
Methods*, 17, 261–272.
doi:[10.1038/s41592-019-0686-2](https://doi.org/10.1038/s41592-019-0686-2)

**Oprogramowanie bez publikacji recenzowanej**, cytowane jako
oprogramowanie, z podaniem wersji i daty dostępu:

- GDAL/OGR contributors. *GDAL/OGR Geospatial Data Abstraction software
  Library*. Open Source Geospatial Foundation. <https://gdal.org>
- PROJ contributors. *PROJ coordinate transformation software library*.
  Open Source Geospatial Foundation. <https://proj.org>
- Gillies, S. i in. *Rasterio: geospatial raster I/O for Python
  programmers*. Mapbox. <https://rasterio.readthedocs.io>
- Gillies, S. i in. *Fiona: OGR's neat, nimble API for Python
  programmers*. <https://fiona.readthedocs.io>
- QGIS Development Team. *QGIS Geographic Information System*. Open
  Source Geospatial Foundation Project. <https://qgis.org>
- van Rossum, G., Drake, F. L. (2009). *Python 3 Reference Manual*.
  CreateSpace. <https://python.org>

---

© Grzegorz Górniak · gorniakgrzegorz@gmail.com · GPL-3.0-or-later
