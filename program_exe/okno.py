# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
GeoAI Klasyfikator — okno programu dla Windows.

Ten sam silnik co wtyczka QGIS i program wiersza poleceń, tylko
podany w oknie: wskazujesz pliki, klikasz i czekasz. Napisane
w tkinterze, który jest częścią Pythona, więc program nie potrzebuje
żadnej biblioteki do rysowania okien.

© Grzegorz Górniak <gorniakgrzegorz@gmail.com>
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import traceback
import webbrowser

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def _ostry_tekst() -> float:
    """Włącza świadomość gęstości pikseli i zwraca mnożnik skali.

    Bez tego Windows rysuje okno w 96 punktach na cal i rozciąga obraz,
    przez co tekst robi się rozmyty na ekranach 4K i na laptopach
    z powiększeniem 125 albo 150 procent. Po włączeniu świadomości
    system rysuje czcionki od razu w docelowym rozmiarze, więc są
    ostre. Zwracany mnożnik służy do przeskalowania rozmiarów okna.
    """
    if not sys.platform.startswith("win"):
        return 1.0
    import ctypes
    try:
        # 2 oznacza świadomość na każdym monitorze osobno
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            return 1.0
    try:
        uchwyt = ctypes.windll.user32.GetDC(0)
        # 88 to LOGPIXELSX, czyli liczba pikseli na cal w poziomie
        pikseli = ctypes.windll.gdi32.GetDeviceCaps(uchwyt, 88)
        ctypes.windll.user32.ReleaseDC(0, uchwyt)
        return max(1.0, pikseli / 96.0)
    except Exception:
        return 1.0

NAZWA = "GeoAI Klasyfikator"
WERSJA = "1.0.1"
AUTOR = "Grzegorz Górniak"
POCZTA = "gorniakgrzegorz@gmail.com"

BARWA = "#00bde7"
BARWA_CIEMNA = "#009ec2"
TLO = "#ffffff"
SZARY = "#607d8b"


