"""De verslagen van de afdeling Bouw voor Mehdi: de uitkomst in de eerste regel, de volgende stap in de tweede, dan
de details. Mehdi leest weinig; niets wordt verstuurd, dat staat er telkens bij.
"""
from . import scheiding as S



def euro(bedrag):
    """1234.5 -> '1.234,50 euro' (Belgische schrijfwijze); None -> 'onbekend'."""
    if bedrag is None:
        return "onbekend"
    tekst = f"{bedrag:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{tekst} euro"


def onvolledig(agent, firma, ontbreekt):
    """Het korte verslag als de vraag niet volstaat om te werken (overleg X1, X2)."""
    wie = f" ({S.FIRMANAMEN[firma]})" if firma in S.FIRMANAMEN else ""
    code = firma if firma in S.FIRMANAMEN else "<firmacode>"
    voorbeeld = (f"firma: {code}; werk: plafonneerwerk; omvang: 120 m2; gemeente: 3020 Herent; straal: 25; tegen: 15-11-2026"
                 if agent == "aannemerszoeker" else f"firma: {code}; project: <projectnummer>; lot: <nummer van het lot>")
    return (f"**Niet gestart:** de vraag mist {', '.join(ontbreekt)}{wie}. Ik heb niets gezocht of gelezen.\n\n"
            f"Stel de vraag opnieuw als velden, bijvoorbeeld: `{voorbeeld}`.")


def tegengehouden(soorten):
    return ("**Niet gestart:** in het werk staat iets dat lijkt op " + ", ".join(soorten) + ". Naar het zoeken op het web "
            "gaan alleen het werk en de gemeente, nooit een naam, adres of nummer van de bouwheer. Stel de vraag opnieuw "
            "zonder.")


def _firma_regel(i, f, firma, eerder, boekhouding_bekend):
    delen = [f"{i}. [{f.get('naam') or 'naam onbekend'}]({f['url']})"]
    # De plaats van de KBO als de code die las: daar rekent de afstand vanaf, niet vanaf wat het model of de site zegt
    plaats = f.get("zetel") or " ".join(str(x) for x in (f.get("postcode"), f.get("gemeente")) if x)
    if plaats:
        delen.append(plaats + (f" ({f['afstand_km']} km)" if f.get("afstand_km") is not None else " (afstand onbekend)"))
    nr = f.get("ondernemingsnummer")
    kbo = {True: "actief in de KBO", False: "stopgezet in de KBO", None: "KBO niet gecontroleerd"}[f.get("kbo_actief")]
    delen.append(f"{nr}, {kbo}" if nr else "geen geldig ondernemingsnummer gevonden")
    if f.get("telefoon"):
        delen.append(f"tel. {f['telefoon']}")
    if f.get("email"):
        delen.append(str(f["email"]))
    if f.get("specialiteit"):
        delen.append(S.schoon_veld(str(f["specialiteit"]), firma))
    if nr and nr.replace(".", "") in eerder:
        delen.append("al leverancier in onze boekhouding")
    elif nr and not boekhouding_bekend:
        delen.append("boekhouding niet nagekeken")
    if firma == S.HB:
        delen.append("inhoudingsplicht niet gecontroleerd")
    if f.get("waarom"):
        delen.append(S.schoon_veld(str(f["waarom"]), firma))
    return "; ".join(d for d in delen if d)


