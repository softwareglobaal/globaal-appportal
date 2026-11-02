"""De dagvaststelling (koppelingen/dagvaststelling.py, ontwerp docs/ontwerp-dagvaststelling.md v1.2).

Legt vast, zonder netwerk:
- de Brusselse daggrens om 23:30 UTC in winter en zomer en in de nachten van beide wissels; het venster van dagen;
- het bewijs per afspraak (D6, E3): bevestigd alleen met een persoon van de afspraak (klant of gast, nooit Mehdi of de
  eigenaar van de agenda), aanwijzing bij de auto ter plaatse of bij alleen overlap voor een afspraak die niet ter
  plaatse is, anders geen spoor met de vraag of het doorging;
- een gesprek hoort alleen via een persoon bij een afspraak; al de rest staat onder niet gepland (E3);
- alleen leidende rijen van gespreksbronnen; mail en chats nooit als gesprek; een Plaud-dubbel telt niet (D7, E1);
- agenda: leeg tegenover ongelezen tegenover onbekend, met voorbehoud op niet gepland (E2);
- Zoom-stand en kanaalstand van WhatsApp en telefoon (D2) staan in het overzicht, nooit als zekere nul;
- mail: Brusselse dag, ontdubbeld per Message-ID, onvolledig met reden, soort uit mailbericht (D8, E4);
- privacy: geen privénaam of privétitel in de tekst (D5, RZ2-01);
- de hash negeert het blok 'Over deze vaststelling'; wijzigingen per sectie (E6);
- een goudtest naar het model van 22-10-2026 (bronproef), met verzonnen namen.
Draaien: python3 mijnagents-runner/tests/test_dagvaststelling.py
"""
import os
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "koppelingen"))
import dagvaststelling as V  # noqa: E402

DAG = "2026-10-22"
FOUTEN = []
AAN = {"whatsapp": "aangesloten", "telefoon": "aangesloten"}


def eis(voorwaarde, wat):
    if not voorwaarde:
        FOUTEN.append(wat)
        print("FOUT:", wat)


def afspraak(id_, start, einde, titel, deelnemers=(), personen=None):
    a = {"id": id_, "titel": titel, "start": f"{DAG}T{start}:00+02:00", "einde": f"{DAG}T{einde}:00+02:00",
         "deelnemers": list(deelnemers), "kalender": "werk"}
    if personen is not None:
        a["_personen"] = personen
    return a


def rij(uniek, start, minuten, personen, bron="zoom", prive=0, dubbel_van="", thema="", datum=DAG, **x):
    return dict({"uniek": uniek, "datum": datum, "start": start, "minuten": minuten, "personen": personen, "bron": bron,
                 "prive": prive, "afdeling": "", "dubbel_van": dubbel_van, "thema": thema}, **x)


def is_prive(a):
    return "[LA]" in a["titel"] or "[PR]" in a["titel"]


def vast(afs=(), rijen=(), loc=None, bezoeken=(), zoom="volledig", mail=None, kanalen=None, ongelezen=()):
    return V.vaststellen(DAG, list(afs), set(ongelezen) if ongelezen is not None else None, list(rijen),
                         {} if loc is None else loc, list(bezoeken) if bezoeken is not None else None, zoom,
                         V.mail_telling(DAG, {}, {}) if mail is None else mail, kanalen, is_prive)


def test_daggrens():
    utc = timezone.utc
    eis(V.gisteren(datetime(2026, 10, 26, 23, 30, tzinfo=utc)) == "2026-10-26", "winter: 23:30 UTC is 00:30 Brussel")
    eis(V.gisteren(datetime(2026, 7, 10, 23, 30, tzinfo=utc)) == "2026-07-10", "zomer: 23:30 UTC is 01:30 Brussel")
    eis(V.gisteren(datetime(2026, 3, 28, 23, 30, tzinfo=utc)) == "2026-03-28", "nacht voor de zomertijd")
    eis(V.gisteren(datetime(2026, 10, 24, 23, 30, tzinfo=utc)) == "2026-10-24", "nacht van de wintertijd")
    eis(V.gisteren(datetime(2026, 10, 25, 23, 30, tzinfo=utc)) == "2026-10-25", "de dag van 25 uur")
    eis(V.gisteren(datetime(2026, 10, 27, 7, 0, tzinfo=utc)) == "2026-10-26", "ochtendketen")
    eis(V.venster(datetime(2026, 10, 26, 23, 30, tzinfo=utc), 3) == ["2026-10-26", "2026-10-25", "2026-10-24"], "venster")
    eis(V.venster(datetime(2026, 10, 27, 7, 0, tzinfo=utc), 1) == ["2026-10-26"], "ochtend: alleen gisteren")
    try:
        V.gisteren(datetime(2026, 10, 26, 23, 30))
        eis(False, "nu zonder tijdzone moet weigeren")
    except ValueError:
        pass
    # een gesprek om 00:30 Brussel op de dag van de wissel valt op die dag
    eis(V.brusselse_dag("2026-10-24T22:30:00+00:00") == "2026-10-25", "mail om 00:30 Brussel (zomertijd)")
    eis(V.brusselse_dag("2026-10-25T23:30:00+00:00") == "2026-10-26", "mail om 00:30 Brussel (wintertijd)")