def katalog_programu() -> str:
    """Katalog, w którym leży program — także po spakowaniu do .exe."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _przygotuj_sciezki():
    """Dokłada do ścieżki katalogi z modułami obliczeniowymi."""
    tu = katalog_programu()
    if getattr(sys, "frozen", False):
        zasoby = getattr(sys, "_MEIPASS", tu)
        for katalog in (zasoby, tu):
            if katalog not in sys.path:
                sys.path.insert(0, katalog)
    else:
        for wzgledny in ("..", os.path.join("..", "program_cli")):
            katalog = os.path.normpath(os.path.join(tu, wzgledny))
            if katalog not in sys.path:
                sys.path.insert(0, katalog)


_przygotuj_sciezki()


class Przekierowanie:
    """Przechwytuje wypisywanie, żeby trafiało do okna, a nie w próżnię."""

    def __init__(self, kolejka):
        self.kolejka = kolejka

    def __call__(self, tekst=""):
        self.kolejka.put(str(tekst))

    # zgodność z obiektem Dziennik z wersji konsolowej
    def szczegol(self, tekst):
        self.kolejka.put("    " + str(tekst))

    def blad(self, tekst):
        self.kolejka.put("BŁĄD: " + str(tekst))

    def naglowek(self, tekst):
        self.kolejka.put("")
        self.kolejka.put(tekst)
        self.kolejka.put("=" * len(tekst))


def _dymek(widget, tekst: str) -> None:
    """Mała chmurka z podpowiedzią po najechaniu myszą."""
    stan = {"okno": None}

    def pokaz(_zdarzenie=None):
        if stan["okno"] is not None:
            return
        x = widget.winfo_rootx()
        y = widget.winfo_rooty() - 26
        okno = tk.Toplevel(widget)
        okno.wm_overrideredirect(True)
        okno.wm_geometry("+{0}+{1}".format(x, y))
        tk.Label(okno, text=tekst, bg="#263238", fg="#ffffff",
                 font=("Segoe UI", 8), padx=6, pady=3).pack()
        stan["okno"] = okno

    def ukryj(_zdarzenie=None):
        if stan["okno"] is not None:
            stan["okno"].destroy()
            stan["okno"] = None

    widget.bind("<Enter>", pokaz, add="+")
    widget.bind("<Leave>", ukryj, add="+")


class Aplikacja(tk.Tk):

    def __init__(self, skala: float = 1.0):
        super().__init__()
        self.skala = skala
        self.title("{0} {1}".format(NAZWA, WERSJA))
        # Tk liczy rozmiary w pikselach, więc przy powiększonym ekranie
        # okno trzeba powiększyć w tej samej proporcji, inaczej wyjdzie
        # malutkie i etykiety zaczną się nachodzić.
        self.tk.call("tk", "scaling", skala * 1.3333)
        self.geometry("{0}x{1}".format(int(940 * skala), int(720 * skala)))
        self.minsize(int(820 * skala), int(620 * skala))
        self.configure(bg=TLO)

        self.kolejka = queue.Queue()
        self.watek = None
        self._ustaw_style()
        self._zbuduj()
        self.after(100, self._oproznij_kolejke)

    # ── wygląd ───────────────────────────────────────────────────────

    def _ustaw_style(self):
        # Rozmiary czcionek podajemy w punktach ze znakiem minus, czyli
        # w pikselach, żeby Tk nie skalował ich drugi raz.
        import tkinter.font as tkfont
        for nazwa, rozmiar in (("TkDefaultFont", 10), ("TkTextFont", 10),
                               ("TkMenuFont", 10), ("TkHeadingFont", 10)):
            try:
                tkfont.nametofont(nazwa).configure(family="Segoe UI",
                                                   size=rozmiar)
            except Exception:
                pass
        styl = ttk.Style(self)
        try:
            styl.theme_use("clam")
        except tk.TclError:
            pass
        styl.configure("TFrame", background=TLO)
        styl.configure("TLabel", background=TLO, foreground="#1a1a1a")
        styl.configure("Podpowiedz.TLabel", foreground=SZARY,
                       font=("Segoe UI", 8))
        styl.configure("Naglowek.TLabel", font=("Segoe UI", 10, "bold"),
                       foreground="#37474f")
        styl.configure("TLabelframe", background=TLO)
        styl.configure("TLabelframe.Label", background=TLO,
                       foreground="#37474f", font=("Segoe UI", 9, "bold"))
        styl.configure("TNotebook", background=TLO)
        styl.configure("Akcja.TButton", font=("Segoe UI", 10, "bold"),
                       foreground="#ffffff", background=BARWA,
                       borderwidth=0, padding=8)
        styl.map("Akcja.TButton",
                 background=[("active", BARWA_CIEMNA),
                             ("disabled", "#b0bec5")])

    def _zbuduj(self):
        # pasek tytułowy
        pasek = tk.Frame(self, bg=BARWA, height=56)
        pasek.pack(fill="x")
        tk.Label(pasek, text=NAZWA, bg=BARWA, fg="#ffffff",
                 font=("Segoe UI", 15, "bold")).pack(
                     side="left", padx=14, pady=(8, 0), anchor="w")
        tk.Label(pasek, text="Pokrycie terenu ze zdjęć z drona",
                 bg=BARWA, fg="#eafaff",
                 font=("Segoe UI", 9)).place(x=16, y=32)
        tk.Button(pasek, text="Instrukcja", bg="#ffffff", fg=BARWA_CIEMNA,
                  relief="flat", font=("Segoe UI", 9, "bold"),
                  command=self._instrukcja).pack(side="right", padx=14)

        zakladki = ttk.Notebook(self)
        zakladki.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        zakladki.add(self._zakladka_nauki(zakladki), text="  1. Nauka  ")
        zakladki.add(self._zakladka_klasyfikacji(zakladki),
                     text="  2. Klasyfikacja wsadowa  ")

        # pasek postępu i dziennik
        dolny = ttk.Frame(self)
        dolny.pack(fill="both", padx=10, pady=(0, 8))
        self.postep = ttk.Progressbar(dolny, mode="determinate")
        self.postep.pack(fill="x", pady=(0, 4))

        ramka = ttk.Frame(dolny)
        ramka.pack(fill="both", expand=True)
        self.dziennik = tk.Text(ramka, height=13, wrap="word",
                                font=("Consolas", 9), bg="#fbfdfe",
                                relief="solid", borderwidth=1)
        suwak = ttk.Scrollbar(ramka, command=self.dziennik.yview)
        self.dziennik.configure(yscrollcommand=suwak.set, state="disabled")
        self.dziennik.pack(side="left", fill="both", expand=True)
        suwak.pack(side="right", fill="y")

        # Maleńki podpis w prawym dolnym rogu. Kliknięcie otwiera
        # program pocztowy z adresem autora.
        stopka = tk.Label(self, text="©{0}".format(AUTOR),
                          bg=TLO, fg="#90a4ae", font=("Segoe UI", 7),
                          cursor="hand2")
        stopka.pack(anchor="e", padx=10, pady=(0, 4))
        stopka.bind("<Button-1>",
                    lambda _e: webbrowser.open("mailto:" + POCZTA))
        stopka.bind("<Enter>", lambda _e: stopka.configure(fg=BARWA_CIEMNA))
        stopka.bind("<Leave>", lambda _e: stopka.configure(fg="#90a4ae"))
        _dymek(stopka, "Napisz do autora: " + POCZTA)

    # ── zakładka nauki ───────────────────────────────────────────────

    def _zakladka_nauki(self, rodzic):
        ramka = ttk.Frame(rodzic, padding=12)

        ttk.Label(ramka, text="Naucz program rozpoznawać Twoje klasy",
                  style="Naglowek.TLabel").pack(anchor="w")
        ttk.Label(ramka, wraplength=760, style="Podpowiedz.TLabel",
                  text="Wskaż jedno reprezentatywne zdjęcie i plik "
                       "z przykładami (poligony z kolumną „klasa”, "
                       "narysowane w QGIS). Program podzieli zdjęcie na "
                       "obiekty, zmierzy je i nauczy się Twoich klas. "
                       "Powstanie plik modelu, który potem zastosujesz "
                       "do całego folderu.").pack(anchor="w", pady=(2, 10))

        self.p_zdjecie = self._wiersz_pliku(
            ramka, "Zdjęcie RGB:", "otworz",
            [("Zdjęcia", "*.tif *.tiff *.img *.jp2"), ("Wszystkie", "*.*")])
        self.p_probki = self._wiersz_pliku(
            ramka, "Plik z przykładami:", "otworz",
            [("Warstwy wektorowe", "*.gpkg *.shp *.geojson"),
             ("Wszystkie", "*.*")])
        self.p_pole = self._wiersz_tekstu(
            ramka, "Kolumna z nazwą klasy:", "klasa")
        self.p_nmpt = self._wiersz_pliku(
            ramka, "Model wysokości (opcjonalnie):", "otworz",
            [("Zdjęcia", "*.tif *.tiff"), ("Wszystkie", "*.*")])
        ttk.Label(ramka, style="Podpowiedz.TLabel", wraplength=760,
                  text="Model wysokości nie jest konieczny, ale bardzo "
                       "pomaga: dzięki niemu program odróżni dach od "
                       "asfaltu, a drzewo od trawnika.").pack(
                           anchor="w", pady=(0, 8))

        ustawienia = ttk.LabelFrame(ramka, text="Ustawienia podziału",
                                    padding=8)
        ustawienia.pack(fill="x", pady=(0, 8))
        self.p_rozdzielczosc = self._wiersz_liczby(
            ustawienia, "Rozdzielczość robocza (m):", "0.05",
            "Zostaw 0, żeby pracować w rozdzielczości pliku.")
        self.p_wielkosc = self._wiersz_liczby(
            ustawienia, "Wielkość obiektu (m²):", "10",
            "Obiekt musi być mniejszy niż najwęższa rzecz na mapie. "
            "Pola i dachy: 5-20. Pojedyncze drzewa: 2-5.")

        self.p_model = self._wiersz_pliku(
            ramka, "Zapisz model jako:", "zapisz",
            [("Model GeoAI", "*.geoai")], domyslna="model.geoai")

        przycisk = ttk.Button(ramka, text="NAUCZ MODEL",
                              style="Akcja.TButton",
                              command=self._uruchom_nauke)
        przycisk.pack(fill="x", pady=(10, 0))
        self.btn_nauka = przycisk
        return ramka

    # ── zakładka klasyfikacji ────────────────────────────────────────

    def _zakladka_klasyfikacji(self, rodzic):
        ramka = ttk.Frame(rodzic, padding=12)

        ttk.Label(ramka, text="Zastosuj model do wszystkich zdjęć",
                  style="Naglowek.TLabel").pack(anchor="w")
        ttk.Label(ramka, wraplength=760, style="Podpowiedz.TLabel",
                  text="Program przeleci po kolei każde zdjęcie we "
                       "wskazanym folderze, zapisze mapę jako GeoTIFF "
                       "z gotowym stylem dla QGIS, a na końcu zbiorczy "
                       "raport z powierzchnią każdej klasy.").pack(
                           anchor="w", pady=(2, 10))

        self.k_model = self._wiersz_pliku(
            ramka, "Plik modelu:", "otworz",
            [("Model GeoAI", "*.geoai"), ("Wszystkie", "*.*")])
        self.k_folder = self._wiersz_pliku(
            ramka, "Folder ze zdjęciami:", "folder")
        self.k_nmpt = self._wiersz_pliku(
            ramka, "Folder z modelami wysokości:", "folder")
        self.k_wyjscie = self._wiersz_pliku(
            ramka, "Gdzie zapisać mapy:", "folder")

        opcje = ttk.LabelFrame(ramka, text="Opcje", padding=8)
        opcje.pack(fill="x", pady=(8, 8))
        self.k_mmu = self._wiersz_liczby(
            opcje, "Najmniejszy zachowany płat (m²):", "0",
            "Usuwa pojedyncze drobiny z mapy. Zero wyłącza "
            "czyszczenie.")
        self.k_podfoldery = tk.BooleanVar(value=False)
        ttk.Label(opcje, text="").pack(pady=(2, 0))
        ttk.Checkbutton(opcje, text="Szukaj zdjęć także w podfolderach",
                        variable=self.k_podfoldery).pack(anchor="w")
        self.k_nadpisuj = tk.BooleanVar(value=False)
        ttk.Checkbutton(opcje, variable=self.k_nadpisuj,
                        text="Policz ponownie także te, które już mają "
                             "wynik").pack(anchor="w")

        przycisk = ttk.Button(ramka, text="KLASYFIKUJ CAŁY FOLDER",
                              style="Akcja.TButton",
                              command=self._uruchom_klasyfikacje)
        przycisk.pack(fill="x", pady=(10, 0))
        self.btn_klasyfikacja = przycisk
        return ramka

    # ── drobne elementy formularza ───────────────────────────────────

    # Szerokość kolumny z etykietami, w znakach. Musi pomieścić
    # najdłuższą etykietę w całym oknie, czyli "Policz ponownie także
    # te, które już mają wynik", inaczej napisy zachodzą na pola.
    SZEROKOSC_ETYKIETY = 34

    def _wiersz_pliku(self, rodzic, etykieta, rodzaj, filtry=None,
                      domyslna=""):
        wiersz = ttk.Frame(rodzic)
        wiersz.pack(fill="x", pady=3)
        ttk.Label(wiersz, text=etykieta, width=self.SZEROKOSC_ETYKIETY,
                  anchor="w").pack(side="left")
        zmienna = tk.StringVar(value=domyslna)
        pole = ttk.Entry(wiersz, textvariable=zmienna)
        pole.pack(side="left", fill="x", expand=True, padx=(0, 6))

        def wskaz():
            if rodzaj == "folder":
                wybrane = filedialog.askdirectory(title=etykieta)
            elif rodzaj == "zapisz":
                wybrane = filedialog.asksaveasfilename(
                    title=etykieta, defaultextension=".geoai",
                    filetypes=filtry or [("Wszystkie", "*.*")])
            else:
                wybrane = filedialog.askopenfilename(
                    title=etykieta, filetypes=filtry or [("Wszystkie", "*.*")])
            if wybrane:
                zmienna.set(wybrane)

        ttk.Button(wiersz, text="Wskaż...", width=10,
                   command=wskaz).pack(side="left")
        return zmienna

    def _wiersz_tekstu(self, rodzic, etykieta, domyslna=""):
        wiersz = ttk.Frame(rodzic)
        wiersz.pack(fill="x", pady=3)
        ttk.Label(wiersz, text=etykieta, width=self.SZEROKOSC_ETYKIETY,
                  anchor="w").pack(side="left")
        zmienna = tk.StringVar(value=domyslna)
        ttk.Entry(wiersz, textvariable=zmienna,
                  width=24).pack(side="left")
        return zmienna

    def _wiersz_liczby(self, rodzic, etykieta, domyslna, podpowiedz=""):
        blok = ttk.Frame(rodzic)
        blok.pack(fill="x", pady=(3, 0))
        wiersz = ttk.Frame(blok)
        wiersz.pack(fill="x")
        ttk.Label(wiersz, text=etykieta, width=self.SZEROKOSC_ETYKIETY,
                  anchor="w").pack(side="left")
        zmienna = tk.StringVar(value=domyslna)
        ttk.Entry(wiersz, textvariable=zmienna, width=12).pack(side="left")
        if podpowiedz:
            # Podpowiedź idzie pod pole, a nie obok niego. Obok nakładała
            # się na sąsiednie elementy przy węższym oknie.
            ttk.Label(blok, text=podpowiedz, style="Podpowiedz.TLabel",
                      wraplength=640, justify="left").pack(
                          anchor="w", padx=(4, 0), pady=(1, 4))
        return zmienna

    # ── obsługa dziennika i wątku roboczego ──────────────────────────

    def _pisz(self, tekst):
        self.dziennik.configure(state="normal")
        self.dziennik.insert("end", tekst + "\n")
        self.dziennik.see("end")
        self.dziennik.configure(state="disabled")

    def _oproznij_kolejke(self):
        try:
            while True:
                self._pisz(self.kolejka.get_nowait())
        except queue.Empty:
            pass
        self.after(120, self._oproznij_kolejke)

    def _zajety(self) -> bool:
        if self.watek is not None and self.watek.is_alive():
            messagebox.showinfo(
                NAZWA, "Chwileczkę — poprzednie obliczenie jeszcze trwa.")
            return True
        return False

    def _start(self, funkcja):
        self.btn_nauka.state(["disabled"])
        self.btn_klasyfikacja.state(["disabled"])
        self.postep.configure(mode="indeterminate")
        self.postep.start(12)

        def opakowanie():
            try:
                funkcja()
            except Exception as blad:
                self.kolejka.put("")
                self.kolejka.put("BŁĄD: {0}".format(blad))
                self.kolejka.put("")
                self.kolejka.put("Jeśli nie wiesz, co z tym zrobić, "
                                 "napisz na {0} i dołącz treść "
                                 "powyższego komunikatu.".format(POCZTA))
                if os.environ.get("GEOAI_SZCZEGOLY"):
                    self.kolejka.put(traceback.format_exc())
            finally:
                self.after(0, self._koniec)

        self.watek = threading.Thread(target=opakowanie, daemon=True)
        self.watek.start()

    def _koniec(self):
        self.postep.stop()
        self.postep.configure(mode="determinate", value=0)
        self.btn_nauka.state(["!disabled"])
        self.btn_klasyfikacja.state(["!disabled"])

    # ── właściwe akcje ───────────────────────────────────────────────

    def _uruchom_nauke(self):
        if self._zajety():
            return
        zdjecie = self.p_zdjecie.get().strip()
        probki = self.p_probki.get().strip()
        model = self.p_model.get().strip()

        braki = []
        if not zdjecie:
            braki.append("zdjęcie RGB")
        if not probki:
            braki.append("plik z przykładami")
        if not model:
            braki.append("miejsce zapisu modelu")
        if braki:
            messagebox.showwarning(
                NAZWA, "Brakuje: {0}.\n\nWskaż te pliki i spróbuj "
                       "ponownie.".format(", ".join(braki)))
            return

        argumenty = [
            "ucz", "--zdjecie", zdjecie, "--probki", probki,
            "--pole", self.p_pole.get().strip() or "klasa",
            "--model", model,
            "--rozdzielczosc", self.p_rozdzielczosc.get().strip() or "0",
            "--wielkosc-obiektu", self.p_wielkosc.get().strip() or "10",
            "--separowalnosc",
        ]
        nmpt = self.p_nmpt.get().strip()
        if nmpt:
            argumenty += ["--nmpt", nmpt]

        self._wyczysc_dziennik()
        self._start(lambda: self._wywolaj(argumenty,
                                          "Nauka zakończona."))

    def _uruchom_klasyfikacje(self):
        if self._zajety():
            return
        model = self.k_model.get().strip()
        folder = self.k_folder.get().strip()
        wyjscie = self.k_wyjscie.get().strip()

        braki = []
        if not model:
            braki.append("plik modelu")
        if not folder:
            braki.append("folder ze zdjęciami")
        if not wyjscie:
            braki.append("folder na wyniki")
        if braki:
            messagebox.showwarning(
                NAZWA, "Brakuje: {0}.".format(", ".join(braki)))
            return

        argumenty = ["klasyfikuj", "--model", model, "--folder", folder,
                     "--wyjscie", wyjscie]
        nmpt = self.k_nmpt.get().strip()
        if nmpt:
            argumenty += ["--nmpt-folder", nmpt]
        try:
            mmu = float(self.k_mmu.get().strip() or "0")
        except ValueError:
            mmu = 0.0
        if mmu > 0:
            argumenty += ["--mmu", str(mmu)]
        if self.k_podfoldery.get():
            argumenty.append("--rekurencyjnie")
        if self.k_nadpisuj.get():
            argumenty.append("--nadpisuj")

        self._wyczysc_dziennik()
        self._start(lambda: self._wywolaj(
            argumenty, "Klasyfikacja zakończona. Mapy i raport.csv "
                       "czekają w folderze wyników."))

    def _wyczysc_dziennik(self):
        self.dziennik.configure(state="normal")
        self.dziennik.delete("1.0", "end")
        self.dziennik.configure(state="disabled")

    def _wywolaj(self, argumenty, komunikat_konca):
        """Uruchamia polecenie z wersji konsolowej, kierując wypisywanie
        do okna."""
        from geoai_cli import main as program

        mowi = Przekierowanie(self.kolejka)
        parser = program.zbuduj_parser()
        args = parser.parse_args(argumenty)

        polecenia = {
            "ucz": program.polecenie_ucz,
            "klasyfikuj": program.polecenie_klasyfikuj,
        }
        kod = polecenia[args.polecenie](args, mowi)
        self.kolejka.put("")
        if kod == 0:
            self.kolejka.put(komunikat_konca)
        else:
            self.kolejka.put("Zakończono z błędami — sprawdź komunikaty "
                             "powyżej.")

    # ── instrukcja ───────────────────────────────────────────────────

    def _instrukcja(self):
        okno = tk.Toplevel(self)
        okno.title("Instrukcja — " + NAZWA)
        okno.geometry("700x600")
        okno.configure(bg=TLO)

        ramka = ttk.Frame(okno, padding=10)
        ramka.pack(fill="both", expand=True)
        tekst = tk.Text(ramka, wrap="word", font=("Segoe UI", 10),
                        bg="#ffffff", relief="flat", padx=10, pady=8)
        suwak = ttk.Scrollbar(ramka, command=tekst.yview)
        tekst.configure(yscrollcommand=suwak.set)
        tekst.pack(side="left", fill="both", expand=True)
        suwak.pack(side="right", fill="y")

        tekst.tag_configure("tytul", font=("Segoe UI", 13, "bold"),
                            spacing1=10, spacing3=6)
        tekst.tag_configure("podtytul", font=("Segoe UI", 10, "bold"),
                            spacing1=10, spacing3=4)
        for znacznik, linia in INSTRUKCJA:
            tekst.insert("end", linia + "\n", znacznik)
        tekst.configure(state="disabled")

        tk.Label(okno, text="© {0}  ·  {1}".format(AUTOR, POCZTA),
                 bg=TLO, fg=SZARY, font=("Segoe UI", 8)).pack(
                     anchor="e", padx=14)
        ttk.Button(okno, text="Zamknij",
                   command=okno.destroy).pack(pady=(0, 10))


INSTRUKCJA = [
    ("tytul", "Jak to działa"),
    ("", "Program robi mapę pokrycia terenu ze zdjęcia z drona albo "
         "zdjęcia lotniczego. Nie patrzy na pojedyncze piksele, tylko "
         "najpierw tnie zdjęcie na obiekty — kawałki pola, dachu, "
         "korony drzewa — a potem uczy się od Ciebie, co jest czym."),
    ("podtytul", "Co jest potrzebne"),
    ("", "• Zdjęcie RGB: ortomozaika z drona, zdjęcie lotnicze albo "
         "scena satelitarna. Wystarczą trzy kanały."),
    ("", "• Plik z przykładami: poligony z kolumną „klasa”, narysowane "
         "w QGIS na terenach, które znasz."),
    ("", "• Model wysokości (NMPT) — nieobowiązkowy, ale bardzo "
         "pomaga. Bez niego program mierzy 19 cech, z nim 24."),
    ("podtytul", "Krok 1 — nauka"),
    ("", "Wskaż jedno reprezentatywne zdjęcie i plik z przykładami. "
         "Najważniejsze ustawienie to wielkość obiektu: obiekt musi "
         "być mniejszy niż najwęższa rzecz, którą chcesz pokazać na "
         "mapie. Dla pól i dachów zwykle 5-20 m², dla pojedynczych "
         "drzew 2-5 m²."),
    ("", "Trzy rzeczy decydują o jakości wyniku:"),
    ("", "   1. Rozrzuć przykłady po całym zdjęciu, nie w jednym rogu."),
    ("", "   2. Pokaż każdą odmianę klasy — i bujną trawę, i tę "
         "przyschniętą."),
    ("", "   3. Rysuj tylko tam, gdzie jesteś pewien. Poligon na "
         "granicy dwóch klas i tak zostanie pominięty."),
    ("", "Program przy okazji sprawdzi, czy Twoje klasy w ogóle da się "
         "rozróżnić. Jeśli któraś para wypadnie SŁABO, dodaj "
         "przykładów albo połącz te klasy w jedną."),
    ("podtytul", "Krok 2 — klasyfikacja wsadowa"),
    ("", "Wskaż folder ze zdjęciami i gotowy model. Program przeleci "
         "po kolei każde zdjęcie, zapisze mapę jako GeoTIFF z plikiem "
         "stylu .qml obok (więc w QGIS otworzy się od razu "
         "w kolorach), a na końcu zbiorczy raport.csv z powierzchnią "
         "każdej klasy na każdym zdjęciu."),
    ("", "Przerwany przebieg można wznowić: bez zaznaczonej opcji "
         "„Policz ponownie” program pomija zdjęcia, które już mają "
         "wynik."),
    ("podtytul", "Modele wysokości"),
    ("", "Program dopasowuje je po nazwie: dla zdjęcia nalot_01.tif "
         "szuka pliku nalot_01_nmpt.tif we wskazanym folderze. Jeśli "
         "model uczył się z wysokością, a dla któregoś zdjęcia jej "
         "zabraknie, program zgłosi to wyraźnie, zamiast po cichu "
         "liczyć gorzej."),
    ("podtytul", "Ocena dokładności"),
    ("", "Losowanie punktów kontrolnych, macierz błędów i powierzchnie "
         "z przedziałami ufności są we wtyczce QGIS — tam można "
         "opisywać punkty klikając po mapie, czego w tym oknie zrobić "
         "się nie da. Wczytaj gotową mapę do QGIS i przejdź do kroku 4 "
         "wtyczki."),
    ("podtytul", "Kontakt"),
    ("", "Autor: Grzegorz Górniak, gorniakgrzegorz@gmail.com"),
    ("", "Masz pytanie, znalazłeś błąd albo chcesz zgłosić pomysł? Napisz "
         "na ten adres albo załóż zgłoszenie na stronie projektu: "
         "https://github.com/gorniakgrzegorz/geoai_klasyfikator/issues"),
    ("", "Przy zgłoszeniu błędu dołącz treść komunikatu z dziennika "
         "u dołu okna, rozmiar zdjęcia i to, co robiłeś przed błędem."),
    ("podtytul", "Skąd ta metoda"),
    ("", "Segmentacja SLIC (Achanta i in., 2012), faktura GLCM "
         "(Haralick i in., 1973), zieloność ExG (Woebbecke i in., "
         "1995), Random Forest (Breiman, 2001) oraz ocena dokładności wg "
         "Olofssona i in. (2014) i Stehmana (2014)."),
]


def main():
    # Świadomość gęstości pikseli trzeba włączyć, zanim powstanie okno.
    skala = _ostry_tekst()
    try:
        aplikacja = Aplikacja(skala)
    except tk.TclError as blad:
        print("Nie udało się otworzyć okna: {0}".format(blad))
        return 1
    aplikacja.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
