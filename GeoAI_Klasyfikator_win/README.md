# GeoAI_Klasyfikator_win

Zestaw instalacyjny programu **GeoAI Klasyfikator** dla systemu Windows.

## Gdzie są pliki do pobrania

Gotowego instalatora nie ma w tym folderze i nie będzie. Powód jest
prozaiczny: waży kilkaset megabajtów, bo niesie w sobie biblioteki GDAL,
PROJ, NumPy, SciPy i scikit-learn, a repozytorium git nie jest miejscem
na pliki tej wielkości. Powstaje też na nowo przy każdej zmianie kodu,
więc leżąca tu kopia byłaby po tygodniu nieaktualna.

Pobierz go stąd:

| Skąd | Co dostajesz | Kiedy się aktualizuje |
|---|---|---|
| [**Releases**](https://github.com/gorniakgrzegorz/geoai_klasyfikator/releases) | `GeoAI_Klasyfikator_Setup.exe` oraz `GeoAI_Klasyfikator_win.zip` | po oznaczeniu wersji znacznikiem `v...` |
| [**Actions**](https://github.com/gorniakgrzegorz/geoai_klasyfikator/actions/workflows/zbuduj-exe.yml) → ostatni przebieg → **Artifacts** → `GeoAI_Klasyfikator_win` | to samo, plus sumy kontrolne | po każdej zmianie kodu |

## Co jest w paczce

| Plik | Co to jest |
|---|---|
| `GeoAI_Klasyfikator_Setup.exe` | instalator; nie wymaga praw administratora, instaluje do katalogu użytkownika, dodaje skrót w menu Start i wpis do Ustawień, skąd da się go odinstalować |
| `GeoAI_Klasyfikator_win.zip` | wersja przenośna; rozpakuj gdziekolwiek i uruchom `GeoAI Klasyfikator.exe`, nic się nie instaluje |
| `SUMY-KONTROLNE.txt` | sumy SHA-256 obu plików, do sprawdzenia, czy pobrałeś dokładnie to, co zbudował GitHub |

Program nie wymaga Pythona ani QGIS. Wszystko ma w środku.

## Instalacja

1. Pobierz `GeoAI_Klasyfikator_Setup.exe`.
2. Przeglądarka ostrzeże, że plik jest niebezpieczny. Nie jest to
   wykryty wirus, tylko brak podpisu certyfikatem wydawcy. W Chrome:
   strzałka przy wpisie na liście pobierania, potem **Zachowaj**.
3. Uruchom plik. Windows SmartScreen pokaże niebieskie okno: **Więcej
   informacji**, potem **Uruchom mimo to**.
4. Przejdź przez instalator. Program pojawi się w menu Start.

Chcesz się upewnić, że plik jest oryginalny? Porównaj sumę kontrolną
z zawartością `SUMY-KONTROLNE.txt`:

```powershell
Get-FileHash .\GeoAI_Klasyfikator_Setup.exe -Algorithm SHA256
```

## Odinstalowanie

Ustawienia, potem Aplikacje, potem GeoAI Klasyfikator, potem Odinstaluj.
Wersję przenośną po prostu kasujesz razem z folderem.

## Jak to powstaje

Paczkę buduje maszyna Windows w chmurze GitHuba, z kodu w tym
repozytorium, bez kroków wykonywanych ręcznie. Przepis leży w pliku
[`.github/workflows/zbuduj-exe.yml`](../.github/workflows/zbuduj-exe.yml),
a składniki w folderze [`program_exe/`](../program_exe/): okno programu,
przepis dla PyInstallera, skrypt instalatora Inno Setup, ikona i zasób
wersji.

Chcesz zbudować paczkę u siebie? Opisuje to
[`program_exe/README.md`](../program_exe/README.md).

## Dokumentacja

- [Instrukcja użytkownika](../INSTRUKCJA_UZYTKOWNIKA.md), wtyczka i program, pole po polu
- [Instrukcja z rysunkami](https://gorniakgrzegorz.github.io/geoai_klasyfikator/)
- [Code signing policy](../CODE_SIGNING_POLICY.md)

---

© Grzegorz Górniak · gorniakgrzegorz@gmail.com · GPL-3.0-or-later