def test_bewijs():
    online = afspraak("o", "10:30", "11:00", "Mehdi: [UNABO-PO] Lotte Verhaegen [prospect online]")
    buiten = afspraak("b", "14:15", "15:15", "!! Mehdi: [UB-KB] PL 9001 - Pieter Claes, Dorpstraat 1, Proefdorp")
    met = rij("zoom:meeting:1", "10:31", 25, "Mehdi, Lotte Verhaegen")
    zonder = rij("zoom:meeting:2", "10:35", 10, "Mehdi, Ruben (H-AI & ICT)")
    b = V.bewijs(online, [met, zonder])
    eis(b["uitkomst"] == "bevestigd" and b["gesprekken"] == ["zoom:meeting:1"], f"persoon van de afspraak: bevestigd ({b})")
    b = V.bewijs(online, [zonder])
    eis(b["uitkomst"] == "aanwijzing" and b["gesprekken"] == [], f"alleen overlap online: aanwijzing, gesprek blijft vrij ({b})")
    b = V.bewijs(buiten, [], {"uitkomst": "doorgegaan", "tekst": "auto ter plaatse 14:31-16:07"})
    eis(b["uitkomst"] == "aanwijzing" and "auto ter plaatse" in b["grond"], f"auto zonder gesprek: aanwijzing ({b})")
    collega = rij("zoom:meeting:3", "14:28", 5, "Mehdi, Ruben (H-AI & ICT)")
    b = V.bewijs(buiten, [collega], {"uitkomst": "niet_gezien"})
    eis(b["uitkomst"] == "geen spoor" and "Ging dit door?" in b["grond"], f"Zoom met collega tijdens plaatsbezoek ({b})")
    b = V.bewijs(buiten, [], {"uitkomst": "niet_gezien", "tekst": "auto reed voorbij de plek 13:19, geen stop gemeten"})
    eis(b["uitkomst"] == "geen spoor" and "auto reed voorbij de plek 13:19" in b["grond"], f"de reden van de locatie ({b})")
    b = V.bewijs(buiten, [], {"uitkomst": "onbekend"})
    eis(b["uitkomst"] == "geen spoor" and "locatie niet gelezen" in b["grond"], f"locatie onbekend ({b})")
    b = V.bewijs(online, [])
    eis(b["uitkomst"] == "geen spoor", f"niets: geen spoor ({b})")
    oproep = rij("telefoon:9", "14:20", 6, "Pieter Claes", bron="telefoon")
    eis(V.bewijs(buiten, [oproep], {"uitkomst": "niet_gezien"})["uitkomst"] == "bevestigd", "oproep met de klant bevestigt")
    # E3: de eigenaar van de agenda voor de code is geen persoon van de afspraak
    eigenaar = afspraak("e", "13:00", "14:00", "!! Mehdi: Collega: [HA-KB] PL 9002 - Ilse Proefkens, Proeflaan 46")
    met_collega = rij("zoom:meeting:4", "13:05", 20, "Mehdi, Collega (Architecture)")
    eis(V.bewijs(eigenaar, [met_collega], {"uitkomst": "niet_gezien"})["uitkomst"] == "geen spoor",
        "een Zoom met de eigenaar van de agenda bevestigt de klantafspraak niet")
    a = afspraak("k", "10:30", "11:00", "Mehdi: [UNABO-PO] Lotte Verhaegen")
    eis(V.bewijs(a, [rij("zoom:meeting:5", "10:31", 9, "Mehdi")])["gesprekken"] == [], "Mehdi alleen is geen persoon")
    leeg = afspraak("l", "10:30", "11:00", "Mehdi: [EL-IN] intern overleg")
    eis(V.bewijs(leeg, [met])["uitkomst"] == "aanwijzing", "zonder personen hoogstens een aanwijzing")
    # F3 (tegenproef van Codex): twee verschillende personen met dezelfde voornaam, of alleen een plaatsnaam, bevestigen niet
    eis(V.bewijs(a, [rij("zoom:meeting:6", "10:31", 9, "Mehdi, Lotte Peeters")])["uitkomst"] == "aanwijzing",
        "dezelfde voornaam, andere familienaam")
    eis(V.bewijs(buiten, [rij("telefoon:7", "14:20", 6, "Garage Proefdorp", bron="telefoon")], {"uitkomst": "niet_gezien"})
        ["uitkomst"] == "geen spoor", "een plaatsnaam is geen persoon")
    eis(V.bewijs(a, [rij("zoom:meeting:8", "10:31", 9, "Mehdi, Lotte Verhaegen (UNABO)")])["uitkomst"] == "bevestigd",
        "dezelfde volle naam, met afdeling tussen haakjes")
    eis(V.bewijs(afspraak("c", "12:00", "13:00", "Mehdi: [HA-KO] 9007 - Celine Dupont"),
                 [rij("fathom:c", "12:02", 35, "Céline Dupont, Afspraken")])["uitkomst"] == "bevestigd", "accenten tellen niet")
    gast = afspraak("g", "10:30", "11:00", "Mehdi: [UNABO-PO] online kennismaking", deelnemers=["lotte.verhaegen@voorbeeld.be"])
    eis(V.bewijs(gast, [met])["uitkomst"] == "bevestigd", "een gast van buiten op zijn e-mailadres")
    partikel = afspraak("r", "14:15", "15:15", "!! Mehdi: [UB-KB] PL 9001 - Jonas De Proefmaeker, Oude Proefstraat 23, 9999 Proefdorp - ST")
    eis(V.bewijs(partikel, [rij("telefoon:9", "14:20", 6, "Jonas De Proefmaeker", bron="telefoon")], {"uitkomst": "niet_gezien"})
        ["uitkomst"] == "bevestigd", "een naam met partikel")
    eis(V.bewijs(partikel, [rij("telefoon:10", "14:20", 6, "Jonas", bron="telefoon")], {"uitkomst": "niet_gezien"})
        ["uitkomst"] == "geen spoor", "alleen een voornaam bevestigt niet")
    # G1: twee personen in een titel blijven twee personen; 'Anna Claes' is geen van beiden
    twee = afspraak("2", "10:30", "11:00", "Mehdi: [HA-KO] Anna Peeters en Jan Claes")
    eis(V.bewijs(twee, [rij("zoom:meeting:11", "10:31", 9, "Anna Claes")])["uitkomst"] == "aanwijzing", "G1: Anna Claes")
    eis(V.bewijs(twee, [rij("zoom:meeting:12", "10:31", 9, "Jan Claes")])["uitkomst"] == "bevestigd", "G1: Jan Claes")
    eis(V.bewijs(afspraak("3", "10:30", "11:00", "Mehdi: [HA-KO] Anna Peeters & Jan Claes"),
                 [rij("zoom:meeting:13", "10:31", 9, "Anna Claes")])["uitkomst"] == "aanwijzing", "G1: met &")
    # G2: een onbekende locatie draagt haar reden
    b = V.bewijs(buiten, [], {"uitkomst": "onbekend", "tekst": "auto zonder meting op dat uur"})
    eis(b["uitkomst"] == "geen spoor" and "auto zonder meting op dat uur" in b["grond"], f"G2: reden ({b})")


