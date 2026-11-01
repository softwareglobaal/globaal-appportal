"""Het prijsverslag voor Mehdi: beslissing eerst, dan de aanbiedingen met klikbare link, dan wat niet na te gaan was
en de voorgestelde volgende stap. Mehdi leest weinig: de aanbeveling staat in de eerste regels.
"""


def euro(bedrag):
    """1234.5 -> '1.234,50 euro' (Belgische schrijfwijze)."""
    if bedrag is None:
        return "onbekend"
    tekst = f"{bedrag:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{tekst} euro"


def _kort(tekst, n=160):
    """Vrije tekst van het model, begrensd en op een regel (Codex X2, ronde 2); nooit in de aanbeveling zelf."""
    tekst = " ".join(str(tekst).split())
    return tekst if len(tekst) <= n else tekst[:n - 3].rstrip() + "..."


def _prijs_in_munt(a):
    munt = str(a.get("munt") or "").upper()
    return "" if munt == "EUR" else f" ({a.get('prijs')} {munt})"


def _regel(a):
    # Ook bij een onvolledig totaal staat de prijs erbij: zonder prijs is de lijst voor Mehdi waardeloos (proef 30-10-2026).
    totaal = (euro(a["totaal_eur"]) if a["totaal_eur"] is not None
              else f"prijs {a.get('prijs')} {str(a.get('munt') or '').upper()}, totaal onvolledig: " + ", ".join(a["ontbreekt"]))
    delen = [f"[{a['titel']}]({a['url']})", f"{a.get('winkel') or 'winkel onbekend'} ({a.get('land') or '?'})",
             a.get("soort") or "", totaal + _prijs_in_munt(a)]
    if a.get("staat") and a.get("soort") != "nieuw":
        delen.append(f"staat: {a['staat']}")
    if a.get("garantie"):
        delen.append(f"garantie: {a['garantie']}")
    if a.get("betrouwbaarheid"):
        delen.append(f"verkoper: {a['betrouwbaarheid']}")
    if a.get("btw_factuur") is False:
        delen.append("geen factuur met btw")
    if a.get("foto"):
        delen.append(f"[foto]({a['foto']})")
    if a.get("compatibel") == "onbekend":
        delen.append("compatibiliteit niet bevestigd")
    delen += a.get("uitleg") or []
    if a.get("waarom"):
        delen.append("toelichting: " + _kort(a["waarom"]))
    return "- " + "; ".join(d for d in delen if d)


def _bewijsregel(a):
    """Waarop de aanbeveling steunt: per bewijs de tekst zoals ze op de pagina staat, met wat eromheen staat, en de
    pagina als die niet de aanbodpagina is (Codex ronde 3 en 5). Mehdi ziet zo een accessoire, een oude prijs of een
    ander product dat het citaat alleen zou weglaten."""
    ctx = a.get("context") if isinstance(a.get("context"), dict) else {}
    if not ctx:
        return "Bewijs op de pagina: geen citaat bewaard."
    regels = ["Bewijs op de pagina:"]
    for veld, (tekst, bron) in ctx.items():
        waar = "" if bron == a.get("url") else f" ([bron]({bron}))"
        regels.append(f'- {veld}: "{_kort(tekst, 600)}"{waar}')
    return "\n".join(regels)


def _gezien(x):
    """Een regel uit "gezien, niet nagekeken": klikbare link, de prijs zoals ze in het zoekresultaat zelf stond
    (onderzoek.alleen_gezien), en waarom de pagina niet nagekeken is (overleg 9, X4)."""
    prijs = f"{x['prijs']} {x.get('munt') or 'EUR'} volgens het zoekresultaat"
    reden = f"; {_kort(x['reden'], 100)}" if x.get("reden") else ""
    return f"- [{_kort(x['titel'], 100)}]({x['url']}): {prijs}{reden}"


def titel(gegevens, resultaat):
    """Korte titel voor het bord. Het verslag gaat als soort 'prijsverslag': De Bode stuurt het niet vanzelf door
    (overleg X2: het antwoord komt via De Regisseur in de chat, De Bode alleen op uitdrukkelijk verzoek)."""
    kort = (gegevens or {}).get("vraag_kort") or "prijsvraag"
    beste = resultaat.get("beste")
    t = f"Prijsonderzoek: {kort}"[:90]
    if beste:
        t += f" (beste {euro(beste['totaal_eur'])})"
    return t


