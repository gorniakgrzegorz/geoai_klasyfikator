# Szkic manuskryptu

**Status dokumentu.** To jest szkielet artykułu, nie artykuł gotowy.
Sekcje 1, 2 i 3 są napisane w całości, bo opisują metodę faktycznie
zaimplementowaną w kodzie i zweryfikowaną literaturę. Sekcje 4, 5 i 6
są rusztowaniem: zawierają strukturę, układ tabel i rycin oraz
pytania, na które trzeba odpowiedzieć, ale **nie zawierają żadnych
liczb**, ponieważ badania na danych rzeczywistych nie wykonano.
Każde miejsce wymagające danych oznaczono jako
**[DO UZUPEŁNIENIA]**, a każde miejsce wymagające decyzji autora jako
**[DECYZJA AUTORA]**.

**Ustalenia wstępne, do zatwierdzenia przed dalszą pracą:**

| Punkt | Stan |
|---|---|
| Typ tekstu | artykuł oryginalny z elementami pracy metodycznej **[DECYZJA AUTORA]** |
| Czasopismo docelowe | **[DECYZJA AUTORA]**. Kandydaci do sprawdzenia pod kątem zakresu, limitu słów i stylu cytowań: *Remote Sensing* (MDPI), *International Journal of Applied Earth Observation and Geoinformation*, *Environmental Modelling and Software*, *SoftwareX*. Pozycję kwartylową każdego z nich trzeba sprawdzić w aktualnym wykazie, a nie przyjmować z pamięci |
| Materiał wejściowy | kod programu w wersji 1.0.0 oraz dokument `UWARUNKOWANIA_NAUKOWE.md`. **Brak danych rzeczywistych**: ortomozaiki, NMPT i zbioru referencyjnego |
| Teza, jedno zdanie | jawnie opisany tor obiektowy działający na samym kanale widzialnym, z opcjonalnym modelem pokrycia terenu, pozwala wytworzyć mapę pokrycia wraz z powierzchnią klas i jej niepewnością w jednym otwartym środowisku GIS, bez korzystania z modelu uczonego na danych zewnętrznych. **[DECYZJA AUTORA: zatwierdzić lub przeformułować]** |

Przyjęta tu teza jest twierdzeniem o metodzie, a nie o terenie.
Jeżeli artykuł ma zamiast tego odpowiadać na pytanie o teren (na
przykład o strukturę pokrycia strefy podmiejskiej), teza i wszystkie
pytania badawcze wymagają przebudowy, a opisany tor staje się
narzędziem, nie przedmiotem pracy.

---

## Tytuł

**[DECYZJA AUTORA]** Propozycja robocza: *Otwarty tor klasyfikacji
obiektowej zdjęć z bezzałogowego statku powietrznego w kanale
widzialnym, z estymacją powierzchni i jej niepewności*.

Tytuł nie powinien zapowiadać wyniku, którego praca nie przedstawia.
Dopóki rozdział 4 jest pusty, tytuł nie może zawierać wartości
liczbowych ani słowa „dokładny".

## Streszczenie

**[DO UZUPEŁNIENIA]** Streszczenie strukturalne, 200 do 250 słów,
pisane na końcu. Układ: kontekst, luka, cel, dane i metody, trzy lub
cztery wyniki liczbowe, wniosek, znaczenie.

Warunek twardy: każda liczba w streszczeniu musi pochodzić z
rozdziału 4. Dopóki rozdział 4 nie zawiera wyników, streszczenie
pozostaje puste. Nie wolno wstawiać wartości przykładowych.

## Słowa kluczowe

**[DECYZJA AUTORA]** Pięć lub sześć, bez powtarzania słów z tytułu.
Propozycja: analiza obiektowa obrazu; superpiksele; Random Forest;
wskaźniki roślinności w zakresie widzialnym; estymacja powierzchni
warstwowa; odtwarzalność.

---

## 1. Wprowadzenie

