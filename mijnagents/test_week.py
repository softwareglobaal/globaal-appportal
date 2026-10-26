"""Grendel op de weekpagina /week (driehoeksoverleg 27-10-2026).

Mehdi wil per ISO-week zien wat hij effectief deed, naast wat gepland stond. Een runner zet per week een klaarzet-item
weekoverzicht:<JJJJ-Www> met json klaar; de pagina toont het alleen. Deze test legt vast:

- W01: zonder beheer 403, ook voor een week die niet bestaat;
- W02: /week stuurt door naar de huidige week /week/JJJJ-Www;
- W03: een week die niet bestaat (2026-W54, 2026-W00, abc, 2025-W53) geeft 404 voor beheer;
- W04: een week zonder overzicht zegt dat ze nog niet samengevat is (200), met vorige en volgende week;
- W05: een opgeslagen overzicht toont totalen, een dag die niet vastgesteld is, een vraagteken voor null, de stand van
  een kanaal dat niet aangesloten is, de uren per firma met een komma, en de link naar de dag;
- W06: vorige en volgende over de jaargrens: 2026-W53 gaat naar 2027-W01 en terug;
- W07: een inhoud die geen geldige json is of een vreemde vorm heeft, laat de pagina niet vallen;
- W08: geen gedachtestreepje; het bord, de dagenpagina en de dagpagina linken naar de week.

Draait in de Docker-build: faalt dit, dan blijft de vorige container staan.
"""
import os
import re
import sys
import tempfile

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "start.db")
os.environ["AGENTS_TOKEN"] = "proef"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402

K = {"X-Agents-Token": "proef"}
BEHEER = {"X-authentik-groups": "admin", "X-authentik-username": "proef"}
ANDER = {"X-authentik-groups": "agents", "X-authentik-username": "iemand"}
C = A.app.test_client()
fout = 0

# De locatietegel bestaat niet in de proef; /dagen en /dag vragen er anders tien seconden naar.
A._locatie = lambda pad, standaard=None: standaard


def check(naam, voorwaarde, extra=""):
    global fout
    print(("  ok   " if voorwaarde else "  FOUT ") + naam, "" if voorwaarde else extra)
    fout += 0 if voorwaarde else 1


def verse_db(naam):
    """Een eigen, nieuwe databank per toets."""
    A.DB_PAD = os.path.join(MAP, naam + ".db")
    A.init_db()
    return A.DB_PAD


def klaarzet(week, inhoud):
    return C.post("/api/klaarzet", headers=K, json={"items": [{
        "van": "weekoverzicht", "voor": "mehdi", "soort": "weekoverzicht", "sleutel": week,
        "titel": f"Weekoverzicht {week}", "inhoud": inhoud, "uniek": f"weekoverzicht:{week}"}]})


def pagina(pad, kop=BEHEER):
    r = C.get(pad, headers=kop)
    return r, r.get_data(as_text=True)


