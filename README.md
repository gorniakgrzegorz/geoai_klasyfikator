<div align="center">

# GeoAI Klasyfikator

**Mapa pokrycia terenu ze zdjęć z drona lub satelity, w trzech wersjach, na jednym silniku.**

[📖 Instrukcja z rysunkami](https://gorniakgrzegorz.github.io/geoai_klasyfikator/) ·
[⬇️ Pobierz program dla Windows](https://github.com/gorniakgrzegorz/geoai_klasyfikator/releases) ·
[GPL-3.0](LICENSE)

[![Zbuduj program Windows](https://github.com/gorniakgrzegorz/geoai_klasyfikator/actions/workflows/zbuduj-exe.yml/badge.svg)](https://github.com/gorniakgrzegorz/geoai_klasyfikator/actions/workflows/zbuduj-exe.yml)

</div>

---

Program dzieli zdjęcie na **obiekty**, kawałki pola, dachu, korony
drzewa, mierzy każdy z nich 19 albo 24 liczbami, uczy się Twoich klas
z kilkunastu przykładów i na końcu uczciwie mówi, ile ta mapa jest
warta.

```
'wysokość nad gruntem' 7,1 m · faktura gładka · jasność wysoka  →  zabudowa
```

## Trzy wersje

| Wersja | Dla kogo | Gdzie |
|---|---|---|
| 🗺️ **Wtyczka QGIS** | gdy chcesz widzieć, co się dzieje, i ocenić dokładność | [`geoai_klasyfikator/`](geoai_klasyfikator/) |
| 🪟 **Program dla Windows** | gdy nie chcesz instalować QGIS | [`program_exe/`](program_exe/) |
| ⌨️ **Wiersz poleceń** | gdy zdjęć są setki | [`program_cli/`](program_cli/) |

Wszystkie trzy liczą **dokładnie to samo**, dzielą katalog
[`geoai_klasyfikator/core/`](geoai_klasyfikator/core/): ten sam podział
na obiekty, te same cechy, ten sam Random Forest.

## Co program mierzy

| Grupa | Liczb | Co to jest |
|---|---|---|
| Kolor | 7 | średnia i zmienność R, G, B oraz jasność |
| Zieleń | 3 | ExG, VARI, NGRDI liczone na udziałach barw, więc liść w cieniu i w słońcu wypadają podobnie |
| Faktura | 4 | kontrast, jednolitość, regularność, nieuporządkowanie (GLCM) |
| Kształt | 4 | powierzchnia, obwód, okrągłość, wypukłość |
| Otoczenie | 1 | jasność na tle sąsiadów |
| Wysokość | 5 | z NMPT: wysokość, zmienność, nachylenie, wysokość nad gruntem |

Zwykłe kamery dronowe nie rejestrują podczerwieni, więc **NDVI tu nie
ma**. Zastępują go wskaźniki z zakresu widzialnego, faktura, kształt
i wysokość.

## Szybki start: wtyczka QGIS

1. QGIS →Wtyczki →Zarządzanie wtyczkami →**Zainstaluj z pliku ZIP**
2. Wskaż `geoai_klasyfikator.zip`
3. Na pasku pojawi się przycisk **GeoAI Klasyfikator**

## Szybki start: wiersz poleceń

```bash
cd program_cli
python -m pip install -r requirements.txt
python geoai.py sprawdz

# nauka na jednym zdjęciu
python geoai.py ucz --zdjecie proba.tif --probki przyklady.gpkg \
                    --nmpt proba_nmpt.tif --model model.geoai

# cały folder
python geoai.py klasyfikuj --folder ./naloty --model model.geoai \
                           --wyjscie ./mapy --nmpt-folder ./nmpt
```

## Szybki start: program dla Windows

Gotowego pliku nie trzymamy w repozytorium, bo powstaje przy każdej
zmianie kodu. Buduje go maszyna Windows w chmurze GitHuba, a pobrać
można go na dwa sposoby:

- **Wydanie:** zakładka [Releases](https://github.com/gorniakgrzegorz/geoai_klasyfikator/releases),
  plik `GeoAI_Klasyfikator_Setup.exe`. Instalator nie wymaga praw
  administratora i nie wymaga Pythona.
- **Najnowszy build:** zakładka
  [Actions](https://github.com/gorniakgrzegorz/geoai_klasyfikator/actions/workflows/zbuduj-exe.yml),
  ostatni przebieg, sekcja **Artifacts**, paczka
  `GeoAI_Klasyfikator_win`. Zawiera instalator oraz wersję
  przenośną w pliku ZIP, którą wystarczy rozpakować i uruchomić
  `GeoAI Klasyfikator.exe`.

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

Ostrzeżenie zniknie dopiero po podpisaniu programu certyfikatem
wydawcy. Pliki nie są jeszcze podpisane. Projekt przygotowuje wniosek
do programu SignPath Foundation dla projektów open source; po jego
przyjęciu pliki programu dla Windows będą podpisywane na tych zasadach:
*Free code signing provided by [SignPath.io](https://about.signpath.io),
certificate by [SignPath Foundation](https://signpath.org).*
Szczegóły, w tym role w zespole i politykę prywatności, opisuje
[Code signing policy](CODE_SIGNING_POLICY.md).

Opis samej paczki instalacyjnej, krok po kroku, jest w folderze
[`GeoAI_Klasyfikator_win/`](GeoAI_Klasyfikator_win/).

Samodzielne zbudowanie na własnym komputerze opisuje
[`program_exe/README.md`](program_exe/README.md).

## Skąd wziąć zdjęcia

Własny nalot dronem daje najlepszy wynik i jako jedyny daje model
wysokości. Za darmo i bez konta można też pobrać dane satelitarne,
wtyczkami tego samego autora, które składają gotową kompozycję RGB:

| Wtyczka | Co pobiera |
|---|---|
| [Pobieranie Sentinel](https://plugins.qgis.org/plugins/pobieranie_sentinel/) ([EN](https://plugins.qgis.org/plugins/sentinel_download/)) | Sentinel-2 (L2A, L1C) i Sentinel-1 (GRD) z Copernicus Data Space, piksel 10 m |
| [Pobieranie Landsat](https://plugins.qgis.org/plugins/pobieranie_landsat/) ([EN](https://plugins.qgis.org/plugins/Landsat-Download/)) | Landsat 4 do 9, Collection 2 Level-2, archiwum od 1982, piksel 30 m, bez konta |

Klasyfikator czyta **trzy pierwsze kanały pliku**, więc zawsze podawaj
gotowy produkt RGB, nigdy surowej sceny wielokanałowej. Szczegóły
w [INSTRUKCJA_UZYTKOWNIKA.md](INSTRUKCJA_UZYTKOWNIKA.md), rozdziały 4 i 5.

## Ocena dokładności

Część, której w QGIS brakuje. Program losuje punkty kontrolne (nigdy
na obiektach użytych do nauki), Ty opisujesz je patrząc na samo
zdjęcie, a na wyjściu dostajesz macierz błędów, trafność i kompletność
każdej klasy oraz **powierzchnie klas z przedziałami ufności 95%**,
ważone powierzchnią, czyli to, czego wymagają dziś recenzenci.

Postępowanie zgodne z Olofsson i in. (2014) oraz Stehman (2014).
Współczynnika kappa świadomie nie liczymy.

## Wymagania

| Wersja | Czego potrzebuje |
|---|---|
| Wtyczka QGIS | QGIS 3.22 lub nowszy i nic więcej |
| Wiersz poleceń | Python 3.9+, `numpy`, `rasterio`, `fiona` |
| Program Windows | nic, instalator ma wszystko w środku |

`scikit-image` i `scikit-learn` są opcjonalne: bez nich program działa,
z nimi liczy kilkakrotnie szybciej.

## Dokumentacja

| Dokument | Dla kogo |
|---|---|
| [📖 Instrukcja z rysunkami](https://gorniakgrzegorz.github.io/geoai_klasyfikator/) | każdy, jak to działa i jak tego używać |
| [INSTRUKCJA_UZYTKOWNIKA.md](INSTRUKCJA_UZYTKOWNIKA.md) | **pełny podręcznik**: wtyczka i program .exe, pole po polu, co działa gdzie |
| [INSTRUKCJA_TESTERA.md](INSTRUKCJA_TESTERA.md) | tester, instalacja i pierwszy przebieg, krok po kroku |
| [DOKUMENTACJA_TECHNICZNA.md](DOKUMENTACJA_TECHNICZNA.md) | **do pracy naukowej**: algorytmy, biblioteki, wszystkie parametry, odtwarzalność |
| [UWARUNKOWANIA_NAUKOWE.md](UWARUNKOWANIA_NAUKOWE.md) | **do artykułu**, wzory, stałe, reguły decyzyjne, ograniczenia, co cytować |
| [SZKIC_MANUSKRYPTU.md](SZKIC_MANUSKRYPTU.md) | szkielet artykułu: metoda napisana, wyniki do wypełnienia po badaniu |
| [RAPORT_ZGODNOSCI.md](RAPORT_ZGODNOSCI.md) | dowód, że wtyczka i program liczą to samo, co do piksela |
| [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md) | **Code signing policy**: kto podpisuje pliki, role w zespole, polityka prywatności |
| [NOTICE.md](NOTICE.md) | pochodzenie i licencja |

## Jak cytować

> Górniak, G. (2026). *GeoAI Klasyfikator* (wersja 1.0.2) [oprogramowanie
> komputerowe]. https://github.com/gorniakgrzegorz/geoai_klasyfikator

Metadane do cytowania są w pliku [CITATION.cff](CITATION.cff); GitHub
pokazuje je pod przyciskiem **Cite this repository** w prawej kolumnie.
Każde wydanie jest archiwizowane w Zenodo, które nadaje mu trwały
identyfikator DOI.

## Struktura repozytorium

```
geoai_klasyfikator/        wtyczka QGIS (ten folder instalujesz w QGIS)
  core/                    silnik wspólny dla wszystkich wersji
  dialogs/                 panel wtyczki i narzędzia na mapie
program_cli/               wersja dla wiersza poleceń
program_exe/               zestaw do zbudowania programu .exe dla Windows
GeoAI_Klasyfikator_win/    zestaw instalacyjny dla Windows: skad pobrac i jak zainstalowac
docs/                      instrukcja publikowana na GitHub Pages
  ryciny/                  schemat logiki artykułu, cztery formaty
.github/workflows/         budowanie programu Windows w chmurze
INSTRUKCJA_TESTERA.md      instalacja i pierwszy przebieg
UWARUNKOWANIA_NAUKOWE.md   metoda, wzory i stałe, do artykułu
DOKUMENTACJA_TECHNICZNA.md algorytmy, biblioteki, parametry, odtwarzalność
CITATION.cff               metadane do cytowania (GitHub, Zenodo)
.zenodo.json               opis wydania archiwizowanego w Zenodo
SZKIC_MANUSKRYPTU.md       szkielet artykułu, rozdziały 4 do 6 do wypełnienia
```


---

© Grzegorz Górniak · gorniakgrzegorz@gmail.com · GPL-3.0-or-later