def zoekverslag(v, g, res, eigen, mails, eerder, boekhouding_bekend, aan_te_vullen, vandaag):
    """Het verslag van De Aannemerszoeker. v: de ontlede vraag; g: de gegevens van het model; res: keur(); eigen:
    in_mappen(); mails: {url: mail of None}; eerder: {cijfers: naam}."""
    firma, naam = v["firma"], S.FIRMANAMEN[v["firma"]]
    goed, na, buiten = res["goed"], res["na_te_kijken"], res["buiten"]
    kop = (f"**{v['werk']} in {v.get('gemeente') or 'het gebied'} ({naam}):** {len(goed)} firma's klaar om aan te "
           f"schrijven, {len(na)} na te kijken, {len(buiten)} buiten {v['straal']} km. Niets verstuurd.")
    van = next((m["van"] for m in mails.values() if m), "")
    stap = ("**Volgende stap:** kies wie je aanschrijft; de mails staan onderaan, " +
            f"verstuur ze zelf vanuit {van or 'het adres van de firma'}.")
    if aan_te_vullen:
        stap += f" Vul eerst aan in de mail: {', '.join(aan_te_vullen)}."
    if firma == S.HB:
        stap += " Kijk de inhoudingsplicht na op checkinhoudingsplicht.be voor je een opdracht geeft."
    regels = [kop, "", stap]
    if v.get("weggelaten"):
        regels += ["", "Weggelaten uit de zoekvraag (geen vakwoord): " + ", ".join(v["weggelaten"]) + "."]
    if S.schoon_veld(str(g.get("vervolgvraag") or ""), firma):
        regels += ["", f"**Vraag:** {g['vervolgvraag']}"]
    for titel, lijst in (("Klaar om aan te schrijven", goed), ("Na te kijken (KBO of afstand niet bevestigd)", na),
                         (f"Buiten {v['straal']} km", buiten)):
        if lijst:
            regels += ["", f"## {titel}"] + [_firma_regel(i, f, firma, eerder, boekhouding_bekend)
                                            for i, f in enumerate(lijst, 1)]
    regels += ["", f"## Eerder in de mappen van {naam}"]
    if getattr(eigen, "volledig", True) is False:
        regels.append("- Let op: niet alle treffers gelezen (meer dan twintig pagina's in Dropbox).")
    regels += ([f"- {e['naam']}" + (f" (project {e['project']})" if e.get("project") else "") + f": `{e['pad']}`"
                for e in eigen] or ["- niets gevonden met deze woorden"])
    aannames = [a for a in g.get("aannames") or [] if S.schoon_veld(str(a), firma)]
    niet = [n for n in g.get("niet_gevonden") or [] if S.schoon_veld(str(n), firma)]
    if aannames:
        regels += ["", "## Aannames"] + [f"- {a}" for a in aannames]
    if niet:
        regels += ["", "## Niet gevonden"] + [f"- {n}" for n in niet]
    if res["afgewezen"]:
        regels += ["", f"Weggelaten: {len(res['afgewezen'])} (pagina niet gelezen of stopgezet)."]
    geweigerd = [u for u, m in mails.items() if m is None]
    regels += ["", "## Mails (concept, niet verstuurd)"]
    for i, f in enumerate(goed + na, 1):
        m = mails.get(f["url"])
        if not m:
            continue
        regels += ["", f"### {i}. {f.get('naam') or ''}", f"Aan: {f.get('email') or 'mailadres niet op de site'}",
                   f"Van: {m['van']}", f"Onderwerp: {m['onderwerp']}", "", "```", m["tekst"], "```"]
    if geweigerd:
        regels += ["", f"Geen mail voor {len(geweigerd)} firma's: de tekst haalde de grendel van de firma niet."]
    regels += ["", f"Gezocht op {vandaag}. Ik contacteerde niemand en verstuurde niets."]
    return "\n".join(regels)


def zoektitel(v, res):
    return f"Aannemers {v['werk']} {v.get('gemeente') or ''} ({S.FIRMANAMEN[v['firma']]}): {len(res['goed'])} klaar"[:110]


def lotkeuze(v, lots):
    """Het verslag als er geen lot gekozen is of het lot niet te vinden was: de lots om uit te kiezen."""
    namen = [l.rsplit("/", 1)[-1] for l in lots]
    return (f"**Niet vergeleken:** kies een lot in project {v.get('project')} ({S.FIRMANAMEN[v['firma']]}). "
            f"Ik las nog geen offerte.\n\n" + "\n".join(f"- {n}" for n in namen) +
            "\n\nStel de vraag opnieuw met `lot:`, bijvoorbeeld het nummer vooraan de map.")


