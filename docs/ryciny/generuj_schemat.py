import subprocess, html
KOL = {'zr': ('#fdf6e3', '#b7791f'), 'pb': ('#fdf0e3', '#dd6b20'), 'met': ('#eef7ea', '#38a169'), 'wyn': ('#e8f1fb', '#2b6cb0'),
       'dys': ('#f1edfa', '#6b46c1'), 'brak': ('#fde8e8', '#c53030'), 'nowe': ('#e6fffa', '#2c7a7b'), 'tez': ('#2d3748', '#2d3748')}
LEG = [('zr', 'Wprowadzenie: twierdzenie i źródła'), ('pb', 'Pytanie badawcze'), ('met', 'Dane i metody'), ('nowe', 'Nowa analiza'),
       ('wyn', 'Wynik'), ('dys', 'Dyskusja i wnioski'), ('brak', 'Brak lub ryzyko: blokuje dalszy tekst')]
DX, DY = 3.45, 1.95
W, H = 3.05, 1.42
TYTUL = 'Logika artykułu: GeoAI Klasyfikator, klasyfikacja obiektowa zdjęć z drona'
WIERSZE = ['1. Wprowadzenie', 'Luka i cel', 'Pytania', '3. Metody', '3. Metody (cd.)', '4. Wyniki', '5. Dyskusja', '6. Wnioski']
TORY = [(0, 'Wspólna podstawa'), (1.35, 'Tor PB1: cechy'), (2.7, 'Tor PB2: wysokość'), (4.05, 'Tor PB3: korekty'), (5.4, 'Tor PB4: powierzchnia')]
N = {
 # 1. Wprowadzenie
 'w1': (0, 0, 'zr', '1.1 GEOBIA zamiast pikseli',
        'Jednostką analizy jest segment odpowiadający fragmentowi terenu, nie piksel.',
        'Blaschke 2010'),
 'w2': (1.7, 0, 'zr', '1.2 Nalot RGB bez podczerwieni',
        'Tanie kamery konsumenckie nie dają NIR, więc NDVI jest niedostępny.',
        'Woebbecke i in. 1995; Gitelson i in. 2002'),
 'w3': (3.4, 0, 'zr', '1.3 Powierzchnia z mapy jest obciążona',
        'Zliczenie pikseli klasy nie jest estymatorem powierzchni tej klasy.',
        'Olofsson i in. 2014; Stehman 2014'),
 'w4': (5.1, 0, 'zr', '1.4 Narzędzia GEOBIA są zamknięte lub trudne',
        'Pełny tor GEOBIA z oceną dokładności rzadko bywa dostępny w jednym otwartym narzędziu.',
        '[DO UZUPEŁNIENIA: źródło przeglądowe]'),
 # Luka i cel
 'luka': (1.35, 1, 'brak', 'Luka badawcza',
        'Brak otwartego toru łączącego segmentację, cechy, Random Forest i estymację powierzchni z niepewnością w jednym środowisku GIS.',
        'wymaga zapisu przeszukania literatury'),
 'cel': (4.05, 1, 'tez', 'Cel i teza',
        'Teza: tor obiektowy na samym RGB, z opcjonalnym NMPT, daje mapę pokrycia wraz z powierzchnią i jej niepewnością, odtwarzalnie i bez zewnętrznego modelu.',
        'DECYZJA AUTORA: teza do zatwierdzenia'),
 # Pytania
 'pb1': (1.35, 2, 'pb', 'PB1 Cechy',
        'Które z 19 cech RGB rozdzielają klasy pokrycia i jak mierzyć tę rozdzielność?', ''),
 'pb2': (2.7, 2, 'pb', 'PB2 Wysokość',
        'Jaki przyrost rozdzielności wnoszą 5 cech z NMPT, w tym wysokość nad gruntem?', ''),
 'pb3': (4.05, 2, 'pb', 'PB3 Korekty',
        'Czy korekta zieleni i sito poprawiają mapę i jak naruszają jej obiektowy charakter?', ''),
 'pb4': (5.4, 2, 'pb', 'PB4 Powierzchnia',
        'Jak szeroki jest przedział ufności powierzchni klas przy próbie warstwowej?', ''),
 # Metody, wspólna podstawa
 'm31': (0, 3, 'met', '3.1 Dane',
        'Ortomozaika RGB z drona, opcjonalnie NMPT z tego samego nalotu, ten sam układ i piksel.',
        '[DO UZUPEŁNIENIA: obszar, data, rozdzielczość, licencja]'),
 'm32': (0, 4, 'met', '3.2 Segmentacja SLIC',
        'Przestrzeń CIELAB, D65, zwartość 0,15, sigma 2,5, 10 iteracji, liczba segmentów z wielkości obiektu.',
        'Achanta i in. 2012'),
 # Tory metod
 'm33': (1.35, 3, 'met', '3.3 Cechy barwy i faktury',
        '7 wielkości barwy, 3 wskaźniki na współrzędnych chromatycznych (ExG, VARI, NGRDI), 4 cechy GLCM (15 poziomów, odległość 1, cztery kierunki), 4 cechy kształtu, 1 cecha kontekstu.',
        'Haralick i in. 1973; obwód estymatorem Croftona'),
 'm34': (1.35, 4, 'met', '3.4 Random Forest',
        '100 drzew, Gini, pierwiastek z liczby cech, bootstrap, ziarno 42, głosowanie miękkie.',
        'Breiman 2001'),
 'm35': (2.7, 3, 'met', '3.5 Cechy z NMPT',
        'Średnia i odchylenie NMPT, nachylenie, wysokość względem sąsiedztwa oraz wysokość nad gruntem.', ''),
 'm36': (2.7, 4, 'met', '3.6 Grunt z samego NMPT',
        'Minimum w blokach 1 m, otwarcie morfologiczne 40 m z ograniczeniem do połowy krótszego boku, wygładzenie średnią ruchomą.',
        'ograniczenie: duże dachy są zaniżane'),
 'm37': (4.05, 3, 'met', '3.7 Korekta zieleni',
        'ExG wygładzony w oknie 3 na 3, próg Youdena z 256 kandydatów, segment przypisany w całości, gdy udział pikseli przekroczy 0,25.', ''),
 'm38': (4.05, 4, 'met', '3.8 Sito',
        'Usuwanie łat mniejszych od progu w sąsiedztwie czterospójnym, bez wygładzania granic.', ''),
 'm39': (5.4, 3, 'met', '3.9 Próba warstwowa',
        'Warstwy to klasy mapy, punkty losowane w obrębie warstwy, warstwa zapisana razem z punktem.',
        'Stehman 2014'),
 'm40': (5.4, 4, 'met', '3.10 Estymatory Olofssona',
        'Udziały p_ij ważone powierzchnią warstw, wariancje z równań 5 do 7, przedział 95 procent z z = 1,96.',
        'Olofsson i in. 2014, równania 5 do 7'),
 # Warunek blokujący
 'blok': (0, 5, 'brak', 'Warunek: zbiór referencyjny',
        'Bez niezależnego zbioru referencyjnego z realnego nalotu żaden wynik liczbowy nie może wejść do artykułu.',
        'STAN: brak, analizy na danych rzeczywistych nie wykonano'),
 # Wyniki
 'r1': (1.35, 5, 'wyn', '4.1 Rozdzielność klas (PB1)',
        'Macierz JM par klas z walidacji krzyżowej, progi 1,9 i 1,7; ranking ważności cech.',
        '[DO UZUPEŁNIENIA: liczby po biegu na danych]'),
 'r2': (2.7, 5, 'wyn', '4.2 Wkład wysokości (PB2)',
        'Dokładność i JM dla 19 cech kontra 24 cechy, ta sama próba i to samo ziarno.',
        '[DO UZUPEŁNIENIA: liczby po biegu na danych]'),
 'r3': (4.05, 5, 'wyn', '4.3 Skutek korekt (PB3)',
        'Dokładność przed i po korekcie zieleni oraz po sicie, liczba i powierzchnia zmienionych segmentów.',
        '[DO UZUPEŁNIENIA: liczby po biegu na danych]'),
 'r4': (5.4, 5, 'wyn', '4.4 Powierzchnia z niepewnością (PB4)',
        'Powierzchnie klas skorygowane o błąd klasyfikacji z przedziałami 95 procent, obok powierzchni zliczonej z mapy.',
        'kod sprawdzony na tab. 8 z Olofsson i in. 2014: 0,9449'),
 # Dyskusja
 'd1': (1.35, 6, 'dys', '5.1 Czego RGB nie rozdziela',
        'Klasy różniące się układem przestrzennym, a nie materiałem, pozostają nierozdzielone, bo brak cech wyglądu z sieci transformerowej.',
        'ograniczenie wpisane w metodę'),
 'd2': (2.7, 6, 'dys', '5.2 Granice estymacji gruntu',
        'Otwarcie 40 m zaniża wysokość budynków szerszych od okna; wariant z osobnym NMT usuwa to ograniczenie.', ''),
 'd3': (4.05, 6, 'dys', '5.3 Cena korekt pikselowych',
        'Korekta zieleni i sito są operacjami pikselowymi w torze obiektowym, co trzeba podać wprost przy opisie mapy.', ''),
 'd4': (5.4, 6, 'dys', '5.4 Powierzchnia kontra piksele',
        'Różnica między powierzchnią z mapy a estymatorem ważonym pokazuje, dlaczego sama mapa nie wystarcza.',
        'Olofsson i in. 2014'),
 # Wnioski
 'wn': (1.7, 7, 'dys', '6. Wnioski',
        'Odpowiedzi na PB1 do PB4, bez nowych liczb, z zasięgiem ograniczonym do badanego obszaru i rozdzielczości.', ''),
 'st': (4.05, 7, 'tez', 'Streszczenie i Highlights',
        'Liczby wyłącznie z rozdziału 4; dopóki rozdział 4 jest pusty, streszczenie nie zawiera wartości.', ''),
 'kod': (5.4, 7, 'met', 'Dostępność kodu i danych',
        'Repozytorium geoai_klasyfikator z tagiem wersji, DOI z Zenodo, spis wersji bibliotek.',
        '[DO UZUPEŁNIENIA: DOI Zenodo]'),
}
E = [('w1','luka'),('w2','luka'),('w3','cel'),('w4','cel'),('luka','cel'),
     ('cel','pb1'),('cel','pb2'),('cel','pb3'),('cel','pb4'),
     ('m31','m32'),('m32','blok'),
     ('pb1','m33'),('m33','m34'),('m34','r1'),
     ('pb2','m35'),('m35','m36'),('m36','r2'),
     ('pb3','m37'),('m37','m38'),('m38','r3'),
     ('pb4','m39'),('m39','m40'),('m40','r4'),
     ('blok','r1','war'),('blok','r2','war'),('blok','r3','war'),('blok','r4','war'),
     ('r1','d1'),('r2','d2'),('r3','d3'),('r4','d4'),
     ('d1','wn'),('d2','wn'),('d3','st'),('d4','st'),('wn','st')]

