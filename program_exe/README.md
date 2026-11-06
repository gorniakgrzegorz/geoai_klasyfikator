# GeoAI Klasyfikator — program dla Windows

Ten katalog zawiera wszystko, czego trzeba, żeby zrobić z programu
**zwykłą aplikację Windows z instalatorem**: okno, przepis dla
PyInstallera, skrypt instalatora i jeden plik, który to wszystko
uruchamia.

---

## Gdzie jest gotowy plik .exe

**Nie w tym katalogu.** Program dla Windows daje się złożyć wyłącznie
na Windowsie: PyInstaller pakuje do niego prawdziwe biblioteki
systemowe (GDAL, PROJ, biblioteki Pythona), a tych nie da się uzyskać
z innego systemu. Pliku wynikowego nie trzymamy też w repozytorium,
bo waży kilkaset megabajtów i powstaje na nowo przy każdej zmianie
kodu.

Buduje go **maszyna Windows w chmurze GitHuba**, automatycznie.
Pobierz stamtąd:

| Skąd | Co dostajesz | Kiedy się aktualizuje |
|---|---|---|
| [Releases](https://github.com/gorniakgrzegorz/geoai_klasyfikator/releases) | `GeoAI_Klasyfikator_Setup.exe` | po oznaczeniu wersji znacznikiem `v...` |
| [Actions](https://github.com/gorniakgrzegorz/geoai_klasyfikator/actions/workflows/zbuduj-exe.yml) → ostatni przebieg → **Artifacts** | instalator oraz wersja przenośna w pliku ZIP | po każdej zmianie kodu |

Wersja przenośna nie wymaga instalacji: rozpakuj ZIP i uruchom
`GeoAI Klasyfikator.exe`.

Przepis, według którego chmura buduje program, leży w
[`.github/workflows/zbuduj-exe.yml`](../.github/workflows/zbuduj-exe.yml).
Jest to ten sam plik `.spec` i ten sam skrypt instalatora, co przy
budowaniu ręcznym, więc wynik jest identyczny.

---

## Jak zbudować program samodzielnie, krok po kroku

Potrzebne tylko wtedy, gdy chcesz zmienić kod i zobaczyć efekt od razu,
bez czekania na chmurę.

### 1. Zainstaluj Pythona (raz)

Pobierz z [python.org](https://www.python.org/downloads/), wersję 3.9
lub nowszą. **Przy instalacji zaznacz „Add Python to PATH"** — bez
tego nic nie zadziała.

### 2. Zainstaluj Inno Setup (raz, opcjonalnie)

Pobierz z [jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php).
Potrzebny tylko do zrobienia instalatora. Bez niego i tak powstanie
działający program — po prostu w katalogu, zamiast w instalatorze.

### 3. Kliknij dwa razy `zbuduj.bat`

Reszta dzieje się sama:

```
[1/5] Python 3.12.1 - jest.
[2/5] Tworzę środowisko .venv ...
[3/5] Instaluję biblioteki (to trwa najdłużej) ...
[4/5] Składam program (kilka minut) ...
[5/5] Szukam Inno Setup ...
      Gotowe: instalator\GeoAI_Klasyfikator_Setup.exe
```

Trwa to zwykle **5–15 minut** i zajmuje około 1,5 GB na dysku (prawie
wszystko to biblioteki w katalogu `.venv`, który potem możesz skasować).

### 4. Co powstaje

| Ścieżka | Co to jest |
|---|---|
| `dist\GeoAI Klasyfikator\GeoAI Klasyfikator.exe` | gotowy program — działa od razu, bez instalacji |
| `instalator\GeoAI_Klasyfikator_Setup.exe` | instalator do rozdawania innym |

Instalator **nie wymaga praw administratora**. Instaluje do katalogu
użytkownika (`%LOCALAPPDATA%\Programs\GeoAI Klasyfikator`), dodaje
skrót w menu Start i pozwala odinstalować przez Ustawienia → Aplikacje.

---

## Co jest w tym katalogu

| Plik | Do czego służy |
|---|---|
| `okno.py` | samo okno programu: dwie zakładki, pasek postępu, dziennik |
| `GeoAI_Klasyfikator.spec` | przepis dla PyInstallera — co dołożyć do `.exe` |
| `instalator.iss` | skrypt instalatora dla Inno Setup, po polsku |
| `zbuduj.bat` | uruchamia całość jednym kliknięciem |
| `ikona.ico` | ikona programu i instalatora |

---

## Jak wygląda program

Dwie zakładki, obie po polsku:

**1. Nauka** — wskazujesz zdjęcie, plik z przykładami i (opcjonalnie)
model wysokości, ustawiasz rozdzielczość i wielkość obiektu, klikasz
„NAUCZ MODEL". Program przy okazji sprawdza, czy Twoje klasy w ogóle
da się rozróżnić.

**2. Klasyfikacja wsadowa** — wskazujesz folder ze zdjęciami i gotowy
model, klikasz „KLASYFIKUJ CAŁY FOLDER". Program przelatuje po kolei
każde zdjęcie, zapisuje mapy jako GeoTIFF ze stylem `.qml` i na końcu
zbiorczy `raport.csv`.

Pod spodem pracuje **dokładnie ten sam silnik** co we wtyczce QGIS
i w wersji dla wiersza poleceń — ten sam podział na obiekty, te same
19 albo 24 cechy, ten sam Random Forest.

Przycisk „Instrukcja" w prawym górnym rogu otwiera opis metody
i wskazówki, jak dobierać ustawienia.

---

## Gdy coś nie wyjdzie

| Objaw | Co zrobić |
|---|---|
| `Nie znalazłem Pythona` | zainstaluj Pythona i **zaznacz „Add Python to PATH"**; potem otwórz `zbuduj.bat` ponownie |
| `Nie udało się zainstalować bibliotek` | uruchom `zbuduj.bat` prawym przyciskiem → „Uruchom jako administrator" |
| Program startuje i od razu znika | uruchom go z wiersza poleceń, zobaczysz komunikat; albo ustaw zmienną `GEOAI_SZCZEGOLY=1`, żeby okno pokazało pełny ślad błędu |
| `Nie udało się otworzyć pliku` przy GeoTIFF | w `.spec` nie dołączyły się dane GDAL-a — upewnij się, że budujesz tym samym Pythonem, w którym zainstalowano `rasterio` |
| Antywirus blokuje `.exe` | typowe dla programów z PyInstallera; dodaj wyjątek albo podpisz plik certyfikatem |
| `.exe` waży 400–600 MB | to normalne: w środku siedzą GDAL, PROJ, NumPy, SciPy i scikit-learn |

---

## Dla ciekawych: jak to jest poskładane

```
okno.py  (tkinter — jest w każdym Pythonie, nic nie trzeba dokładać)
   |
   v
geoai_cli/  (ta sama logika, co w wierszu poleceń)
   |
   v
geoai_klasyfikator/core/  (silnik wspólny z wtyczką QGIS)
```

Okno nie ma własnej logiki obliczeniowej — buduje tylko listę
argumentów i woła dokładnie te same funkcje, które wykonuje polecenie
`geoai ucz` i `geoai klasyfikuj`. Dzięki temu nie ma ryzyka, że okno
i wiersz poleceń policzą co innego.

---

© Grzegorz Górniak · GPL-3.0-or-later · gorniakgrzegorz@gmail.com