def vergelijkingsverslag(v, lotnaam, letters, uit, per_post, post_redenen, vandaag, ai_aan, overgeslagen=0):
    """Het verslag van De Offertevergelijker. letters: [(letter, bestand, sleutelregel)]; uit: offertes.vergelijk();
    per_post: [{onderwerp, cellen}] of None. Geen gunning: de laagste prijs is een feit, geen advies (X4)."""
    from .offertes import datumtekst
    firma = v["firma"]
    rijen = uit["rijen"]
    gelezen = [r for r in rijen if r.get("soort") == "offerte"]
    geen = [r for r in rijen if r.get("soort") == "geen offerte"]
    niet = [r for r in rijen if r.get("soort") not in ("offerte", "geen offerte")]
    kop = f"**Vergelijking {lotnaam} ({S.FIRMANAMEN[firma]}):** {len(gelezen)} offertes gelezen"
    kop += f", {len(niet)} niet gelezen (scan, onleesbaar of te veel: zie de redenen)" if niet else ""
    andere = len(geen) + (overgeslagen or 0)
    kop += f", {andere} documenten die geen offerte zijn (fiche of brochure) tellen niet mee." if andere else "."
    if uit.get("laagste") and uit.get("verschil") is not None:
        kop += (f" Laagste totaal exclusief btw: Inschrijver {uit['laagste']['letter']}, {euro(uit['laagste']['excl'])}; "
                f"verschil met de hoogste {euro(uit['verschil'])} ({uit['verschil_pct']} procent).")
        if not per_post:
            # Codex X6 (controle 8): zonder vergelijking per post zegt het totaal niet of ze hetzelfde werk dekken
            kop += " Let op: alleen de totalen; wat inbegrepen is en op welke basis, is niet vergeleken."
    kop += " Geen gunning: jij beslist."
    stap = "**Volgende stap:** lees de punten om op te letten; "
    stap += ("de vergelijking per post staat hieronder." if per_post else
             "de vergelijking per post komt pas als de offerte-inhoud naar de AI mag." if not ai_aan else
             "er is minder dan twee leesbare offertes, dus niets om per post te vergelijken." if len(gelezen) < 2 else
             "er zijn minder dan twee offertes met een totaal exclusief btw, dus niets om per post te vergelijken."
             if sum(1 for r in gelezen if r.get("excl") is not None) < 2 else
             "een vergelijking per post was niet betrouwbaar (zie de redenen).")
    regels = [kop, "", stap, "", "## Totalen",
              "| Inschrijver | Datum | Excl. btw | Btw | Incl. btw | Geldig tot |", "|---|---|---|---|---|---|"]
    for r in rijen:
        if r.get("soort") != "offerte":
            regels.append(f"| {r['letter']} | | {('; '.join(r.get('redenen') or []))} | | | |")
            continue
        btw = "verlegd" if r.get("verlegd") else (f"{r['btw_tarief']} %" if r.get("btw_tarief") is not None else "onbekend")
        regels.append(f"| {r['letter']} | {datumtekst(r.get('datum'))} | {euro(r.get('excl'))} | {btw} | "
                      f"{euro(r.get('incl'))} | {datumtekst(r.get('geldig_tot'))} |")
    if per_post:
        letters_lijst = [l for l, _, _ in letters]
        regels += ["", "## Per post (exclusief btw; ontbreekt is geen nul)",
                   "| Onderdeel | " + " | ".join(letters_lijst) + " |", "|---|" + "---|" * len(letters_lijst)]
        for p in per_post:
            regels.append(f"| {p['onderwerp']} | " + " | ".join(
                euro(p["cellen"].get(l)) if p["cellen"].get(l) is not None else "ontbreekt" for l in letters_lijst) + " |")
    letop = list(uit["letop"]) + [f"Inschrijver {l}: {r}" for l, rs in (post_redenen or {}).items() for r in rs]
    regels += ["", "## Om op te letten"] + ([f"- {x}" for x in letop] or ["- niets bijzonders gevonden in de totalen"])
    regels += ["", "## Welke offerte is welke letter (alleen voor jou)"] + [f"- Inschrijver {l}: {s}" for l, _, s in letters]
    regels += ["", f"Gelezen op {vandaag}. Ik aanvaardde, tekende of verstuurde niets en schreef niets in Dropbox."]
    return "\n".join(regels)


def vergelijkingstitel(v, lotnaam):
    return f"Offertes {lotnaam} ({S.FIRMANAMEN[v['firma']]})"[:110]