def zawin(t, n=38):
    w, lin, akt = t.split(' '), [], ''
    for s in w:
        if len(akt) + len(s) + 1 > n and akt:
            lin.append(akt); akt = s
        else:
            akt = (akt + ' ' + s).strip()
    lin.append(akt)
    return '<BR/>'.join(html.escape(x) for x in lin)

def etyk(t, o, d, bialy=False):
    k = 'white' if bialy else 'black'; kd = '#cbd5e0' if bialy else '#4a5568'
    r = f'<TR><TD><B><FONT POINT-SIZE="12" COLOR="{k}">{zawin(t, 34)}</FONT></B></TD></TR><TR><TD><FONT POINT-SIZE="9" COLOR="{k}">{zawin(o, 44)}</FONT></TD></TR>'
    if d:
        r += f'<TR><TD><FONT POINT-SIZE="8" COLOR="{kd}"><I>{zawin(d, 50)}</I></FONT></TD></TR>'
    return f'<<TABLE BORDER="0" CELLSPACING="0" CELLPADDING="1">{r}</TABLE>>'

def poz(k, w):
    return k * DX * 72, -w * DY * 72

L = ['digraph G {', 'graph [splines=ortho, outputorder=edgesfirst, bgcolor="white", pad=0.4, fontname="Liberation Sans"];',
     f'node [shape=box, style="rounded,filled", fontname="Liberation Sans", margin="0.10,0.06", width={W}, height={H}, fixedsize=true, penwidth=1.4];',
     'edge [color="#2d3748", penwidth=1.6, arrowsize=0.8];']