def test_dubbels_en_niet_gepland():
    rijen = [rij("zoom:meeting:a", "09:00", 20, "Mehdi, Ruben"),
             rij("fathom:1", "09:00", 20, "Mehdi, Ruben", bron="fathom", dubbel_van="zoom:meeting:a"),
             rij("zoom:chat:x:2026-10-22", "09:30", 0, "Ruben", thema="12 berichten"),
             rij("zoom:meeting:b", "16:00", 1, "Mehdi, Ruben"),
             rij("zoom:meeting:c", "18:00", 7, "Mehdi, Anja", dubbel_van="buiten:alleen-mehdi"),
             rij("fathom:2", "11:00", 30, "Mehdi, Lotte", bron="fathom"),
             rij("plaud:1", "09:02", 18, "Mehdi", bron="plaud"),
             rij("plaud:2", "15:00", 25, "Mehdi, aannemer", bron="plaud"),
             rij("mail:<x@y>", "10:00", 0, "Pieter Claes", bron="mail"),
             rij("zoom:meeting:d", "12:00", 9, "Mehdi, Ruben", datum="2026-10-21")]
    v = vast(rijen=rijen)
    g = v["gesprekken"]
    eis(g["aantal"] == 4 and g["minuten"] == 76, f"leidende gesprekken van de dag, elk een keer ({g})")
    # F6: de Zoom-rij met een samenvallende Plaud-opname telt een keer, als gesprek met opname
    eis(g["alleen_zoom"] == 1 and g["met_opname"] == 3, f"Fathom met dubbel_van telt niet, Plaud-dubbel geeft opname ({g})")
    eis(v["zoom"]["chats"] == 1, "een chatgesprek")
    namen = [g["uniek"] for g in v["niet_gepland"]["gesprekken"]]
    eis(namen == ["zoom:meeting:a", "fathom:2", "plaud:2"],
        f"niet gepland: geen chat, mail, dubbel, korter dan 2 min of andere dag ({namen})")
    # E3: een gesprek op het uur van een online afspraak zonder persoon blijft onder niet gepland
    v = vast([afspraak("o", "10:50", "11:30", "Mehdi: [UNABO-PO] Lotte Verhaegen")], [rij("zoom:meeting:z", "11:00", 30, "Mehdi, Ruben")])
    eis(v["agenda"]["afspraken"][0]["uitkomst"] == "aanwijzing", "aanwijzing")
    eis([g["uniek"] for g in v["niet_gepland"]["gesprekken"]] == ["zoom:meeting:z"], "en toch niet gepland")


def test_agenda_en_standen():
    t = V.tekst(vast())
    eis("- geen afspraken" in t and "onder voorbehoud" not in t, "lege agenda, alles gelezen")
    t = V.tekst(vast(ongelezen={"Gezin", "archief"}))
    eis("agenda onvolledig, niet gelezen: Gezin, archief" in t and "onder voorbehoud" in t and "geen afspraken gelezen" in t,
        f"ongelezen agenda of archief: onvolledig met voorbehoud\n{t}")
    v = V.vaststellen(DAG, [], None, [], None, None, "onbekend", None, None, is_prive)
    t = V.tekst(v)
    eis("agenda niet gelezen: onbekend" in t and "locatie: niet gelezen" in t and "mail: niet gelezen" in t,
        "niets gelezen is onbekend, geen nul")
    eis("gesprekken in Zoom, Fathom en Plaud: onbekend" in t and "Zoom-chat: onbekend" in t and "0 chatgesprek" not in t,
        f"F5: Zoom onbekend\n{t}")
    t = V.tekst(V.vaststellen(DAG, [], set(), [rij("zoom:chat:a:2026-10-22", "09:00", 0, "Ruben")], {}, [], "volledig",
                              V.mail_telling(DAG, {}, {}), None, is_prive, chatstand="ondergrens"))
    eis("Zoom-chat: 1 chatgesprek(ken) gezien" in t and "gesprekken gezien in Zoom, Fathom en Plaud: 0, 0 min" in t
        and "De Zoomwacht: volledig gelezen" in t, f"de chat apart; Zoom zegt zelf volledig\n{t}")
    eis("WhatsApp: nog niet aangesloten" in t and "telefoon: nog niet aangesloten" in t, "zonder kanaalstand: niet aangesloten")
    t = V.tekst(vast(rijen=[rij("zoom:meeting:a", "09:00", 20, "Ruben")], zoom="ondergrens"))
    eis("gesprekken gezien in Zoom, Fathom en Plaud: 1, 20 min (0 met opname, 1 alleen in Zoom); De Zoomwacht: "
        "onvolledig gelezen" in t and "Zoom-chat: 0 chatgesprek(ken) gezien" in t and "minstens" not in t, f"L2: gezien\n{t}")
    t = V.tekst(vast(rijen=[rij("fathom:a", "09:00", 20, "Ruben", bron="fathom")], zoom="onbekend"))
    eis("gezien in Zoom, Fathom en Plaud: 1, 20 min (1 met opname, 0 alleen in Zoom); De Zoomwacht: stand onbekend" in t,
        f"L2: gezien bij onbekende stand\n{t}")
    eis("volledig gelezen" not in V.tekst(vast(zoom="voorlopig")) and "nog niet afgesloten" in V.tekst(vast(zoom="voorlopig")),
        "voorlopig")
    # D2: rijen zonder aangesloten wacht tellen niet als aangesloten; een stille wacht is onvolledig
    wa = [rij("whatsapp:abc:2026-10-22", "08:01", 0, "Broer Ali", bron="whatsapp", thema="14 berichten (5 van Mehdi)")]
    # Codex-toets 1 (T-0120): een wacht die nu niet aangesloten is, verbergt nooit wat al gezien is; het blijft een
    # ondergrens met de stand erbij, nooit 'aangesloten'
    t = V.tekst(vast(rijen=wa, kanalen={"whatsapp": "niet aangesloten"}))
    eis("WhatsApp: gezien 14 berichten in 1 gesprekken; oproepen en minuten onbekend (niet aangesloten)" in t, f"rijen alleen\n{t}")
    eis("WhatsApp: nog niet aangesloten" in V.tekst(vast(kanalen={"whatsapp": "niet aangesloten"})), "zonder rijen")
    t = V.tekst(vast(rijen=wa, kanalen={"whatsapp": "stil sinds 2026-10-20 09:00"}))
    # WA-6 (T-0120): op een dag die niet gelezen is, is een nul onbekend; wat gezien is, blijft een ondergrens
    eis("WhatsApp: gezien 14 berichten in 1 gesprekken; oproepen en minuten onbekend (stil sinds 2026-10-20 09:00)" in t
        and "0 oproepen" not in t and "0 min gezien" not in t, f"stille wacht\n{t}")
    t = V.tekst(vast(kanalen={"whatsapp": "onbekend voor deze dag", "telefoon": "stil sinds 25-10 08:00"}))
    eis("WhatsApp: onbekend (onbekend voor deze dag)" in t and "telefoon: onbekend (stil sinds 25-10 08:00)" in t,
        f"F5: zonder dekking van de dag geen nul\n{t}")