### 1.1 Obiekt zamiast piksela

Klasyfikacja obiektowa przyjmuje za jednostkę analizy segment obrazu
odpowiadający fragmentowi terenu, a nie pojedynczy piksel. Przy
rozdzielczości centymetrowej, typowej dla nalotów bezzałogowych,
pojedynczy piksel jest mniejszy od najmniejszego obiektu, który ma
znaczenie tematyczne, więc klasyfikacja pikselowa daje mapy
rozdrobnione i trudne do interpretacji. Przegląd założeń i praktyki
tego podejścia podaje {{cite: Blaschke, 2010, 10.1016/j.isprsjprs.2009.06.004}}.

Segment niesie przy tym informację, której piksel nie ma: kształt,
wielkość, fakturę i relację do sąsiadów. To te wielkości, a nie sama
barwa, pozwalają odróżnić klasy o zbliżonym odbiciu spektralnym.

### 1.2 Nalot w kanale widzialnym bez bliskiej podczerwieni

Kamery konsumenckie montowane na dronach rejestrują wyłącznie trzy
kanały widzialne. Najczęściej używany wskaźnik roślinności, NDVI,
wymaga bliskiej podczerwieni i w takim nalocie jest niedostępny.
Zastępują go wskaźniki liczone na składowych widzialnych:
ExG {{cite: Woebbecke i in., 1995, 10.13031/2013.27838}},
VARI {{cite: Gitelson i in., 2002, 10.1016/S0034-4257(01)00289-9}}
oraz NGRDI {{cite: Hunt i in., 2005, 10.1007/s11119-005-2324-5}}.

Wskaźniki te nie są równoważne NDVI. Oddzielają roślinność zieloną od
podłoża, ale nie niosą informacji o strukturze wewnętrznej liścia,
więc nie rozróżniają kondycji roślin w tym zakresie, w jakim robi to
NDVI. Praca przyjmuje to ograniczenie jako warunek zadania, a nie
jako wadę do obejścia.

### 1.3 Powierzchnia odczytana z mapy jest obciążona

Zliczenie pikseli przypisanych do klasy nie jest estymatorem
powierzchni tej klasy, ponieważ mapa zawiera błędy klasyfikacji,
które nie znoszą się wzajemnie. Procedurę estymacji powierzchni
skorygowanej o błąd klasyfikacji, wraz z wariancją i przedziałem
ufności, podają {{cite: Olofsson i in., 2014, 10.1016/j.rse.2014.02.015}},
rozwijając wcześniejsze ujęcie
{{cite: Olofsson i in., 2013, 10.1016/j.rse.2012.10.031}}. Warunki
poprawności estymatorów przy próbie warstwowej, w której warstwy nie
pokrywają się z klasami mapy, omawia
{{cite: Stehman, 2014, 10.1080/01431161.2014.930207}}.

Bez tego kroku artykuł podaje liczbę, która wygląda jak powierzchnia,
ale nią nie jest. Dotyczy to również opracowań z nalotów
bezzałogowych, gdzie wysoka rozdzielczość bywa mylona z wysoką
dokładnością tematyczną.

### 1.4 Luka badawcza

Poszczególne elementy opisanego toru są dobrze opisane osobno:
segmentacja superpikselowa {{cite: Achanta i in., 2012, 10.1109/TPAMI.2012.120}},
cechy faktury {{cite: Haralick i in., 1973, 10.1109/TSMC.1973.4309314}},
Random Forest jako klasyfikator teledetekcyjny
{{cite: Breiman, 2001, 10.1023/A:1010933404324}};
{{cite: Belgiu i Drăguţ, 2016, 10.1016/j.isprsjprs.2016.01.011}}
oraz estymacja powierzchni z niepewnością
{{cite: Olofsson i in., 2014, 10.1016/j.rse.2014.02.015}}.

