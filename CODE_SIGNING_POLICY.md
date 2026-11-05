# Code signing policy

Polityka podpisywania kodu / Code signing policy for **GeoAI Klasyfikator**.

> This page is required by SignPath Foundation. It is kept in English
> because that is the language of the policy it refers to; a Polish
> summary follows at the end.

## Signing

Free code signing provided by [SignPath.io](https://about.signpath.io),
certificate by [SignPath Foundation](https://signpath.org).

Signed artifacts: the Windows installer
(`GeoAI_Klasyfikator_Setup.exe`) and the portable build
(`GeoAI Klasyfikator.exe` inside `GeoAI_Klasyfikator_win.zip`),
published under
[Releases](https://github.com/gorniakgrzegorz/geoai_klasyfikator/releases).

All binaries are built from this repository by GitHub Actions, by the
workflow [`zbuduj-exe.yml`](.github/workflows/zbuduj-exe.yml), on a
`windows-latest` runner, with no manual steps. The QGIS plugin itself
and the command line program are plain Python source and are not
signed.

## Team roles

This project is currently maintained by a single person.

| Role | Member |
|---|---|
| Author (commits to the repository) | [Grzegorz Górniak](https://github.com/gorniakgrzegorz) |
| Reviewer (reviews external contributions) | [Grzegorz Górniak](https://github.com/gorniakgrzegorz) |
| Approver (approves signing requests) | [Grzegorz Górniak](https://github.com/gorniakgrzegorz) |

Every contribution from outside the team arrives as a pull request and
is reviewed before merging. Multi-factor authentication is enabled for
the GitHub account and for SignPath. Should the team grow, this table
will be updated before any new member is given signing rights.

## Privacy policy

This program will not transfer any information to other networked
systems unless specifically requested by the user or the person
installing or operating it.

The program reads image files and vector layers from paths the user
selects, and writes maps, style files and a report to the folder the
user selects. It makes no network connections of any kind: it has no
update check, no telemetry, no crash reporting and no licence check.

Third party components bundled with the Windows build (NumPy, SciPy,
scikit-learn, scikit-image, rasterio, Fiona, GDAL, PROJ) are used only
for local computation and are not configured to contact any service.

## Uninstallation

The installer registers the program in **Settings**, then **Apps**, so
it can be removed the usual way. The portable build is a folder: delete
it. Neither leaves files outside its own installation folder.

## Licence

[GPL-3.0-or-later](LICENSE). All components of this project are open
source; there is no dual licensing and no proprietary component.

---

## Podsumowanie po polsku

Pliki programu dla Windows są podpisywane bezpłatnie przez
SignPath.io, certyfikatem SignPath Foundation. Powstają wyłącznie
w chmurze GitHuba, z kodu w tym repozytorium, bez ręcznych kroków.
Projekt prowadzi jedna osoba, Grzegorz Górniak, która jest zarazem
autorem, recenzentem zgłoszeń i osobą zatwierdzającą podpisy.

Program nie wysyła niczego przez sieć: nie sprawdza aktualizacji, nie
zbiera statystyk i nie zgłasza błędów na zewnątrz. Czyta pliki
wskazane przez użytkownika i zapisuje wyniki tam, gdzie użytkownik
każe. Instalator można usunąć przez Ustawienia, potem Aplikacje;
wersję przenośną po prostu się kasuje.