def test_mail():
    k = lambda d, mid, aan, ond="x": {"datum": d, "message_id": mid, "aan": [aan], "onderwerp": ond}  # noqa: E731
    k1 = k("2026-10-21T22:30:00+00:00", "<a@x>", "Pieter Claes <p@claes.be>")
    k2 = k("2026-10-22T22:30:00+00:00", "<b@x>", "iemand <i@x.be>")
    k3 = k("2026-10-22T09:00:00+02:00", "<c@x>", "Vriend <v@gmail.com>")
    i1, i2, i3 = (k("2026-10-22T08:00:00+02:00", "<i1@x>", "mch"), k("2026-10-22T09:00:00+02:00", "<i2@x>", "mch"),
                  k("2026-10-21T09:00:00+02:00", "<i3@x>", "mch"))
    ontvangen = {"mch@h-architects.be": {"berichten": [i1, i2, i3]},
                 "info@h-architects.be": {"berichten": [i1], "onvolledig": ["INBOX.ORDE: niet leesbaar"]}}
    verzonden = {"mch@h-architects.be": {"berichten": [k1, k2]},
                 "info@h-architects.be": {"berichten": [k1], "onvolledig": ["INBOX.Sent: bestaat maar is niet leesbaar"]},
                 "mehdichegini@hotmail.com": {"berichten": [k3], "onvolledig": ["kopie 150 uur oud"]}}
    m = V.mail_telling(DAG, ontvangen, verzonden, {"<i1@x>": "koud"})
    pv = m["postvakken"]
    eis(pv["mch@h-architects.be"]["binnen"] == 2 and pv["mch@h-architects.be"]["soorten"] == {"koud": 1}, f"binnen ({m})")
    eis(pv["info@h-architects.be"]["binnen"] == 1, "dezelfde inkomende mail telt in elk postvak")
    eis(m["binnen"] == 2 and m["verzonden"] == 2, f"totaal: Brusselse dag, ontdubbeld per Message-ID ({m})")
    eis(pv["mch@h-architects.be"]["verzonden"] == 1 and pv["info@h-architects.be"]["verzonden"] == 1, "verzonden per postvak")
    eis(m["onvolledig"], "een onvolledig postvak maakt het totaal onvolledig")
    t = V.tekst(vast(mail=m), prive_postvakken=("mehdichegini@hotmail.com",))
    eis("onvolledig: INBOX.ORDE: niet leesbaar; INBOX.Sent: bestaat maar is niet leesbaar" in t, f"onvolledig met reden\n{t}")
    eis("kopie 150 uur oud" in t, "oude kopie")
    eis("Vriend" not in t, "privépostvak: geen ontvanger")
    eis("Pieter Claes" in t, "zakelijke ontvanger staat erbij")
    veel = {"info@h-architects.be": {"berichten": [k(f"{DAG}T10:0{i}:00+02:00", f"<v{i}@x>", f"klant{i}@x.be") for i in range(8)]}}
    t = V.tekst(vast(mail=V.mail_telling(DAG, {}, veel)))
    eis("klant4@x.be en 3 meer" in t and "klant5@x.be" not in t, f"hoogstens vijf ontvangers bij naam\n{t}")


def test_mail3_alleen_verzonden_gelezen():
    """MAIL-3 (T-0120): een postvak dat alleen voor verzonden gelezen wordt (een adres waaruit een wacht antwoordt), toont
    'binnen: niet gelezen', nooit '0 binnen'; het is daarom niet onvolledig en geeft geen nood. Tot 01-11-2026 stonden er
    zo 60 valse nullen in 20 dagbestanden."""
    k = {"datum": f"{DAG}T10:00:00+02:00", "message_id": "<u1@x>", "aan": ["klant <k@proef.test>"], "onderwerp": "x"}
    i = {"datum": f"{DAG}T09:00:00+02:00", "message_id": "<b1@x>"}
    m = V.mail_telling(DAG, {"wacht@proef.test": {"berichten": [i]}},
                       {"wacht@proef.test": {"berichten": []}, "uit@proef.test": {"berichten": [k]}})
    pv = m["postvakken"]
    eis(pv["uit@proef.test"]["binnen"] is None and pv["uit@proef.test"]["verzonden"] == 1, f"per richting ({pv})")
    eis(pv["wacht@proef.test"]["binnen"] == 1 and pv["wacht@proef.test"]["verzonden"] == 0, f"gelezen postvak ({pv})")
    eis(not m["onvolledig"] and m["binnen"] == 1, f"niet gelezen is geen onvolledig ({m})")
    t = V.tekst(vast(mail=m))
    eis("  - uit@proef.test: binnen: niet gelezen, 1 verzonden; naar klant\n" in t, f"exact 'binnen: niet gelezen'\n{t}")
    eis("  - wacht@proef.test: 1 binnen, 0 verzonden\n" in t, f"een gelezen postvak houdt zijn aantal\n{t}")
    eis("0 binnen" not in t and "onvolledig" not in t, f"geen valse nul\n{t}")
    # omgekeerd: een postvak dat alleen voor binnen in de lezing zit, zegt 'verzonden: niet gelezen'
    t = V.tekst(vast(mail=V.mail_telling(DAG, {"wacht@proef.test": {"berichten": [i]}}, {})))
    eis("  - wacht@proef.test: 1 binnen, verzonden: niet gelezen\n" in t, f"per richting\n{t}")


