# GeoAI Klasyfikator

Wtyczka QGIS, która robi **mapę pokrycia terenu** ze zdjęcia z drona
albo zdjęcia lotniczego i od razu mówi, ile ta mapa jest warta.

Nie klasyfikuje pojedynczych pikseli, tylko tnie zdjęcie na **obiekty**
(kawałki pola, dachu, korony drzewa), mierzy każdy z nich i uczy się
od Ciebie, co jest czym.

**Autor:** Grzegorz Górniak (gorniakgrzegorz@gmail.com)
**Licencja:** GPL-3.0-or-later
**Wymaga:** QGIS 3.22 lub nowszy i nic więcej

---

## Dlaczego obiekty, a nie piksele

Pojedynczy piksel mówi tylko o kolorze. Obiekt ma jeszcze fakturę,
kształt, wysokość i otoczenie, a mapa nie wychodzi „zaśmiecona”
pojedynczymi kropkami.

## Cztery kroki

| Krok | Co się dzieje |
|---|---|
| 1 · Zdjęcie i obiekty | wczytanie rastra i opcjonalnego NMPT, podział metodą SLIC, pomiar 19 lub 24 cech |
| 2 · Klasy i przykłady | dodajesz klasy i klikasz na mapie przykłady każdej z nich |
| 3 · Nauka i mapa | sprawdzenie rozróżnialności klas, Random Forest, poprawki, zapis GeoTIFF |
| 4 · Ocena dokładności | losowanie punktów, opis na ślepo, macierz błędów i powierzchnie z przedziałami ufności |

## Co wtyczka mierzy

| Grupa | Cechy |
|---|---|
| Kolor (7) | średnia i zmienność R, G, B oraz jasność |
| Wskaźniki roślinności (3) | zieloność ExG, VARI, NGRDI, liczone na współrzędnych chromatycznych, więc liść w cieniu i w słońcu wypadają podobnie |
| Faktura GLCM (4) | kontrast, jednolitość, powtarzalność, nieuporządkowanie |
| Kształt (4) | powierzchnia, obwód, okrągłość, wypukłość |
| Otoczenie (1) | jasność na tle sąsiadów |
| Wysokość z NMPT (5) | średnia, zmienność, nachylenie, wysokość na tle sąsiadów, wysokość nad gruntem |

Zwykłe kamery dronowe nie rejestrują podczerwieni, więc **NDVI tu nie
ma**. Zastępują go wskaźniki z zakresu widzialnego, faktura, kształt
i wysokość.

## Instalacja

1. QGIS, menu Wtyczki, Zarządzanie wtyczkami
2. Wyszukaj „GeoAI Klasyfikator” i kliknij **Zainstaluj wtyczkę**
3. Na pasku narzędzi pojawi się przycisk **GeoAI Klasyfikator**

Strona wtyczki: <https://plugins.qgis.org/plugins/geoai_klasyfikator/>. Bez dostępu do internetu: zakładka
**Zainstaluj z pliku ZIP** i plik `geoai_klasyfikator.zip`.

### Szybciej na dużych zdjęciach (nieobowiązkowe)

Wtyczka działa bez niczego więcej. Jeśli jednak doinstalujesz dwie
biblioteki, podział na obiekty i nauka pójdą wyraźnie szybciej:

```
python -m pip install scikit-image scikit-learn
```

Polecenie wpisz w **OSGeo4W Shell** (menu Start, katalog QGIS), potem
uruchom QGIS ponownie. Jeśli nie przejdzie, uruchom powłokę jako
administrator.

## Trzy rady, które decydują o wyniku

1. **Dobierz wielkość obiektu do najwęższej rzeczy**, którą chcesz
   pokazać na mapie, a nie do tego, czego jest najwięcej.
2. **Rozrzuć przykłady po całym zdjęciu** i pokaż każdą odmianę klasy:
   i bujną trawę, i tę przyschniętą.
3. **Poprawianie to metoda, nie porażka.** Pierwsza mapa nigdy nie
   jest dobra. Przejrzyj ją, wypisz rodzaje pomyłek, dodaj po kilka
   przykładów każdego rodzaju i powtórz. Dwie, trzy rundy dają
   najwięcej.

## Ocena dokładności

Tu wtyczka robi rzecz, której w QGIS-ie brakuje. Losuje punkty
kontrolne (nigdy na obiektach użytych do nauki), Ty opisujesz je
patrząc na samo zdjęcie, a na wyjściu dostajesz:

- macierz błędów,
- trafność mapy i kompletność każdej klasy,
- dokładność ogólną **ważoną powierzchnią**,
- **szacowane powierzchnie klas z przedziałami ufności 95 procent**.

Przy losowaniu warstwowym udział punktów nie jest udziałem
powierzchni, dlatego w publikacji cytuje się liczby ważone
powierzchnią i szacowaną powierzchnię, a nie tę odczytaną wprost
z mapy (Olofsson i in., 2014; Stehman, 2014). Współczynnika kappa
świadomie nie liczymy.

## Co zostaje w projekcie

- **GeoAI obiekty**: warstwa poligonowa; w tabeli atrybutów wszystkie
  zmierzone cechy, kolumna `klasa_uczaca` (Twoje przykłady) i
  `klasa_mapy` (wynik).
- **GeoAI punkty kontrolne**: punkty z opisem ze zdjęcia, klasą
  z mapy i warstwą losowania.
- Zapisany **GeoTIFF** z plikiem stylu `.qml` obok.

## Struktura

```
geoai_klasyfikator/
├── metadata.txt            dane wtyczki dla QGIS
├── main_plugin.py          przycisk na pasku, otwieranie panelu
├── dialogs/
│   ├── dock.py             panel z czterema krokami
│   └── maptools.py         klikanie obiektów i punktów na mapie
└── core/
    ├── slic.py             podział na obiekty
    ├── features.py         19 lub 24 cechy obiektu
    ├── classifier.py       Random Forest i rozróżnialność klas
    ├── refine.py           dociąganie po zieloności, sito
    ├── accuracy.py         ocena dokładności wg Olofssona
    ├── qgis_io.py          odczyt rastrów, zapis GeoTIFF, polygonizacja
    ├── deps.py             wykrywanie bibliotek opcjonalnych
    └── compat.py           zgodność QGIS 3.22 - 4.x
```