**[DO UZUPEŁNIENIA: przeszukanie literatury]** Luki nie wolno
zadeklarować bez dowodu. Potrzebny jest zapis przeszukania (baza,
zapytanie, data, liczba trafień, kryteria włączenia), który pokaże,
ile istniejących narzędzi łączy te cztery elementy w jednym otwartym
środowisku i udostępnia wszystkie progi decyzyjne. Dopóki tego zapisu
nie ma, zdanie o luce pozostaje twierdzeniem bez pokrycia.

### 1.5 Cel i pytania badawcze

Celem pracy jest opisanie i ocena toru klasyfikacji obiektowej, który
działa na samym kanale widzialnym, opcjonalnie korzysta z numerycznego
modelu pokrycia terenu i zwraca mapę wraz z powierzchnią klas i jej
przedziałem ufności.

- **PB1.** Które z 19 cech liczonych wyłącznie z kanałów widzialnych
  rozdzielają przyjęte klasy pokrycia i jak zmierzyć tę rozdzielność
  tak, by miara nie była zawyżona przez dopasowanie do próby?
- **PB2.** Jaki przyrost rozdzielności i dokładności wnosi pięć cech
  wyprowadzonych z modelu pokrycia terenu, w tym wysokość nad gruntem
  szacowana bez osobnego modelu terenu?
- **PB3.** Czy korekta pikselowa oparta na progu ExG oraz usuwanie
  małych łat poprawiają mapę i w jakim stopniu naruszają jej obiektowy
  charakter?
- **PB4.** Jak szeroki jest przedział ufności powierzchni klas przy
  próbie warstwowej i jak odbiega on od powierzchni odczytanej wprost
  z mapy?

### 1.6 Wkład pracy

1. Pełny opis toru obiektowego do poziomu stałych i progów, w postaci
   pozwalającej odtworzyć wynik poza oprogramowaniem autorów.
2. Miara rozdzielności klas liczona z walidacją krzyżową, która nie
   nasyca się przy małej próbie w sposób typowy dla wersji klasycznej
   (sekcja 3.8).
3. Estymacja powierzchni skorygowanej o błąd klasyfikacji wbudowana w
   to samo narzędzie, które wytwarza mapę.
4. Otwarta implementacja w trzech postaciach: wtyczka QGIS, program
   wiersza poleceń i program okienkowy dla systemu Windows.

### 1.7 Układ artykułu

Rozdział 2 opisuje obszar i dane. Rozdział 3 podaje metodę wraz ze
stałymi. Rozdział 4 przedstawia wyniki w kolejności pytań badawczych.
Rozdział 5 omawia je wobec literatury i wskazuje ograniczenia.
Rozdział 6 zawiera wnioski.

---

## 2. Obszar badań i dane

### 2.1 Obszar

**[DO UZUPEŁNIENIA]** Położenie, powierzchnia, typ krajobrazu,
uzasadnienie wyboru. Przy tezie o metodzie obszar powinien zawierać
pary klas trudne do rozdzielenia (na przykład sucha trawa i goła
gleba), inaczej praca nie testuje tego, co zapowiada.

### 2.2 Nalot i ortomozaika

**[DO UZUPEŁNIENIA]** Platforma, kamera, data i godzina nalotu,
wysokość lotu, pokrycie podłużne i poprzeczne, oprogramowanie
fotogrametryczne wraz z wersją, terenowa wielkość piksela, układ
współrzędnych, warunki oświetleniowe, liczba i rozmieszczenie punktów
osnowy, błąd średni na punktach kontrolnych.

### 2.3 Model pokrycia terenu

**[DO UZUPEŁNIENIA]** Sposób wytworzenia, rozdzielczość, zgodność
siatki z ortomozaiką. Warunek: NMPT musi pochodzić z tego samego
nalotu i mieć ten sam układ współrzędnych oraz ten sam rozmiar piksela
co ortomozaika, inaczej cechy wysokościowe liczone są dla
niewłaściwych obszarów.

