# Uwarunkowania naukowe

**Co dokładnie decyduje o tym, że obiekt trafia do danej klasy**

Dokument opisuje metodę zaimplementowaną w programie GeoAI
Klasyfikator w wersji 1.0.0: wzory, stałe, progi i reguły decyzyjne
w takiej postaci, w jakiej występują w kodzie. Powstał po to, by
wyniki dało się opisać w artykule i powtórzyć.

Każda liczba podana niżej jest wartością faktycznie użytą
w obliczeniach; przy każdej wskazano plik źródłowy. Tam, gdzie
implementacja odbiega od kanonicznego sformułowania z literatury,
jest to zaznaczone osobno.

---

## Spis treści

1. [Rzecz najważniejsza: co jest ustalone, a co wyuczone](#1)
2. [Jednostka analizy: obiekt, nie piksel](#2)
3. [Segmentacja SLIC](#3)
4. [Przestrzeń cech: 19 albo 24 wymiary](#4)
   - [4.1 Barwa](#41) · [4.2 Wskaźniki roślinności](#42)
   - [4.3 Faktura GLCM](#43) · [4.4 Kształt](#44)
   - [4.5 Kontekst](#45) · [4.6 Wysokość](#46)
5. [Reguła decyzyjna: las losowy](#5)
6. [Rozróżnialność klas przed uczeniem](#6)
7. [Korekty po klasyfikacji](#7)
8. [Ocena dokładności i estymacja powierzchni](#8)
9. [Zestawienie wszystkich stałych](#9)
10. [Ograniczenia metody](#10)
11. [Jak to opisać w artykule](#11)
12. [Literatura](#12)

---

<a name="1"></a>
## 1. Rzecz najważniejsza: co jest ustalone, a co wyuczone

To jest pytanie, od którego trzeba zacząć, bo bez odpowiedzi na nie
reszta dokumentu bywa źle rozumiana.

**W programie nie ma ani jednej reguły typu „jeśli zieloność powyżej
0,15, to trawa".** Nie istnieje żaden słownik klas, żadna tablica
progów dla pokrycia terenu, żadna wiedza o tym, jak wygląda droga czy
dach. Przynależność obiektu do klasy wynika **wyłącznie** z granic
decyzyjnych, których las losowy nauczył się z przykładów wskazanych
przez użytkownika.

Trzy poziomy, które warto rozdzielić:

| Poziom | Co to jest | Czy można to zmienić |
|---|---|---|
| **Stałe algorytmu** | sposób liczenia cech: liczba poziomów szarości w GLCM, kierunki analizy, szerokość okna gruntu, liczba drzew | wymagają zmiany w kodzie; wszystkie wypisane w rozdz. 9 |
| **Parametry użytkownika** | rozdzielczość robocza, wielkość obiektu, zwartość, wygładzenie, próg zieloności, najmniejszy płat | ustawiane w interfejsie przy każdym przebiegu |
| **Granice klas** | co właściwie znaczy „trawa" w danym zbiorze | **wyuczone z przykładów, inne dla każdego nalotu** |

Praktyczny wniosek dla artykułu: **model nie jest przenośny między
nalotami bez ponownego uczenia.** Oświetlenie, faza fenologiczna,
wilgotność gleby i ustawienia kamery przesuwają rozkłady cech. Model
wyuczony na nalocie czerwcowym zastosowany do wrześniowego da wynik,
którego nie da się obronić. Ta sama uwaga dotyczy nalotów z różnych
wysokości i różnych kamer.

---

<a name="2"></a>
## 2. Jednostka analizy: obiekt, nie piksel

Klasyfikacja obiektowa (GEOBIA, *geographic object-based image
analysis*, Blaschke 2010) grupuje sąsiadujące piksele o podobnych
własnościach i klasyfikuje takie grupy. Ma to trzy konsekwencje
istotne dla interpretacji wyników.

**Pierwsza: nośnik informacji.** Pojedynczy piksel zdjęcia RGB niesie
trzy liczby. Obiekt złożony z kilkuset pikseli niesie ich 19 albo 24,
w tym wielkości, których pojedynczy piksel mieć nie może: wariancję
wewnętrzną, miary faktury, kształt, relację do otoczenia. Przy
rozdzielczości dronowej jeden obiekt odpowiada realnemu fragmentowi
terenu, kawałkowi zagonu, połaci dachu, koronie drzewa.

**Druga: brak szumu typu „sól z pieprzem".** Mapa pikselowa z zakresu
widzialnego zawsze zawiera rozproszone pojedyncze piksele błędnie
sklasyfikowane. Mapa obiektowa ich nie ma, bo najmniejszą jednostką
decyzji jest cały obiekt.

**Trzecia, i to jest ograniczenie, nie zaleta: rozdzielczość
tematyczna mapy jest ograniczona przez wielkość obiektu.** Obiekt
nigdy nie zostanie podzielony między dwie klasy. Pas trawy węższy niż
obiekt nie pojawi się na mapie, chyba że zostanie odzyskany korektą
pikselową (rozdz. 7.1). To musi znaleźć się w opisie metody, bo ma
wpływ na bilans powierzchni klas liniowych i wąskich.

---

<a name="3"></a>
## 3. Segmentacja SLIC

**Źródło:** Achanta i in. (2012).
**Implementacja:** `core/slic.py`; przy obecnym `scikit-image` wywoływana
jest `skimage.segmentation.slic` z identycznymi parametrami (wynik
bit w bit zgodny), bez tej biblioteki działa implementacja własna
realizująca ten sam algorytm.

### 3.1 Przestrzeń i miara

SLIC to lokalne grupowanie metodą k-średnich w przestrzeni
pięciowymiarowej: trzy składowe barwy w przestrzeni **CIELAB** oraz
współrzędne piksela *x*, *y*. Odległość między pikselem a środkiem
skupienia:

```
D = sqrt( d_barwy² + (d_przestrzenna / S)² · m² )

d_barwy       = sqrt( (L−L₀)² + (a−a₀)² + (b−b₀)² )
d_przestrzenna = sqrt( (x−x₀)² + (y−y₀)² )
S             = sqrt( liczba_pikseli / liczba_obiektów )    (odstęp siewu)
m             = zwartość (compactness)
```

**Dlaczego CIELAB, a nie RGB.** Przestrzeń CIELAB jest w przybliżeniu
percepcyjnie jednorodna: równym odległościom liczbowym odpowiadają
podobnie duże różnice barwy w odbiorze. W RGB odległość euklidesowa
jest mocno zniekształcona, ta sama różnica liczbowa oznacza co
innego w ciemnych i w jasnych partiach obrazu. Konwersja przebiega
przez linearyzację sRGB (próg 0,04045), macierz do XYZ, biel D65
(0,950456 / 1,0 / 1,088754) i funkcję sześcianu z progiem
ε = 216/24389, κ = 24389/27 (`core/slic.py`, `rgb_to_lab`).

### 3.2 Zwartość: co ta liczba naprawdę robi

Parametr *m* waży człon przestrzenny względem barwnego:

- **m małe (domyślnie 0,15)**, człon barwny dominuje; granice
  obiektów wiernie podążają za krawędziami barwnymi, ale obiekty
  bywają nieregularne i różnej wielkości;
- **m duże (1,0 i więcej)**, człon przestrzenny dominuje; obiekty są
  regularne, zbliżone do siatki, ale potrafią przeciąć rzeczywistą
  granicę.

**Uwaga praktyczna, którą należy zgłosić w artykule:** przy m = 0,15
rzeczywista liczba obiektów bywa 2–3 razy mniejsza od zamówionej,
a rozrzut ich powierzchni jest duży (obiekt największy bywa
dziesięciokrotnie większy od mediany). Program po każdym podziale
wypisuje **rzeczywistą medianę i maksimum powierzchni** i ostrzega,
gdy mediana przekracza zamówienie o ponad 30 procent. **W publikacji
należy podawać liczbę obiektów zrealizowaną, nie zamówioną**, oraz
medianę ich powierzchni.

### 3.3 Pozostałe ustawienia

| Element | Wartość | Uzasadnienie |
|---|---|---|
| Liczba iteracji | 10 | wartość kanoniczna z pracy Achanty; dalsze iteracje nie zmieniają już podziału w zauważalnym stopniu |
| Wygładzenie przed podziałem | σ = 2,5 (gaussowskie) | tłumi szum sensora i drobną fakturę, które inaczej zalęgłyby sztuczne obiekty |
| Wymuszanie spójności | obiekty mniejsze niż 0,5 · (powierzchnia / liczba_obiektów) są wchłaniane przez sąsiada | każdy obiekt jest jednym spójnym płatem; bez tego k-średnie potrafią zostawić rozproszone resztki |
| Maska | piksele bez danych (nodata, czarne rogi ortomozaiki) wyłączone z podziału | obiekty nie przekraczają granicy zdjęcia |

### 3.4 Dobór wielkości obiektu

Wielkość obiektu jest **najważniejszą decyzją metodyczną całego
postępowania** i powinna być w artykule uzasadniona, nie tylko podana.

Zasada operacyjna: *obiekt musi być mniejszy niż najwęższy element,
który ma zostać wykartowany*. Obiekt obejmujący dwa rodzaje pokrycia
wprowadza błąd, którego żaden klasyfikator nie naprawi, jest to błąd
na poziomie jednostki analizy, nie decyzji.

Wartości wyjściowe stosowane w praktyce:

| Przedmiot kartowania | Siatka robocza | Wielkość obiektu |
|---|---|---|
| Zagony, pola, dachy | 5–10 cm | 5–20 m² |
| Pojedyncze drzewa, krzewy | 3–5 cm | 2–5 m² |
| Luki w drzewostanie, korony | 10–25 cm | 10–30 m² |
| Naloty wielkoobszarowe | 20–25 cm | 20–50 m² |

Poniżej mniej więcej 1–5 cm na piksel segmentacja zaczyna wydzielać
pojedyncze liście i arkusze blachy; obiekty przestają wtedy
odpowiadać obiektom terenowym, a cechy fakturowe tracą interpretację.

---

<a name="4"></a>
## 4. Przestrzeń cech: 19 albo 24 wymiary

**Implementacja:** `core/features.py`.

Każdy obiekt jest opisany wektorem liczb. **To ten wektor, a nie
obraz, trafia do klasyfikatora**, las losowy nigdy nie „widzi"
zdjęcia. Zrozumienie, co w tym wektorze siedzi, jest więc warunkiem
zrozumienia, dlaczego obiekt trafił tam, gdzie trafił.

Bez numerycznego modelu pokrycia terenu (NMPT) wektor ma **19
wymiarów**, z modelem **24**. Program nie dopuszcza mieszania:
klasyfikacja zdjęcia bez NMPT modelem wyuczonym z NMPT jest blokowana
komunikatem błędu, bo oznaczałaby porównywanie różnych przestrzeni
cech.

### Komplet cech: nazwy używane w kodzie i w tabeli atrybutów

| # | Nazwa w kodzie | Grupa | Jednostka |
|---|---|---|---|
| 1 | `r_mean` | barwa | 0–1 |
| 2 | `g_mean` | barwa | 0–1 |
| 3 | `b_mean` | barwa | 0–1 |
| 4 | `r_std` | barwa | 0–1 |
| 5 | `g_std` | barwa | 0–1 |
| 6 | `b_std` | barwa | 0–1 |
| 7 | `brightness_mean` | barwa | 0–1 |
| 8 | `exg_mean` | wskaźnik | bezwymiarowa, ok. −1…1 |
| 9 | `vari_mean` | wskaźnik | bezwymiarowa |
| 10 | `ngrdi_mean` | wskaźnik | bezwymiarowa, −1…1 |
| 11 | `contrast` | faktura | bezwymiarowa, ≥ 0 |
| 12 | `homogeneity` | faktura | bezwymiarowa, 0–1 |
| 13 | `energy` | faktura | bezwymiarowa, 0–1 |
| 14 | `entropy` | faktura | bity (skala sumy 4 kierunków) |
| 15 | `area` | kształt | m² |
| 16 | `perimeter` | kształt | m |
| 17 | `circularity` | kształt | bezwymiarowa, 0–1,5 |
| 18 | `convexity` | kształt | bezwymiarowa, 0–1 |
| 19 | `brightness_rel_neighbors` | kontekst | 0–1, ze znakiem |
| 20 | `dsm_mean` | wysokość | m (rzędna) |
| 21 | `dsm_std` | wysokość | m |
| 22 | `slope_mean` | wysokość | stopnie |
| 23 | `dsm_rel_neighbors` | wysokość | m, ze znakiem |
| 24 | `hag_mean` | wysokość | m nad gruntem |

Cechy 1–19 liczone są zawsze; 20–24 wymagają NMPT. Kolejność
w tabeli odpowiada kolejności kolumn w macierzy cech i w tabeli
atrybutów warstwy obiektów, co ma znaczenie przy odczytywaniu
ważności cech z modelu.

Istotna cecha wspólna: **żadna z 24 wielkości nie jest standaryzowana
ani skalowana.** Las losowy jest niewrażliwy na monotoniczne
przekształcenia pojedynczej cechy, dzieli po progach, nie po
odległościach, więc skalowanie byłoby zbędną operacją, która
utrudniłaby interpretację ważności cech.

<a name="41"></a>
### 4.1 Barwa: 7 wielkości

| Cecha | Definicja | Co różnicuje |
|---|---|---|
| `r_mean`, `g_mean`, `b_mean` | średnia wartość kanału w obiekcie, w skali 0–1 | barwa ogólna; cień i luki |
| `r_std`, `g_std`, `b_std` | odchylenie standardowe kanału **wewnątrz** obiektu | poszarpana korona kontra gładki trawnik lub dach |
| `brightness_mean` | średnia z (R+G+B)/3 | powierzchnie oświetlone kontra zacienione |

Skalowanie do 0–1 odbywa się według **typu danych pliku**, nie według
rozstępu wartości w zdjęciu: 8-bitowe dzielone przez 255, 16-bitowe
przez 65535. Dzięki temu dwa naloty w tym samym formacie dają
porównywalne wartości, czego nie zapewniłoby rozciąganie histogramu.

Wariancja wewnętrzna (`*_std`) jest w praktyce jedną z
najskuteczniejszych cech dla rozdzielenia pokryć o zbliżonej barwie
średniej: sucha trawa i goła gleba mają podobne `r_mean`, ale trawa
ma wyraźnie wyższe `g_std`.

<a name="42"></a>
### 4.2 Wskaźniki roślinności: 3 wielkości

Konsumenckie kamery dronowe rejestrują wyłącznie zakres widzialny.
**NDVI jest zatem niedostępny**, wymaga bliskiej podczerwieni.
Stosowane są wskaźniki z zakresu widzialnego, liczone na
**współrzędnych chromatycznych**, czyli po normalizacji każdego kanału
sumą trzech:

```
r = R / (R+G+B)     g = G / (R+G+B)     b = B / (R+G+B)
```

| Wskaźnik | Wzór | Źródło |
|---|---|---|
| `exg_mean` | ExG = 2g − r − b | Woebbecke i in. (1995) |
| `vari_mean` | VARI = (g − r) / (g + r − b) | Gitelson i in. (2002) |
| `ngrdi_mean` | NGRDI = (g − r) / (g + r) | Hunt i in. (2005) |

**Po co normalizacja chromatyczna.** Liść w cieniu i ten sam liść
w pełnym słońcu różnią się jasnością kilkukrotnie, ale *proporcją*
barw niemal wcale. Normalizacja usuwa składową jasności, dzięki czemu
ten sam materiał w różnym oświetleniu daje podobną wartość wskaźnika.
Jest to warunek sensownego działania na ortomozaice sklejanej ze
zdjęć wykonanych w zmiennym oświetleniu.

Zabezpieczenia numeryczne: mianowniki bliższe zeru niż 10⁻⁹ dają
wartość 0 zamiast dzielenia przez zero (dotyczy to w praktyce
pikseli czarnych, poza maską).

ExG wraca w drugiej roli, jako podstawa korekty pikselowej
(rozdz. 7.1). Dzięki temu próg wyznaczony na próbkach uczących znaczy
w obu miejscach dokładnie to samo.

<a name="43"></a>
### 4.3 Faktura GLCM: 4 wielkości

**Źródło:** Haralick, Shanmugam i Dinstein (1973).
**Weryfikacja:** zgodność z `skimage.feature.graycoprops` do szóstej
cyfry znaczącej (test w historii projektu).

Procedura, krok po kroku:

1. **Luminancja** według Rec. 601:
   `Y = 0,299·R + 0,587·G + 0,114·B`
2. **Kwantyzacja globalna** do 15 poziomów szarości. Rozstęp brany
   jest z **całego zdjęcia**, nie z pojedynczego obiektu, dzięki temu
   kontrast dwóch obiektów jest porównywalny. Poziom 0 jest
   zarezerwowany dla pikseli spoza obiektu.
3. **Zliczanie par** pikseli sąsiadujących w odległości 1, w czterech
   kierunkach: 0°, 45°, 90°, 135°, symetrycznie.
4. **Odrzucenie poziomu 0** i ponowna normalizacja macierzy, tak by
   liczyły się wyłącznie pary leżące w całości wewnątrz obiektu.
5. **Obliczenie miar** z macierzy P(i,j):

```
contrast     = Σ P(i,j) · (i−j)²                  (średnia z 4 kierunków)
homogeneity  = Σ P(i,j) / (1 + (i−j)²)            (średnia z 4 kierunków)
energy       = Σ P(i,j)²                          (średnia z 4 kierunków)
entropy      = −Σ P(i,j) · log₂ P(i,j)            (średnia × 4 kierunki)
```

**Uwaga do entropii.** Jest ona podawana w skali sumy po czterech
kierunkach, tak jak w implementacji wzorcowej, do której program się
odwołuje, ale liczona jako *średnia pomnożona przez cztery*. Różnica
jest istotna: przy prostym sumowaniu obiekt wąski i wydłużony, dla
którego część kierunków nie ma prawidłowych par, otrzymywał wartość
4–5 razy niższą **wyłącznie z powodu swojego kształtu**. Klasyfikator
uczyłby się wtedy kształtu pod przebraniem faktury. Przyjęte
rozwiązanie zachowuje skalę, usuwając artefakt.

**Próg wielkości.** Obiekty mniejsze niż **16 pikseli** dostają
wartości neutralne (contrast 0, homogeneity 1, energy 1, entropy 0).
Macierz współwystąpień z kilkunastu par jest statystycznie pusta
i wnosiłaby wyłącznie szum.

<a name="44"></a>
### 4.4 Kształt: 4 wielkości

| Cecha | Definicja | Jednostka |
|---|---|---|
| `area` | liczba pikseli × (bok piksela)² | m² |
| `perimeter` | estymator Croftona (niżej) | m |
| `circularity` | 4πA / P², obcięte do 1,5 | bezwymiarowa |
| `convexity` | A / A_otoczki_wypukłej | bezwymiarowa, 0–1 |

**Obwód liczony metodą Croftona**, nie przez zliczanie krawędzi
pikseli:

```
P ≈ (π/4) · [ (poziome + pionowe)/2 + (przekątne)/(2·√2) ]
```

gdzie zliczane są przejścia między wnętrzem a zewnętrzem obiektu
wzdłuż czterech rodzin prostych równoległych. **Uzasadnienie:**
zliczanie krawędzi pikselowych zamienia okrąg w schodki i zawyża jego
obwód o około 27 procent, przez co okrągłość koła nigdy nie
osiągnęłaby 1. Estymator Croftona jest nieobciążony: dla koła
o promieniu 30 pikseli daje 190,2 przy wartości prawdziwej 188,5.
Ceną jest niewielkie zaniżenie dla prostokątów (kwadrat 20 × 20
pikseli: 74,7 zamiast 80).

**Wypukłość liczona z narożników pikseli**, nie z ich środków.
Otoczka wypukła poprowadzona po środkach pikseli jest systematycznie
mniejsza od powierzchni obiektu o pół piksela na obwodzie, przez co
kwadrat wychodziłby „bardziej niż w pełni wypukły". Po poprawce
kwadrat daje dokładnie 1,000, koło 0,978, kształt krzyża 0,609.

Interpretacja: niska wypukłość oznacza obiekt rozgałęziony lub
z wcięciami, typowo fragment sieci drogowej, cieku lub rozczłonkowanej
korony. Niska okrągłość przy wysokiej wypukłości oznacza obiekt
wydłużony, ale zwarty.

<a name="45"></a>
### 4.5 Kontekst: 1 wielkość

```
brightness_rel_neighbors = brightness_mean(obiekt)
                         − średnia brightness_mean(obiekty stykające się)
```

Sąsiedztwo wyznaczane jest z **grafu przyległości** (RAG) budowanego
w sąsiedztwie czterospójnym: dwa obiekty są sąsiadami, jeśli stykają
się bokiem piksela (styk narożnikiem nie wystarcza).

**Po co ta cecha.** Rów melioracyjny, luka w drzewostanie czy cień
pod koroną są ciemniejsze **względem swojego otoczenia**, choć ich
jasność bezwzględna zależy od pory dnia i ekspozycji stoku. Cecha
względna jest odporna na te zmiany i wykrywa obiekty wyróżniające się
lokalnie, czego żadna cecha bezwzględna nie zapewnia.

<a name="46"></a>
### 4.6 Wysokość: 5 wielkości (tylko z NMPT)

| Cecha | Definicja |
|---|---|
| `dsm_mean` | średnia wysokość NMPT w obiekcie |
| `dsm_std` | odchylenie standardowe wysokości wewnątrz obiektu |
| `slope_mean` | średnie nachylenie powierzchni NMPT, w stopniach |
| `dsm_rel_neighbors` | `dsm_mean` minus średnia sąsiadów (ten sam graf co wyżej) |
| `hag_mean` | średnia **wysokość nad gruntem** |

Nachylenie liczone z gradientu numerycznego:
`slope = arctan( sqrt( (∂z/∂x)² + (∂z/∂y)² ) )`, przeliczone na
stopnie.

**Wysokość nad gruntem (`hag_mean`) to cecha o najwyższej wartości
rozdzielczej i zarazem najbardziej wymagająca wyjaśnienia.**

NMPT opisuje wysokość **powierzchni pokrycia**, a nie gruntu. Wartość
bezwzględna miesza więc rzeźbę terenu z obiektami na nim stojącymi:
dach na wzniesieniu ma wyższą rzędną niż dach w dolinie, choć oba mają
tę samą wysokość nad gruntem. Program estymuje powierzchnię gruntu
z samego NMPT, w trzech krokach (`core/features.py`,
`ground_surface`):

1. **minimum w blokach ~1 m**, usuwa pojedyncze wysokie punkty;
2. **otwarcie morfologiczne oknem 40 m** (minimum ruchome, potem
   maksimum ruchome), usuwa wszystko, co węższe niż 40 m, czyli
   korony i budynki, zachowując rzeźbę;
3. **wygładzenie średnią ruchomą**, likwiduje schodki po otwarciu.

```
hag_mean(obiekt) = średnia( NMPT − grunt_estymowany )
```

**Dwa ograniczenia, które należy podać w artykule:**

Po pierwsze, **pod zwartym pokryciem szerszym niż 40 m estymowany
grunt „wjeżdża" na to pokrycie** i wysokość jest tam systematycznie
zaniżona. Dotyczy to wnętrza dużych kompleksów leśnych i rozległych
hal. Jest to znane ograniczenie estymacji gruntu z samego NMPT,
rozwiązaniem jest dostarczenie osobnego NMT, czego obecna wersja nie
obsługuje.

Po drugie, **okno 40 m jest ograniczane do połowy krótszego boku
zdjęcia.** Przy pracy na wycinku węższym niż 80 m realne okno jest
mniejsze niż zalecane i duże dachy mogą otrzymać wysokość bliską zeru.
Program ostrzega o tym w dzienniku. Do wyników publikowanych należy
liczyć całe zdjęcie.

---

<a name="5"></a>
## 5. Reguła decyzyjna: las losowy

**Źródło:** Breiman (2001); przegląd zastosowań w teledetekcji:
Belgiu i Drăguţ (2016).
**Implementacja:** `core/classifier.py`; przy obecnym `scikit-learn`
używana jest `RandomForestClassifier`, bez niej implementacja własna
realizująca ten sam algorytm.

### 5.1 Parametry

| Parametr | Wartość | Uwagi |
|---|---|---|
| Liczba drzew | **100** | |
| Ziarno losowe | **42** | wynik powtarzalny przy tych samych danych |
| Kryterium podziału | **Gini** | domyślne w scikit-learn |
| Liczba cech losowanych w węźle | **√p** (czyli 4 z 19, 5 z 24) | domyślne |
| Próbkowanie | **bootstrap**, n obserwacji ze zwracaniem | domyślne |
| Głębokość | **nieograniczona** (implementacja własna: 40) | domyślne |
| Wagi klas | **brak** | patrz uwaga o niezrównoważeniu niżej |
| `n_jobs` | −1 | rozkłada drzewa na rdzenie; nie zmienia wyniku |

### 5.2 Jak zapada decyzja

1. Każde ze 100 drzew otrzymuje wektor cech obiektu i prowadzi go
   przez ciąg pytań postaci *„czy cecha X ≤ próg?"* aż do liścia.
2. Liść zwraca rozkład klas wyznaczony z obserwacji uczących, które
   w nim wylądowały.
3. Rozkłady z wszystkich drzew są **uśredniane** (głosowanie miękkie,
   nie większościowe).
4. Obiekt otrzymuje klasę o **największym udziale w tym uśrednionym
   rozkładzie**.
5. Udział klasy zwycięskiej jest zapisywany jako **pewność decyzji**.

Formalnie, dla obiektu o wektorze **x**:

```
klasa(x) = argmax_k   (1/100) · Σ_t  P_t(k | x)
pewność(x) =  max_k   (1/100) · Σ_t  P_t(k | x)
```

Progi w pytaniach wewnątrz drzew **nie są zadane z góry**, wybiera je
algorytm tak, by maksymalizować spadek nieczystości Giniego na danych
uczących. To właśnie tu, i tylko tu, powstaje odpowiedź na pytanie
„co decyduje, że obiekt trafia do danej klasy".

### 5.3 Dlaczego las losowy, a nie reguły progowe

Reguła ręczna („jasność poniżej 50 to cień") jest czytelna, ale krucha:
łamie ją każda zmiana oświetlenia, a przy 24 cechach i ośmiu klasach
liczba potrzebnych reguł i ich interakcji przekracza możliwości ręcznego
strojenia. Las losowy ma w tym zastosowaniu cztery własności, które
przesądzają o wyborze (zob. Belgiu i Drăguţ 2016):

- **toleruje cechy skorelowane**, a `exg_mean`, `ngrdi_mean` i `vari_mean`
  są ze sobą silnie skorelowane z definicji;
- **nie wymaga skalowania ani normalizacji**, dzieli po progach;
- **działa przy kilkuset obserwacjach uczących**, co odpowiada
  realistycznemu nakładowi pracy operatora;
- **uczy się w sekundach**, co umożliwia pętlę poprawiania.

### 5.4 Pewność decyzji i co z nią robić

Obiekty, dla których klasa zwycięska zebrała **mniej niż połowę
głosów**, są zliczane i raportowane po każdej klasyfikacji. Są to
miejsca, w których las się waha, zwykle obiekty graniczne albo
reprezentujące odmianę klasy nieobecną w zbiorze uczącym. To one
przynoszą największy przyrost dokładności na jeden dodany przykład.

### 5.5 Niezrównoważenie klas uczących

Program **nie stosuje wag klas**, zachowuje domyślne zachowanie
scikit-learn, by wynik był porównywalny z implementacją wzorcową.
Konsekwencja jest realna: klasa z 300 przykładami systematycznie
wygrywa głosowania z klasą, która ma ich 15.

Program **ostrzega**, gdy stosunek liczebności najliczniejszej do
najrzadszej klasy przekroczy **5:1**, i zaleca dołożenie przykładów
klasie rzadszej. W artykule należy podać liczebności zbioru uczącego
w rozbiciu na klasy.

### 5.6 Pętla poprawiania jako element metody

Pierwszy model niemal nigdy nie jest dobry i nie jest to oznaka
błędu, lecz normalny tryb pracy, który należy opisać:

1. klasyfikacja całości,
2. przegląd **całej** mapy i spisanie *rodzajów* pomyłek (nie
   pojedynczych miejsc),
3. dodanie kilku przykładów każdego rodzaju, w **różnych** częściach
   zdjęcia,
4. ponowne uczenie i klasyfikacja.

Dwie–trzy rundy dają zwykle największy przyrost; kolejne coraz mniej.
Dobór przykładów ukierunkowany na błędy jest skuteczniejszy niż
zwiększanie ich liczby na ślepo.

**Warunek metodyczny:** przykłady uczące dobierane po obejrzeniu mapy
nie mogą być później użyte jako punkty kontrolne. Program pilnuje
tego automatycznie, punkty do oceny nigdy nie trafiają na obiekty
uczące (rozdz. 8.1).

---

<a name="6"></a>
## 6. Rozróżnialność klas przed uczeniem

**Miara:** odległość Jeffriesa–Matusity (JM), liczona **z walidacją
krzyżową**.
**Implementacja:** `core/classifier.py`, `pair_separability`.

### 6.1 Po co to jest

Zanim operator zainwestuje godziny w dobieranie przykładów i opisywanie
punktów kontrolnych, warto wiedzieć, czy przyjęta lista klas w ogóle
jest rozdzielalna w dostępnej przestrzeni cech. Para klas o niskiej
rozróżnialności będzie się myliła niezależnie od liczby przykładów,
trzeba ją albo wzmocnić dodatkową informacją (NMPT), albo połączyć.

### 6.2 Procedura

Dla każdej pary klas:

1. próbki dzielone na **5 części** (walidacja krzyżowa),
2. na części uczącej wyznaczany jest **kierunek Fishera**:
   `w = Σ_pooled⁻¹ (μ_A − μ_B)`, gdzie macierz kowariancji jest
   estymowana ze **skurczem Ledoita–Wolfa** (Ledoit i Wolf 2004),
3. próbki części testowej są **rzutowane na ten kierunek**,
4. na rzutach liczona jest odległość Bhattacharyyi:

```
B = (1/8)·(μ₁−μ₂)²·2/(σ₁²+σ₂²) + (1/2)·ln[ (σ₁²+σ₂²)/2 / (σ₁σ₂) ]
JM = 2·(1 − e^(−B))
```

5. wynik uśredniany po pięciu podziałach.

### 6.3 Dlaczego z walidacją krzyżową i dlaczego to zmienia progi

Klasyczna JM liczona **w pełnej przestrzeni cech** na tych samych
próbkach, z których estymowano parametry, **przy 24 cechach i kilkuset
próbkach osiąga wartość 2,00 dla niemal każdej pary**, również dla
klasy sztucznie rozciętej na pół. Jest to efekt przeuczenia estymatora:
przy wielu wymiarach zawsze znajdzie się kierunek rozdzielający próbkę.
Taka miara nie potrafi wskazać pary problematycznej, czyli nie robi
tego, po co ją liczymy.

Wersja z walidacją krzyżową jest wolna od tej wady. Sprawdzenie
kontrolne: klasa rozcięta losowo na pół daje **0,02–0,07** zamiast
2,00.

**Konsekwencja, którą trzeba zgłosić w artykule:** jest to **miara
pochodna, nie klasyczna wielowymiarowa JM**. Rzut na jeden kierunek
jest z definicji dolnym ograniczeniem pełnej odległości
wielowymiarowej, więc wartości są systematycznie niższe. Progi
1,9 / 1,7 przyjęte z literatury dla klasycznej JM **nie przenoszą się
na tę miarę jeden do jednego** i należy je traktować jako orientacyjne.
**Najbardziej użyteczna jest kolejność par od najtrudniejszej oraz
ranking cech rozdzielających**, nie bezwzględna wartość liczby.

| Wartość | Etykieta w programie | Interpretacja |
|---|---|---|
| ≥ 1,9 | dobrze | klasy wyraźnie rozdzielne |
| 1,7 – 1,9 | znośnie | rozdzielne, ale z pomyłkami |
| < 1,7 | SŁABO | para wymaga interwencji |

### 6.4 Ranking cech

Dla każdej pary liczona jest dodatkowo **jednowymiarowa JM osobno dla
każdej z 24 cech**, a wynik sortowany malejąco. Daje to odpowiedź na
pytanie „czym właściwie te dwie klasy się różnią".

Jest to informacja diagnostyczna o dużej wartości: jeśli „trawa"
i „grunt odkryty" rozchodzą się głównie na `exg_mean`, mamy różnicę
materiałową i wynik jest wiarygodny. Jeśli rozchodzą się głównie na
`area`, model złapał przypadkową prawidłowość w sposobie klikania
przykładów, a nie własność terenu.

---

<a name="7"></a>
## 7. Korekty po klasyfikacji

**Implementacja:** `core/refine.py`. Obie korekty są opcjonalne
i obie **naruszają czysto obiektowy charakter mapy**, fakt ten musi
znaleźć się w opisie metody, jeśli zostały użyte.

<a name="71"></a>
### 7.1 Dociąganie po zieloności

**Problem.** Pas trawy między zagonami, miedza albo trawa wzdłuż rowu
bywa węższy niż obiekt. Jednostka analizy go pochłania i mapa pokazuje
w tym miejscu glebę, choć punkt kontrolny trafia na trawę. Zmniejszanie
obiektów pomaga tylko do pewnego stopnia i kosztuje czas oraz pamięć.

**Rozwiązanie.** Obiekty nadal rozstrzygają, jakim rodzajem terenu
jest dany obszar, ale **dla dwóch wskazanych klas** o przynależności
każdego piksela rozstrzyga jego zieloność. Wszystkie pozostałe klasy
zostają nietknięte.

**Miara.** ExG = 2g − r − b na współrzędnych chromatycznych, ten sam
wskaźnik co cecha `exg_mean`, uśredniony w oknie kwadratowym
(domyślnie **3 × 3 piksele**), by pojedyncze piksele nie migotały.

**Próg.** Wyznaczany **z próbek uczących obu klas**: spośród 256
wartości rozpiętych na zakresie obserwowanym wybierana jest ta,
która maksymalizuje średnią z dwóch trafności, udziału poprawnie
zakwalifikowanych pikseli klasy zielonej i klasy drugiej (kryterium
zrównoważone, odporne na nierówne liczebności).

**Dwa tryby.** W obu piksele klasy drugiej, które czytają się jako
zielone, przechodzą pojedynczo do klasy zielonej, to właśnie odzyskuje
wąskie pasy. Różnią się kierunkiem powrotnym:

- **„Zachowaj zielone obiekty w całości" (domyślny):** obiekt klasy
  zielonej przechodzi do klasy drugiej **tylko w całości** i tylko
  wtedy, gdy mniej niż **25 procent** jego pikseli czyta się jako
  zielone. Trawa przyschnięta lub rzadka zostaje jednolita.
- **„Każdy piksel osobno":** każdy piksel poniżej progu przechodzi do
  klasy drugiej. Krawędzie najostrzejsze, ale płaty trawy bywają
  podziurawione.

**Ograniczenie do zgłoszenia w artykule.** Uśrednianie w oknie 3 × 3
sprawia, że odzyskane pasy wychodzą **nieco szersze niż w naturze**.
Powierzchnię klasy zielonej w uprawach rzędowych należy więc podawać
z zastrzeżeniem albo wyłączyć tę korektę przy bilansowaniu powierzchni.

<a name="72"></a>
### 7.2 Najmniejsza jednostka kartowania

Płaty jednej klasy mniejsze niż zadany próg są wchłaniane przez klasę
otaczającą. Operacja wykonywana jest filtrem `gdal.SieveFilter`
w sąsiedztwie czterospójnym, bez wygładzania granic, przesuwane są
wyłącznie całe małe płaty, a przebieg dużych granic zostaje nienaruszony.

**Zasada metodyczna:** próg należy ustawić **według przeznaczenia
mapy**, a nie tak, by podnieść wynik oceny dokładności. Sito dobrane
pod punkty kontrolne przestaje być od nich niezależne i unieważnia
ocenę.

Uwaga praktyczna: sito o progu rzędu kilku m² usuwa pasy odzyskane
korektą zieloności. Obu korekt zwykle nie stosuje się razem.

---

<a name="8"></a>
## 8. Ocena dokładności i estymacja powierzchni

**Źródła:** Congalton i Green (2019); Olofsson i in. (2014);
Stehman (2014); Pontius i Millones (2011).
**Implementacja:** `core/accuracy.py`.
**Weryfikacja:** implementacja odtwarza opublikowany przykład
rachunkowy z Olofsson i in. (2014, tab. 8), dokładność ogólna 0,9449
przy wartości publikowanej 0,944.

To jest część, której brak w typowym postępowaniu najczęściej
dyskwalifikuje wynik w recenzji.

<a name="81"></a>
### 8.1 Projekt próby

Dwa warianty:

**Losowanie proste.** Punkty rozmieszczone losowo na całej mapie,
niezależnie od tego, co mapa mówi. Daje wynik ogólnomapowy wprost
z liczebności, ale klasy rzadkie otrzymują zbyt mało punktów, by
cokolwiek o nich powiedzieć.

**Losowanie warstwowe według klas mapy (zalecane).** Każda klasa
otrzymuje **nie mniej niż zadane minimum** punktów (domyślnie 50),
a reszta rozdzielana jest proporcjonalnie do powierzchni. Dzięki temu
klasa zajmująca 2 procent mapy ma własny, sensowny przedział ufności.

**Dwa zabezpieczenia wbudowane w program:**

1. **Punkty nigdy nie trafiają na obiekty użyte do uczenia.** Bez
   tego sprawdzalibyśmy model na jego własnej ściądze.
2. **Wagi powierzchniowe zapamiętywane są w chwili losowania**, a nie
   odczytywane z bieżącej mapy. Jest to wymóg Stehmana (2014): warstwy
   muszą zostać przypisane do próby, nawet jeśli mapa zostanie później
   zmieniona. Gdyby operator po wylosowaniu punktów dołożył przykłady
   i przeliczył mapę, wagi przestałyby odpowiadać warstwom, z których
   losowano, a estymatory byłyby obciążone.

**Konsekwencja wykluczenia obiektów uczących, którą trzeba opisać
w metodyce:** populacją docelową nie jest wtedy cała mapa, lecz **mapa
poza obiektami użytymi do uczenia**. Wagi powierzchniowe liczone są na
tej samej, zawężonej populacji, więc estymatory są wewnętrznie
spójne, ale nazwa populacji musi być w artykule podana wprost.

<a name="82"></a>
### 8.2 Opisywanie punktów

Interpretator opisuje każdy punkt **patrząc na samo zdjęcie,
z ukrytą klasyfikacją**. Program sprawdza widoczność warstwy
z wynikiem i ostrzega, zanim pozwoli zacząć.

Nie jest to formalność. Widoczna odpowiedź modelu uruchamia efekt
potwierdzenia: interpretator zgadza się z nią w przypadkach
wątpliwych, a dokładność wychodzi zawyżona o kilka do kilkunastu
punktów procentowych. Jest to jedna z pierwszych rzeczy, o które
pyta recenzent.

**Status danych.** Punkty opisane z lotu ptaka to **dane
referencyjne** wysokiej jakości, nie *ground truth*. Tylko punkty
sprawdzone w terenie są prawdą terenową. Tam, gdzie interpretacja
jest trudna, sucha trawa kontra goła gleba, błędy interpretatora
przypominają błędy modelu, co zawyża zgodność. Rozróżnienie to musi
znaleźć się w artykule.

<a name="83"></a>
### 8.3 Macierz błędów i miary podstawowe

Wiersze: klasa z mapy. Kolumny: klasa referencyjna. Na przekątnej
zgodności.

| Miara | Pytanie | Wzór |
|---|---|---|
| **Dokładność ogólna** | jaka część mapy jest poprawna | suma przekątnej / suma wszystkich |
| **Dokładność użytkownika** (trafność) | gdy mapa mówi „trawa", jak często to naprawdę trawa | przekątna / suma wiersza |
| **Dokładność producenta** (kompletność) | ile rzeczywistej trawy mapa znalazła | przekątna / suma kolumny |

**Kappa nie jest liczona świadomie.** Pontius i Millones (2011)
wykazali, że współczynnik ten jest trudny do interpretacji, silnie
skorelowany z dokładnością ogólną i wprowadza w błąd przy
niezrównoważonych klasach; obecne zalecenia go odradzają.

<a name="84"></a>
### 8.4 Estymatory ważone powierzchnią

To jest sedno rozdziału. Przy losowaniu warstwowym **udział punktów
nie jest udziałem powierzchni**, klasa zajmująca 2 procent mapy może
mieć 20 procent punktów. Zwykła średnia z punktów jest wtedy
obciążona.

Oznaczenia: *W_i* to udział powierzchniowy warstwy *i*; *n_i* to liczba
punktów w warstwie *i*; *n_ij* to punkty z warstwy *i* o klasie
referencyjnej *j*.

```
p_ij = W_i · n_ij / n_i                     udział powierzchni mapy

Dokładność ogólna:        Ô = Σ_j p_jj
Dokładność użytkownika:   Û_i = n_ii / n_i
Dokładność producenta:    P̂_j = p_jj / Σ_i p_ij
Udział powierzchni:       p̂_·j = Σ_i W_i · n_ij / n_i
Powierzchnia:             Â_j = A_całkowita · p̂_·j
```

Wariancje (Olofsson i in. 2014, równania 5–7):

```
V(Ô)    = Σ_i W_i² · Û_i(1−Û_i) / (n_i − 1)
V(Û_i)  = Û_i(1−Û_i) / (n_i − 1)
V(p̂_·j) = Σ_i W_i² · (n_ij/n_i)(1 − n_ij/n_i) / (n_i − 1)

V(P̂_j) = (1/N̂²_·j) · [ N²_j (1−P̂_j)² Û_j(1−Û_j)/(n_j−1)
                       + P̂_j² Σ_{i≠j} N²_i (n_ij/n_i)(1−n_ij/n_i)/(n_i−1) ]
```

Przedziały ufności: **95 procent, z ± 1,96 · pierwiastek z wariancji**.

Dla losowania prostego program liczy analogiczne estymatory
z wagami równymi, tak by i ten projekt dawał przedziały ufności oraz
szacowane powierzchnie.

<a name="85"></a>
### 8.5 Co cytować w artykule

| Liczba | Cytować? |
|---|---|
| Powierzchnia odczytana z mapy | **nie**, zawiera błędy klasyfikacji |
| **Powierzchnia szacowana Â_j** | **tak, zawsze z przedziałem ufności** |
| Dokładność ogólna ważona powierzchnią | **tak, z przedziałem** |
| Dokładność ogólna z surowych liczebności | tylko dodatkowo, dla porównania |

Estymator powierzchni koryguje mapę o błędy wykryte przez próbę
i jest **estymatorem nieobciążonym** przy poprawnie wykonanym
losowaniu. Powierzchnia odczytana wprost z mapy nim nie jest.

Sprawdzenie empiryczne przeprowadzone na danych syntetycznych
o znanej prawdzie (200 powtórzeń, próba warstwowa): pokrycie
95-procentowych przedziałów ufności wyniosło **93,5 / 94,5 / 95,5
procent** dla trzech klas, przy nominalnych 95 procentach. Sama mapa
myliła się w tym teście o −4,6 / +2,2 / +2,4 punktu procentowego,
i właśnie tę różnicę estymator koryguje.

<a name="86"></a>
### 8.6 Ostrzeżenia, które program zgłasza

| Sytuacja | Dlaczego to problem |
|---|---|
| Warstwa bez ani jednego opisanego punktu | jej waga wypada z bilansu, udziały nie sumują się do 100 procent, dokładność ogólna jest zaniżona |
| Klasa z mniej niż ~30 punktami | przedział ufności dla niej jest zbyt szeroki, by cokolwiek orzec |
| Widoczna warstwa klasyfikacji przy opisywaniu | ocena zawyżona, wynik nie nadaje się do publikacji |

---

<a name="9"></a>
## 9. Zestawienie wszystkich stałych

Komplet wartości zaszytych w kodzie. Zmiana którejkolwiek wymaga
ingerencji w pliki źródłowe i powinna być w artykule odnotowana.

### Segmentacja: `core/slic.py`

| Stała | Wartość | Rola |
|---|---|---|
| `DEFAULT_COMPACTNESS` | 0,15 | waga członu przestrzennego |
| `DEFAULT_SIGMA` | 2,5 | wygładzenie przed podziałem |
| `MAX_ITERATIONS` | 10 | iteracje k-średnich |
| próg wchłaniania | 0,5 · (powierzchnia / liczba_obiektów) | wymuszanie spójności |
| biel odniesienia | D65 (0,950456 / 1,0 / 1,088754) | konwersja do CIELAB |

### Cechy: `core/features.py`

| Stała | Wartość | Rola |
|---|---|---|
| `GREY_LEVELS` | 15 | poziomy szarości w GLCM |
| `DIRECTIONS` | 0°, 45°, 90°, 135° | kierunki analizy faktury |
| odległość par | 1 piksel | GLCM |
| `MIN_TEXTURE_PIXELS` | 16 | poniżej: wartości neutralne faktury |
| luminancja | 0,299 R + 0,587 G + 0,114 B | Rec. 601 |
| `GROUND_BLOCK_M` | 1,0 m | blok minimum przy estymacji gruntu |
| `GROUND_OPENING_M` | 40,0 m | okno otwarcia morfologicznego |
| ograniczenie okna | połowa krótszego boku zdjęcia | zabezpieczenie dla wycinków |
| obcięcie okrągłości | 1,5 | zabezpieczenie numeryczne |

### Klasyfikator: `core/classifier.py`

| Stała | Wartość | Rola |
|---|---|---|
| `N_TREES` | 100 | liczba drzew |
| `RANDOM_SEED` | 42 | powtarzalność |
| liczba cech w węźle | √p | losowanie w podziale |
| `JM_GOOD` / `JM_FAIR` | 1,9 / 1,7 | progi oceny rozróżnialności |
| podziały walidacji krzyżowej | 5 | estymacja JM |
| próg ostrzeżenia o niezrównoważeniu | 5:1 | |
| próg pewności decyzji | 0,5 | zliczanie obiektów niepewnych |

### Korekty: `core/refine.py`

| Stała | Wartość | Rola |
|---|---|---|
| `DEFAULT_WINDOW` | 3 × 3 piksele | uśrednianie zieloności |
| `WHOLE_SEGMENT_SHARE` | 0,25 | próg przejścia całego obiektu |
| liczba kandydatów na próg | 256 | wyznaczanie progu ExG |
| sąsiedztwo sita | czterospójne | najmniejsza jednostka kartowania |

### Ocena dokładności: `core/accuracy.py`

| Stała | Wartość | Rola |
|---|---|---|
| `CONFIDENCE_Z` | 1,96 | przedział 95 procent |
| minimum punktów na klasę | 50 (domyślne) | próba warstwowa |

---

<a name="10"></a>
## 10. Ograniczenia metody

Lista do przepisania do sekcji *Limitations*. Każda pozycja jest
realnym ograniczeniem implementacji, nie formalnością.

**1. Wyłącznie zakres widzialny.** Brak bliskiej podczerwieni, więc
brak NDVI i pochodnych. Rozróżnienie gatunków roślin o zbliżonej
barwie w zakresie widzialnym jest poza zasięgiem metody.

**2. Brak cech wyglądu z sieci neuronowej.** Implementacja wzorcowa,
na której wzorowano postępowanie, dokłada opis otoczenia obiektu
z sieci transformerowej (DINOv2/v3). Tutaj go nie ma, pakowanie
PyTorcha i 85 MB wag do wtyczki QGIS nie jest rozsądne. **Skutek jest
konkretny:** klasy różniące się **wzorem przestrzennym**, a nie
materiałem, dwie uprawy o tej samej barwie i wysokości, lecz innym
układzie rzędów, pozostaną nierozdzielone. Rozdzielenie oparte na
materiale (barwa, zieloność, faktura, wysokość) działa normalnie.

**3. Jeden nalot, jeden model.** Model nie przenosi się między
nalotami bez ponownego uczenia (rozdz. 1).

**4. Rozdzielczość tematyczna ograniczona wielkością obiektu.**
Elementy węższe niż obiekt (miedze, ścieżki, rowy) są
niedoszacowane. Dla dwóch klas rozdzielanych zielonością ratuje to
korekta pikselowa, kosztem czystości metody i z lekkim zawyżeniem
szerokości pasów.

**5. Wysokość nad gruntem pod zwartym pokryciem.** Grunt estymowany
z samego NMPT „wjeżdża" na pokrycie szersze niż 40 m (rozdz. 4.6).

**6. Segmentacja wrażliwa na parametry.** Realizowana liczba obiektów
różni się od zamówionej, zwłaszcza przy niskiej zwartości. Należy
raportować liczbę zrealizowaną, medianę powierzchni obiektu, wartość
zwartości i silnik (`scikit-image` albo wbudowany).

**7. Rozróżnialność szacowana z próbek uczących.** Miara JM
w wariancie z walidacją krzyżową jest wskaźnikiem ryzyka, nie dowodem
rozdzielności; jej progi nie są tożsame z progami dla klasycznej JM
(rozdz. 6.3).

**8. Dane referencyjne to nie prawda terenowa** (rozdz. 8.2).

**9. Brak wyrównywania klas.** Klasy rzadkie są systematycznie
niedoszacowywane, gdy zbiór uczący jest niezrównoważony (rozdz. 5.5).

**10. Ograniczenie rozmiaru.** Siatka robocza powyżej 15 milionów
pikseli jest odrzucana z komunikatem; większe zdjęcia wymagają
grubszej rozdzielczości albo podziału na fragmenty. Bez
`scikit-image` praktyczna granica jest znacznie niższa, rzędu pół
miliona pikseli.

**11. Wymagany układ metryczny.** Wszystkie powierzchnie liczone są
jako (bok piksela)², więc zdjęcie w stopniach geograficznych dałoby
wyniki pozbawione sensu.

---

<a name="11"></a>
## 11. Jak to opisać w artykule

Szkielet sekcji *Materials and Methods*, z zaznaczeniem, co
koniecznie podać.

**Dane.** Źródło zdjęcia, data i godzina nalotu, wysokość lotu,
kamera, terenowy rozmiar piksela (GSD), oprogramowanie
fotogrametryczne, układ współrzędnych. Obecność i pochodzenie NMPT.

**Siatka robocza i segmentacja.** Rozdzielczość robocza; zamówiona
i **zrealizowana** liczba obiektów; mediana i rozstęp powierzchni
obiektu; zwartość i wygładzenie; użyty silnik.

**Cechy.** Liczba (19 albo 24) z wyliczeniem grup; zaznaczenie, że
wartości nie są skalowane; parametry GLCM (15 poziomów, odległość 1,
cztery kierunki).

**Zbiór uczący.** Liczba obiektów uczących **w rozbiciu na klasy**;
sposób doboru (klikanie na kanwie albo poligony); liczba rund
poprawiania; informacja, czy przykłady dobierano po obejrzeniu mapy.

**Klasyfikator.** Las losowy, 100 drzew, kryterium Giniego, √p cech
w węźle, bootstrap, ziarno 42, bez wag klas.

**Rozróżnialność.** Wartości JM dla par najtrudniejszych, z adnotacją,
że jest to miara z walidacją krzyżową, a nie klasyczna wielowymiarowa JM.

**Korekty.** Czy użyto dociągania po zieloności (z progiem i oknem)
i najmniejszej jednostki kartowania (z progiem). Jeśli tak, adnotacja,
że mapa nie jest dla tych klas czysto obiektowa.

**Ocena dokładności.** Projekt próby; liczba punktów ogółem i na
klasę; **informacja, że punkty nie trafiały na obiekty uczące,
i wynikające z tego określenie populacji docelowej**; sposób
opisywania punktów (z ukrytą klasyfikacją); macierz błędów;
dokładność ogólna, użytkownika i producenta **ważone powierzchnią**,
z przedziałami 95 procent; **szacowane powierzchnie klas
z przedziałami**; adnotacja o statusie danych referencyjnych;
informacja, że kappy nie liczono i dlaczego.

**Powtarzalność.** Wersja programu, wersje `scikit-image`
i `scikit-learn` (albo informacja, że użyto silników wbudowanych),
ziarno losowe, wartości wszystkich parametrów użytkownika.

---

<a name="12"></a>
## 12. Literatura

Achanta, R., Shaji, A., Smith, K., Lucchi, A., Fua, P.,
Süsstrunk, S. (2012). SLIC superpixels compared to state-of-the-art
superpixel methods. *IEEE Transactions on Pattern Analysis and Machine
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

Congalton, R. G., Green, K. (2019). *Assessing the Accuracy of
Remotely Sensed Data: Principles and Practices* (wyd. 3). CRC Press.

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

Olofsson, P., Foody, G. M., Herold, M., Stehman, S. V.,
Woodcock, C. E., Wulder, M. A. (2014). Good practices for estimating
area and assessing accuracy of land change. *Remote Sensing of
Environment*, 148, 42–57.
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
259–269. doi:[10.13031/2013.27838](https://doi.org/10.13031/2013.27838)

---

## Jak cytować program

> Górniak, G. (2026). *GeoAI Klasyfikator* (wersja 1.0.0)
> [oprogramowanie]. https://github.com/gorniakgrzegorz/geoai_klasyfikator


---

© Grzegorz Górniak · GPL-3.0-or-later · gorniakgrzegorz@gmail.com
