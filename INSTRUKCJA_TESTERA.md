# GeoAI Klasyfikator: instrukcja dla testera

Cześć! Poniżej wszystko, czego potrzebujesz, żeby program zadziałał.
Całość zajmuje około 20 minut, z czego połowa to czekanie na instalację.

Jeśli coś nie wyjdzie, **napisz mi, co dokładnie zrobiłeś i jaki
komunikat zobaczyłeś**. Zrzut ekranu wystarczy.
→ gorniakgrzegorz@gmail.com

---

## Czego potrzebujesz do testu

- **zdjęcie z drona** (ortomozaika, GeoTIFF, trzy kanały RGB),
- opcjonalnie **model wysokości (NMPT)** z tego samego nalotu, nie
  jest konieczny, ale bardzo poprawia wynik,
- **QGIS 3.22 lub nowszy** (do wersji wtyczki),
- **Python 3.9 lub nowszy** (do wersji z wiersza poleceń).

Zdjęcie musi być w **układzie metrycznym** (np. PUWG 1992, EPSG:2180).
Jeśli jest w stopniach geograficznych (EPSG:4326), przelicz je:
*Raster → Projekcje → Przekształć*.

---

# A. Wtyczka QGIS: 5 minut

## Instalacja

1. QGIS → **Wtyczki → Zarządzanie wtyczkami…**
2. Zakładka **Zainstaluj z pliku ZIP**
3. Wskaż `geoai_klasyfikator.zip` → **Zainstaluj wtyczkę**
4. Na pasku narzędzi pojawi się przycisk **GeoAI Klasyfikator**

## Pierwszy przebieg