### 2.4 Legenda klas

**[DECYZJA AUTORA]** Lista klas wraz z definicją każdej z nich, w
postaci pozwalającej na jednoznaczne rozstrzygnięcie przypadków
granicznych. Definicja musi obejmować najmniejszą jednostkę kartowania
oraz próg udziału, powyżej którego obiekt mieszany trafia do klasy
dominującej.

### 2.5 Zbiór referencyjny

**[DO UZUPEŁNIENIA]** Pochodzenie, data pozyskania, osoba
interpretująca, niezależność od danych uczących, sposób rozstrzygania
przypadków spornych. To jest warunek blokujący: bez niezależnego
zbioru referencyjnego rozdziały 4.1 do 4.4 nie mogą zawierać liczb.

---

## 3. Metody

Wszystkie stałe podane niżej są wartościami domyślnymi programu w
wersji 1.0.0 i występują w kodzie w tej postaci. Pełne wyprowadzenie
wraz z uzasadnieniem każdego progu zawiera dokumentacja metody
dołączona do repozytorium.

### 3.1 Przygotowanie obrazu

Program pracuje na trzech kanałach widzialnych. Przy obrazie
większym niż 15 milionów pikseli stosowane jest zmniejszenie robocze,
a wynik przenoszony jest z powrotem na pełną rozdzielczość.
**[DO UZUPEŁNIENIA: czy w opisywanym biegu zmniejszenie wystąpiło]**

### 3.2 Segmentacja

Segmentacja metodą SLIC {{cite: Achanta i in., 2012, 10.1109/TPAMI.2012.120}}
w przestrzeni CIELAB, przy punkcie bieli D65. Odległość między
pikselem a środkiem skupienia:

$$D = \sqrt{d_{\text{barwa}}^{2} + \left(\frac{d_{\text{odleg}}}{S}\right)^{2} m^{2}}$$

gdzie *S* jest przewidywanym bokiem segmentu, a *m* zwartością.
Wartości domyślne: zwartość 0,15, wygładzenie wstępne sigma 2,5,
10 iteracji. Niska zwartość oznacza, że o przebiegu granicy decyduje
przede wszystkim barwa, a segmenty przylegają do rzeczywistych
krawędzi kosztem regularności kształtu.

Liczbę segmentów wyznacza podana przez użytkownika typowa wielkość
obiektu w metrach, przeliczana przez rozmiar piksela. Błąd na tym
etapie jest nieodwracalny: segment obejmujący dwie klasy zostanie
przypisany do jednej z nich niezależnie od jakości klasyfikatora.

### 3.3 Cechy obiektów

Dla każdego segmentu liczonych jest 19 wielkości z kanałów
widzialnych, a przy dostępnym NMPT dodatkowo 5 wielkości
wysokościowych.

**Barwa, 7 wielkości.** Średnie i odchylenia standardowe trzech
kanałów oraz średnia jasność.

**Roślinność, 3 wielkości.** ExG, VARI i NGRDI liczone na
współrzędnych chromatycznych, czyli na udziałach kanałów w sumie
kanałów. Dzięki temu ten sam materiał w cieniu i w pełnym słońcu daje
zbliżone wartości.

**Faktura, 4 wielkości.** Kontrast, jednorodność, energia i entropia
z macierzy współwystąpień {{cite: Haralick i in., 1973, 10.1109/TSMC.1973.4309314}}.
Parametry: 15 poziomów szarości, odległość 1 piksel, cztery kierunki
(0, 45, 90 i 135 stopni), macierz symetryczna. Kwantyzacja do
poziomów szarości liczona jest z całego zdjęcia, a nie z pojedynczego
segmentu, dzięki czemu wartości są porównywalne między obiektami.
Segmenty mniejsze niż 16 pikseli otrzymują wartości neutralne.

