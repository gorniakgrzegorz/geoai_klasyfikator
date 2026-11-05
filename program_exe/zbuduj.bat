@echo off
chcp 65001 >nul
rem ====================================================================
rem  GeoAI Klasyfikator - budowanie programu .exe i instalatora
rem
rem  Co to robi, po kolei:
rem    1. sprawdza, czy jest Python
rem    2. tworzy osobne srodowisko w katalogu .venv
rem    3. instaluje potrzebne biblioteki i PyInstallera
rem    4. sklada program do katalogu dist
rem    5. jesli jest Inno Setup, buduje tez instalator
rem
rem  Uruchom dwuklikiem albo z wiersza polecen. Trwa 5-15 minut.
rem ====================================================================
setlocal
cd /d "%~dp0"

echo.
echo ====================================================================
echo   GeoAI Klasyfikator - budowanie
echo ====================================================================
echo.

rem --- 1. Python ------------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [BLAD] Nie znalazlem Pythona.
    echo.
    echo Pobierz go z https://www.python.org/downloads/
    echo i przy instalacji ZAZNACZ "Add Python to PATH".
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set WERSJA=%%v
echo [1/5] Python %WERSJA% - jest.

rem --- 2. srodowisko --------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [2/5] Tworze srodowisko .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [BLAD] Nie udalo sie utworzyc srodowiska.
        pause
        exit /b 1
    )
) else (
    echo [2/5] Srodowisko .venv juz jest.
)
set PY=.venv\Scripts\python.exe

rem --- 3. biblioteki --------------------------------------------------
echo [3/5] Instaluje biblioteki (to trwa najdluzej) ...
%PY% -m pip install --upgrade pip --quiet
%PY% -m pip install -r "..\program_cli\requirements.txt" --quiet
if errorlevel 1 (
    echo [BLAD] Nie udalo sie zainstalowac bibliotek.
    echo Sprobuj uruchomic to okno jako administrator.
    pause
    exit /b 1
)
%PY% -m pip install pyinstaller --quiet
if errorlevel 1 (
    echo [BLAD] Nie udalo sie zainstalowac PyInstallera.
    pause
    exit /b 1
)

rem --- 4. skladanie programu ------------------------------------------
echo [4/5] Skladam program (kilka minut) ...
%PY% -m PyInstaller GeoAI_Klasyfikator.spec --noconfirm --clean
if errorlevel 1 (
    echo [BLAD] Budowanie sie nie powiodlo - zajrzyj w komunikaty wyzej.
    pause
    exit /b 1
)

if not exist "dist\GeoAI Klasyfikator\GeoAI Klasyfikator.exe" (
    echo [BLAD] Nie powstal plik .exe.
    pause
    exit /b 1
)
echo       Gotowe: dist\GeoAI Klasyfikator\GeoAI Klasyfikator.exe

rem --- 5. instalator --------------------------------------------------
echo [5/5] Szukam Inno Setup ...
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe

if "%ISCC%"=="" (
    echo       Inno Setup nie jest zainstalowany - pomijam instalator.
    echo.
    echo       Sam program jest gotowy w katalogu dist i dziala.
    echo       Jesli chcesz tez instalator, pobierz Inno Setup z
    echo       https://jrsoftware.org/isdl.php i uruchom to ponownie.
) else (
    echo       Buduje instalator ...
    "%ISCC%" instalator.iss
    if errorlevel 1 (
        echo [BLAD] Budowanie instalatora sie nie powiodlo.
        pause
        exit /b 1
    )
    echo       Gotowe: instalator\GeoAI_Klasyfikator_Setup.exe
)

echo.
echo ====================================================================
echo   SKONCZONE
echo ====================================================================
echo.
pause