1. Wczytaj do QGIS zdjęcie (i NMPT, jeśli masz).
2. Kliknij przycisk wtyczki, panel otworzy się z prawej strony.
3. **Krok 1.** Wybierz zdjęcie z listy. Zaznacz
   **„Policz tylko to, co widać na ekranie"** i przybliż się do
   fragmentu, który dobrze znasz, na pierwszy raz to oszczędza
   kwadrans. Ustaw:
   - *Rozdzielczość robocza (m)*: **0,05** (albo zostaw „jak w pliku")
   - *Wielkość obiektu*: **10 m²**

   Kliknij **PODZIEL NA OBIEKTY I ZMIERZ**.

   W dzienniku na dole zobaczysz, ile obiektów powstało i jaka jest
   ich mediana powierzchni.

4. **Krok 2.** Kliknij **Dodaj klasę** i wpisz np. `trawa`. Powtórz
   dla 3–5 klas (np. `grunt odkryty`, `droga`, `zabudowa`, `drzewa`).

   Zaznacz klasę na liście, kliknij **WSKAZUJ PRZYKŁADY NA MAPIE**
   i klikaj obiekty należące do tej klasy. Z wciśniętym **Ctrl**
   możesz malować, przeciągając myszą.

   Daj po **10–20 przykładów na klasę**, rozrzuconych po całym
   zdjęciu.

5. **Krok 3.** Kliknij po kolei:
   - **Czy klasy da się rozróżnić?** Jeśli któraś para wypadnie
     „SŁABO", dodaj jej przykładów,
   - **Naucz**,
   - **ZRÓB MAPĘ**.

6. Obejrzyj wynik. Wypisz sobie *rodzaje* pomyłek, dodaj po kilka
   przykładów każdego rodzaju i powtórz krok 3. Dwie, trzy rundy
   poprawiają najwięcej.

7. **Krok 4** (jeśli chcesz sprawdzić dokładność): wylosuj punkty,
   **wyłącz w panelu warstw warstwę z mapą**, opisz punkty patrząc na
   samo zdjęcie, kliknij **POLICZ DOKŁADNOŚĆ**.

## Co mnie szczególnie interesuje

- czy coś się wywaliło i przy którym kroku,
- czy wielkość obiektu dała sensowny podział za pierwszym razem,
- czy komunikaty w dzienniku są zrozumiałe,
- ile to wszystko trwało na Twoim zdjęciu.

---

# B. Program w Pythonie: 15 minut

Przydaje się, gdy masz **wiele nalotów** i chcesz je przerobić hurtem.

## Instalacja

1. Zainstaluj Pythona z [python.org](https://www.python.org/downloads/).
   **Przy instalacji zaznacz „Add Python to PATH"**, bez tego nic
   nie zadziała.

2. Otwórz wiersz poleceń (Windows: klawisz Win, wpisz `cmd`) i wejdź
   do katalogu `program_cli`:

   ```
   cd C:\sciezka\do\geoai_klasyfikator\program_cli
   ```

3. Zainstaluj biblioteki, jedno polecenie, trwa kilka minut:

   ```
   python -m pip install -r requirements.txt
   ```

   Gdyby zgłosił brak uprawnień, dodaj `--user`:
   ```
   python -m pip install --user -r requirements.txt
   ```

4. Sprawdź, czy wszystko jest:

   ```
   python geoai.py sprawdz
   ```

   Ma wypisać listę z dopiskiem `[jest]` i na końcu
   „Wszystko na miejscu".

## Przygotowanie przykładów

Program nie ma okna do klikania, więc przykłady podajesz w pliku.

1. Zrób pusty plik:
   ```
   python geoai.py szablon --zdjecie C:\naloty\nalot_01.tif --plik przyklady.gpkg
   ```

2. Otwórz `przyklady.gpkg` i zdjęcie w QGIS. Włącz edycję warstwy
   `przyklady`, rysuj poligony na terenach, które znasz, i w kolumnie
   **`klasa`** wpisuj nazwę: `trawa`, `droga`, `zabudowa`…

3. Po kilkanaście poligonów na klasę, rozrzuconych po całym zdjęciu.
   Zapisz i wyłącz edycję.

## Nauka i klasyfikacja

```
python geoai.py ucz --zdjecie C:\naloty\nalot_01.tif ^
                    --probki przyklady.gpkg ^
                    --nmpt C:\nmpt\nalot_01_nmpt.tif ^
                    --rozdzielczosc 0.05 ^
                    --wielkosc-obiektu 10 ^
                    --separowalnosc ^
                    --model moj_model.geoai
```

```
python geoai.py klasyfikuj --folder C:\naloty ^
                           --model moj_model.geoai ^
                           --wyjscie C:\mapy ^
                           --nmpt-folder C:\nmpt
```

(Znak `^` to łamanie linii w Windows. Możesz też wpisać wszystko
w jednej linii, bez `^`.)

W katalogu `C:\mapy` znajdziesz mapy jako GeoTIFF (wczytaj je do QGIS
otworzą się od razu w kolorach) oraz **raport.csv** z powierzchnią
każdej klasy na każdym zdjęciu.

## Pliki NMPT

Program dopasowuje je po nazwie:
`nalot_01.tif` → szuka `nalot_01_nmpt.tif`.
Jeśli Twoje nazywają się inaczej, dodaj `--nmpt-przyrostek _dsm`.

## Gdy coś nie działa

| Komunikat | Co zrobić |
|---|---|
| `python` nie jest rozpoznane | Python bez „Add to PATH", zainstaluj ponownie z zaznaczoną opcją |
| `No module named 'rasterio'` | nie przeszła instalacja bibliotek, wróć do punktu 3 |
| `Siatka robocza … nie zmieści się w pamięci` | daj grubszą rozdzielczość, np. `--rozdzielczosc 0.10` |
| `Klasy bez ani jednego obiektu uczącego` | poligony za małe, narysuj większe albo zmniejsz `--wielkosc-obiektu` |
| `Ten model uczył się z modelem wysokości` | dodaj `--nmpt-folder` albo naucz model bez `--nmpt` |

Pełna pomoc do każdego polecenia:
```
python geoai.py ucz --help
```

---

## Co zgłaszać

Najbardziej przydadzą mi się:

1. **Każdy komunikat błędu**, w całości, razem z tym, co robiłeś.
2. **Miejsca, gdzie nie wiedziałeś, co kliknąć** albo co wpisać.
3. **Czas**, ile trwał podział i klasyfikacja, przy jakim rozmiarze
   zdjęcia.
4. **Jakość mapy**, czy wynik ma sens dla Twojego terenu i gdzie
   najbardziej się myli.

Dzięki!

---

© Grzegorz Górniak · gorniakgrzegorz@gmail.com