**Kształt, 4 wielkości.** Powierzchnia, obwód, okrągłość i wypukłość.
Obwód szacowany estymatorem Croftona, ponieważ zliczanie krawędzi
pikselowych zawyża obwód koła o około 27 procent i uniemożliwia
osiągnięcie okrągłości równej jedności. Otoczka wypukła liczona jest z
narożników pikseli, nie z ich środków.

**Kontekst, 1 wielkość.** Jasność segmentu odniesiona do średniej
jasności jego sąsiadów.

**Wysokość, 5 wielkości (tylko z NMPT).** Średnia i odchylenie
wysokości, nachylenie, wysokość względem sąsiedztwa oraz wysokość nad
gruntem. Grunt szacowany jest z samego NMPT w trzech krokach:
minimum w blokach około 1 m, otwarcie morfologiczne o oknie 40 m,
wygładzenie średnią ruchomą. Okno otwarcia jest ograniczane do połowy
krótszego boku obrazu, co zapobiega zawyżeniu gruntu na małych
fragmentach.

Cechy nie są skalowane, ponieważ Random Forest dzieli po progach
pojedynczych cech i jest odporny na monotoniczne przekształcenia
zmiennych.

### 3.4 Dane uczące

Użytkownik wskazuje przykłady każdej klasy, klikając segmenty na
obrazie lub wczytując warstwę poligonową. Przykład jest zawsze
etykietą całego segmentu, nie pojedynczego piksela.

### 3.5 Klasyfikator

Random Forest {{cite: Breiman, 2001, 10.1023/A:1010933404324}}: 100
drzew, kryterium Giniego, liczba cech rozpatrywanych przy podziale
równa pierwiastkowi z liczby cech, losowanie ze zwracaniem, ziarno
generatora 42, głosowanie miękkie. Wagi klas nie są stosowane.
Przegląd zastosowań tego klasyfikatora w teledetekcji podaje
{{cite: Belgiu i Drăguţ, 2016, 10.1016/j.isprsjprs.2016.01.011}}.

Progi w węzłach drzew nie są zadane z góry: wybiera je algorytm z
danych uczących. Oznacza to, że granice klas zmieniają się wraz z
przykładami i że żadna liczba podana w artykule jako próg decyzyjny
klasy nie jest stałą programu.

Obok klasy zapisywana jest pewność przypisania, czyli udział drzew
głosujących na klasę zwycięską. Niska pewność wskazuje obiekty
graniczne i obszary niedoreprezentowane w próbie uczącej.

### 3.6 Korekta zieleni

ExG wygładzony w oknie 3 na 3 piksele, próg dobierany jako wartość
maksymalizująca wskaźnik Youdena spośród 256 kandydatów. W trybie
całosegmentowym segment zmienia klasę, gdy udział pikseli zielonych
przekracza 0,25.

Jest to operacja pikselowa wewnątrz toru obiektowego. Fakt ten musi
być podany wprost przy opisie mapy, ponieważ narusza czysto obiektowy
charakter wyniku.

### 3.7 Usuwanie małych łat

Łaty mniejsze od zadanego progu są pochłaniane przez otoczenie w
sąsiedztwie czterospójnym, bez wygładzania granic. Operacja zmienia
powierzchnie klas i musi być wykonana przed oceną dokładności, a nie
po niej.

### 3.8 Miara rozdzielności klas

Rozdzielność pary klas mierzona jest odległością Jeffriesa i Matusity
liczoną z walidacją krzyżową na pięciu podziałach. W każdym podziale
wyznaczany jest kierunek Fishera na części uczącej, z regularyzacją
macierzy kowariancji estymatorem
{{cite: Ledoit i Wolf, 2004, 10.1016/S0047-259X(03)00096-4}},
następnie na części testowej liczona jest odległość Bhattacharyi w
jednym wymiarze, a z niej JM = 2(1 − e^−B). Wynik jest uśredniany po
podziałach. Progi interpretacyjne: 1,9 i 1,7.

