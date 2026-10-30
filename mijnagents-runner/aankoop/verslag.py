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
    totaal = euro(a["totaal_eur"]) if a["totaal_eur"] is not None else "totaal onvolledig: " + ", ".join(a["ontbreekt"])
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
    """Waarop de aanbeveling steunt, letterlijk van de gelezen pagina (Codex ronde 3): Mehdi ziet het bij het klikken
    meteen terug, ook als de pagina meer varianten of een oude prijs toont."""
    bewijs = a.get("bewijs") if isinstance(a.get("bewijs"), dict) else {}
    delen = [f'{veld} "{_kort(bewijs[veld], 80)}"' for veld in ("prijs", "verzending", "opgeld", "veilingkosten")
             if bewijs.get(veld)]
    compat = a.get("compatibiliteit") if isinstance(a.get("compatibiliteit"), dict) else {}   # Codex X15, ronde 4
    for eis, o in compat.items():
        if isinstance(o, dict) and str(o.get("oordeel")).lower() == "ja" and o.get("citaat"):
            delen.append(f'{eis} "{_kort(o["citaat"], 80)}"')
    return "Bewijs op de pagina: " + "; ".join(delen) + "." if delen else "Bewijs op de pagina: geen citaat bewaard."


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


def maak(vraag, gegevens, resultaat, koersdatum, gezien_op):
    """Het verslag als markdown."""
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
    if g.get("niet_gevonden"):
        regels += ["", "## Niet gevonden"] + [f"- {x}" for x in g["niet_gevonden"]]
    afgewezen = r.get("afgewezen", [])
    regels += ["", f"Controle: {len(r.get('goed', [])) + len(r.get('niet_compatibel', []))} aanbiedingen doorstonden de "
               f"controle, {len(afgewezen)} afgewezen (zonder link, prijs of gelezen pagina; details in het werkverslag). "
               f"Prijzen gezien op {gezien_op}; omgerekend met de ECB-koersen van {koersdatum or 'onbekend'}. "
               "Ik kocht, bood en contacteerde niets."]
    return "\n".join(regels)
