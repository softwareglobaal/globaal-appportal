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
    buiten = afspraak("b", "14:15", "15:15", "!! Mehdi: [UB-KB] PL 3846 - Pieter Claes, Dorpstraat 1, Ternat")
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
    b = V.bewijs(buiten, [], {"uitkomst": "onbekend"})
    eis(b["uitkomst"] == "geen spoor" and "locatie niet gelezen" in b["grond"], f"locatie onbekend ({b})")
    b = V.bewijs(online, [])
    eis(b["uitkomst"] == "geen spoor", f"niets: geen spoor ({b})")
    oproep = rij("telefoon:9", "14:20", 6, "Pieter Claes", bron="telefoon")
    eis(V.bewijs(buiten, [oproep], {"uitkomst": "niet_gezien"})["uitkomst"] == "bevestigd", "oproep met de klant bevestigt")
    # E3: de eigenaar van de agenda voor de code is geen persoon van de afspraak
    eigenaar = afspraak("e", "13:00", "14:00", "!! Mehdi: Catalin: [HA-KB] PL 2602 - Annick Janssens, Bergstraat 46")
    met_catalin = rij("zoom:meeting:4", "13:05", 20, "Mehdi, Catalin (Architecture)")
    eis(V.bewijs(eigenaar, [met_catalin], {"uitkomst": "niet_gezien"})["uitkomst"] == "geen spoor",
        "een Zoom met de eigenaar van de agenda bevestigt de klantafspraak niet")
    # E3: met _personen (klant en gasten uit de runner) telt alleen dat
    a = afspraak("k", "10:30", "11:00", "Mehdi: [UNABO-PO] Lotte Verhaegen", personen=["Lotte Verhaegen"])
    eis(V.bewijs(a, [rij("zoom:meeting:5", "10:31", 9, "Mehdi")])["gesprekken"] == [], "Mehdi alleen is geen persoon")
    eis(V.bewijs(a, [met])["uitkomst"] == "bevestigd", "de klant bevestigt")
    leeg = afspraak("l", "10:30", "11:00", "Mehdi: [EL-IN] intern overleg", personen=[])
    eis(V.bewijs(leeg, [met])["uitkomst"] == "aanwijzing", "zonder personen hoogstens een aanwijzing")


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
    eis(g["alleen_zoom"] == 2 and g["met_opname"] == 2, f"Fathom met dubbel_van en Plaud-dubbel tellen niet ({g})")
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
    t = V.tekst(vast(ongelezen={"Lara", "archief"}))
    eis("agenda onvolledig, niet gelezen: Lara, archief" in t and "onder voorbehoud" in t and "geen afspraken gelezen" in t,
        f"ongelezen agenda of archief: onvolledig met voorbehoud\n{t}")
    v = V.vaststellen(DAG, [], None, [], None, None, "onbekend", None, None, is_prive)
    t = V.tekst(v)
    eis("agenda niet gelezen: onbekend" in t and "locatie: niet gelezen" in t and "mail: niet gelezen" in t,
        "niets gelezen is onbekend, geen nul")
    eis("Zoom-stand onbekend" in t, "Zoom onbekend staat erbij")
    eis("WhatsApp: nog niet aangesloten" in t and "telefoon: nog niet aangesloten" in t, "zonder kanaalstand: niet aangesloten")
    eis("(minstens)" in V.tekst(vast(rijen=[rij("zoom:meeting:a", "09:00", 20, "Ruben")], zoom="ondergrens")), "ondergrens")
    # D2: rijen zonder aangesloten wacht tellen niet als aangesloten; een stille wacht is onvolledig
    wa = [rij("whatsapp:abc:2026-10-22", "08:01", 0, "Broer Ali", bron="whatsapp", thema="14 berichten (5 van Mehdi)")]
    eis("WhatsApp: nog niet aangesloten" in V.tekst(vast(rijen=wa, kanalen={"whatsapp": "niet aangesloten"})), "rijen alleen")
    t = V.tekst(vast(rijen=wa, kanalen={"whatsapp": "stil sinds 2026-10-20 09:00"}))
    eis("14 berichten in 1 gesprekken" in t and "stil sinds 2026-10-20 09:00, onvolledig" in t, f"stille wacht\n{t}")


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
                 "mehdichegini@hotmail.com": {"berichten": [k3], "onvolledig": ["kopie van de Mac 150 uur oud"]}}
    m = V.mail_telling(DAG, ontvangen, verzonden, {"<i1@x>": "koud"})
    pv = m["postvakken"]
    eis(pv["mch@h-architects.be"]["binnen"] == 2 and pv["mch@h-architects.be"]["soorten"] == {"koud": 1}, f"binnen ({m})")
    eis(pv["info@h-architects.be"]["binnen"] == 1, "dezelfde inkomende mail telt in elk postvak")
    eis(m["binnen"] == 2 and m["verzonden"] == 2, f"totaal: Brusselse dag, ontdubbeld per Message-ID ({m})")
    eis(pv["mch@h-architects.be"]["verzonden"] == 1 and pv["info@h-architects.be"]["verzonden"] == 1, "verzonden per postvak")
    eis(m["onvolledig"], "een onvolledig postvak maakt het totaal onvolledig")
    t = V.tekst(vast(mail=m), prive_postvakken=("mehdichegini@hotmail.com",))
    eis("onvolledig: INBOX.ORDE: niet leesbaar; INBOX.Sent: bestaat maar is niet leesbaar" in t, f"onvolledig met reden\n{t}")
    eis("kopie van de Mac 150 uur oud" in t, "oude Mac-kopie")
    eis("Vriend" not in t, "privépostvak: geen ontvanger")
    eis("Pieter Claes" in t, "zakelijke ontvanger staat erbij")