Wariant klasyczny, liczony w pełnej przestrzeni cech na tych samych
próbkach, osiąga wartość bliską 2,00 dla niemal każdej pary, również
dla pary powstałej ze sztucznego podziału jednej klasy, więc nie
niesie informacji o rzeczywistej rozdzielności. Wariant z walidacją
krzyżową dla takiej pary kontrolnej zwraca wartości rzędu 0,02 do 0,07.

### 3.9 Ocena dokładności i estymacja powierzchni

Próba warstwowa, w której warstwami są klasy mapy. Warstwa zapisywana
jest razem z punktem, zgodnie z wymogiem
{{cite: Stehman, 2014, 10.1080/01431161.2014.930207}}. Punkty do
oceny nie trafiają na obiekty użyte jako przykłady uczące.

Udziały w macierzy pomyłek ważone są powierzchnią warstw:

$$p_{ij} = W_i \frac{n_{ij}}{n_i}$$

gdzie *W_i* to udział powierzchniowy warstwy *i*, *n_i* to liczba
punktów w warstwie *i*, a *n_ij* to punkty z warstwy *i* o klasie
referencyjnej *j*. Dokładność ogólna, dokładność producenta i
użytkownika oraz powierzchnie klas liczone są z tej macierzy, a
wariancje z równań 5 do 7 pracy
{{cite: Olofsson i in., 2014, 10.1016/j.rse.2014.02.015}}.
Przedziały ufności 95 procent przy z = 1,96.

Współczynnik kappa nie jest raportowany jako miara główna, zgodnie z
argumentacją {{cite: Pontius i Millones, 2011, 10.1080/01431161.2011.552923}}.

Implementację sprawdzono na przykładzie rachunkowym z tabeli 8 pracy
{{cite: Olofsson i in., 2014, 10.1016/j.rse.2014.02.015}}: dokładność
ogólna 0,9449 wobec 0,944 podanego w źródle.

### 3.10 Odtwarzalność

**[DO UZUPEŁNIENIA: DOI archiwum Zenodo]** Kod dostępny w
repozytorium `geoai_klasyfikator` z oznaczoną wersją. Ziarno
generatora liczb pseudolosowych równe 42 we wszystkich losowaniach.
Spis wersji bibliotek **[DO UZUPEŁNIENIA]**.

---

## 4. Wyniki

**Rozdział pusty.** Analiz na danych rzeczywistych nie wykonano.
Poniżej podano wyłącznie układ, w jakim wyniki mają zostać
przedstawione, oraz wymagania wobec każdej pozycji.

### 4.1 Rozdzielność klas w kanale widzialnym (PB1)

**[DO UZUPEŁNIENIA]**

- **Tab. 1.** Macierz odległości JM dla wszystkich par klas, wartości
  z walidacji krzyżowej, oznaczenie par poniżej 1,7.
- **Ryc. 1.** Ranking ważności cech z klasyfikatora Random Forest, z ostrzeżeniem,
  że ważność nie jest miarą przyczynową.
- Komentarz musi wskazać pary, których tor nie rozdziela, a nie
  wyłącznie te, które rozdziela dobrze.

### 4.2 Wkład cech wysokościowych (PB2)

**[DO UZUPEŁNIENIA]**

- **Tab. 2.** Dokładność ogólna oraz dokładności producenta i
  użytkownika dla wariantu z 19 i 24 cechami, przy tej samej próbie i
  tym samym ziarnie, z przedziałami ufności.
- Porównanie dwóch klasyfikatorów na tej samej próbie wymaga testu
  McNemara. Sama różnica dokładności nie wystarcza.

### 4.3 Skutek korekt (PB3)

**[DO UZUPEŁNIENIA]**

- **Tab. 3.** Dokładność przed korektą zieleni, po korekcie i po
  usunięciu małych łat.
- Liczba i łączna powierzchnia segmentów, które zmieniły klasę, w
  podziale na klasy. Bez tej liczby nie da się ocenić, jak głęboko
  operacja pikselowa naruszyła wynik obiektowy.