def test_privacy():
    afs = [afspraak("p", "17:45", "18:30", "!! Mehdi: [PR] Proefafspraak Zeta")]
    rijen = [rij("zoom:meeting:p", "17:06", 18, "Mehdi, Tante Mie", prive=1),
             rij("zoom:meeting:q", "20:00", 10, "Mehdi, Bart", afdeling="privé"),
             rij("whatsapp:abc:2026-10-22", "08:01", 0, "Broer Ali", bron="whatsapp", thema="14 berichten (5 van Mehdi)"),
             rij("whatsapp-oproep:1", "19:00", 12, "Broer Ali", bron="whatsapp", thema="uitgaand"),
             rij("telefoon:1", "11:00", 4, "Dokter Peeters", bron="telefoon", thema="inkomend")]
    v = vast(afs, rijen, {"p": {"uitkomst": "niet_gezien"}}, kanalen=AAN)
    t = V.tekst(v)
    for naam in ("Tante Mie", "Bart", "Broer Ali", "Dokter Peeters", "Proefafspraak Zeta"):
        eis(naam not in t, f"{naam} staat niet in het overzicht")
    eis("17:45 (privé): geen spoor. Ging dit door?" in t, f"privéafspraak zonder titel:\n{t}")
    eis(v["whatsapp"]["berichten"] == 14 and v["whatsapp"]["oproepen"] == 1 and v["whatsapp"]["minuten"] == 12, "WhatsApp")
    namen = [g["uniek"] for g in v["niet_gepland"]["gesprekken"]]
    eis("whatsapp-oproep:1" in namen and "telefoon:1" in namen and not any(n.startswith("whatsapp:") for n in namen),
        f"oproepen zijn gesprekken, chats niet ({namen})")


def test_plekken_en_versie():
    """F2: alleen een werkproject bij naam; een twijfelgeval of een andere plek (kan privé zijn) niet. F8: de versie volgt
    het bestand."""
    b = [{"van": "10:44", "tot": "11:13", "minuten": 29, "waar": "Proefweg 12, 9999 Proefdorp", "soort": "elders"},
         {"van": "11:15", "tot": "11:33", "minuten": 18, "waar": "een van: HARC 9004, HARC 9005", "soort": "twijfel"},
         {"van": "12:00", "tot": "12:40", "minuten": 40, "waar": "Tante Mie, Kerkstraat 1"},
         {"van": "14:31", "tot": "16:07", "minuten": 96, "waar": "project HARC 9001, Dorpstraat 1", "soort": "project"}]
    t = V.tekst(V.vaststellen(DAG, [], set(), [], {}, b, "volledig", V.mail_telling(DAG, {}, {}), None, is_prive, "voorlopig"))
    for weg in ("Proefweg", "HARC 9005", "Tante Mie", "Kerkstraat"):
        eis(weg not in t, f"F2: {weg} staat er niet")
    eis("project HARC 9001, Dorpstraat 1" in t and "verblijf zonder afspraak (plek in het locatielogboek)" in t, t)
    eis("locatie voorlopig: bezoeken kunnen nog veranderen" in t, "voorlopig dagboek")
    eis(V.versie_van(V.tekst(vast(), over=["versie 7, gemaakt 01:00"])) == 7, "versie uit het bestand")
    eis(V.versie_van("# Dag\n- versie 3, gemaakt") is None, "zonder blok geen versie")


def test_hash_en_wijzigingen():
    a = V.tekst(vast(), over=["versie 1, gemaakt 01:00"])
    b = V.tekst(vast(), over=["versie 2, gemaakt 07:00"])
    eis(V.inhoud_hash(a) == V.inhoud_hash(b), "hash negeert het blok over de vaststelling")
    c = V.tekst(vast(rijen=[rij("zoom:meeting:a", "09:00", 20, "Ruben")]))
    eis(V.inhoud_hash(a) != V.inhoud_hash(c), "hash ziet een inhoudelijke wijziging")
    eis(V.wijzigingen(a, c) == ["Niet gepland", "Communicatie"], f"wijzigingen per sectie ({V.wijzigingen(a, c)})")
    eis(V.wijzigingen(a, b) == [], "geen wijziging")
    eis(V.wijzigingen("", a) == ["Gepland", "Niet gepland", "Communicatie"], "eerste versie")