def test_privacy():
    afs = [afspraak("p", "17:45", "18:30", "!! Mehdi: [LA] Lara ophalen bij oma")]
    rijen = [rij("zoom:meeting:p", "17:06", 18, "Mehdi, Tante Mie", prive=1),
             rij("zoom:meeting:q", "20:00", 10, "Mehdi, Bart", afdeling="privé"),
             rij("whatsapp:abc:2026-10-22", "08:01", 0, "Broer Ali", bron="whatsapp", thema="14 berichten (5 van Mehdi)"),
             rij("whatsapp-oproep:1", "19:00", 12, "Broer Ali", bron="whatsapp", thema="uitgaand"),
             rij("telefoon:1", "11:00", 4, "Dokter Peeters", bron="telefoon", thema="inkomend")]
    v = vast(afs, rijen, {"p": {"uitkomst": "niet_gezien"}}, kanalen=AAN)
    t = V.tekst(v)
    for naam in ("Tante Mie", "Bart", "Broer Ali", "Dokter Peeters", "Lara ophalen"):
        eis(naam not in t, f"{naam} staat niet in het overzicht")
    eis("17:45 (privé): geen spoor. Ging dit door?" in t, f"privéafspraak zonder titel:\n{t}")
    eis(v["whatsapp"]["berichten"] == 14 and v["whatsapp"]["oproepen"] == 1 and v["whatsapp"]["minuten"] == 12, "WhatsApp")
    namen = [g["uniek"] for g in v["niet_gepland"]["gesprekken"]]
    eis("whatsapp-oproep:1" in namen and "telefoon:1" in namen and not any(n.startswith("whatsapp:") for n in namen),
        f"oproepen zijn gesprekken, chats niet ({namen})")


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
    """Het model van 22-10-2026 uit de bronproef, met verzonnen namen: Ternat aanwijzing (auto), Leuven en Lara geen
    spoor, het interne overleg van 23:00 geen spoor, en elk Zoom-gesprek van minstens 2 minuten niet gepland."""
    afs = [afspraak("leuven", "12:30", "13:30", "!! Mehdi: [HA] 2616 Stad Leuven vooroverleg varianten, Stadskantoor"),
           afspraak("ternat", "14:15", "15:15", "!! Mehdi: [UB-KB] PL 3846 - Pieter Claes, Dorpstraat 1, Ternat"),
           afspraak("lara", "17:45", "18:30", "!! Mehdi: [LA] Lara ophalen bij oma"),
           afspraak("ai", "23:00", "23:30", "Mehdi: [EL-IN] AI Ruben - Automation")]
    loc = {"leuven": {"uitkomst": "niet_gezien"}, "ternat": {"uitkomst": "doorgegaan", "tekst": "auto ter plaatse 14:31-16:07"},
           "lara": {"uitkomst": "niet_gezien"}}
    zoom = [("10:24", 6), ("11:53", 3), ("13:12", 7), ("13:19", 16), ("13:35", 25), ("14:10", 13), ("14:27", 5),
            ("16:54", 5), ("17:02", 3), ("17:06", 18), ("17:24", 1), ("17:32", 25), ("17:57", 7), ("18:05", 3)]
    rijen = [rij(f"zoom:meeting:{i}", s, m, "Mehdi, Ruben (H-AI & ICT)") for i, (s, m) in enumerate(zoom)]
    v = vast(afs, rijen, loc, [{"van": "11:15", "tot": "11:33", "minuten": 18, "waar": "project HARC 2197"}])
    uit = {x["id"]: x["uitkomst"] for x in v["agenda"]["afspraken"]}
    eis(uit == {"leuven": "geen spoor", "ternat": "aanwijzing", "lara": "geen spoor", "ai": "geen spoor"}, f"goud: {uit}")
    eis(v["gesprekken"]["aantal"] == 14 and v["gesprekken"]["minuten"] == 137, f"goud: 14 gesprekken, 137 min ({v['gesprekken']})")
    eis(len(v["niet_gepland"]["gesprekken"]) == 13, "goud: 13 niet gepland (een sessie van 1 min telt niet)")
    eis("project HARC 2197" in V.tekst(v), "goud: projectbezoek zonder afspraak")


if __name__ == "__main__":
    for naam, f in list(globals().items()):
        if naam.startswith("test_") and callable(f):
            f()
    print("geslaagd" if not FOUTEN else f"{len(FOUTEN)} fout(en)")
    sys.exit(1 if FOUTEN else 0)