def rij(html, begin):
    """De celteksten van de tabelrij die met deze tekst begint (zonder tags)."""
    m = re.search(r"<tr[^>]*>\s*<td[^>]*>(?:<a[^>]*>)?" + re.escape(begin) + r".*?</tr>", html, re.S)
    if not m:
        return []
    return [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", m.group(0), re.S)]


def dag(datum, **extra):
    d = {"dag": datum, "vastgesteld": True, "dagversie": 1,
         "afspraken": {"bevestigd": 1, "aanwijzing": 1, "geen spoor": 1, "privé": 0, "totaal": 3},
         "niet_gepland": {"gesprekken": 2, "minuten": 30, "bezoeken": 0},
         "gesprekken": {"aantal": 3, "minuten": 45, "met_opname": 2, "alleen_zoom": 1},
         "zoom_chats": 1,
         "whatsapp": {"stand": "niet aangesloten", "gesprekken": 0, "berichten": 0, "oproepen": 0, "minuten": 0},
         "telefoon": {"stand": "niet aangesloten", "oproepen": 0, "minuten": 0},
         "mail": {"binnen": 5, "verzonden": 2, "onvolledig": False},
         "standen": {"agenda": "volledig", "zoom": "voorlopig", "locatie": "afgesloten"}}
    d.update(extra)
    return d


# Het contract van de runner (weekcontract.json), met zeven dagen; dinsdag niet vastgesteld, woensdag met een null en
# WhatsApp aangesloten, donderdag met een onvolledige mail.
OVERZICHT = {
    "soort": "weekoverzicht", "versie": 1, "week": "2026-W43", "van": "2026-10-19", "tot": "2026-10-25",
    "gemaakt": "2026-10-26T23:40:00+00:00",
    "dagen": [
        dag("2026-10-19", afspraken={"bevestigd": 2, "aanwijzing": 3, "geen spoor": 4, "privé": 1, "totaal": 10},
            gesprekken={"aantal": 25, "minuten": 225, "met_opname": 13, "alleen_zoom": 12}, zoom_chats=13,
            mail={"binnen": 21, "verzonden": 7, "onvolledig": False}),
        {"dag": "2026-10-20", "vastgesteld": False},
        dag("2026-10-21", gesprekken={"aantal": 4, "minuten": None, "met_opname": 1, "alleen_zoom": 0},
            whatsapp={"stand": "aangesloten", "gesprekken": 6, "berichten": 48, "oproepen": 2, "minuten": 11}),
        dag("2026-10-22", mail={"binnen": 9, "verzonden": 3, "onvolledig": True}),
        dag("2026-10-23"), dag("2026-10-24"), dag("2026-10-25"),
    ],
    "totaal": {
        "dagen": 7, "vastgesteld": 6,
        "afspraken": {"bevestigd": 9, "aanwijzing": 12, "geen spoor": 20, "privé": 5, "totaal": 46},
        "niet_gepland": {"gesprekken": 60, "minuten": 900, "bezoeken": 3},
        "gesprekken": {"aantal": 120, "minuten": 1500, "met_opname": 70, "alleen_zoom": 50},
        "zoom_chats": 80,
        "whatsapp": {"gesprekken": 0, "berichten": 0, "oproepen": 0, "minuten": 0, "aangesloten_dagen": 0},
        "telefoon": {"oproepen": 0, "minuten": 0, "aangesloten_dagen": 0},
        "mail": {"binnen": 150, "verzonden": 40, "onvolledig": True},
        "voorbehoud": ["2026-10-20 niet vastgesteld", "mail onvolledig", "WhatsApp niet aangesloten",
                       "telefoon niet aangesloten"],
    },
    "planning": {
        "stand": "volledig",
        "uren_per_firma": [
            {"code": "HARC", "naam": "H-Architects", "afspraken": 5, "minuten": 600},
            {"code": "UNAB", "naam": "UNABO", "afspraken": 3, "minuten": 120},
            {"code": "onbekend", "naam": "zonder of met onduidelijke firmacode", "afspraken": 2, "minuten": 90},
            {"code": "privé", "naam": "privé", "afspraken": 6, "minuten": 300},
        ],
        "afspraken": 16, "minuten": 1110,
    },
}


def geen_streepje(html):
    return "\N{EM DASH}" not in html and "\N{EN DASH}" not in html


# ------------------------------------------------------------------------------------------------- W01 ---
def w01_alleen_beheer():
    verse_db("w01")
    check("W01 /week zonder beheer: 403", pagina("/week", {})[0].status_code == 403)
    check("W01 /week voor de groep agents: 403", pagina("/week", ANDER)[0].status_code == 403)
    check("W01 een week zonder beheer: 403", pagina("/week/2026-W43", ANDER)[0].status_code == 403)
    check("W01 een week die niet bestaat, zonder beheer: 403", pagina("/week/2026-W54", ANDER)[0].status_code == 403)


# ------------------------------------------------------------------------------------------------- W02 ---
def w02_doorsturen():
    verse_db("w02")
    r = C.get("/week", headers=BEHEER)
    plek = r.headers.get("Location", "")
    check("W02 /week stuurt door", r.status_code in (301, 302) and re.search(r"/week/\d{4}-W\d{2}$", plek), (r.status_code, plek))
    check("W02 naar de huidige week in Brussel", plek.endswith("/week/" + A.week_naam(A.datetime.now(A.BRUSSEL).date())), plek)
    check("W02 die week opent", pagina(plek[plek.index("/week/"):])[0].status_code == 200)


# ------------------------------------------------------------------------------------------------- W03 ---
def w03_foute_week():
    verse_db("w03")
    for w in ("2026-W54", "2026-W00", "abc", "2025-W53", "26-W01", "2026-W5", "2026W43"):
        check(f"W03 {w} geeft 404 voor beheer", pagina("/week/" + w)[0].status_code == 404)
    check("W03 2026-W53 bestaat wel", pagina("/week/2026-W53")[0].status_code == 200)


# ------------------------------------------------------------------------------------------------- W04 ---
def w04_lege_week():
    verse_db("w04")
    r, html = pagina("/week/2026-W43")
    check("W04 lege week: 200", r.status_code == 200, r.status_code)
    check("W04 lege week zegt het", "Deze week is nog niet samengevat." in html, html[-1500:])
    check("W04 lege week heeft vorige en volgende", 'href="/week/2026-W42"' in html and 'href="/week/2026-W44"' in html)
    check("W04 lege week toont de dagen van-tot", "19-10 tot 25-10" in html)
    check("W04 lege week zonder tabel", "Gepland tegenover gebeurd" not in html)


# ------------------------------------------------------------------------------------------------- W05 ---
def w05_overzicht():
    verse_db("w05")
    r = klaarzet("2026-W43", OVERZICHT)
    check("W05 klaarzetten lukt", r.status_code == 200 and r.get_json().get("nieuw") == 1, r.get_json())
    r, html = pagina("/week/2026-W43")
    check("W05 pagina: 200", r.status_code == 200, r.status_code)
    check("W05 geen melding van een lege week", "nog niet samengevat" not in html)
    check("W05 bovenaan de week en de dagen", "2026-W43 · 19-10 tot 25-10 · 6 van 7 dagen vastgesteld" in html, html[:3000])
    check("W05 het voorbehoud staat bovenaan", "Let op: 2026-10-20 niet vastgesteld, mail onvolledig, WhatsApp niet "
          "aangesloten, telefoon niet aangesloten." in html)
    check("W05 de dag linkt naar de dagpagina", '<a href="/dag/2026-10-19">Ma 19-10</a>' in html, html[-6000:])
    check("W05 alle zeven dagen staan er", all(f'href="/dag/2026-10-{d}"' in html for d in range(19, 26)))
    ma = rij(html, "Ma 19-10")
    check("W05 maandag: afspraken, niet gepland, gesprekken, zoom-chats",
          ma[:11] == ["Ma 19-10", "2", "3", "4", "1", "2", "30", "25", "225", "13", "13"], ma)
    check("W05 maandag: WhatsApp en telefoon niet aangesloten in grijs, mail in en uit",
          ma[11:] == ["niet aangesloten", "niet aangesloten", "21", "7"], ma)
    check("W05 stand over de breedte van WhatsApp", '<td class="stand b" colspan="4">niet aangesloten</td>' in html)
    check("W05 stand over de breedte van telefoon", '<td class="stand b" colspan="2">niet aangesloten</td>' in html)
    di = rij(html, "Di 20-10")
    check("W05 dinsdag niet vastgesteld over de hele rij", di == ["Di 20-10", "niet vastgesteld"]
          and '<td class="stand b" colspan="18">niet vastgesteld</td>' in html, di)
    wo = rij(html, "Wo 21-10")
    check("W05 woensdag: null wordt een vraagteken", wo[7:10] == ["4", "?", "1"], wo)
    check("W05 woensdag: WhatsApp aangesloten toont getallen", wo[11:15] == ["6", "48", "2", "11"], wo)
    check("W05 elke vastgestelde rij heeft 19 cellen", len(ma) == 19 - 4 and len(wo) == 19 - 1, (len(ma), len(wo)))
    do = rij(html, "Do 22-10")
    check("W05 onvolledige mail is grijs", do[-2:] == ["9", "3"] and 'class="n b grijs" title="onvolledig">9<' in html, do)
    check("W05 uitleg bij de grijze mail", "Grijze mailcijfers zijn onvolledig." in html)
    tot = rij(html, "Totaal")
    check("W05 totaalrij", tot == ["Totaal", "9", "12", "20", "5", "60", "900", "120", "1500", "70", "80",
                                    "niet aangesloten", "niet aangesloten", "150", "40"], tot)
    check("W05 totaalrij is vet", '<tr class="totaal"><td>Totaal</td>' in html)
    check("W05 uren per firma met een komma", rij(html, "H-Architects") == ["H-Architects", "5", "10,0"]
          and rij(html, "zonder of met onduidelijke firmacode") == ["zonder of met onduidelijke firmacode", "2", "1,5"],
          rij(html, "H-Architects"))
    check("W05 firma's in de volgorde van de runner", html.index(">H-Architects<") < html.index(">UNABO<")
          < html.index(">zonder of met") < html.index(">privé<"))
    firma_tot = re.findall(r'<tr class="totaal"><td>Totaal</td><td class="n">(.*?)</td><td class="n">(.*?)</td></tr>', html)
    check("W05 totaal van de planning", firma_tot == [("16", "18,5")], firma_tot)
    check("W05 planning volledig: geen stand", "Planning:" not in html)
    check("W05 de zin onder de tabellen", "Geplande uren en gemeten gespreksminuten staan apart; een afspraak zonder "
          "spoor is niet 'niet gedaan'." in html)
    check("W05 geen gedachtestreepje", geen_streepje(html))
    # een planning die niet volledig is, zegt dat
    klaarzet("2026-W44", dict(OVERZICHT, week="2026-W44", dagen=[],
                              planning=dict(OVERZICHT["planning"], stand="voorlopig: agenda niet gelezen")))
    r, html = pagina("/week/2026-W44")
    check("W05 planning niet volledig: de stand staat erbij", "Planning: voorlopig: agenda niet gelezen" in html, html[-3000:])
    check("W05 zonder dagen: elke dag niet vastgesteld", html.count(">niet vastgesteld</td>") == 7)


# ------------------------------------------------------------------------------------------------- W06 ---
def w06_jaargrens():
    verse_db("w06")
    r, html = pagina("/week/2026-W53")
    check("W06 2026-W53: volgende is 2027-W01", 'href="/week/2027-W01"' in html, html[:2000])
    check("W06 2026-W53: vorige is 2026-W52", 'href="/week/2026-W52"' in html)
    check("W06 2026-W53 loopt van 28-12 tot 03-01", "28-12 tot 03-01" in html)
    r, html = pagina("/week/2027-W01")
    check("W06 2027-W01: vorige is 2026-W53", 'href="/week/2026-W53"' in html, html[:2000])
    check("W06 2027-W01: volgende is 2027-W02", 'href="/week/2027-W02"' in html)


# ------------------------------------------------------------------------------------------------- W07 ---
def w07_vreemde_inhoud():
    verse_db("w07")
    for w, inhoud in (("2026-W40", "{niet json"), ("2026-W41", "[1, 2]"), ("2026-W42", "")):
        klaarzet(w, inhoud)
        r, html = pagina("/week/" + w)
        check(f"W07 {inhoud!r}: geen crash en een melding", r.status_code == 200 and "niet leesbaar (geen geldige JSON)" in html,
              (r.status_code, html[-1500:]))
        check(f"W07 {inhoud!r}: geen tabel, wel vorige en volgende", "Gepland tegenover gebeurd" not in html
              and html.count('href="/week/') == 2)
    vreemd = {"dagen": "x", "totaal": [1], "planning": {"uren_per_firma": [5, {"naam": None, "minuten": "veel"}],
                                                          "afspraken": True, "minuten": float("nan")}}
    klaarzet("2026-W39", vreemd)
    r, html = pagina("/week/2026-W39")
    check("W07 een vreemde vorm laat de pagina niet vallen", r.status_code == 200, r.status_code)
    check("W07 een vreemde vorm: alles onbekend of niet vastgesteld", html.count(">niet vastgesteld</td>") == 7
          and rij(html, "?") == ["?", "?", "?"], rij(html, "?"))
    dagen = [dag(f"2026-09-{14 + i}") for i in range(7)]
    dagen[0] = dict(dagen[0], afspraken=None, whatsapp={"stand": None}, telefoon={"stand": "gedeeltelijk", "oproepen": 3})
    klaarzet("2026-W38", dict(OVERZICHT, dagen=dagen))
    r, html = pagina("/week/2026-W38")
    ma = rij(html, "Ma 14-09")
    check("W07 een blok null wordt vier vraagtekens, een stand null wordt onbekend",
          r.status_code == 200 and ma[1:5] == ["?"] * 4 and "onbekend" in ma and "gedeeltelijk" in ma, ma)


# ------------------------------------------------------------------------------------------------- W08 ---
def w08_links():
    verse_db("w08")
    klaarzet("2026-W43", OVERZICHT)
    html = pagina("/")[1]
    check("W08 het bord heeft een knop Week voor beheer", re.search(r'<a href="/week"[^>]*>Week</a>', html) is not None)
    check("W08 het bord toont die knop niet aan anderen", 'href="/week"' not in pagina("/", ANDER)[1])
    r, html = pagina("/dagen")
    check("W08 de dagenpagina linkt naar de week", r.status_code == 200 and '<a href="/week">week</a>' in html)
    check("W08 de dagenpagina telt het weekoverzicht niet als dag", "2026-W43" not in html)
    check("W08 de dagenpagina zonder gedachtestreepje", geen_streepje(html))
    r, html = pagina("/dag/2026-10-21")
    check("W08 de dagpagina linkt naar haar ISO-week", r.status_code == 200 and '<a href="/week/2026-W43">week</a>' in html)
    r, html = pagina("/dag/2027-01-02")
    check("W08 2 januari 2027 hoort bij 2026-W53", '<a href="/week/2026-W53">week</a>' in html)
    r, html = pagina("/dag/2026-13-45")
    check("W08 een dag die niet bestaat, linkt naar de huidige week", r.status_code == 200 and '<a href="/week">week</a>' in html)


if __name__ == "__main__":
    w01_alleen_beheer()
    w02_doorsturen()
    w03_foute_week()
    w04_lege_week()
    w05_overzicht()
    w06_jaargrens()
    w07_vreemde_inhoud()
    w08_links()
    print(f"{fout} fout")
    sys.exit(1 if fout else 0)