for n, (k, w, typ, t, o, d) in N.items():
    f, c = KOL[typ]; x, y = poz(k, w)
    L.append(f'{n} [pos="{x:.2f},{y:.2f}!", label={etyk(t, o, d, typ == "tez")}, fillcolor="{f}", color="{c}"{", penwidth=2.8" if typ == "brak" else ""}];')
for i, t in enumerate(WIERSZE):
    x, y = poz(-1.05, i)
    L.append(f'lw{i} [pos="{x:.2f},{y:.2f}!", shape=plaintext, style="", width=1.9, height=0.6, label=<<B><FONT POINT-SIZE="13" COLOR="#4a5568">{html.escape(t)}</FONT></B>>];')
for k, t in TORY:
    x, y = poz(k, 2)
    L.append(f'h{str(k).replace(".", "_")} [pos="{x:.2f},{y + 0.95 * 72:.2f}!", shape=plaintext, style="", width=2.4, height=0.35, label=<<B><FONT POINT-SIZE="12" COLOR="#dd6b20">{html.escape(t)}</FONT></B>>];')
import os
BEZ_TYT = os.environ.get('BEZ_TYT') == '1'
x, y = poz(2.7, -1.35)
if not BEZ_TYT: L.append(f'tyt [pos="{x:.2f},{y:.2f}!", shape=plaintext, style="", width=16, height=1.0, label=<<FONT POINT-SIZE="22"><B>{html.escape(TYTUL)}</B></FONT><BR/>'
         '<FONT POINT-SIZE="12">Wiersze: kolejne etapy wywodu. Kolumny: tory pytań badawczych (pytanie, metoda, wynik, dyskusja). Czerwone: warunek, bez którego liczby nie trafią do streszczenia.</FONT>>];')