def test_goud_22_10():
    """Het model van 22-10-2026 uit de bronproef, met verzonnen namen en plaatsen: het plaatsbezoek aanwijzing (auto),
    het vooroverleg en de privéafspraak geen spoor, het interne overleg van 23:00 geen spoor, en elk Zoom-gesprek van minstens 2 minuten niet gepland."""
    afs = [afspraak("stad", "12:30", "13:30", "!! Mehdi: [HA] 9003 Stad Proefstad vooroverleg varianten, Stadhuis"),
           afspraak("dorp", "14:15", "15:15", "!! Mehdi: [UB-KB] PL 9001 - Pieter Claes, Dorpstraat 1, Proefdorp"),
           afspraak("prive", "17:45", "18:30", "!! Mehdi: [PR] Proefafspraak Zeta"),
           afspraak("ai", "23:00", "23:30", "Mehdi: [EL-IN] AI Ruben - Automation")]
    loc = {"stad": {"uitkomst": "niet_gezien"}, "dorp": {"uitkomst": "doorgegaan", "tekst": "auto ter plaatse 14:31-16:07"},
           "prive": {"uitkomst": "niet_gezien"}}
    zoom = [("10:24", 6), ("11:53", 3), ("13:12", 7), ("13:19", 16), ("13:35", 25), ("14:10", 13), ("14:27", 5),
            ("16:54", 5), ("17:02", 3), ("17:06", 18), ("17:24", 1), ("17:32", 25), ("17:57", 7), ("18:05", 3)]
    rijen = [rij(f"zoom:meeting:{i}", s, m, "Mehdi, Ruben (H-AI & ICT)") for i, (s, m) in enumerate(zoom)]
    v = vast(afs, rijen, loc, [{"van": "11:15", "tot": "11:33", "minuten": 18, "waar": "project HARC 9004", "soort": "project"}])
    uit = {x["id"]: x["uitkomst"] for x in v["agenda"]["afspraken"]}
    eis(uit == {"stad": "geen spoor", "dorp": "aanwijzing", "prive": "geen spoor", "ai": "geen spoor"}, f"goud: {uit}")
    eis(v["gesprekken"]["aantal"] == 14 and v["gesprekken"]["minuten"] == 137, f"goud: 14 gesprekken, 137 min ({v['gesprekken']})")
    eis(len(v["niet_gepland"]["gesprekken"]) == 13, "goud: 13 niet gepland (een sessie van 1 min telt niet)")
    eis("project HARC 9004" in V.tekst(v), "goud: projectbezoek zonder afspraak")


# ------------------------------------------------------------------- de bundel voor Ai Angel (T-0120) ---
INHOUD = {
    "fathom:701": {"firma": "UNABO", "soort": "project", "dossier": "9405", "dossier_bewijs": "agendatitel, niet bevestigd",
                   "samenvatting": "Het ontwerp van de keuken is besproken. De klant wacht op de offerte.", "van": "Fathom",
                   "actiepunten": [{"wat": "Offerte keuken sturen", "wie": "Mehdi", "tijd": "00:12:30", "klaar": False},
                                   {"wat": "Plannen [v2]; nakijken", "wie": "Klant Omega", "tijd": "", "klaar": True}]},
    "fathom:702": {"firma": "HA", "soort": "sales", "dossier": "", "samenvatting": "Kennismaking. Geen afspraak.",
                   "van": "Fathom", "actiepunten": []},
    "fathom:703": {"samenvatting": None, "actiepunten": None, "van": "Fathom", "reden": "Fathom leverde ze nog niet"},
    "plaud:p1": {"samenvatting": None, "actiepunten": None, "van": "De Gespreksanalist",
                 "reden": "nog niet geanalyseerd (De Gespreksanalist staat uit)"},
    "plaud:p2": {"prive": True},
}


def test_angel2_werkgesprekken_per_gesprek_met_verwijzing():
    """ANGEL-2 en VOL-5 (T-0120): per werkgesprek titel, firma en dossier, samenvatting, actiepunten en verwijzing.
    Onbekend (geen bestand van Fathom, geen uitvoer van De Gespreksanalist) is nooit 'geen actiepunten'; een
    privégesprek (vlag van de rij, of privé volgens De Gespreksanalist) is alleen 'privégesprek, N min', en voor een rij
    die privé is wordt de inhoud niet eens gevraagd."""
    gevraagd = []

    def inhoud_van(g):
        gevraagd.append(g["uniek"])
        return INHOUD.get(g["uniek"])
    rijen = [rij("fathom:701", "09:00", 45, "Klant Omega", bron="fathom", thema="Keuken ontwerp"),
             rij("fathom:702", "10:00", 20, "Klant Zeta", bron="fathom", thema="Kennismaking"),
             rij("fathom:703", "11:00", 15, "Klant Eta", bron="fathom", thema="Nazorg"),
             rij("plaud:p1", "13:00", 30, "", bron="plaud", thema="Werfbezoek"),
             rij("plaud:p2", "15:00", 12, "", bron="plaud", thema="Geheim onderwerp"),
             rij("fathom:704", "16:00", 50, "Broer Ali", bron="fathom", prive=1, thema="Familie"),
             rij("plaud:p3", "09:05", 40, "", bron="plaud", thema="Dubbel van Fathom"),       # valt in fathom:701
             rij("zoom:meeting:kort", "18:00", 1, "Ruben", thema="kort")]
    v = V.vaststellen(DAG, [], set(), rijen, {}, [], "volledig", V.mail_telling(DAG, {}, {}), AAN, is_prive,
                      bundel={"inhoud_van": inhoud_van, "morgen": [], "mail_open": [], "prive_postvakken": set()})
    eis("fathom:704" not in gevraagd, f"privé: niets gevraagd ({gevraagd})")
    t = V.tekst(v)
    blok = t.split("## Werkgesprekken", 1)[1].split("\n## ", 1)[0]
    eis("- 09:00 Fathom, 45 min: Keuken ontwerp, met Klant Omega (ook opgenomen met Plaud) [fathom:701]" in blok, f"titel\n{blok}")
    eis("  - firma: UNABO project; dossier: 9405 (agendatitel, niet bevestigd)" in blok, f"firma en dossier\n{blok}")
    eis("  - samenvatting (Fathom): Het ontwerp van de keuken is besproken. De klant wacht op de offerte." in blok, blok)
    eis("  - actiepunt [fathom:701; UNABO 9405; wie: Mehdi; op 00:12:30]: Offerte keuken sturen" in blok, blok)
    eis("  - actiepunt [fathom:701; UNABO 9405; wie: Klant Omega; klaar in Fathom]: Plannen [v2]; nakijken" in blok,
        f"een tekst met haken blijft na de haken staan\n{blok}")
    eis("  - firma: HA sales; dossier: onbekend" in blok and "  - actiepunten: geen (Fathom vond er geen)" in blok,
        f"geen actiepunt is 'geen'\n{blok}")
    eis("[fathom:703]\n  - firma: onbekend; dossier: onbekend\n  - samenvatting en actiepunten: Fathom leverde ze nog niet" in blok,
        f"onbekend bij Fathom\n{blok}")
    eis("[plaud:p1]\n  - firma: onbekend; dossier: onbekend\n  - samenvatting en actiepunten: nog niet geanalyseerd" in blok,
        f"Plaud zonder uitvoer\n{blok}")
    eis("- 15:00 privégesprek, 12 min" in blok and "Geheim onderwerp" not in t, f"privé volgens De Gespreksanalist\n{blok}")
    eis("- 16:00 privégesprek, 50 min" in blok and "Familie" not in t and "Broer Ali" not in t, f"privé van de rij\n{blok}")
    eis("actiepunten: geen" not in blok.split("[fathom:703]")[1].split("\n- ")[0], "onbekend is nooit geen")
    eis("Werkgesprekken" in V.wijzigingen(V.tekst(vast()), t), "het blok telt in de wijzigingen")
    # Codex-toets 1: wat privé is volgens de inhoud, is privé in de hele dagtekst (ook Niet gepland en Gepland)
    rijen2 = rijen + [rij("plaud:p5", "17:00", 25, "Klant Privaat", bron="plaud", thema="Geheim")]
    INHOUD["plaud:p5"] = {"prive": True}
    afs = [afspraak("a", "16:55", "17:30", "!! Mehdi: [HA] 9003 Bespreking", personen="Klant Privaat")]
    v2 = V.vaststellen(DAG, afs, set(), rijen2, {}, [], "volledig", V.mail_telling(DAG, {}, {}), AAN, is_prive,
                       bundel={"inhoud_van": lambda g: INHOUD.get(g["uniek"]), "morgen": [], "mail_open": [],
                               "prive_postvakken": set()})
    t2 = V.tekst(v2)
    eis("Klant Privaat" not in t2 and "- 17:00 Plaud, 25 min, privé" in t2 and "- 17:00 privégesprek, 25 min" in t2,
        f"privé volgens de inhoud: nergens een naam\n{t2}")
    eis("Klant Omega" in t2, "een werkgesprek houdt zijn naam")
    # zonder bundel (oude aanroep) geen nieuwe blokken
    eis(all(f"## {k}" not in V.tekst(vast()) for k in V.BUNDELKOPPEN), "oude aanroep zonder blokken")