def tegengehouden(soorten):
    """Het korte verslag als de vraag persoonsgegevens bevat en dus niet naar het model ging (overleg X4, K6)."""
    return ("**Vraag niet verstuurd:** er staat iets in dat lijkt op " + ", ".join(soorten) + ". Alleen de productvraag "
            "gaat naar de AI. Stel de vraag opnieuw zonder die gegevens (bijvoorbeeld alleen het land of de firma).")


def maak(vraag, gegevens, resultaat, koersdatum, gezien_op, niet_nagekeken=(), verbruik=None):
    """Het verslag als markdown. niet_nagekeken: de rijen van onderzoek.alleen_gezien, nooit aanbevolen.
    verbruik: {"tokens": ...} voor de controleregel onderaan (overleg 9, X3; sinds overleg 14 via het abonnement)."""
    g = gegevens or {}
    r = resultaat
    regels = []
    beste = r.get("beste")
    if beste:
        regels.append(f"**Aanbevolen:** [{beste['titel']}]({beste['url']}) bij {beste.get('winkel') or 'onbekend'}, "
                      f"{euro(beste['totaal_eur'])} alles inbegrepen.")
    else:
        regels.append("**Geen aanbeveling:** geen aanbod dat compatibel is en een volledige totaalprijs heeft.")
    if beste:
        regels.append(_bewijsregel(beste))
    reserve = r.get("reserve")
    if reserve:
        regels.append(f"**Reserve:** [{reserve['titel']}]({reserve['url']}) bij {reserve.get('winkel') or 'onbekend'}, "
                      f"{euro(reserve['totaal_eur'])}.")
        regels.append(_bewijsregel(reserve))
    if g.get("vervolgvraag"):
        regels.append(f"**Vraag aan jou:** {g['vervolgvraag']}")
    # Geen vrije adviestekst van het model: die kon een afgewezen aanbod alsnog aanraden (Codex X2). De aanbeveling
    # en de volgende stap komen uit de code; de uitleg van het model staat alleen bij een aanbod dat de controle doorstond.
    if beste:
        regels.append("**Voorstel:** open de link van het aanbevolen aanbod en beslis zelf; ik koop, bied en contacteer niets.")
    elif r.get("goed"):
        regels.append("**Voorstel:** kijk bij de aanbiedingen wat ontbreekt (meestal verzending, btw of invoer) en vraag "
                      "mij gericht verder, of beslis op de link.")
    regels.append("")
    regels.append(f"Vraag: {vraag}")
    if g.get("aannames"):
        regels.append("Aannames: " + "; ".join(map(str, g["aannames"])))
    if g.get("eisen"):
        regels.append("Eisen: " + "; ".join(map(str, g["eisen"])))
    regels.append("")
    regels.append("## Aanbiedingen")
    regels += [_regel(a) for a in r.get("goed", [])] or ["- geen aanbod dat de controle doorstond"]
    if r.get("niet_compatibel"):
        regels += ["", "## Niet compatibel (nooit aanbevolen)"] + [_regel(a) for a in r["niet_compatibel"]]
    if niet_nagekeken:
        regels += ["", "## Gezien, niet nagekeken (nooit aanbevolen)"] + [_gezien(x) for x in niet_nagekeken]
    if g.get("niet_gevonden"):
        regels += ["", "## Niet gevonden"] + [f"- {x}" for x in g["niet_gevonden"]]
    afgewezen = r.get("afgewezen", [])
    regels += ["", f"Controle: {len(r.get('goed', [])) + len(r.get('niet_compatibel', []))} aanbiedingen doorstonden de "
               f"controle, {len(afgewezen)} afgewezen (zonder link, prijs of gelezen pagina; details in het werkverslag). "
               f"Prijzen gezien op {gezien_op}; omgerekend met de ECB-koersen van {koersdatum or 'onbekend'}. "
               + (f"Verbruik: {verbruik['tokens']} tokens via het Claude-abonnement, geen API-kost. " if verbruik else "")
               + "Ik kocht, bood en contacteerde niets."]
    return "\n".join(regels)