for i, (typ, t) in enumerate(LEG):
    f, c = KOL[typ]; x, y = poz(-0.45 + i * 0.95, -0.68)
    L.append(f'leg{i} [pos="{x:.2f},{y:.2f}!", width=3.0, height=0.38, label=<<FONT POINT-SIZE="11">{html.escape(t)}</FONT>>, fillcolor="{f}", color="{c}"];')
for e in E:
    a, b = e[:2]; war = len(e) > 2
    styl = 'color="#c53030", style=dashed, penwidth=2.4' if war else ''
    L.append('%s -> %s [%s];' % (a, b, styl))
L.append('}')
open('logika_artykulu_bez_tytulu.dot' if BEZ_TYT else 'logika_artykulu.dot', 'w', encoding='utf-8').write('\n'.join(L))
for fmt, out in (('svg:cairo', 'logika_artykulu.svg'), ('svg', 'logika_artykulu_tekst.svg'), ('png:cairo', 'logika_artykulu.png'), ('pdf', 'logika_artykulu.pdf')):
    out = out.replace('logika_artykulu', 'logika_artykulu_bez_tytulu') if BEZ_TYT else out
    subprocess.run(['neato', '-n2', f'-T{fmt}'] + (['-Gdpi=220'] if fmt.startswith('png') else []) + [('logika_artykulu_bez_tytulu.dot' if BEZ_TYT else 'logika_artykulu.dot'), '-o', out], check=True)
tsvg = 'logika_artykulu_bez_tytulu_tekst.svg' if BEZ_TYT else 'logika_artykulu_tekst.svg'
t = open(tsvg, encoding='utf-8').read().replace('font-family="Liberation Sans"', 'font-family="Arial, Liberation Sans, Helvetica, sans-serif"')
open(tsvg, 'w', encoding='utf-8').write(t)
print("ok")