def test_db6_gemist_zonder_terugbellen_zonder_naam():
    """DB-6 (T-0081): de gemiste inkomende oproepen van de dag zonder latere oproep met dezelfde persoon (ook de dag
    erna telt); alleen uur en kanaal, nooit een naam (privé, X8); een verborgen nummer: terugbellen onbekend; een dag die
    niet gelezen is: onbekend, nooit 'geen'."""
    morgen = "2026-10-23"
    rijen = [rij("telefoon:a-1", "10:12", 0, "Proef Een", bron="telefoon", prive=1, dubbel_van="buiten:gemist",
                 thema="iPhone, inkomend, gemist"),
             rij("telefoon:b-1", "11:00", 0, "Proef Twee", bron="telefoon", prive=1, dubbel_van="buiten:gemist",
                 thema="iPhone, inkomend, gemist"),
             rij("telefoon:b-2", "09:00", 0, "Proef Twee", bron="telefoon", prive=1, dubbel_van="buiten:gemist",
                 thema="iPhone, uitgaand, niet beantwoord", datum=morgen),                 # een poging de dag erna
             rij("telefoon:c-1", "12:00", 0, "nummer verborgen", bron="telefoon", prive=1, dubbel_van="buiten:gemist",
                 thema="iPhone, inkomend, gemist"),
             rij("whatsapp-oproep:d", "13:00", 0, "Proef Drie", bron="whatsapp", prive=1, dubbel_van="buiten:gemist",
                 thema="WhatsApp-oproep, inkomend, gemist"),
             rij("whatsapp-oproep:e", "13:30", 4, "Proef Drie", bron="whatsapp", prive=1, thema="WhatsApp-oproep, inkomend"),
             rij("xelion:f", "14:00", 0, "Proef Vier", bron="xelion", prive=1, dubbel_van="buiten:gemist",
                 thema="Xelion, inkomend, gemist"),
             rij("telefoon:g", "15:00", 0, "Proef Vijf", bron="telefoon", prive=1, dubbel_van="buiten:gemist",
                 thema="iPhone, uitgaand, niet beantwoord")]
    bundel = {"inhoud_van": lambda g: None, "morgen": [], "mail_open": [], "prive_postvakken": set()}
    alle = {"whatsapp": "aangesloten", "telefoon": "aangesloten", "xelion": "aangesloten"}
    v = V.vaststellen(DAG, [], set(), rijen, {}, [], "volledig", V.mail_telling(DAG, {}, {}), alle, is_prive, bundel=bundel)
    blok = V.tekst(v).split("## Gemist zonder terugbellen", 1)[1].split("\n## ", 1)[0]
    eis([x["tijd"] for x in v["gemist_open"]] == ["10:12", "12:00", "14:00"], f"teruggebeld valt weg ({v['gemist_open']})")
    eis("- 10:12 telefoon (privé): geen terugbelpoging gezien" in blok and "- 14:00 Xelion (privé): geen terugbelpoging gezien"
        in blok and "- 12:00 telefoon (privé): terugbellen onbekend (nummer onbekend of verborgen)" in blok, blok)
    eis(not any(n in V.tekst(v) for n in ("Proef Een", "Proef Twee", "Proef Drie", "Proef Vier")), "geen naam")
    eis("onvolledig" not in blok, blok)
    leeg = V.tekst(V.vaststellen(DAG, [], set(), [], {}, [], "volledig", None, {}, is_prive, bundel=bundel))
    eis("- onbekend (telefoon, WhatsApp en Xelion niet gelezen voor deze dag)" in leeg, f"niet gelezen is onbekend\n{leeg}")
    half = V.tekst(V.vaststellen(DAG, [], set(), [], {}, [], "volledig", None, {"telefoon": "aangesloten"}, is_prive,
                                 bundel=bundel))
    eis("- geen gezien (WhatsApp en Xelion niet gelezen voor deze dag)" in half, half)


