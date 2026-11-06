# GeoAI Klasyfikator: instrukcja użytkownika

Pełny opis obu programów, pole po polu, przycisk po przycisku.
Napisane dla osoby, która nie zajmuje się teledetekcją.

Jeśli chcesz tylko szybko sprawdzić, czy program działa, zajrzyj do
[INSTRUKCJA_TESTERA.md](INSTRUKCJA_TESTERA.md). Jeśli szukasz wzorów
i stałych do artykułu, to [UWARUNKOWANIA_NAUKOWE.md](UWARUNKOWANIA_NAUKOWE.md).

---

## Spis treści

1. [Co ten program właściwie robi](#1-co-ten-program-właściwie-robi)
2. [Którą wersję wybrać](#2-którą-wersję-wybrać)
3. [Czego potrzebujesz](#3-czego-potrzebujesz)
4. [Co program obsługuje](#4-co-program-obsługuje)
5. [Skąd wziąć dane źródłowe](#5-skąd-wziąć-dane-źródłowe)
6. [Co to znaczy, że program się uczy](#6-co-to-znaczy-że-program-się-uczy)
7. [Przygotowanie przykładów](#7-przygotowanie-przykładów)
8. [Wtyczka QGIS, krok po kroku](#8-wtyczka-qgis-krok-po-kroku)
9. [Program dla Windows, krok po kroku](#9-program-dla-windows-krok-po-kroku)
10. [Co powstaje na wyjściu](#10-co-powstaje-na-wyjściu)
11. [Ściąga z ustawieniami](#11-ściąga-z-ustawieniami)
12. [Gdy coś nie działa](#12-gdy-coś-nie-działa)
13. [Słowniczek](#13-słowniczek)

---

## 1. Co ten program właściwie robi

Dostajesz zdjęcie z drona. Program zamienia je na **mapę pokrycia
terenu**: każdy fragment zdjęcia dostaje nazwę klasy, na przykład
*zabudowa*, *droga*, *trawa*, *las*, *woda*, *grunt odkryty*.

### Obiekty zamiast pikseli

Zwykłe programy klasyfikują pojedyncze piksele. Przy zdjęciu z drona,
gdzie piksel ma 3 centymetry, jest to bez sensu: piksel widzi kawałek
liścia albo kawałek dachówki, a nie drzewo czy dach. Wynik wygląda jak
sypnięty pieprzem.

Ten program najpierw **tnie zdjęcie na obiekty**: zwarte kawałki
o podobnej barwie, odpowiadające fragmentowi zagonu, połaci dachu czy
koronie drzewa. Dopiero obiekt dostaje klasę, w całości.

### Czego program się uczy

Dla każdego obiektu program mierzy **19 liczb** z samego zdjęcia,
a jeśli dołożysz model wysokości, to **24 liczby**:

| Grupa | Ile | Co to opisuje |
|---|---|---|
| Kolor | 7 | średnia i zmienność czerwieni, zieleni, niebieskiego, oraz jasność |
| Zieleń | 3 | jak bardzo coś jest zielone, liczone tak, by cień nie mylił wyniku |
| Faktura | 4 | czy powierzchnia jest gładka jak dach, czy chropowata jak korona drzewa |
| Kształt | 4 | powierzchnia, obwód, okrągłość, wypukłość obiektu |
| Otoczenie | 1 | czy obiekt jest jaśniejszy czy ciemniejszy od sąsiadów |
| Wysokość | 5 | tylko z modelem wysokości: wysokość, nachylenie, wysokość nad gruntem |

Potem pokazujesz programowi po kilkanaście przykładów każdej klasy,
a on uczy się reguły i stosuje ją do całego zdjęcia. Metoda nazywa się
**Random Forest**: sto drzew decyzyjnych głosuje nad każdym obiektem.

### Czego program nie robi

Warto wiedzieć od razu, żeby nie szukać potem po menu.

- **Nie ma NDVI.** Zwykłe kamery dronowe nie rejestrują podczerwieni.
  Zastępują ją wskaźniki zieloności liczone z kanałów widzialnych.
- **Nie rozpozna klas, które różnią się tylko układem przestrzennym.**
  Dwie uprawy o tej samej barwie i wysokości, różniące się tylko
  rozstawem rzędów, zostaną pomieszane.
- **Nie zgadnie, czego chcesz.** Klasy definiujesz Ty, przykładami.
- **Nie policzy niczego bez przykładów.** To nie jest gotowy model
  wytrenowany na cudzych danych.

---

## 2. Którą wersję wybrać

Są trzy wersje. Wszystkie liczą **dokładnie to samo**, bo korzystają
z tego samego silnika. Różnią się tym, co potrafisz przez nie zrobić.

| | Wtyczka QGIS | Program Windows (.exe) | Wiersz poleceń |
|---|---|---|---|
| Co instalujesz | QGIS 3.22 lub nowszy | sam instalator, nic więcej | Pythona i biblioteki |
| Podział na obiekty | tak | tak | tak |
| Pomiar 19 albo 24 cech | tak | tak | tak |
| Nauka klasyfikatora Random Forest | tak | tak | tak |
| Wskazywanie przykładów **klikaniem po mapie** | **tak** | nie | nie |
| Przykłady z gotowej warstwy poligonowej | tak | tak | tak |
| Sprawdzenie, czy klasy da się rozróżnić | tak | tak, automatycznie przy nauce | tak |
| Podgląd wyniku na mapie | tak | nie | nie |
| Poprawianie i ponowna nauka w kółko | **tak, wygodnie** | tak, ale przez pliki | tak, przez pliki |
| Dociąganie wąskich pasów zieleni | **tak** | nie | nie |
| Usuwanie drobnych płatów | tak, w pikselach | tak, w metrach kwadratowych | tak |
| **Ocena dokładności i powierzchnie z przedziałami ufności** | **tak** | **nie** | nie |
| Wiele zdjęć naraz | nie | **tak, cały folder** | **tak, cały folder** |

**Zasada praktyczna.** Wtyczka QGIS służy do **wymyślenia i dopracowania
modelu**, bo tylko tam widzisz, co się dzieje, i tylko tam ocenisz, ile
mapa jest warta. Program Windows służy do **zastosowania gotowego
modelu do wielu zdjęć**.

Najczęstszy sensowny układ pracy: wtyczka na jednym zdjęciu, potem
program okienkowy na pozostałych stu, potem znowu wtyczka, żeby ocenić
dokładność na wybranym fragmencie.

---

## 3. Czego potrzebujesz

Krótka lista. Szczegóły tego, co program przyjmie, są w rozdziale 4,
a miejsca, z których dane pobierzesz za darmo, w rozdziale 5.

### Zdjęcie

Ortomozaika z drona, zdjęcie lotnicze albo scena satelitarna.
Trzy kanały widzialne wystarczą. Formaty: `.tif`, `.tiff`, `.img`,
`.jp2`.

Zdjęcie musi mieć **układ współrzędnych**. Zwykły plik JPG z telefonu
się nie nadaje, bo program nie wie, gdzie to jest i jak duży jest
piksel.

### Model wysokości, czyli NMPT (opcjonalnie)

To rastrowy plik, w którym każdy piksel niesie wysokość powierzchni:
dachu, korony drzewa, gruntu. Powstaje z tego samego nalotu co
ortomozaika, w oprogramowaniu fotogrametrycznym.

Nie jest konieczny, ale robi dużą różnicę. Bez niego program nie
odróżni dachu od asfaltu o tej samej barwie ani drzewa od trawnika.
Z nim ma do dyspozycji 24 cechy zamiast 19, w tym najważniejszą
pojedynczą cechę: **wysokość nad gruntem**.

Warunek: NMPT musi mieć **ten sam układ współrzędnych** co
ortomozaika. Rozdzielczość może się różnić, program sobie poradzi.

### Przykłady

Garść miejsc, o których wiesz na pewno, co tam jest. Albo klikasz je
myszą we wtyczce, albo rysujesz jako poligony w QGIS. Opisane
w rozdziale 7.

### Wymagania sprzętowe

Granicą jest pamięć. Na każdy piksel siatki roboczej obliczenia zajmują
około 100 bajtów, więc największa dopuszczalna siatka, 15 milionów
pikseli, potrzebuje około 1,5 GB pamięci na same obliczenia. Większej
siatki program nie przyjmie: ustaw wtedy grubszą rozdzielczość roboczą
albo podziel zdjęcie na fragmenty. Karta graficzna nie jest potrzebna.
Jak przyspieszyć pracę, opisuje strona programu, dział „Komputer
i szybkość pracy”.

---

## 4. Co program obsługuje

Zanim poszukasz danych, sprawdź, czy program je przyjmie. Reguły są
proste, ale sztywne.

### Zdjęcie: dokładnie trzy pierwsze kanały

Program czyta **pierwsze trzy kanały pliku** i traktuje je jako
czerwony, zielony i niebieski, w tej kolejności.

- Plik z mniej niż trzema kanałami zostanie odrzucony z komunikatem.
- Plik z większą liczbą kanałów **nie** zostanie odrzucony. Program
  weźmie kanały 1, 2 i 3 i nic nie zauważy.

To drugie jest najczęstszą pułapką przy danych satelitarnych.
W surowej scenie Sentinel-2 kanał pierwszy to aerozol, drugi niebieski,
trzeci zielony. Czerwieni wśród nich nie ma w ogóle. Program policzy
coś, co będzie wyglądać jak mapa, a będzie pomyłką.

**Wniosek praktyczny: zawsze podawaj gotową kompozycję RGB**, czyli
plik, w którym kanał 1 to czerwień, kanał 2 zieleń, a kanał 3 barwa
niebieska. Ortomozaika z drona jest taka z natury. Scenę satelitarną
trzeba najpierw złożyć, a najprościej pobrać ją od razu jako produkt
RGB (rozdział 5).

### Formaty i wielkości

| Co | Co program przyjmuje |
|---|---|
| Zdjęcie | `.tif`, `.tiff`, `.img`, `.jp2`, a we wtyczce każda warstwa rastrowa wczytana w QGIS |
| Przykłady | `.gpkg`, `.shp`, `.geojson`, a we wtyczce także klikanie po mapie |
| Model wysokości | `.tif`, `.tiff` |
| Głębia bitowa | 8-bitowa, 16-bitowa ze znakiem i bez znaku, oraz zmiennoprzecinkowa |
| Układ współrzędnych | dowolny, ale **ten sam** dla zdjęcia i modelu wysokości |

Jasności są przeliczane na zakres od 0 do 1 według typu danych pliku:
8-bitowe dzielone przez 255, 16-bitowe przez 65 535. Dzięki temu
zdjęcie z drona i scena satelitarna liczą się tak samo i nie trzeba
niczego skalować ręcznie.

Siatka robocza większa niż 15 milionów pikseli jest odrzucana
z komunikatem. Ustaw wtedy grubszą rozdzielczość roboczą albo licz
zdjęcie we fragmentach. Przy zgrubianiu jasności pikseli są
uśredniane, a wynik zapisuje się na siatce roboczej.

### Jakie dane mają sens, a jakie nie

Program mierzy barwę, zieloność, fakturę, kształt i otoczenie obiektu.
Faktura i kształt mają sens tylko wtedy, gdy piksel jest wyraźnie
mniejszy od obiektu, który chcesz rozpoznać.

| Źródło | Piksel | Czy ma sens |
|---|---|---|
| Dron | 2 do 10 cm | **tak, do tego program powstał**: widać pojedyncze drzewa, miedze, fragmenty dachu |
| Zdjęcie lotnicze, ortofotomapa | 10 do 25 cm | **tak**, wszystkie cechy działają |
| Sentinel-2 | 10 m | **tak, ale** tylko dla dużych form: pole, las, zabudowa, woda. Pojedyncze drzewo to mniej niż piksel |
| Landsat | 30 m | **ostrożnie**: faktura i kształt niewiele wnoszą, zostaje głównie barwa |
| Zdjęcie z telefonu | brak odniesienia | **nie**: brak układu współrzędnych, program nie wie, gdzie to jest ani jak duży jest piksel |

Przy danych satelitarnych pamiętaj też, że modelu wysokości dla nich
zwykle nie ma, więc zostaje 19 cech zamiast 24.

---

## 5. Skąd wziąć dane źródłowe

Cztery drogi, od najlepszej jakości do najłatwiejszej w zdobyciu.

### Droga 1. Własny nalot dronem

Najlepsza jakość i jedyna, która daje model wysokości. Zdjęcia
przetwarza się w oprogramowaniu fotogrametrycznym, na przykład
w otwartym **WebODM** albo w komercyjnych Agisoft Metashape czy
Pix4D. Na wyjściu dostajesz dwie rzeczy, których program potrzebuje:
**ortomozaikę** (gotowy RGB) i **NMPT**.

Dwie rady z praktyki. Leć przy równym zachmurzeniu albo w pełnym
słońcu, nigdy przy przelatujących chmurach, bo połowa zdjęcia wyjdzie
w cieniu i model będzie się mylił. Pokrycie podłużne ustaw na co
najmniej 75 procent, inaczej model wysokości wyjdzie dziurawy.

### Droga 2. Ortofotomapa z Geoportalu

Dla Polski, za darmo, bez rejestracji. Ortofotomapa ma zwykle piksel
od 5 do 25 cm, czyli w zupełności wystarczająco.

1. Wejdź na <https://mapy.geoportal.gov.pl>, zakładka **Dane do
   pobrania**.
2. Wskaż obszar i pobierz arkusze ortofotomapy.
3. Wczytaj plik do QGIS.

Można też podłączyć ortofotomapę jako usługę WMS prosto w QGIS, ale do
klasyfikacji potrzebny jest plik na dysku, a nie usługa.

Modelu wysokości z tego źródła nie ma. Osobno, w tym samym serwisie,
dostępny jest NMT (sam grunt), który **nie** zastąpi NMPT.

### Droga 3. Sentinel-2, czyli 10 metrów za darmo

Satelita Europejskiej Agencji Kosmicznej. Zdjęcie tego samego miejsca
co kilka dni, archiwum od 2015 roku, cała Ziemia, bez opłat.

Najwygodniej pobrać je **wtyczką Pobieranie Sentinel**, którą napisał
autor tego programu:

- strona wtyczki: <https://plugins.qgis.org/plugins/pobieranie_sentinel/>
- wersja angielska: <https://plugins.qgis.org/plugins/sentinel_download/>

Wtyczka pobiera zdjęcia Sentinel-2 (poziom L2A i L1C) oraz Sentinel-1
(GRD) z Copernicus Data Space i **od razu składa gotowe produkty**,
w tym **kompozycję RGB**. To jest dokładnie to, czego potrzebuje
klasyfikator: plik, w którym kanały są już we właściwej kolejności.

Krok po kroku:

1. QGIS, menu **Wtyczki**, **Zarządzanie wtyczkami**, wpisz
   `Pobieranie Sentinel`, kliknij **Zainstaluj**.
2. Wczytaj albo narysuj warstwę z obszarem, który Cię interesuje.
3. Otwórz wtyczkę, wskaż ten obszar, ustaw zakres dat i maksymalne
   zachmurzenie.
4. Z listy produktów wybierz **RGB**.
5. Pobierz i poczekaj.
6. Powstały plik RGB podaj klasyfikatorowi jako **Zdjęcie RGB**.

Przy wyborze sceny patrz na zachmurzenie. Scena z 40 procentami chmur
bywa bezużyteczna, nawet jeśli Twój fragment akurat wyszedł czysto,
bo cienie chmur nadal są.

### Droga 4. Landsat, czyli czterdzieści lat wstecz

Satelity NASA i USGS. Piksel 30 metrów, czyli grubo, ale archiwum
sięga **1982 roku**. To jedyne darmowe źródło, którym zobaczysz, jak
teren wyglądał przed czterdziestu laty.

Również wtyczką autora:

- **Landsat Download**: <https://plugins.qgis.org/plugins/Landsat-Download/>
- wersja polska, **Pobieranie Landsat**: <https://plugins.qgis.org/plugins/pobieranie_landsat/>

Wtyczka pobiera dane Landsat 4 do 9, Collection 2 Level-2 (odbicie
powierzchniowe i temperatura powierzchni) z archiwum USGS, udostępniane
przez Microsoft Planetary Computer. **Nie wymaga zakładania konta ani
klucza.** Podobnie jak wersja sentinelowa, składa gotowe produkty,
w tym kompozycję **RGB**, a także CIR, SWIR, wskaźniki NDVI, NDWI,
NDMI, NBR, NDSI oraz temperaturę powierzchni w stopniach Celsjusza.

Kroki są takie same jak przy Sentinelu: zainstaluj, wskaż obszar,
ustaw zakres dat i misję, wybierz produkt **RGB**, pobierz.

Uwaga przy 30 metrach: faktura i kształt obiektu niewiele już wnoszą,
bo jeden piksel to kawałek terenu 30 na 30 metrów. Klasyfikacja
obiektowa nadal działa, ale rozsądne klasy to las, pole, woda,
zabudowa, a nie pojedyncze drzewa czy ścieżki. Wielkość obiektu trzeba
wtedy ustawić dużo większą, rzędu tysięcy metrów kwadratowych.

### Skąd wziąć model wysokości

| Źródło | Co dostajesz |
|---|---|
| Własny nalot dronem | **NMPT**, dokładnie to, czego program potrzebuje |
| Geoportal, dane lotniczego skanowania laserowego | NMPT i NMT dla Polski, rozdzielczość zwykle 0,5 do 1 m |
| Dane satelitarne | zwykle nic; licz się z 19 cechami zamiast 24 |

Jeśli masz NMPT z innego źródła niż zdjęcie, dopilnuj **tego samego
układu współrzędnych**. Rozdzielczość może się różnić, program sobie
poradzi, ale inny układ oznacza, że wysokości trafią w niewłaściwe
miejsca, a program tego nie wykryje.

---

## 6. Co to znaczy, że program się uczy

To jest pojęcie, które brzmi groźnie, a jest proste. Warto je rozumieć,
bo od tego zależy, czy będziesz wiedział, co robić, gdy mapa wyjdzie
źle.

### Nie ma żadnej gotowej wiedzy w środku

Program **nie wie**, jak wygląda las ani dach. Nie ma w nim żadnego
modelu nauczonego wcześniej na cudzych zdjęciach. Zaczyna od zera przy
każdym nowym zdjęciu i uczy się wyłącznie od Ciebie.

To ma dwie strony. Dobrą: działa na każdym terenie i na każdych
klasach, jakie wymyślisz, także na takich, których nie ma w żadnej
oficjalnej legendzie. Złą: bez Twoich przykładów nie zrobi nic.

### Co to jest uczenie, w jednym akapicie

Program zmierzył już każdy obiekt na zdjęciu: ma dla niego 19 albo 24
liczby. Ty wskazujesz kilkanaście obiektów i mówisz „to jest trawa",
a potem kilkanaście innych: „a to jest dach". Program porównuje liczby
w obu grupach i **sam znajduje reguły**, które je rozdzielają.

Reguły wyglądają mniej więcej tak:

```
czy wysokość nad gruntem jest większa niż 2,4 m?
    tak  -> czy faktura jest gładka?
                tak  -> dach
                nie  -> drzewo
    nie  -> czy zieloność jest większa niż 0,07?
                tak  -> trawa
                nie  -> grunt
```

Nikt tych progów nie wpisał: **2,4 metra i 0,07 program wyliczył
z Twoich przykładów**. Gdybyś wskazał inne obiekty, progi byłyby inne.
Dlatego w instrukcji nie ma tabeli typu „zabudowa powyżej 3 metrów":
takiej tabeli nie ma również w programie.

### Dlaczego sto drzewek, a nie jedno

Jedno takie drzewo reguł łatwo się myli: wystarczy jeden nietypowy
przykład i cała gałąź idzie w złą stronę. Dlatego program buduje
**sto drzew**, każde na nieco innym losowym podzbiorze przykładów
i cech. Potem wszystkie głosują nad każdym obiektem, a wygrywa
większość. Metoda nazywa się **Random Forest**.

Przy okazji dostajesz coś użytecznego: jeśli obiekt dostał **mniej niż
połowę głosów**, to znaczy, że Random Forest się waha. Wtyczka wypisuje liczbę
takich obiektów po zrobieniu mapy. To są miejsca, w których warto
dołożyć przykłady.

### Dlaczego wynik czasem nie poprawia się mimo dokładania przykładów

Bo nie każdego problemu da się nauczyć. Jeśli dwie klasy mają na
zdjęciu **tę samą barwę, tę samą fakturę i tę samą wysokość**, to
żadna liczba przykładów ich nie rozdzieli: w danych po prostu nie ma
informacji, która by je różniła.

Dokładnie po to jest przycisk **Czy klasy da się rozróżnić?** Sprawdza
to, **zanim** stracisz godzinę na klikanie. Jeśli para wypada słabo,
masz trzy wyjścia: zmienić definicję klas, połączyć je w jedną, albo
dołożyć dane (na przykład model wysokości), które wniosą brakującą
informację.

### Co znaczy, że program jest odtwarzalny

Losowanie w klasyfikatorze Random Forest jest sterowane stałym ziarnem (liczbą 42).
Oznacza to, że **te same przykłady na tym samym zdjęciu zawsze dadzą
tę samą mapę**, co do piksela. To ważne przy pisaniu artykułu: wynik
da się powtórzyć, a nie tylko opisać.

### Model jako plik

W programie okienkowym nauczona reguła zapisuje się do pliku `.geoai`.
To jest „pamięć" programu: komplet stu drzew wraz z progami. Taki plik
stosuje się potem do setek zdjęć bez ponownego uczenia.

Model jest ważny **dla danych podobnych do tych, na których się uczył**.
Model nauczony na czerwcowym nalocie zastosowany do sierpniowego da
gorszy wynik, bo barwy i cienie są inne. Model nauczony na zdjęciach
z drona nie nadaje się w ogóle do Sentinela i odwrotnie.

---

## 7. Przygotowanie przykładów

Ten rozdział jest **obowiązkowy dla programu Windows** i opcjonalny dla
wtyczki, w której możesz zamiast tego klikać po mapie.

### Jak zrobić plik z przykładami w QGIS

1. Menu **Warstwa**, potem **Utwórz warstwę**, potem **Nowa warstwa
   GeoPackage**.
2. Nazwij ją na przykład `przyklady.gpkg`, typ geometrii **Poligon**,
   układ współrzędnych **taki sam jak zdjęcie**.
3. W sekcji **Nowe pole** dodaj pole tekstowe o nazwie `klasa`.
   Nazwa jest dowolna, ale musisz ją potem wpisać w programie.
4. Kliknij **OK**. Warstwa pojawi się w panelu warstw.
5. Włącz **tryb edycji** (ikona ołówka), narysuj poligon na terenie,
   który znasz, i wpisz nazwę klasy, na przykład `trawa`.
6. Powtórz dla wszystkich klas i wszystkich odmian każdej klasy.
7. Zapisz edycję i wyłącz ołówek.

### Trzy zasady, które decydują o jakości wyniku

Te trzy rzeczy mają większy wpływ na wynik niż wszystkie ustawienia
razem wzięte.

1. **Rozrzuć przykłady po całym zdjęciu**, nie w jednym rogu. Oświetlenie
   i barwy zmieniają się po ortomozaice, a model uczy się tego, co mu
   pokażesz.
2. **Pokaż każdą odmianę klasy.** Trawa bujna i trawa przyschnięta to
   dla programu dwie zupełnie różne rzeczy. Jeśli pokażesz tylko bujną,
   przyschniętą nazwie gruntem.
3. **Rysuj tylko tam, gdzie jesteś pewien.** Poligon przecinający
   granicę dwóch klas zostanie pominięty albo, co gorsza, nauczy model
   nieprawdy.

### Ile przykładów

Zacznij od około 15 do 30 obiektów na klasę. To nie musi być dokładne:
pierwsza mapa i tak służy do zobaczenia, gdzie model się myli.

### Jak nazywać klasy

Program nadaje klasom kolory automatycznie, rozpoznając fragmenty nazw.
Jeśli nazwiesz klasę zawierającą słowo `las`, `drzew`, `traw`, `łąk`,
`roln`, `upraw`, `pole`, `wod`, `rzek`, `staw`, `zabudow`, `budyn`,
`dach`, `drog`, `asfalt`, `parking`, `gleb`, `grunt` albo `piach`,
dostanie sensowny kolor od razu. Inne klasy dostaną kolor z listy
zapasowej i zawsze możesz go zmienić dwuklikiem.

---

## 8. Wtyczka QGIS, krok po kroku

### Instalacja

1. QGIS, menu **Wtyczki**, potem **Zarządzanie wtyczkami**.
2. Zakładka **Zainstaluj z pliku ZIP**.
3. Wskaż `geoai_klasyfikator.zip` i kliknij **Zainstaluj wtyczkę**.
4. Na pasku narzędzi pojawi się przycisk **GeoAI Klasyfikator**.
   Kliknięcie otwiera panel po prawej stronie okna.

Panel ma cztery kroki, jeden pod drugim. Na samej górze jest przycisk
**Instrukcja**, a pod spodem **okno dziennika**, w którym na bieżąco
widać, co wtyczka robi. Warto tam zaglądać: tam lądują wszystkie
ostrzeżenia.

---

### Krok 1. Zdjęcie i podział na obiekty

| Pole | Co wpisać |
|---|---|
| **Zdjęcie (RGB)** | warstwa rastrowa wczytana w QGIS |
| **Model wysokości (opcjonalnie)** | warstwa NMPT, jeśli masz |
| **Rozdzielczość robocza** | zostaw **jak w pliku**, jeśli nie wiesz. Dla drona typowo 0,05 m |
| **Wielkość obiektu (m²)** | **najważniejsze ustawienie**, domyślnie 10 |
| **albo liczba obiektów** | to samo wyrażone inaczej, domyślnie 10 000 |

Pola **Wielkość obiektu** i **liczba obiektów** są powiązane: zmieniasz
jedno, drugie przelicza się samo.

**Jak dobrać wielkość obiektu.** Obiekt musi być **mniejszy niż
najwęższa rzecz, którą chcesz zobaczyć na mapie**. Dla pól i dachów
zwykle 5 do 20 m². Dla pojedynczych drzew 2 do 5 m². Jeśli ustawisz
za dużo, wąska ścieżka zniknie, bo zostanie wchłonięta przez sąsiedni
obiekt, i żaden klasyfikator tego nie naprawi.

Pod spodem są **dwa ustawienia zaawansowane**, których zwykle nie
rusza się wcale:

- **Zwartość**, domyślnie 0,15. Niska wartość oznacza, że obiekty
  wiernie trzymają się granic kolorów. Wysoka daje obiekty regularne,
  prawie kwadratowe.
- **Wygładzanie**, domyślnie 2,5. Lekkie rozmycie przed podziałem,
  żeby szum nie tworzył sztucznych obiektów.

Jest też pole wyboru **Policz tylko to, co widać na ekranie**. Liczy
wtedy wyłącznie bieżący widok mapy. Przydaje się na słabszym
komputerze i wtedy, gdy dobierasz wielkość obiektu: szybka próba na
małym fragmencie zamiast czekania na całe zdjęcie.

Przycisk **PODZIEL NA OBIEKTY I ZMIERZ** uruchamia obliczenia. Powstaje
warstwa **GeoAI obiekty**: poligony z tabelą atrybutów, w której każdy
obiekt ma swoje 19 albo 24 zmierzone liczby.

Jeśli wtyczka napisze w dzienniku, że *obiekty wyszły większe, niż
zamawiałeś*, to skutek niskiej zwartości podziału: przy domyślnej
zwartości rzeczywista liczba obiektów bywa dwa do trzech razy mniejsza
od zamówionej. Zmniejsz wielkość obiektu albo zwiększ zwartość.

---

### Krok 2. Klasy i przykłady

Najpierw wypisujesz klasy, potem pokazujesz przykłady.

| Przycisk | Co robi |
|---|---|
| **Dodaj klasę** | dopisuje nową klasę do listy |
| **Usuń klasę** | kasuje zaznaczoną klasę razem z jej przykładami |
| **Wyczyść przykłady** | kasuje same przykłady, klasa zostaje |

Klikasz klasę na liście, żeby stała się aktywna. **Dwuklik zmienia jej
kolor.**

Przycisk **WSKAZUJ PRZYKŁADY NA MAPIE** włącza tryb wskazywania. Napis
zmienia się wtedy na **WSKAZUJESZ, kliknij, by zakończyć**, więc zawsze
wiadomo, czy tryb jest włączony.

W tym trybie:

- kliknięcie obiektu dodaje go do aktywnej klasy,
- kliknięcie drugi raz usuwa go z klasy,
- z wciśniętym **Ctrl** możesz malować, przeciągając myszą.

Nie musisz klikać precyzyjnie w środek: klikasz gdziekolwiek w obrębie
obiektu, a cały obiekt dostaje etykietę.

Obowiązują te same trzy zasady, co przy rysowaniu poligonów
(rozdział 7): rozrzucaj po całym zdjęciu, pokaż każdą odmianę klasy,
wskazuj tylko to, co rozpoznajesz bez wahania.

---

### Krok 3. Nauka i mapa

| Przycisk | Co robi |
|---|---|
| **Czy klasy da się rozróżnić?** | sprawdza, **zanim** zaczniesz uczyć, czy Twoje klasy w ogóle różnią się na tyle, żeby je rozdzielić, i które cechy je dzielą |
| **Naucz** | uczy Random Forest na wskazanych przykładach, trwa sekundy |
| **ZRÓB MAPĘ** | nadaje klasę każdemu obiektowi na zdjęciu |
| **Zapisz mapę do pliku GeoTIFF** | zapisuje wynik na dysk razem z plikiem stylu |

**Jak czytać wynik sprawdzenia rozróżnialności.** Wtyczka pokazuje
każdą parę klas z oceną. Para oznaczona jako słaba będzie się myliła
niezależnie od tego, ile dołożysz przykładów. Wtedy albo zmieniasz
definicję klas, albo łączysz dwie klasy w jedną, albo godzisz się
z błędem i opisujesz go w opracowaniu.

**Pętla poprawiania.** Pierwszy model niemal nigdy nie jest dobry i nie
jest to oznaka błędu, tylko normalny tryb pracy. Po pierwszej mapie
przejrzyj ją całą i wypisz sobie *rodzaje* pomyłek, na przykład „sucha
trawa brana za grunt". Dodaj po kilka przykładów każdego rodzaju
w różnych miejscach i kliknij **Naucz** oraz **ZRÓB MAPĘ** jeszcze raz.
Pierwsze dwie, trzy rundy poprawiają najwięcej.

#### Dociąganie wąskich pasów (opcjonalnie)

Ta część jest tylko we wtyczce. Służy do odzyskania pasa trawy
węższego niż obiekt: miedzy między zagonami albo trawy przy rowie.

Obiekty nadal decydują, co to za teren, ale dla **dwóch wybranych
klas** o każdym pikselu rozstrzyga jego zieloność.

| Pole | Znaczenie |
|---|---|
| **Klasa zielona** | klasa, do której trafią piksele zielone |
| **Klasa druga** | klasa, z której można je zabrać |
| **Próg zieloności** | granica; przycisk **Wylicz z przykładów** dobiera ją automatycznie |
| **Okno uśredniania (piksele)** | domyślnie 3; mniejsze wierniej trzyma cienkie pasy, ale bywa niespokojne |
| **Sposób** | **Zachowaj zielone obiekty w całości** (bezpieczniejszy) albo **Każdy piksel osobno, w obie strony** (ostrzejsze krawędzie) |
| **Najmniejszy płat** | w pikselach; płaty mniejsze zostaną wchłonięte przez otoczenie. Zero wyłącza czyszczenie |

Uwaga rzetelnościowa: jedno i drugie to operacje na pikselach wewnątrz
toru obiektowego. Jeśli ich użyjesz, mapa nie jest już czysto
obiektowa i w opracowaniu naukowym trzeba to napisać wprost.

Ustaw **Najmniejszy płat** pod zastosowanie mapy, a nie po to, żeby
podbić wynik dokładności.

---

### Krok 4. Ile ta mapa jest warta

To jest część, której w zwykłym QGIS nie ma, i powód, dla którego warto
używać wtyczki, a nie tylko programu okienkowego.

Mapa jest tyle warta, ile wiesz o jej błędach. Wtyczka losuje punkty
kontrolne, Ty opisujesz je patrząc na samo zdjęcie, a na końcu
dostajesz liczby, które można zacytować w opracowaniu.

| Pole | Co ustawić |
|---|---|
| **Sposób losowania** | **Warstwowy, wg klas mapy (zalecany)** albo **Prosty losowy** |
| **Minimum punktów na klasę** | domyślnie 50 |
| **Łącznie punktów** | domyślnie 200 |

Losowanie warstwowe daje każdej klasie, nawet najmniejszej, dość
punktów, żeby dało się o niej cokolwiek powiedzieć. Prosty losowy
rozsypuje punkty równomiernie i rzadkie klasy dostają ich za mało.
Poniżej 30 punktów na klasę wyniki dla tej klasy będą bardzo niepewne.

| Przycisk | Co robi |
|---|---|
| **Wylosuj punkty kontrolne** | tworzy warstwę **GeoAI punkty kontrolne** |
| **OPISUJ PUNKTY NA MAPIE** | włącza tryb opisywania; napis zmienia się na **OPISUJESZ** |
| **POLICZ DOKŁADNOŚĆ** | liczy wynik końcowy |

**Najważniejsza zasada tego kroku.** Zanim zaczniesz opisywać punkty,
**wyłącz warstwę z mapą klasyfikacji** i patrz na samo zdjęcie. Inaczej
podpowiedź wtyczki wpłynie na Twoją ocenę, a ocena dokładności przestaje
cokolwiek znaczyć.

W trybie opisywania wybierasz klasę i klikasz punkt. Prawy przycisk
czyści opis. Jeśli naprawdę nie wiesz, co jest w danym miejscu, lepiej
skasować ten punkt w tabeli atrybutów niż zgadywać.

Wtyczka pilnuje sama, żeby punkty kontrolne nie trafiły na obiekty
użyte jako przykłady uczące.

**Co dostajesz po kliknięciu POLICZ DOKŁADNOŚĆ:**

- **macierz błędów**, czyli tabela pokazująca, co z czym się myli;
- **dokładność ogólna**, czyli jaki udział punktów został opisany
  poprawnie;
- **dokładność producenta i użytkownika** dla każdej klasy, czyli
  osobno „ile z tej klasy znaleziono" i „ile z tego, co nazwano tą
  klasą, nią rzeczywiście jest";
- **powierzchnie klas skorygowane o błąd klasyfikacji, z przedziałami
  ufności 95 procent**.

Ostatni punkt jest ważniejszy, niż się wydaje. Powierzchnia policzona
przez zliczenie pikseli klasy **nie jest** powierzchnią tej klasy, bo
mapa zawiera błędy, które się nie znoszą. Wtyczka liczy to zgodnie
z procedurą Olofssona i innych (2014) oraz Stehmana (2014).

Współczynnika kappa wtyczka świadomie nie liczy.

---

## 9. Program dla Windows, krok po kroku

### Skąd go wziąć

Gotowy plik nie leży w repozytorium, bo waży kilkaset megabajtów
i powstaje na nowo przy każdej zmianie kodu. Buduje go maszyna Windows
w chmurze GitHuba:

- **Releases**: `GeoAI_Klasyfikator_Setup.exe`, instalator;
- **Actions**, ostatni przebieg, sekcja **Artifacts**: instalator oraz
  wersja przenośna w pliku ZIP.

Instalator nie wymaga praw administratora i nie wymaga Pythona.
Instaluje się do katalogu użytkownika.

### Jak wygląda okno

### Przeglądarka ostrzega przed pobranym plikiem

Chrome, Edge i Windows SmartScreen pokażą ostrzeżenie, bo plik nie jest
podpisany certyfikatem wydawcy. Nie jest to wykryty wirus, tylko brak
reputacji nowego pliku: każdy świeżo zbudowany instalator zaczyna od zera.

Co z tym zrobić:

- W Chrome kliknij strzałkę przy wpisie na liście pobierania, a potem
  **Zachowaj**. W razie potrzeby **Pokaż więcej**, potem **Zachowaj mimo to**.
- Po uruchomieniu SmartScreen pokaże niebieskie okno. Kliknij
  **Więcej informacji**, potem **Uruchom mimo to**.
- Chcesz się upewnić, że pobrałeś dokładnie to, co zbudował GitHub?
  Porównaj sumę kontrolną z pliku `SUMY-KONTROLNE.txt`, dołączonego do
  każdego wydania:

```powershell
Get-FileHash .\GeoAI_Klasyfikator_Setup.exe -Algorithm SHA256
```

- Wersja przenośna w pliku ZIP bywa przepuszczana bez ostrzeżenia,
  bo przeglądarka ocenia archiwum łagodniej niż plik `.exe`.

Ostrzeżenie zniknie dopiero po podpisaniu programu certyfikatem wydawcy,
co jest usługą płatną. Do czasu testów nie ma to sensu.

### Jak wygląda okno

Na górze niebieski pasek z nazwą i przyciskiem **Instrukcja**. Pod nim
dwie zakładki. Na dole **dziennik**, czarne okienko, w którym widać
postęp i komunikaty.

---

### Zakładka 1. Nauka

Tutaj powstaje **plik modelu**, czyli nauczona reguła zapisana na dysk.

| Pole | Co wskazać |
|---|---|
| **Zdjęcie RGB** | jedno **reprezentatywne** zdjęcie, formaty `.tif`, `.tiff`, `.img`, `.jp2` |
| **Plik z przykładami** | warstwa poligonowa `.gpkg`, `.shp` albo `.geojson` z rozdziału 7 |
| **Kolumna z nazwą klasy** | nazwa pola z nazwami klas, czyli zwykle `klasa` |
| **Model wysokości (opcjonalnie)** | plik NMPT |

Sekcja **Ustawienia podziału**:

| Pole | Domyślnie | Uwaga |
|---|---|---|
| **Rozdzielczość robocza (m)** | 0.05 | wpisz 0, żeby pracować w rozdzielczości pliku |
| **Wielkość obiektu (m²)** | 10 | ta sama zasada co we wtyczce: mniejszy niż najwęższa rzecz na mapie |

Na końcu **Zapisz model jako**, domyślnie `model.geoai`. To plik, który
potem wskażesz w drugiej zakładce.

Przycisk **NAUCZ MODEL** uruchamia obliczenia. Przy okazji program sam
sprawdza, czy Twoje klasy da się rozróżnić, i wypisuje wynik
w dzienniku. **Jeśli któraś para wypadnie słabo, dodaj przykładów albo
połącz te klasy w jedną.**

Słowo o wyborze zdjęcia do nauki: musi być reprezentatywne dla całego
zbioru. Model nauczony na zdjęciu z czerwcowego poranka zastosowany do
nalotu z sierpniowego popołudnia da gorszy wynik, bo barwy i cienie są
inne.

---

### Zakładka 2. Klasyfikacja wsadowa

Tutaj stosujesz gotowy model do wszystkich zdjęć w folderze.

| Pole | Co wskazać |
|---|---|
| **Plik modelu** | plik `.geoai` z zakładki 1 |
| **Folder ze zdjęciami** | katalog ze zdjęciami do policzenia |
| **Folder z modelami wysokości** | katalog z plikami NMPT, jeśli model uczył się z wysokością |
| **Gdzie zapisać mapy** | katalog na wyniki |

Sekcja **Opcje**:

| Pole | Znaczenie |
|---|---|
| **Najmniejszy zachowany płat (m²)** | domyślnie 0, czyli bez czyszczenia; usuwa pojedyncze drobiny z mapy |
| **Szukaj zdjęć także w podfolderach** | przechodzi przez całe drzewo katalogów |
| **Policz ponownie także te, które już mają wynik** | bez tego program pomija zdjęcia już policzone |

Zwróć uwagę na dwie różnice wobec wtyczki. Najmniejszy płat podaje się
tutaj w **metrach kwadratowych**, a we wtyczce w **pikselach**. Oraz:
tu nie ma dociągania wąskich pasów zieleni.

Przycisk **KLASYFIKUJ CAŁY FOLDER** rusza z obliczeniami.

**Jak program dopasowuje modele wysokości.** Po nazwie pliku. Dla
zdjęcia `nalot_01.tif` szuka pliku `nalot_01_nmpt.tif` we wskazanym
folderze. Jeśli model uczył się z wysokością, a dla któregoś zdjęcia
jej zabraknie, program zgłosi to wyraźnie, zamiast po cichu policzyć
gorzej.

**Przerwany przebieg można wznowić.** Bez zaznaczonej opcji **Policz
ponownie** program pomija zdjęcia, które już mają wynik, więc po
przerwaniu wystarczy uruchomić go jeszcze raz.

---

### Czego w tym programie nie ma

- **Klikania przykładów po mapie.** Przykłady muszą być gotowym plikiem
  poligonowym.
- **Podglądu wyniku.** Mapy otwiera się potem w QGIS.
- **Oceny dokładności.** Losowanie punktów kontrolnych, macierz błędów
  i powierzchnie z przedziałami ufności są tylko we wtyczce, bo
  wymagają opisywania punktów klikaniem po mapie. Wczytaj gotową mapę
  do QGIS i przejdź do kroku 4 wtyczki.
- **Dociągania wąskich pasów zieleni.**

---

## 10. Co powstaje na wyjściu

### Z wtyczki QGIS

| Warstwa albo plik | Co zawiera |
|---|---|
| **GeoAI obiekty** | warstwa poligonowa z dwiema kolumnami: `klasa_uczaca` (co wskazałeś jako przykład) i `klasa_mapy` (co program nadał) |
| **GeoAI punkty kontrolne** | warstwa punktowa z kolumnami `klasa_ze_zdjecia` (Twój opis) i `klasa_mapy` (co mówi mapa) |
| plik GeoTIFF | mapa klas, zapisana przyciskiem w kroku 3 |
| plik `.qml` obok GeoTIFF-a | styl, dzięki czemu mapa otwiera się od razu w kolorach |

Zmierzone 19 albo 24 cech nie trafia do tabeli atrybutów: służą one do
nauki i zostają w pamięci. W tabeli są same klasy.

Po kliknięciu **ZRÓB MAPĘ** wtyczka wypisuje w dzienniku udział i
powierzchnię każdej klasy, a także liczbę obiektów, które **dostały
mniej niż połowę głosów** klasyfikatora Random Forest. To są obiekty graniczne albo
miejsca, których nie pokazałeś w przykładach, więc ta liczba jest
gotową podpowiedzią, gdzie dodać przykłady w następnej rundzie.

### Z programu Windows

| Plik | Co zawiera |
|---|---|
| mapa GeoTIFF dla każdego zdjęcia | klasy, w folderze wyjściowym |
| plik `.qml` obok każdej mapy | styl, kolory |
| `raport.csv` | zbiorcze zestawienie: powierzchnia każdej klasy na każdym zdjęciu |

`raport.csv` otwiera się w Excelu. Pamiętaj przy jego czytaniu, że są
to powierzchnie **odczytane z mapy**, a więc obciążone błędem
klasyfikacji. Do opracowania naukowego potrzebujesz powierzchni
skorygowanych z kroku 4 wtyczki.

---

## 11. Ściąga z ustawieniami

Wartości domyślne są dobrane sensownie. Ta tabela mówi, co wolno ruszyć
i kiedy.

| Ustawienie | Domyślnie | Kiedy zmieniać |
|---|---|---|
| Wielkość obiektu | 10 m² | **zawsze przemyśl**: musi być mniejsza od najwęższej rzeczy na mapie |
| Rozdzielczość robocza | jak w pliku (wtyczka), 0.05 (program) | gdy zdjęcie jest bardzo duże, a komputer słaby |
| Zwartość | 0,15 | praktycznie nigdy |
| Wygładzanie | 2,5 | praktycznie nigdy |
| Okno uśredniania zieloności | 3 piksele | gdy pasy trawy są bardzo cienkie, zmniejsz |
| Próg zieloności | liczony z przykładów | zostaw automat |
| Najmniejszy płat | 0, czyli wyłączone | pod zastosowanie mapy, nigdy pod wynik dokładności |
| Minimum punktów na klasę | 50 | nie schodź poniżej 30 |
| Łącznie punktów | 200 | więcej klas, więcej punktów |

Stałe metody, których nie da się zmienić w interfejsie i które warto
znać przy opisie w artykule: Random Forest ma 100 drzew i ziarno losowania
42, faktura GLCM liczona jest na 15 poziomach szarości w czterech
kierunkach, przedziały ufności są 95-procentowe. Pełny wykaz jest
w [UWARUNKOWANIA_NAUKOWE.md](UWARUNKOWANIA_NAUKOWE.md).

---

## 12. Gdy coś nie działa

### Wtyczka QGIS

| Objaw | Przyczyna i co zrobić |
|---|---|
| Przycisku wtyczki nie ma na pasku | menu **Widok**, **Paski narzędzi**, zaznacz pasek wtyczek. Sprawdź też w **Zarządzaniu wtyczkami**, czy jest włączona |
| Lista zdjęć w kroku 1 jest pusta | wczytaj najpierw raster do QGIS; wtyczka pokazuje tylko warstwy obecne w projekcie |
| Podział trwa bardzo długo | zaznacz pracę na fragmencie albo zwiększ wielkość obiektu |
| Dziennik pisze, że obiekty wyszły większe, niż zamawiałeś | skutek niskiej zwartości podziału; zmniejsz wielkość obiektu albo zwiększ zwartość |
| Mapa jest usiana pojedynczymi drobinami | ustaw **Najmniejszy płat** na kilkadziesiąt pikseli |
| Wąskie pasy trawy znikają | wielkość obiektu jest za duża; dopiero potem próbuj dociągania pasów |
| Klasy mieszają się mimo wielu przykładów | kliknij **Czy klasy da się rozróżnić?**; jeśli para wypada słabo, żadna liczba przykładów tego nie naprawi |
| Cechy wysokościowe są puste | NMPT ma inny układ współrzędnych niż zdjęcie |

### Program dla Windows

| Objaw | Przyczyna i co zrobić |
|---|---|
| Program startuje i od razu znika | uruchom go z wiersza poleceń, żeby zobaczyć komunikat; albo ustaw zmienną środowiskową `GEOAI_SZCZEGOLY=1`, żeby okno pokazało pełny ślad błędu |
| `Brakuje: ...` | któregoś z pól nie wypełniono; wskaż brakujące pliki |
| `Klasy bez ani jednego obiektu uczącego` | poligony są mniejsze od obiektów; narysuj większe albo zmniejsz wielkość obiektu |
| Program zgłasza brak modelu wysokości dla zdjęcia | plik nie nazywa się tak, jak trzeba: dla `nalot_01.tif` ma to być `nalot_01_nmpt.tif` |
| Nic się nie liczy, dziennik milczy | poprzednie obliczenie jeszcze trwa; program robi jedno naraz |
| Antywirus blokuje plik `.exe` | typowe dla programów składanych PyInstallerem; dodaj wyjątek |
| Plik `.exe` waży kilkaset megabajtów | tak ma być: w środku siedzą biblioteki GDAL, PROJ, NumPy, SciPy i scikit-learn |

### Pytanie, które pada najczęściej

**Mapa wygląda źle, co teraz?**

Prawie zawsze winne jest jedno z trzech, w tej kolejności:

1. **Wielkość obiektu.** Jeśli obiekty są większe niż rzeczy, które
   chcesz pokazać, żadne dalsze poprawki nie pomogą.
2. **Przykłady.** Za mało odmian klasy albo wszystkie z jednego rogu
   zdjęcia.
3. **Definicja klas.** Dwie klasy, które na zdjęciu RGB wyglądają tak
   samo, nie rozdzielą się nigdy.

Ustawienia zaawansowane są na czwartym miejscu i rzadko cokolwiek
zmieniają.

---

## 13. Słowniczek

**Ortomozaika**: zdjęcie złożone z wielu ujęć z drona i przeliczone tak,
że każdy piksel leży tam, gdzie powinien, jak na mapie.

**NMPT, numeryczny model pokrycia terenu**: raster z wysokością
powierzchni, czyli dachów i koron drzew, a nie samego gruntu.

**NMT, numeryczny model terenu**: raster z wysokością samego gruntu.
Program go nie wymaga, szacuje grunt z NMPT.

**Wysokość nad gruntem**: różnica między NMPT a oszacowanym gruntem.
Dla dachu będzie to wysokość budynku, dla trawnika około zera.

**Segment, obiekt**: zwarty kawałek zdjęcia o podobnej barwie,
traktowany jako jedna całość.

**Random Forest**: metoda uczenia maszynowego, w której sto drzew
decyzyjnych głosuje nad każdym obiektem.

**Cecha**: jedna z 19 albo 24 liczb opisujących obiekt.

**GLCM, faktura**: cztery liczby opisujące, jak bardzo powierzchnia jest
gładka albo chropowata.

**ExG, VARI, NGRDI**: trzy wskaźniki zieloności liczone z kanałów
widzialnych. Zastępują NDVI tam, gdzie nie ma podczerwieni.

**Macierz błędów**: tabela pokazująca, ile obiektów każdej klasy
rzeczywistej trafiło do której klasy na mapie.

**Dokładność producenta**: jaki udział tego, co naprawdę jest daną
klasą, program znalazł.

**Dokładność użytkownika**: jaki udział tego, co program nazwał daną
klasą, nią rzeczywiście jest.

**Przedział ufności**: zakres, w którym z zadanym prawdopodobieństwem
mieści się prawdziwa wartość. Tutaj zawsze 95 procent.

**Punkty kontrolne**: punkty losowane niezależnie od danych uczących,
służące wyłącznie do sprawdzenia, ile mapa jest warta.

---

© Grzegorz Górniak · gorniakgrzegorz@gmail.com · GPL-3.0-or-later