### 4.4 Powierzchnia klas z niepewnością (PB4)

**[DO UZUPEŁNIENIA]**

- **Tab. 4.** Dla każdej klasy: powierzchnia odczytana z mapy,
  powierzchnia skorygowana o błąd klasyfikacji, przedział ufności
  95 procent, szerokość przedziału jako udział wartości.
- **Ryc. 2.** Obie powierzchnie na jednym wykresie z przedziałami
  ufności, co pokazuje kierunek i wielkość obciążenia.

---

## 5. Dyskusja

**Rusztowanie.** Punkty poniżej wynikają z własności metody i są
prawdziwe niezależnie od wyniku biegu, ale każdy z nich wymaga
odniesienia do liczb z rozdziału 4, zanim trafi do manuskryptu.

### 5.1 Czego kanał widzialny nie rozdziela

Tor nie zawiera cech wyglądu wyprowadzonych z sieci transformerowej.
Klasy różniące się układem przestrzennym, a nie materiałem, na
przykład dwie uprawy o tej samej barwie i wysokości, lecz odmiennym
układzie rzędów, pozostają nierozdzielone. Jest to ograniczenie
wpisane w konstrukcję, nie usterka. **[DO UZUPEŁNIENIA: które pary
klas w badanym obszarze na to natrafiły]**

### 5.2 Granice estymacji gruntu z samego NMPT

Otwarcie morfologiczne o oknie 40 m usuwa z powierzchni gruntu
wszystko, co węższe od okna, więc obiekty szersze, na przykład duże
hale, są traktowane częściowo jako grunt i ich wysokość jest
zaniżana. Zastosowanie osobnego numerycznego modelu terenu usuwa to
ograniczenie. **[DO UZUPEŁNIENIA: czy w badanym obszarze wystąpiły
obiekty szersze niż 40 m]**

### 5.3 Cena korekt pikselowych

Korekta zieleni i usuwanie małych łat poprawiają wygląd mapy, lecz
przenoszą część decyzji na poziom piksela. Praca, która je stosuje,
nie może przedstawiać wyniku jako czysto obiektowego.

### 5.4 Powierzchnia z mapy wobec estymatora ważonego

**[DO UZUPEŁNIENIA]** Omówienie kierunku i wielkości różnicy między
powierzchnią zliczoną z mapy a estymatorem skorygowanym, wobec
{{cite: Olofsson i in., 2014, 10.1016/j.rse.2014.02.015}}.

### 5.5 Odniesienie do literatury

**[DO UZUPEŁNIENIA]** Porównanie uzyskanych dokładności z pracami o
klasyfikacji obiektowej nalotów bezzałogowych w kanale widzialnym.
Warunek: porównywać wolno wyłącznie prace o zbliżonej rozdzielczości,
liczbie klas i sposobie walidacji. Zestawienie dokładności z prac o
innej legendzie jest porównaniem pozornym i musi być opisane jako
takie.

### 5.6 Ograniczenia

1. Brak bliskiej podczerwieni ogranicza rozróżnienie roślinności do
   cechy zieloności.
2. Brak cech wyglądu z sieci głębokiej ogranicza rozróżnienie klas
   różniących się wzorem przestrzennym (sekcja 5.1).
3. Szacowanie gruntu z samego NMPT zawodzi przy szerokich obiektach
   (sekcja 5.2).
4. Wynik zależy od wielkości segmentu podanej przez użytkownika;
   segment obejmujący dwie klasy wprowadza błąd nieusuwalny na
   późniejszych etapach.
5. Elementy węższe niż segment (miedze, ścieżki, rowy) są wchłaniane
   przez sąsiadów.
6. **[DO UZUPEŁNIENIA]** Zasięg wniosków ograniczony do jednego
   obszaru, jednego terminu i jednej rozdzielczości, dopóki praca nie
   obejmie więcej niż jednego nalotu.