def test_db6_mail_wacht_en_morgen():
    """DB-6: de mails van de dag die nog wachten (uit /api/mail/open), zonder werkdagen en zonder tekst, een privépostvak
    alleen als aantal; niet gelezen is onbekend. Morgen: de afspraken van de dag erna, privé zonder titel."""
    punten = [{"postvak": "info@h-architects.be", "soort": "hoog", "soort_label": "belangrijk", "van": "a@voorbeeld.be",
               "van_naam": "Klant Omega", "onderwerp": "Vraag over de offerte", "datum_iso": f"{DAG}T09:00:00+02:00",
               "werkdagen": 3, "orde": 0, "opvolging": "open"},
              {"postvak": "info@h-architects.be", "soort": "actie", "van": "b@voorbeeld.be", "onderwerp": "Plannen",
               "datum_iso": f"{DAG}T23:30:00+02:00", "orde": 1, "opvolging": "onzeker", "werkdagen": 3},
              {"postvak": "privé@voorbeeld.be", "soort": "hoog", "van_naam": "Broer Ali", "onderwerp": "Familiefeest",
               "datum_iso": f"{DAG}T10:00:00+02:00"},
              {"postvak": "info@h-architects.be", "soort": "hoog", "van_naam": "Klant Zeta", "onderwerp": "Andere dag",
               "datum_iso": "2026-10-21T10:00:00+02:00"}]
    punten = punten[1:2] + punten[:1] + punten[2:]
    morgen = [afspraak("m1", "09:00", "10:00", "!! Mehdi: [HA] 9003 Werfbezoek"),
              afspraak("m2", "11:00", "12:00", "!! Mehdi: [PR] Tandarts Zeta")]
    for a in morgen:
        a["start"] = a["start"].replace(DAG, "2026-10-23")
    bundel = {"inhoud_van": lambda g: None, "morgen": morgen, "mail_open": punten, "prive_postvakken": {"privé@voorbeeld.be"}}
    t = V.tekst(vast(kanalen=AAN) if False else V.vaststellen(DAG, [], set(), [], {}, [], "volledig", None, AAN, is_prive,
                                                              bundel=bundel))
    mail = t.split("## Mail wacht op antwoord", 1)[1].split("\n## ", 1)[0]
    eis("- info@h-architects.be: belangrijk, van Klant Omega: Vraag over de offerte" in mail, mail)
    eis("- info@h-architects.be: actie, van b@voorbeeld.be: Plannen (mogelijk al beantwoord)" in mail, mail)
    eis(mail.index("Vraag over de offerte") < mail.index("Plannen"), f"belangrijk eerst (orde 0 voor 1)\n{mail}")
    eis("- privé@voorbeeld.be: 1 mail (privé)" in mail and "Broer Ali" not in t and "Familiefeest" not in t, mail)
    eis("Andere dag" not in mail and "werkdag" not in mail, f"alleen die dag, geen werkdagen\n{mail}")
    t2 = V.tekst(V.vaststellen(DAG, [], set(), [], {}, [], "volledig", None, AAN, is_prive, bundel=dict(bundel, mail_open=None)))
    eis("- niet gelezen (de lijst van de mailwachten was niet te lezen)" in t2, "niet gelezen is onbekend")
    mo = t.split("## Morgen, 2026-10-23", 1)[1].split("\n## ", 1)[0]
    eis("- 09:00 !! Mehdi: [HA] 9003 Werfbezoek" in mo and "- 11:00 (privé)" in mo and "Tandarts" not in t, mo)
    t3 = V.tekst(V.vaststellen(DAG, [], None, [], {}, [], "volledig", None, AAN, is_prive, bundel=dict(bundel, morgen=[])))
    eis("## Morgen, 2026-10-23 (agenda niet gelezen: onbekend)" in t3 and "- geen afspraken gelezen" in t3, t3)
    eis(V.wijzigingen(t3, t) == ["Gepland", "Mail wacht op antwoord", "Morgen"] or "Morgen" in V.wijzigingen(t3, t),
        f"Morgen telt in de wijzigingen ({V.wijzigingen(t3, t)})")


def test_wa3_en_onbekend_is_nooit_nul():
    """WA-3 (T-0120): 'waarvan K zonder gekende duur' bij de WhatsApp-oproepen die WhatsApp niet gemist noemt maar zonder
    duur. WA-6: op een dag die niet gelezen is, is een nul onbekend (WhatsApp, telefoon en Xelion), wat gezien is blijft."""
    wa = [rij("whatsapp-oproep:a", "09:00", 0, "Proef Een", bron="whatsapp", prive=1,
              thema="WhatsApp-oproep, inkomend, niet gemist, duur onbekend"),
          rij("whatsapp-oproep:b", "10:00", 5, "Proef Een", bron="whatsapp", prive=1, thema="WhatsApp-oproep, uitgaand")]
    t = V.tekst(vast(rijen=wa, kanalen=AAN))
    eis("- WhatsApp: 0 berichten in 0 gesprekken, 2 oproepen (waarvan 1 zonder gekende duur), 5 min gezien" in t, t)
    t = V.tekst(vast(rijen=wa, kanalen={"whatsapp": "onbekend voor deze dag"}))
    eis("- WhatsApp: gezien 2 oproepen (waarvan 1 zonder gekende duur), 5 min; berichten onbekend (onbekend voor deze dag)"
        in t, t)
    xel = [rij("xelion:a", "09:00", 0, "Proef Twee", bron="xelion", prive=1, dubbel_van="buiten:gemist",
               thema="Xelion, inkomend, gemist")]
    v = V.vaststellen(DAG, [], set(), xel, {}, [], "volledig", None, {"xelion": "stil sinds 21-10 08:00"}, is_prive)
    eis("- Xelion: gezien 1 gemist; oproepen en minuten onbekend (stil sinds 21-10 08:00)" in V.tekst(v), V.tekst(v))
    eis(V.kanaalregel("telefoon", "aangesloten", [(0, "0 oproepen", "oproepen")]) == "- telefoon: 0 oproepen gezien",
        "een gelezen dag toont 0")


if __name__ == "__main__":
    for naam, f in list(globals().items()):
        if naam.startswith("test_") and callable(f):
            f()
    print("geslaagd" if not FOUTEN else f"{len(FOUTEN)} fout(en)")
    sys.exit(1 if FOUTEN else 0)