### 5.7 Kierunki dalszych badań

**[DECYZJA AUTORA]** Propozycje: powtórzenie na kilku nalotach z
różnych terminów i terenów w celu oceny przenoszalności; dołączenie
cech wyglądu z modelu wstępnie wytrenowanego i pomiar przyrostu
rozdzielności; ocena wrażliwości wyniku na wielkość segmentu.

---

## 6. Wnioski

**[DO UZUPEŁNIENIA]** Cztery akapity, po jednym na pytanie badawcze,
bez nowych liczb i bez powtarzania rozdziału 4. Każdy wniosek musi
mieścić się w zasięgu danych: jeden obszar, jeden termin, jedna
rozdzielczość, jedna legenda.

---

## Sekcje końcowe

**Dostępność danych i kodu.** Kod: repozytorium `geoai_klasyfikator`,
licencja GPL-3.0-or-later. **[DO UZUPEŁNIENIA: DOI Zenodo, dostępność
ortomozaiki, NMPT i zbioru referencyjnego]**

**Wkład autorów (CRediT).** **[DO UZUPEŁNIENIA]**

**Finansowanie.** **[DO UZUPEŁNIENIA: nazwa i numer grantu albo
oświadczenie o braku finansowania]**

**Konflikt interesów.** **[DO UZUPEŁNIENIA]**

**Podziękowania.** **[DO UZUPEŁNIENIA]**

---

## Literatura do zaimportowania do Zotero

Pozycje sprawdzone w bazie: autorzy, rok, tytuł, czasopismo i DOI
zgadzają się z rekordem, żadna nie jest wycofana ani opatrzona
sprostowaniem.

| Cytowanie w tekście | DOI |
|---|---|
| Achanta i in., 2012 | 10.1109/TPAMI.2012.120 |
| Belgiu i Drăguţ, 2016 | 10.1016/j.isprsjprs.2016.01.011 |
| Blaschke, 2010 | 10.1016/j.isprsjprs.2009.06.004 |
| Breiman, 2001 | 10.1023/A:1010933404324 |
| Gitelson i in., 2002 | 10.1016/S0034-4257(01)00289-9 |
| Haralick i in., 1973 | 10.1109/TSMC.1973.4309314 |
| Hunt i in., 2005 | 10.1007/s11119-005-2324-5 |
| Ledoit i Wolf, 2004 | 10.1016/S0047-259X(03)00096-4 |
| Olofsson i in., 2013 | 10.1016/j.rse.2012.10.031 |
| Olofsson i in., 2014 | 10.1016/j.rse.2014.02.015 |
| Pontius i Millones, 2011 | 10.1080/01431161.2011.552923 |
| Stehman, 2014 | 10.1080/01431161.2014.930207 |
| Woebbecke i in., 1995 | 10.13031/2013.27838 |

Znaczniki `{{cite: Autor, rok, DOI}}` w tekście nie są polami Zotero.
Po przeniesieniu tekstu do Worda każdy znacznik trzeba zastąpić polem
wstawionym wtyczką Zotero, inaczej zmiana stylu cytowania nie zadziała.

---

## Co trzeba zrobić, zanim ten szkic stanie się manuskryptem

1. Zatwierdzić lub przeformułować tezę i wybrać czasopismo docelowe.
2. Wykonać i udokumentować przeszukanie literatury pod lukę badawczą
   (sekcja 1.4).
3. Pozyskać ortomozaikę, NMPT i niezależny zbiór referencyjny.
4. Ustalić legendę klas z definicjami rozstrzygającymi przypadki
   graniczne.
5. Przeprowadzić bieg, zapisać wyniki wraz z wersją programu i
   ziarnem.
6. Wypełnić rozdział 4, potem 5, potem 6, potem streszczenie.
7. Przenieść tekst do pliku Worda na stylach, wstawić pola Zotero,
   wykonać kontrolę końcową.
